"""HttpOnly session cookies and one-time pairing codes."""

from __future__ import annotations

import hmac
import secrets
import time
from hashlib import sha256
from typing import Literal, TypedDict

SESSION_COOKIE = "yank_connect_session"
SESSION_MAX_AGE_S = 30 * 86400
PAIR_TTL_S = 3600


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()


def issue_session_value(secret: str) -> str:
    """Create a signed session blob stored in the session cookie."""
    exp = int(time.time()) + SESSION_MAX_AGE_S
    body = str(exp)
    return f"{body}.{_sign(secret, body)}"


def verify_session_value(value: str | None, secret: str) -> bool:
    if not value or not secret:
        return False
    parts = value.split(".", 1)
    if len(parts) != 2:
        return False
    body, sig = parts
    try:
        exp = int(body)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    expected = _sign(secret, body)
    return hmac.compare_digest(sig, expected)


class SessionCookieKwargs(TypedDict):
    httponly: bool
    samesite: Literal["lax", "strict", "none"]
    max_age: int
    path: str
    secure: bool


def session_cookie_kwargs(*, secure: bool) -> SessionCookieKwargs:
    return {
        "httponly": True,
        "samesite": "lax",
        "max_age": SESSION_MAX_AGE_S,
        "path": "/",
        "secure": secure,
    }


class PairingStore:
    """Short-lived pairing codes minted at ``yank connect`` start."""

    def __init__(self) -> None:
        self._codes: dict[str, float] = {}

    def mint(self, ttl_s: float = PAIR_TTL_S) -> str:
        code = secrets.token_urlsafe(16)
        self._codes[code] = time.time() + ttl_s
        return code

    def mint_link_path(self, ttl_s: float = PAIR_TTL_S) -> str:
        return self.mint(ttl_s)

    def consume(self, code: str) -> bool:
        exp = self._codes.get(code)
        if exp is None or exp < time.time():
            self._codes.pop(code, None)
            return False
        del self._codes[code]
        return True
