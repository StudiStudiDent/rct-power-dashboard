"""
auth.py — JWT authentication via HttpOnly cookies + rate limiting.

Security decisions (from eng review):
- JWT stored as HttpOnly cookie (not localStorage) — XSS-safe
- SameSite=Strict — CSRF-safe for same-origin requests
- slowapi rate limiting: 5 login attempts/minute/IP
- No refresh token — 24h lifetime, re-login on expiry
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Cookie, HTTPException, Request, status
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

ALGORITHM = "HS256"


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def create_access_token(subject: str, secret: str, expire_hours: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    return jwt.encode(
        {"sub": subject, "exp": expire},
        secret,
        algorithm=ALGORITHM,
    )


def decode_token(token: str, secret: str) -> Optional[str]:
    """Returns subject (username) or None if invalid/expired."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def require_auth(
    request: Request,
    access_token: Optional[str] = Cookie(default=None),
):
    """
    Dependency: validates the HttpOnly cookie and returns the username.
    Raises 401 if missing or invalid.
    """
    cfg = request.app.state.config
    secret = cfg["auth"]["jwt_secret"]

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    subject = decode_token(access_token, secret)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    return subject
