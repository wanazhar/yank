"""Canonical filesystem paths for yank configuration and data.

Consolidates every ``Path.home() / …`` call in one place so that the
XDG-ish layout (``~/.config/yank`` + ``~/.local/share/yank``) is
defined once.
"""

from __future__ import annotations

from pathlib import Path

CONFIG_DIR: Path = Path.home() / ".config" / "yank"
CONFIG_PATH: Path = CONFIG_DIR / "config.toml"

DATA_DIR: Path = Path.home() / ".local" / "share" / "yank"
QUEUE_PATH: Path = DATA_DIR / "queue.json"
HISTORY_PATH: Path = DATA_DIR / "history.json"
LOG_PATH: Path = DATA_DIR / "yank.log"
