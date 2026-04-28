import sqlite3
import uuid
from decimal import Decimal

from models.schemas import Actor
from transactions.ledger import LedgerService
from utils.money import money
from utils.money import money_str


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

    def adjust_admin_balance(self, actor: Actor, amount: Decimal, direction: str) -> str:
        if actor.role != "ADMIN":
            raise PermissionError("Only admin can update its own money.")
        amount = money(amount)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        if direction not in {"add", "deduct"}:
            raise ValueError("Invalid admin adjustment.")
        tx_id = str(uuid.uuid4())
        row = self.conn.execute("SELECT * FROM wallets WHERE wallet_id=?", (actor.wallet_id,)).fetchone()
        before = money(row["current_balance"])
        after = money(before + amount) if direction == "add" else money(before - amount)
        if after < 0:
            raise ValueError("Admin balance cannot go below zero.")
        tx_type = "ADMIN_SELF_CREDIT" if direction == "add" else "ADMIN_SELF_DEBIT"
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                """
                INSERT INTO wallet_transactions(
                    transaction_id, idempotency_key, transaction_type, direction,
                    from_wallet_id, to_wallet_id, initiated_by_user_id, initiated_by_user_type,
                    amount, fee_amount, net_amount, balance_before_from, balance_after_from,
                    balance_before_to, balance_after_to, status, remarks, completed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'SUCCESS',?,CURRENT_TIMESTAMP)
                """,
                (
                    tx_id, f"admin-adjust:{actor.id}:{direction}:{uuid.uuid4()}", tx_type, "ADJUSTMENT",
                    actor.wallet_id if direction == "deduct" else None,
                    actor.wallet_id if direction == "add" else None,
                    actor.id, actor.role, money_str(amount), money_str("0.000"), money_str(amount),
                    money_str(before), money_str(after), money_str(before), money_str(after),
                    "Admin self balance adjustment",
                ),
            )
            self.conn.execute(
                "UPDATE wallets SET current_balance=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE wallet_id=?",
                (money_str(after), actor.wallet_id),
            )
            self.conn.execute("COMMIT")
            return tx_id
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def transactions_for_actor(self, actor: Actor) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM wallet_transactions
            WHERE from_wallet_id=? OR to_wallet_id=?
            ORDER BY created_at DESC
            """,
            (actor.wallet_id, actor.wallet_id),
        ).fetchall()
