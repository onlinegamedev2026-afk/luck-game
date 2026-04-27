import sqlite3
import uuid

from core.security import hash_password
from models.schemas import Actor
from services.auth_service import actor_from_row


class HierarchyService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_children(self, actor: Actor, query: str = "") -> list[Actor]:
        params: list[str] = [actor.id]
        where = "a.parent_id=?"
        if query:
            where += " AND (a.username LIKE ? OR a.display_name LIKE ? OR a.id LIKE ?)"
            like = f"%{query}%"
            params.extend([like, like, like])
        rows = self.conn.execute(
            f"""
            SELECT a.*, w.wallet_id, w.current_balance
            FROM accounts a JOIN wallets w ON w.owner_id = a.id
            WHERE {where}
            ORDER BY a.created_at DESC
            """,
            params,
        ).fetchall()
        return [actor_from_row(row) for row in rows]

    def can_create(self, actor: Actor, child_role: str) -> bool:
        if actor.role == "ADMIN":
            return child_role == "AGENT"
        if actor.role == "AGENT":
            return child_role in {"AGENT", "USER"}
        return False

    def create_child(self, actor: Actor, username: str, display_name: str, role: str, password: str) -> str:
        if not self.can_create(actor, role):
            raise PermissionError("This role cannot create that account type.")
        child_id = str(uuid.uuid4())
        wallet_id = str(uuid.uuid4())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT INTO accounts(id, username, display_name, role, password_hash, parent_id) VALUES(?,?,?,?,?,?)",
                (child_id, username, display_name, role, hash_password(password), actor.id),
            )
            self.conn.execute(
                "INSERT INTO wallets(wallet_id, owner_id, owner_type, current_balance) VALUES(?,?,?,'0.000')",
                (wallet_id, child_id, role),
            )
            self.conn.execute("COMMIT")
            return child_id
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def ensure_immediate_child(self, actor: Actor, child_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM accounts WHERE id=?", (child_id,)).fetchone()
        if not row or row["parent_id"] != actor.id:
            raise PermissionError("Only immediate children can be changed.")
        return row

    def set_status(self, actor: Actor, child_id: str, status: str) -> None:
        if status not in {"ACTIVE", "INACTIVE"}:
            raise ValueError("Invalid status.")
        self.ensure_immediate_child(actor, child_id)
        self.conn.execute("UPDATE accounts SET status=? WHERE id=?", (status, child_id))

    def delete_child_subtree(self, actor: Actor, child_id: str) -> None:
        row = self.ensure_immediate_child(actor, child_id)
        if actor.role == "ADMIN" and row["role"] != "AGENT":
            raise PermissionError("Admin can delete immediate agents only.")
        self.conn.execute("DELETE FROM accounts WHERE id=?", (child_id,))

