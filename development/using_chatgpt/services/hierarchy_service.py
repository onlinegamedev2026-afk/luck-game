import sqlite3
import re

from core.security import hash_password
from models.schemas import Actor
from services.auth_service import actor_from_row
from tasks.celery_app import send_email_job
from utils.identity import generate_account_id

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(email.strip()))


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

    @staticmethod
    def can_create(actor: Actor, child_role: str) -> bool:
        if actor.role == "ADMIN":
            return child_role == "AGENT"
        if actor.role == "AGENT":
            return child_role in {"AGENT", "USER"}
        return False

    def create_child(self, actor: Actor, username: str, display_name: str, email: str, role: str, password: str) -> str:
        if not self.can_create(actor, role):
            raise PermissionError("This role cannot create that account type.")
        email = email.strip()
        if role == "AGENT" and not is_valid_email(email):
            raise ValueError("Enter a valid agent email before creating credentials.")
        if not username or not password:
            raise ValueError("Generate the user ID and password before creating the account.")
        child_id = username or generate_account_id(display_name)
        wallet_id = generate_account_id(f"{display_name} wallet")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT INTO accounts(id, username, display_name, email, role, password_hash, parent_id) VALUES(?,?,?,?,?,?,?)",
                (child_id, username, display_name, email, role, hash_password(password), actor.id),
            )
            self.conn.execute(
                "INSERT INTO wallets(wallet_id, owner_id, owner_type, current_balance) VALUES(?,?,?,'0.000')",
                (wallet_id, child_id, role),
            )
            self.conn.execute("COMMIT")
            self._send_creation_emails(actor, child_id, username, display_name, email, role, password)
            return child_id
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def _send_creation_emails(
        self,
        actor: Actor,
        child_id: str,
        username: str,
        display_name: str,
        email: str,
        role: str,
        password: str,
    ) -> None:
        created_at = self.conn.execute("SELECT created_at FROM accounts WHERE id=?", (child_id,)).fetchone()["created_at"]
        parent_subject = f"{role.title()} account created"
        parent_body = (
            f"{role.title()} account created at {created_at}.\n\n"
            f"Name: {display_name}\n"
            f"User ID: {child_id}\n"
            f"Username: {username}\n"
            f"Password: {password}\n"
            f"Created by: {actor.id}"
        )
        self._queue_email(actor.email, parent_subject, parent_body)
        if role == "AGENT" and email:
            child_body = (
                f"Your agent account was created at {created_at}.\n\n"
                f"Agent ID: {child_id}\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                f"Creator ID: {actor.id}"
            )
            self._queue_email(email, "Your agent account details", child_body)

    @staticmethod
    def _queue_email(to_address: str | None, subject: str, body: str) -> None:
        if not to_address:
            return
        try:
            send_email_job.apply_async(args=[to_address, subject, body])
        except Exception:
            send_email_job(to_address, subject, body)

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
