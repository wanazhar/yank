"""In-memory per-session cookies for Connect (never written to TUI config)."""

from __future__ import annotations

import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from yank.logging import get_logger

_logger = get_logger(__name__)

_MAX_BYTES = 256_000
_ALLOWED_DOMAIN = re.compile(r"(?:^|\.)((?:youtube|youtu|google)\.com)$", re.I)


@dataclass
class _JarEntry:
    netscape: str
    updated_at: float


def validate_netscape_cookie_file(text: str) -> str:
    """Return normalized cookie text or raise ValueError."""
    raw = text.strip()
    if not raw:
        raise ValueError("Cookie file is empty")
    if len(raw.encode("utf-8")) > _MAX_BYTES:
        raise ValueError("Cookie file too large (256KB max)")

    lines = raw.splitlines()
    if not lines:
        raise ValueError("Cookie file is empty")

    head = "\n".join(lines[:3]).lower()
    if "netscape" not in head and "cookie" not in head:
        raise ValueError("Expected Netscape cookies.txt (export from a cookie editor)")

    domain_seen = False
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            raise ValueError("Invalid Netscape cookie line (need 7 tab-separated fields)")
        domain = parts[0].lstrip(".")
        if not _ALLOWED_DOMAIN.search(domain):
            raise ValueError("Cookies must be for youtube.com / google.com only")
        domain_seen = True

    if not domain_seen:
        raise ValueError("No cookie lines found for YouTube / Google")

    return raw + ("\n" if not raw.endswith("\n") else "")


class ConnectCookieJar:
    """Thread-safe session → Netscape cookies, RAM only."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jars: dict[str, _JarEntry] = {}

    def set(self, subject: str, netscape: str) -> None:
        normalized = validate_netscape_cookie_file(netscape)
        with self._lock:
            self._jars[subject] = _JarEntry(netscape=normalized, updated_at=time.time())

    def clear(self, subject: str) -> bool:
        with self._lock:
            return self._jars.pop(subject, None) is not None

    def clear_all(self) -> None:
        with self._lock:
            self._jars.clear()

    def status(self, subject: str) -> dict[str, object]:
        with self._lock:
            entry = self._jars.get(subject)
        if entry is None:
            return {"set": False}
        return {"set": True, "updated_at": entry.updated_at}

    def materialize(self, subject: str) -> Path | None:
        """Write a temp cookie file for yt-dlp; caller must delete when done."""
        with self._lock:
            entry = self._jars.get(subject)
            if entry is None:
                return None
            data = entry.netscape

        try:
            fd, path = tempfile.mkstemp(prefix="yank-connect-cookies-", suffix=".txt")
            p = Path(path)
            with open(fd, "w", encoding="utf-8") as f:
                f.write(data)
            try:
                p.chmod(0o600)
            except OSError:
                pass
            return p
        except OSError:
            _logger.debug("Failed to materialize cookie jar", exc_info=True)
            return None
