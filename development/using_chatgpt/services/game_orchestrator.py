import asyncio
import json
import sqlite3
import uuid
from decimal import Decimal
from typing import Any

from core.config import settings
from games.andar_bahar import AndarBaharGame
from games.tin_patti import TinPattiGame
from models.schemas import Actor
from realtime.manager import manager
from transactions.ledger import LedgerService
from utils.money import money, money_str


GAME_DEFINITIONS: dict[str, dict[str, Any]] = {
    "tin-patti": {
        "db_key": "TIN_PATTI",
        "title": "Teen Patti",
        "engine": TinPattiGame,
        "total_draws": 6,
        "cards_per_side": 3,
        "has_joker": False,
    },
    "andar-bahar": {
        "db_key": "ANDAR_BAHAR",
        "title": "Andar Bahar",
        "engine": AndarBaharGame,
        "total_draws": None,
        "cards_per_side": None,
        "has_joker": True,
    },
}


class GameOrchestrator:
    _locks: dict[str, asyncio.Lock] = {}
    _session_ids: dict[str, str | None] = {}
    _in_progress: dict[str, bool] = {}
    _cards_dealt: dict[str, list[dict]] = {}
    _winner: dict[str, str | None] = {}
    _joker: dict[str, dict | None] = {}
    _winning_card: dict[str, dict | None] = {}

    def __init__(self, conn: sqlite3.Connection, game_key: str = "tin-patti"):
        if game_key not in GAME_DEFINITIONS:
            raise ValueError("Unknown game.")
        self.conn = conn
        self.game_key = game_key
        self.definition = GAME_DEFINITIONS[game_key]
        self.db_key = self.definition["db_key"]
        self.ledger = LedgerService(conn)
        self._ensure_game_state()

    @classmethod
    def available_games(cls) -> list[dict[str, str]]:
        return [
            {"key": key, "title": definition["title"], "url": f"/games/{key}"}
            for key, definition in GAME_DEFINITIONS.items()
        ]

    def current_state(self) -> dict:
        return {
            "game_key": self.game_key,
            "in_progress": self._in_progress[self.game_key],
            "session_id": self._session_ids[self.game_key],
            "cards_dealt": self._cards_dealt[self.game_key],
            "winner": self._winner[self.game_key],
            "joker": self._joker[self.game_key],
            "winning_card": self._winning_card[self.game_key],
            "last_10_winners": self.last_10_winners(),
            "delay": settings.card_drawing_delay_seconds,
            "total_draws": self.definition["total_draws"],
        }

    def last_10_winners(self) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT winner FROM game_sessions
            WHERE game_key=? AND status='COMPLETED' AND winner IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 10
            """,
            (self.db_key,),
        ).fetchall()
        return [row["winner"] for row in reversed(rows)]

    def active_game_for_player(self, actor: Actor) -> dict | None:
        row = self.conn.execute(
            """
            SELECT gs.game_key, gs.status
            FROM bets b JOIN game_sessions gs ON gs.session_id=b.session_id
            WHERE b.player_id=? AND b.status='PLACED' AND gs.status IN ('BETTING','RUNNING')
            ORDER BY gs.created_at DESC
            LIMIT 1
            """,
            (actor.id,),
        ).fetchone()
        if not row:
            return None
        return {
            "game_key": self._route_key(row["game_key"]),
            "title": self._title_for_db_key(row["game_key"]),
            "status": row["status"],
        }

    async def place_bet(self, actor: Actor, side: str, amount: Decimal) -> None:
        if side not in {"A", "B"}:
            raise ValueError("Choose side A or B.")
        amount = money(amount)
        if amount < settings.min_bet:
            raise ValueError("Minimum bet is 10.000.")
        if not self._session_ids[self.game_key] or self._in_progress[self.game_key]:
            raise ValueError("Betting is open only before a round starts.")
        active = self.active_game_for_player(actor)
        if active and active["game_key"] != self.game_key:
            raise ValueError(f"You already have an active {active['title']} round.")
        bet_id = str(uuid.uuid4())
        pool_wallet = self._pool_wallet()
        self.ledger.transfer(
            actor=actor,
            from_wallet_id=actor.wallet_id,
            to_wallet_id=pool_wallet,
            amount=amount,
            transaction_type="BET_DEBIT",
            idempotency_key=f"bet:{bet_id}",
            reference_type="BET",
            reference_id=bet_id,
        )
        self.conn.execute(
            "INSERT INTO bets(bet_id, session_id, player_id, side, amount) VALUES(?,?,?,?,?)",
            (bet_id, self._session_ids[self.game_key], actor.id, side, money_str(amount)),
        )
        column = "group_a_total" if side == "A" else "group_b_total"
        self.conn.execute(
            f"UPDATE game_sessions SET {column}=CAST(CAST({column} AS REAL)+? AS TEXT) WHERE session_id=?",
            (float(amount), self._session_ids[self.game_key]),
        )

    async def open_betting(self) -> str:
        async with self._locks[self.game_key]:
            if self._in_progress[self.game_key]:
                raise ValueError(f"A {self.definition['title']} round is already running.")
            if self._session_ids[self.game_key]:
                raise ValueError("Betting is already open.")
            session_id = str(uuid.uuid4())
            self._session_ids[self.game_key] = session_id
            self._cards_dealt[self.game_key] = []
            self._winner[self.game_key] = None
            self._joker[self.game_key] = None
            self._winning_card[self.game_key] = None
            self.conn.execute(
                "INSERT INTO game_sessions(session_id, game_key, status) VALUES(?,?,?)",
                (session_id, self.db_key, "BETTING"),
            )
            await manager.broadcast(
                "betting_opened",
                {"game_key": self.game_key, "session_id": session_id, "seconds": settings.betting_window_seconds},
            )
            return session_id

    async def run_round(self) -> None:
        async with self._locks[self.game_key]:
            session_id = self._session_ids[self.game_key]
            try:
                if not session_id:
                    session_id = str(uuid.uuid4())
                    self._session_ids[self.game_key] = session_id
                    self.conn.execute(
                        "INSERT INTO game_sessions(session_id, game_key, status) VALUES(?,?,?)",
                        (session_id, self.db_key, "BETTING"),
                    )
                session = self.conn.execute(
                    "SELECT * FROM game_sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                self._in_progress[self.game_key] = True
                await manager.broadcast("game_started", {"game_key": self.game_key, "delay": settings.card_drawing_delay_seconds})
                result = self.definition["engine"]().play(float(session["group_a_total"]), float(session["group_b_total"]))
                self.conn.execute(
                    "UPDATE game_sessions SET status='RUNNING', payload=? WHERE session_id=?",
                    (json.dumps(result), session_id),
                )
                if self.definition["has_joker"]:
                    self._joker[self.game_key] = self._card_dict(result["JOKER"])
                    await asyncio.sleep(settings.card_drawing_delay_seconds)
                    await manager.broadcast("joker_opened", {"game_key": self.game_key, "joker": self._joker[self.game_key]})
                    await self._deal_andar_bahar(result)
                else:
                    await self._deal_tin_patti(result)

                self._winner[self.game_key] = str(result["WINNER"])
                self._winning_card[self.game_key] = self._card_dict(result.get("WINNING_CARD"))
                self._settle_bets(session_id, self._winner[self.game_key])
                self.conn.execute(
                    "UPDATE game_sessions SET status='COMPLETED', winner=?, completed_at=CURRENT_TIMESTAMP WHERE session_id=?",
                    (self._winner[self.game_key], session_id),
                )
                await manager.broadcast(
                    "game_result",
                    {
                        "game_key": self.game_key,
                        "winner": self._winner[self.game_key],
                        "time": result["TIME"],
                        "winning_card": self._winning_card[self.game_key],
                        "last_10_winners": self.last_10_winners(),
                    },
                )
            except Exception as exc:
                if session_id:
                    self.conn.execute(
                        "UPDATE game_sessions SET status='FAILED', completed_at=CURRENT_TIMESTAMP WHERE session_id=?",
                        (session_id,),
                    )
                await manager.broadcast("game_error", {"game_key": self.game_key, "message": str(exc)})
            finally:
                self._in_progress[self.game_key] = False
                self._session_ids[self.game_key] = None

    async def _deal_tin_patti(self, result: dict[str, object]) -> None:
        cards_a = result["A"]
        cards_b = result["B"]
        for i in range(3):
            await asyncio.sleep(settings.card_drawing_delay_seconds)
            await self._deal("A", cards_a[i], i * 2 + 1, 6)
            await asyncio.sleep(settings.card_drawing_delay_seconds)
            await self._deal("B", cards_b[i], i * 2 + 2, 6)

    async def _deal_andar_bahar(self, result: dict[str, object]) -> None:
        cards = {"A": list(result["A"]), "B": list(result["B"])}
        indexes = {"A": 0, "B": 0}
        deal_order = result.get("DEAL_ORDER") or []
        total_draws = int(result.get("TOTAL_DRAWS") or len(deal_order))
        for draw_num, group in enumerate(deal_order, start=1):
            await asyncio.sleep(settings.card_drawing_delay_seconds)
            card = cards[group][indexes[group]]
            indexes[group] += 1
            await self._deal(group, card, draw_num, total_draws)

    async def _deal(self, group: str, card: tuple[str, str], draw_num: int, total_draws: int) -> None:
        event = {
            "game_key": self.game_key,
            "group": group,
            "rank": card[0],
            "suit": card[1],
            "draw_num": draw_num,
            "total_draws": total_draws,
        }
        self._cards_dealt[self.game_key].append(event)
        await manager.broadcast("card_dealt", event)

    def _pool_wallet(self) -> str:
        row = self.conn.execute(
            "SELECT w.wallet_id FROM accounts a JOIN wallets w ON w.owner_id=a.id WHERE a.username='system_pool'"
        ).fetchone()
        return row["wallet_id"]

    def _settle_bets(self, session_id: str, winner: str) -> None:
        if winner not in {"A", "B"}:
            return
        pool_wallet = self._pool_wallet()
        bets = self.conn.execute("SELECT * FROM bets WHERE session_id=? AND status='PLACED'", (session_id,)).fetchall()
        required_payout = Decimal("0.000")
        for bet in bets:
            if bet["side"] == winner:
                bet_amount = money(bet["amount"])
                fee = money(bet_amount * settings.payout_fee_rate)
                required_payout = money(required_payout + bet_amount + (bet_amount - fee))
        self._ensure_pool_balance(pool_wallet, required_payout, session_id)
        for bet in bets:
            if bet["side"] != winner:
                self.conn.execute("UPDATE bets SET status='LOST' WHERE bet_id=?", (bet["bet_id"],))
                continue
            player_wallet = self.conn.execute("SELECT wallet_id FROM wallets WHERE owner_id=?", (bet["player_id"],)).fetchone()
            bet_amount = money(bet["amount"])
            fee = money(bet_amount * settings.payout_fee_rate)
            payout = money(bet_amount + (bet_amount - fee))
            system_actor = Actor("system", "system", "System", None, "SYSTEM", "ACTIVE", None, pool_wallet, Decimal("0.000"))
            self.ledger.transfer(
                actor=system_actor,
                from_wallet_id=pool_wallet,
                to_wallet_id=player_wallet["wallet_id"],
                amount=payout,
                transaction_type="BET_WIN_CREDIT",
                idempotency_key=f"payout:{bet['bet_id']}",
                reference_type="GAME_SESSION",
                reference_id=session_id,
                fee_amount=fee,
            )
            self.conn.execute("UPDATE bets SET status='WON' WHERE bet_id=?", (bet["bet_id"],))

    def _ensure_pool_balance(self, pool_wallet: str, required_amount: Decimal, session_id: str) -> None:
        if required_amount <= 0:
            return
        row = self.conn.execute("SELECT * FROM wallets WHERE wallet_id=?", (pool_wallet,)).fetchone()
        before = money(row["current_balance"])
        if before >= required_amount:
            return
        top_up = money(required_amount - before)
        after = money(before + top_up)
        tx_id = str(uuid.uuid4())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                """
                INSERT INTO wallet_transactions(
                    transaction_id, idempotency_key, transaction_type, direction,
                    from_wallet_id, to_wallet_id, initiated_by_user_id, initiated_by_user_type,
                    amount, fee_amount, net_amount, balance_before_to, balance_after_to,
                    reference_type, reference_id, status, remarks, completed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'SUCCESS',?,CURRENT_TIMESTAMP)
                """,
                (
                    tx_id,
                    f"pool-topup:{session_id}:{uuid.uuid4()}",
                    "SYSTEM_POOL_TOPUP",
                    "CREDIT",
                    None,
                    pool_wallet,
                    "system",
                    "SYSTEM",
                    money_str(top_up),
                    money_str("0.000"),
                    money_str(top_up),
                    money_str(before),
                    money_str(after),
                    "GAME_SESSION",
                    session_id,
                    "Automatic game pool reserve top-up",
                ),
            )
            self.conn.execute(
                "UPDATE wallets SET current_balance=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE wallet_id=?",
                (money_str(after), pool_wallet),
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def _ensure_game_state(self) -> None:
        self._locks.setdefault(self.game_key, asyncio.Lock())
        self._session_ids.setdefault(self.game_key, None)
        self._in_progress.setdefault(self.game_key, False)
        self._cards_dealt.setdefault(self.game_key, [])
        self._winner.setdefault(self.game_key, None)
        self._joker.setdefault(self.game_key, None)
        self._winning_card.setdefault(self.game_key, None)

    @staticmethod
    def _card_dict(card: tuple[str, str] | None) -> dict | None:
        if not card:
            return None
        return {"rank": card[0], "suit": card[1]}

    @staticmethod
    def _route_key(db_key: str) -> str:
        for key, definition in GAME_DEFINITIONS.items():
            if definition["db_key"] == db_key:
                return key
        return db_key.lower().replace("_", "-")

    @staticmethod
    def _title_for_db_key(db_key: str) -> str:
        for definition in GAME_DEFINITIONS.values():
            if definition["db_key"] == db_key:
                return definition["title"]
        return db_key
