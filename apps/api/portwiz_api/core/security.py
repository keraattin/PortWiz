"""Password hashing and JWT helpers."""

from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from pwdlib import PasswordHash

from .config import get_settings

settings = get_settings()

# Argon2-based recommended hasher (no bcrypt 72-byte truncation pitfalls).
_password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hash.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = dt.datetime.now(tz=dt.timezone.utc)
    expire = now + dt.timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token. Raises jwt exceptions on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
