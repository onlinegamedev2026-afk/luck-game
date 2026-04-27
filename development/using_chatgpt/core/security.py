import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 150000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, stored = password_hash.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 150000).hex()
    return hmac.compare_digest(digest, stored)


def sign_session(user_id: str, role: str) -> str:
    expires = int((datetime.utcnow() + timedelta(hours=8)).timestamp())
    payload = f"{user_id}:{role}:{expires}"
    sig = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def read_session(token: str | None) -> tuple[str, str] | None:
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 4:
        return None
    user_id, role, expires, sig = parts
    payload = f"{user_id}:{role}:{expires}"
    expected = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    if int(expires) < int(datetime.utcnow().timestamp()):
        return None
    return user_id, role

