import sqlite3
import uuid
from decimal import Decimal

from models.schemas import Actor
from transactions.ledger import LedgerService
from utils.money import money


class WalletService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.ledger = LedgerService(conn)

    def _child_wallet(self, actor: Actor, child_id: str) -> str:
        row = self.conn.execute(
            """
            SELECT w.wallet_id, a.status
            FROM accounts a JOIN wallets w ON w.owner_id=a.id
            WHERE a.id=? AND a.parent_id=?
            """,
            (child_id, actor.id),
        ).fetchone()
        if not row:
            raise PermissionError("Transfers are allowed only with immediate children.")
        if row["status"] != "ACTIVE":
            raise ValueError("Child account is inactive.")
        return row["wallet_id"]

    def add_money(self, actor: Actor, child_id: str, amount: Decimal) -> str:
        child_wallet = self._child_wallet(actor, child_id)
        return self.ledger.transfer(
            actor=actor,
            from_wallet_id=actor.wallet_id,
            to_wallet_id=child_wallet,
            amount=money(amount),
            transaction_type="PARENT_TO_CHILD_CREDIT",
            idempotency_key=f"credit:{actor.id}:{child_id}:{uuid.uuid4()}",
        )

    def deduct_money(self, actor: Actor, child_id: str, amount: Decimal) -> str:
        child_wallet = self._child_wallet(actor, child_id)
        return self.ledger.transfer(
            actor=actor,
            from_wallet_id=child_wallet,
            to_wallet_id=actor.wallet_id,
            amount=money(amount),
            transaction_type="PARENT_FROM_CHILD_DEBIT",
            idempotency_key=f"debit:{actor.id}:{child_id}:{uuid.uuid4()}",
        )

    def transactions_for_actor(self, actor: Actor) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM wallet_transactions
            WHERE from_wallet_id=? OR to_wallet_id=?
            ORDER BY created_at DESC
            """,
            (actor.wallet_id, actor.wallet_id),
        ).fetchall()

