import asyncio
import json
import sqlite3
import uuid
from decimal import Decimal

from core.config import settings
from games.tin_patti import TinPattiGame
from models.schemas import Actor
from realtime.manager import manager
from transactions.ledger import LedgerService
from utils.money import money, money_str


class GameOrchestrator:
    _lock = asyncio.Lock()
    _session_id: str | None = None
    _in_progress = False
    _cards_dealt: list[dict] = []
    _winner: str | None = None
    _last_10: list[str] = []

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.ledger = LedgerService(conn)

    def current_state(self) -> dict:
        return {
            "in_progress": self._in_progress,
            "session_id": self._session_id,
            "cards_dealt": self._cards_dealt,
            "winner": self._winner,
            "last_10_winners": self._last_10,
            "delay": settings.card_drawing_delay_seconds,
            "total_draws": 6,
        }

    async def place_bet(self, actor: Actor, side: str, amount: Decimal) -> None:
        if side not in {"A", "B"}:
            raise ValueError("Choose side A or B.")
        amount = money(amount)
        if amount < settings.min_bet:
            raise ValueError("Minimum bet is 10.000.")
        if not self._session_id or self._in_progress:
            raise ValueError("Betting is open only before a round starts.")
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
            (bet_id, self._session_id, actor.id, side, money_str(amount)),
        )
        column = "group_a_total" if side == "A" else "group_b_total"
        self.conn.execute(
            f"UPDATE game_sessions SET {column}=CAST(CAST({column} AS REAL)+? AS TEXT) WHERE session_id=?",
            (float(amount), self._session_id),
        )

    async def open_betting(self) -> str:
        async with self._lock:
            if self._in_progress:
                raise ValueError("A Tin Patti round is already running.")
            session_id = str(uuid.uuid4())
            self._session_id = session_id
            self._cards_dealt = []
            self._winner = None
            self.conn.execute(
                "INSERT INTO game_sessions(session_id, game_key, status) VALUES(?,?,?)",
                (session_id, "TIN_PATTI", "BETTING"),
            )
            await manager.broadcast("betting_opened", {"session_id": session_id, "seconds": settings.betting_window_seconds})
            return session_id

    async def run_round(self) -> None:
        async with self._lock:
            if not self._session_id:
                self._session_id = str(uuid.uuid4())
                self.conn.execute(
                    "INSERT INTO game_sessions(session_id, game_key, status) VALUES(?,?,?)",
                    (self._session_id, "TIN_PATTI", "BETTING"),
                )
            session = self.conn.execute("SELECT * FROM game_sessions WHERE session_id=?", (self._session_id,)).fetchone()
            self._in_progress = True
            await manager.broadcast("game_started", {"delay": settings.card_drawing_delay_seconds})
            result = TinPattiGame().play(float(session["group_a_total"]), float(session["group_b_total"]))
            cards_a = result["A"]
            cards_b = result["B"]
            self.conn.execute(
                "UPDATE game_sessions SET status='RUNNING', payload=? WHERE session_id=?",
                (json.dumps(result), self._session_id),
            )
            for i in range(3):
                await asyncio.sleep(settings.card_drawing_delay_seconds)
                await self._deal("A", cards_a[i], i * 2 + 1)
                await asyncio.sleep(settings.card_drawing_delay_seconds)
                await self._deal("B", cards_b[i], i * 2 + 2)
            self._winner = str(result["WINNER"])
            self._settle_bets(self._session_id, self._winner)
            self._last_10.append(self._winner)
            self._last_10 = self._last_10[-10:]
            self.conn.execute(
                "UPDATE game_sessions SET status='COMPLETED', winner=?, completed_at=CURRENT_TIMESTAMP WHERE session_id=?",
                (self._winner, self._session_id),
            )
            await manager.broadcast("game_result", {"winner": self._winner, "time": result["TIME"], "last_10_winners": self._last_10})
            self._in_progress = False
            self._session_id = None

    async def _deal(self, group: str, card: tuple[str, str], draw_num: int) -> None:
        event = {"group": group, "rank": card[0], "suit": card[1], "draw_num": draw_num}
        self._cards_dealt.append(event)
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
        for bet in bets:
            if bet["side"] != winner:
                self.conn.execute("UPDATE bets SET status='LOST' WHERE bet_id=?", (bet["bet_id"],))
                continue
            player_wallet = self.conn.execute("SELECT wallet_id FROM wallets WHERE owner_id=?", (bet["player_id"],)).fetchone()
            bet_amount = money(bet["amount"])
            fee = money(bet_amount * settings.payout_fee_rate)
            payout = money(bet_amount + (bet_amount - fee))
            system_actor = Actor("system", "system", "System", "SYSTEM", "ACTIVE", None, pool_wallet, Decimal("0.000"))
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
