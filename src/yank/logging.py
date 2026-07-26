"""Logging configuration for yank.

Configures a rotating file logger at ~/.local/share/yank/yank.log
plus a stderr stream for console visibility. Use :func:`get_logger`
to obtain a logger for any module.
"""

from __future__ import annotations

import logging
import sys

from yank.paths import DATA_DIR, LOG_PATH

LOG_DIR = DATA_DIR
LOG_FILE = LOG_PATH
MAX_BYTES = 512 * 1024  # 512 KiB
BACKUP_COUNT = 2

_configured: bool = False


def _ensure_configured() -> None:
    """One-time logging setup — idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("yank")
    root.setLevel(logging.DEBUG)

    # File handler — rotating (manual rotation via backup copies)
    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Stderr handler — INFO and above only, compact
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sfmt = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    sh.setFormatter(sfmt)
    root.addHandler(sh)

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "requests", "yt_dlp", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger for *name* (usually ``__name__``)."""
    _ensure_configured()
    return logging.getLogger(name)


def rotate_log() -> None:
    """Rotate the log file if it exceeds MAX_BYTES (best-effort)."""
    try:
        if not LOG_FILE.exists():
            return
        size = LOG_FILE.stat().st_size
        if size < MAX_BYTES:
            return
        # Rotate existing backups
        for i in range(BACKUP_COUNT - 1, 0, -1):
            src = LOG_DIR / f"yank.log.{i}"
            dst = LOG_DIR / f"yank.log.{i + 1}"
            if src.exists():
                src.replace(dst)
        backup = LOG_DIR / "yank.log.1"
        LOG_FILE.replace(backup)
    except OSError:
        pass  # best-effort rotation
