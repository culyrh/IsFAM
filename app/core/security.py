import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings


class TokenError(Exception):
    """Raised when an access token cannot be decoded or verified."""


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(*, user_id: int, role: str, session_id: int, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": session_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


def mask_phone_number(phone_number: str) -> str:
    """Mask a phone number for display, e.g. 01012341234 -> 010****1234."""

    if len(phone_number) <= 7:
        return phone_number
    return f"{phone_number[:3]}{'*' * (len(phone_number) - 7)}{phone_number[-4:]}"
