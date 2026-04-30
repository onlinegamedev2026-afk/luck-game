import sqlite3
import uuid
from decimal import Decimal

from models.schemas import Actor
from utils.money import money, money_str


class LedgerService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def transfer(
        self,
        *,
        actor: Actor,
        from_wallet_id: str,
        to_wallet_id: str,
        amount: Decimal,
        transaction_type: str,
        idempotency_key: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        fee_amount: Decimal = Decimal("0.000"),
        remarks: str | None = None,
    ) -> str:
        amount = money(amount)
        fee_amount = money(fee_amount)
        net_amount = money(amount)
        if amount <= 0:
            raise ValueError("Amount must be positive.")

        existing = self.conn.execute(
            "SELECT transaction_id FROM wallet_transactions WHERE idempotency_key=? AND status='SUCCESS'",
            (idempotency_key,),
        ).fetchone()
        if existing:
            return existing["transaction_id"]

        tx_id = str(uuid.uuid4())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self.conn.execute(
                "SELECT * FROM wallets WHERE wallet_id IN (?,?) ORDER BY wallet_id",
                (from_wallet_id, to_wallet_id),
            ).fetchall()
            wallets = {row["wallet_id"]: row for row in rows}
            from_wallet = wallets[from_wallet_id]
            to_wallet = wallets[to_wallet_id]
            if from_wallet["status"] != "ACTIVE" or to_wallet["status"] != "ACTIVE":
                raise ValueError("Wallets must be active.")
            before_from = money(from_wallet["current_balance"])
            before_to = money(to_wallet["current_balance"])
            if before_from < amount:
                raise ValueError(
                    "This account does not have enough credit. "
                    f"Available balance: {money_str(before_from)}, requested amount: {money_str(amount)}."
                )
            after_from = money(before_from - amount)
            after_to = money(before_to + net_amount)
            self.conn.execute(
                """
                INSERT INTO wallet_transactions(
                    transaction_id, idempotency_key, transaction_type, direction,
                    from_wallet_id, to_wallet_id, initiated_by_user_id, initiated_by_user_type,
                    amount, fee_amount, net_amount, balance_before_from, balance_after_from,
                    balance_before_to, balance_after_to, reference_type, reference_id, status, remarks, completed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'SUCCESS',?,CURRENT_TIMESTAMP)
                """,
                (
                    tx_id, idempotency_key, transaction_type, "TRANSFER", from_wallet_id, to_wallet_id,
                    actor.id, actor.role, money_str(amount), money_str(fee_amount), money_str(net_amount),
                    money_str(before_from), money_str(after_from), money_str(before_to), money_str(after_to),
                    reference_type, reference_id, remarks,
                ),
            )
            self.conn.execute(
                "UPDATE wallets SET current_balance=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE wallet_id=?",
                (money_str(after_from), from_wallet_id),
            )
            self.conn.execute(
                "UPDATE wallets SET current_balance=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE wallet_id=?",
                (money_str(after_to), to_wallet_id),
            )
            self.conn.execute("COMMIT")
            return tx_id
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
