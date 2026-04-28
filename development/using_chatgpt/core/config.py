import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Luck Game")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./luck_game.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_email_id: str = os.getenv("ADMIN_EMAIL_ID", "admin@example.com")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_USERNAME", ""))
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
    smtp_delete_sent_copy: bool = os.getenv("SMTP_DELETE_SENT_COPY", "true").lower() in {"1", "true", "yes", "on"}
    smtp_imap_host: str = os.getenv("SMTP_IMAP_HOST", "imap.gmail.com")
    smtp_imap_port: int = int(os.getenv("SMTP_IMAP_PORT", "993"))
    smtp_sent_mailbox: str = os.getenv("SMTP_SENT_MAILBOX", "[Gmail]/Sent Mail")
    betting_window_seconds: int = int(os.getenv("BETTING_WINDOW_SECONDS", "30"))
    card_drawing_delay_seconds: float = float(os.getenv("CARD_DRAWING_DELAY_SECONDS", "1.25"))
    min_bet: Decimal = Decimal("10.000")
    payout_fee_rate: Decimal = Decimal("0.050")


settings = Settings()
