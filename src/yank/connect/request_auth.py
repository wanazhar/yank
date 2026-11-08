"""Resolve Connect API authentication from cookies, headers, or tokens."""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request

from yank.connect.auth import verify_token
from yank.connect.runtime import ConnectRuntime
from yank.connect.session_auth import SESSION_COOKIE, verify_session_value


def _client_local_proxy(request: Request) -> bool:
    """True when the request was proxied by Tailscale Serve/Funnel on this machine."""
    if request.client is None:
        return False
    return request.client.host in ("127.0.0.1", "::1")


def tailscale_user_login(request: Request) -> str | None:
    login = request.headers.get("Tailscale-User-Login") or request.headers.get(
        "Tailscale-User-Name"
    )
    return login.strip() if login else None


def resolve_credential(request: Request, runtime: ConnectRuntime) -> str | None:
    """Return a non-empty credential label if the request is authenticated."""
    session = request.cookies.get(SESSION_COOKIE)
    if verify_session_value(session, runtime.token):
        return "session"

    header = request.headers.get("authorization") or ""
    token: str | None = None
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    if token is None:
        token = request.headers.get("x-yank-token") or request.query_params.get("token")
    if verify_token(token, runtime.token):
        return "token"

    # Tailscale Serve injects identity headers on requests it proxies to localhost.
    ts_user = tailscale_user_login(request)
    if ts_user and _client_local_proxy(request):
        return f"tailscale:{ts_user}"

    return None


def require_auth(request: Request, runtime: ConnectRuntime) -> None:
    if resolve_credential(request, runtime) is None:
        raise HTTPException(status_code=401, detail="Not authenticated")


def auth_subject(request: Request, runtime: ConnectRuntime) -> str | None:
    """Stable id for per-user Connect state (cookies, etc.)."""
    cred = resolve_credential(request, runtime)
    if cred is None:
        return None
    if cred == "session":
        raw = request.cookies.get(SESSION_COOKIE) or ""
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return f"session_{digest}"
    return cred.replace(":", "_", 1)
