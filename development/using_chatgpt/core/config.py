import os
from dataclasses import dataclass
from decimal import Decimal


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
    betting_window_seconds: int = int(os.getenv("BETTING_WINDOW_SECONDS", "30"))
    card_drawing_delay_seconds: float = float(os.getenv("CARD_DRAWING_DELAY_SECONDS", "1.25"))
    min_bet: Decimal = Decimal("10.000")
    payout_fee_rate: Decimal = Decimal("0.050")


settings = Settings()

