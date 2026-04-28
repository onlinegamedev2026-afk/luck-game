import sqlite3
import uuid
from typing import Any
from pathlib import Path

from core.config import settings
from core.security import hash_password
from utils.money import money_str


def _sqlite_path() -> Path:
    raw = settings.database_url.replace("sqlite:///", "")
    return Path(raw)


class PostgresConnection:
    def __init__(self, dsn: str):
        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    @staticmethod
    def _sql(sql: str) -> str:
        command = sql.strip().upper()
        if command == "BEGIN IMMEDIATE":
            return "BEGIN"
        return sql.replace("?", "%s")

    def execute(self, sql: str, params: Any = None):
        return self._conn.execute(self._sql(sql), params or ())

    def executescript(self, sql: str) -> None:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def close(self) -> None:
        self._conn.close()


def connect() -> sqlite3.Connection | PostgresConnection:
    if settings.database_url.startswith(("postgresql://", "postgres://")):
        return PostgresConnection(settings.database_url)

    db_path = _sqlite_path()
    conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                email TEXT NULL,
                role TEXT NOT NULL CHECK(role IN ('ADMIN','AGENT','USER','SYSTEM')),
                password_hash TEXT NOT NULL,
                parent_id TEXT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS wallets (
                wallet_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE,
                owner_type TEXT NOT NULL CHECK(owner_type IN ('ADMIN','AGENT','USER','SYSTEM')),
                current_balance TEXT NOT NULL DEFAULT '0.000',
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','LOCKED','FROZEN','CLOSED')),
                version INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS wallet_transactions (
                transaction_id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                transaction_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                from_wallet_id TEXT NULL REFERENCES wallets(wallet_id),
                to_wallet_id TEXT NULL REFERENCES wallets(wallet_id),
                initiated_by_user_id TEXT NOT NULL,
                initiated_by_user_type TEXT NOT NULL,
                amount TEXT NOT NULL,
                fee_amount TEXT NOT NULL DEFAULT '0.000',
                net_amount TEXT NOT NULL,
                balance_before_from TEXT NULL,
                balance_after_from TEXT NULL,
                balance_before_to TEXT NULL,
                balance_after_to TEXT NULL,
                reference_type TEXT NULL,
                reference_id TEXT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                failure_reason TEXT NULL,
                remarks TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT NULL
            );

            CREATE TABLE IF NOT EXISTS bets (
                bet_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                player_id TEXT NOT NULL REFERENCES accounts(id),
                side TEXT NOT NULL CHECK(side IN ('A','B')),
                amount TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PLACED',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS game_sessions (
                session_id TEXT PRIMARY KEY,
                game_key TEXT NOT NULL,
                status TEXT NOT NULL,
                group_a_total TEXT NOT NULL DEFAULT '0.000',
                group_b_total TEXT NOT NULL DEFAULT '0.000',
                winner TEXT NULL,
                payload TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_accounts_parent ON accounts(parent_id);
            CREATE INDEX IF NOT EXISTS idx_wallet_tx_from ON wallet_transactions(from_wallet_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_wallet_tx_to ON wallet_transactions(to_wallet_id, created_at DESC);
            """
        )
        ensure_schema(conn)
        ensure_seed_data(conn)
    finally:
        conn.close()


def ensure_schema(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE accounts ADD COLUMN email TEXT NULL")
    except Exception:
        pass


def ensure_seed_data(conn: sqlite3.Connection) -> None:
    admin = conn.execute("SELECT id FROM accounts WHERE role='ADMIN'").fetchone()
    if admin:
        conn.execute(
            "UPDATE accounts SET username=?, email=?, password_hash=? WHERE role='ADMIN'",
            (settings.admin_username, settings.admin_email_id, hash_password(settings.admin_password)),
        )
        return
    admin_id = str(uuid.uuid4())
    wallet_id = str(uuid.uuid4())
    system_id = str(uuid.uuid4())
    system_wallet_id = str(uuid.uuid4())
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO accounts(id, username, display_name, email, role, password_hash, parent_id) VALUES(?,?,?,?,?,?,NULL)",
            (admin_id, settings.admin_username, "Main Admin", settings.admin_email_id, "ADMIN", hash_password(settings.admin_password)),
        )
        conn.execute(
            "INSERT INTO wallets(wallet_id, owner_id, owner_type, current_balance) VALUES(?,?,?,?)",
            (wallet_id, admin_id, "ADMIN", money_str("0.000")),
        )
        conn.execute(
            "INSERT INTO accounts(id, username, display_name, email, role, password_hash, parent_id) VALUES(?,?,?,?,?,?,NULL)",
            (system_id, "system_pool", "System Game Pool", "", "SYSTEM", hash_password(uuid.uuid4().hex)),
        )
        conn.execute(
            "INSERT INTO wallets(wallet_id, owner_id, owner_type, current_balance) VALUES(?,?,?,?)",
            (system_wallet_id, system_id, "SYSTEM", money_str("0.000")),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
