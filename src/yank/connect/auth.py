"""Simple bearer token auth for the Connect API."""

from __future__ import annotations

import secrets
from pathlib import Path

from yank.connect.paths import CONNECT_TOKEN_PATH


def load_or_create_token(path: Path = CONNECT_TOKEN_PATH) -> str:
    """Load persisted token or create a new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return token


def verify_token(provided: str | None, expected: str) -> bool:
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided.strip(), expected.strip())


def reset_token(path: Path = CONNECT_TOKEN_PATH) -> str:
    """Rotate token on disk."""
    if path.is_file():
        path.unlink(missing_ok=True)
    return load_or_create_token(path)
