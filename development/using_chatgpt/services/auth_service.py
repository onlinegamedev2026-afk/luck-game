import sqlite3

from core.security import sign_session, verify_password
from models.schemas import Actor
from utils.money import money


def actor_from_row(row: sqlite3.Row) -> Actor:
    return Actor(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
        status=row["status"],
        parent_id=row["parent_id"],
        wallet_id=row["wallet_id"],
        balance=money(row["current_balance"]),
    )


class AuthService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def login(self, username: str, password: str, expected_role: str) -> str | None:
        row = self.conn.execute(
            """
            SELECT a.*, w.wallet_id, w.current_balance
            FROM accounts a JOIN wallets w ON w.owner_id = a.id
            WHERE a.username=? AND a.role=?
            """,
            (username, expected_role),
        ).fetchone()
        if not row or row["status"] != "ACTIVE":
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return sign_session(row["id"], row["role"])

    def get_actor(self, user_id: str) -> Actor | None:
        row = self.conn.execute(
            """
            SELECT a.*, w.wallet_id, w.current_balance
            FROM accounts a JOIN wallets w ON w.owner_id = a.id
            WHERE a.id=?
            """,
            (user_id,),
        ).fetchone()
        return actor_from_row(row) if row else None

