import sqlite3
import re

from core.security import hash_password, verify_password
from models.schemas import Actor
from services.auth_service import actor_from_row
from tasks.celery_app import send_email_job
from utils.identity import generate_account_id, generate_password

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

    def list_children_page(self, actor: Actor, query: str = "", role_filter: str = "ALL", page: int = 1, per_page: int = 20) -> tuple[list[Actor], int]:
        page = max(page, 1)
        per_page = max(1, per_page)
        params: list[str] = [actor.id]
        where = "a.parent_id=?"
        if query:
            where += " AND (a.username LIKE ? OR a.display_name LIKE ? OR a.id LIKE ?)"
            like = f"%{query}%"
            params.extend([like, like, like])
        if role_filter in {"AGENT", "USER"}:
            where += " AND a.role=?"
            params.append(role_filter)
        total = self.conn.execute(f"SELECT COUNT(*) AS total FROM accounts a WHERE {where}", params).fetchone()["total"]
        rows = self.conn.execute(
            f"""
            SELECT a.*, w.wallet_id, w.current_balance
            FROM accounts a JOIN wallets w ON w.owner_id = a.id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, per_page, (page - 1) * per_page],
        ).fetchall()
        return [actor_from_row(row) for row in rows], int(total)

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
        row = self.ensure_immediate_child(actor, child_id)
        ids = self._subtree_ids(child_id) if row["role"] == "AGENT" else [child_id]
        placeholders = ",".join("?" for _ in ids)
        self.conn.execute(f"UPDATE accounts SET status=? WHERE id IN ({placeholders})", [status, *ids])

    def delete_child_subtree(self, actor: Actor, child_id: str) -> None:
        row = self.ensure_immediate_child(actor, child_id)
        if actor.role == "ADMIN" and row["role"] != "AGENT":
            raise PermissionError("Admin can delete immediate agents only.")
        ids = self._subtree_ids(child_id)
        if self._has_active_game(ids):
            self._mark_subtree_inactive(ids)
            self.conn.execute(
                "INSERT OR REPLACE INTO pending_account_deletions(account_id, requested_by) VALUES(?,?)",
                (child_id, actor.id),
            )
            return
        self._delete_accounts(ids)

    def update_password(self, actor: Actor, old_password: str, new_password: str) -> None:
        new_password = new_password.strip()
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters.")
        row = self.conn.execute("SELECT password_hash FROM accounts WHERE id=?", (actor.id,)).fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            raise ValueError("Old password is incorrect.")
        self.conn.execute("UPDATE accounts SET password_hash=? WHERE id=?", (hash_password(new_password), actor.id))
        if actor.role == "AGENT":
            self._send_agent_self_password_email(actor, new_password)

    def regenerate_child_password(self, actor: Actor, child_id: str) -> str:
        row = self.ensure_immediate_child(actor, child_id)
        new_password = generate_password()
        self.conn.execute("UPDATE accounts SET password_hash=? WHERE id=?", (hash_password(new_password), child_id))
        self._send_password_regenerated_emails(actor, row, new_password)
        return new_password

    def process_pending_deletions(self) -> None:
        rows = self.conn.execute("SELECT account_id FROM pending_account_deletions ORDER BY created_at").fetchall()
        for row in rows:
            account_id = row["account_id"]
            if not self.conn.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone():
                self.conn.execute("DELETE FROM pending_account_deletions WHERE account_id=?", (account_id,))
                continue
            ids = self._subtree_ids(account_id)
            if self._has_active_game(ids):
                continue
            self._delete_accounts(ids)
            self.conn.execute("DELETE FROM pending_account_deletions WHERE account_id=?", (account_id,))

    def account_pending_deletion(self, account_id: str) -> bool:
        rows = self.conn.execute("SELECT account_id FROM pending_account_deletions").fetchall()
        for row in rows:
            if account_id in self._subtree_ids(row["account_id"]):
                return True
        return False

    def _subtree_ids(self, root_id: str) -> list[str]:
        rows = self.conn.execute(
            """
            WITH RECURSIVE subtree(id) AS (
                SELECT id FROM accounts WHERE id=?
                UNION ALL
                SELECT a.id FROM accounts a JOIN subtree s ON a.parent_id=s.id
            )
            SELECT id FROM subtree
            """,
            (root_id,),
        ).fetchall()
        return [row["id"] for row in rows]

    def _has_active_game(self, account_ids: list[str]) -> bool:
        if not account_ids:
            return False
        placeholders = ",".join("?" for _ in account_ids)
        row = self.conn.execute(
            f"""
            SELECT 1
            FROM bets b JOIN game_sessions gs ON gs.session_id=b.session_id
            WHERE b.player_id IN ({placeholders})
              AND b.status='PLACED'
              AND gs.status IN ('BETTING','RUNNING')
            LIMIT 1
            """,
            account_ids,
        ).fetchone()
        return bool(row)

    def _mark_subtree_inactive(self, account_ids: list[str]) -> None:
        if not account_ids:
            return
        placeholders = ",".join("?" for _ in account_ids)
        self.conn.execute(f"UPDATE accounts SET status='INACTIVE' WHERE id IN ({placeholders})", account_ids)

    def _delete_accounts(self, account_ids: list[str]) -> None:
        if not account_ids:
            return
        placeholders = ",".join("?" for _ in account_ids)
        wallet_rows = self.conn.execute(f"SELECT wallet_id FROM wallets WHERE owner_id IN ({placeholders})", account_ids).fetchall()
        wallet_ids = [row["wallet_id"] for row in wallet_rows]
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(f"DELETE FROM pending_account_deletions WHERE account_id IN ({placeholders})", account_ids)
            self.conn.execute(f"DELETE FROM bets WHERE player_id IN ({placeholders})", account_ids)
            if wallet_ids:
                wallet_placeholders = ",".join("?" for _ in wallet_ids)
                self.conn.execute(
                    f"DELETE FROM wallet_transactions WHERE from_wallet_id IN ({wallet_placeholders}) OR to_wallet_id IN ({wallet_placeholders})",
                    [*wallet_ids, *wallet_ids],
                )
                self.conn.execute(f"DELETE FROM wallets WHERE wallet_id IN ({wallet_placeholders})", wallet_ids)
            self.conn.execute(f"DELETE FROM accounts WHERE id IN ({placeholders})", account_ids)
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def _send_password_regenerated_emails(self, actor: Actor, child_row: sqlite3.Row, new_password: str) -> None:
        subject = "Luck Game password regenerated"
        parent_body = (
            f"Password regenerated for {child_row['role'].title()} account.\n\n"
            f"Name: {child_row['display_name']}\n"
            f"User ID: {child_row['id']}\n"
            f"Username: {child_row['username']}\n"
            f"New Password: {new_password}\n"
            f"Updated by: {actor.id}"
        )
        self._queue_email(actor.email, subject, parent_body)
        if child_row["role"] == "AGENT" and child_row["email"]:
            child_body = (
                "Your Luck Game password was regenerated by your parent account.\n\n"
                f"User ID: {child_row['id']}\n"
                f"Username: {child_row['username']}\n"
                f"New Password: {new_password}"
            )
            self._queue_email(child_row["email"], subject, child_body)

    def _send_agent_self_password_email(self, actor: Actor, new_password: str) -> None:
        body = (
            "Your Luck Game password was changed from your account.\n\n"
            f"Agent ID: {actor.id}\n"
            f"Username: {actor.username}\n"
            f"New Password: {new_password}"
        )
        self._queue_email(actor.email, "Luck Game password changed", body)
