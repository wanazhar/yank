"""Named constants used throughout yank.

Import from here instead of scattering magic numbers across modules.
"""

from __future__ import annotations

# ── Limits ──────────────────────────────────────────────────────────────
HISTORY_CAP: int = 1000
MAX_CONCURRENT: int = 5
MAX_SUBTITLE_DISPLAY: int = 12
MAX_CONTENT_WIDTH: int = 120
ERROR_MSG_MAX_LEN: int = 200

# ── Timeouts (seconds) ──────────────────────────────────────────────────
FORMAT_TIMEOUT: int = 30
PIP_TIMEOUT: int = 180

# ── Durations (seconds) ─────────────────────────────────────────────────
SECONDS_PER_DAY: int = 86400

# ── Poll intervals (seconds) ────────────────────────────────────────────
DOWNLOAD_POLL_INTERVAL: float = 0.25
QUEUE_POLL_INTERVAL: float = 0.5
