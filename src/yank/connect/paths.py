"""Filesystem paths used only by Yank Connect."""

from __future__ import annotations

from pathlib import Path

from yank.paths import DATA_DIR

CONNECT_DIR: Path = DATA_DIR / "connect"
CONNECT_STAGING_DIR: Path = CONNECT_DIR / "downloads"
CONNECT_TOKEN_PATH: Path = CONNECT_DIR / "token"
CONNECT_STATE_PATH: Path = CONNECT_DIR / "state.json"
CONNECT_QUEUE_PATH: Path = CONNECT_DIR / "queue.json"
CONNECT_HISTORY_PATH: Path = CONNECT_DIR / "history.json"
CONNECT_LOG_PATH: Path = CONNECT_DIR / "server.log"


def repo_root() -> Path:
    """Repository root (monorepo), resolved from this package."""
    return Path(__file__).resolve().parents[3]


def web_out_dir() -> Path:
    return repo_root() / "web" / "out"
