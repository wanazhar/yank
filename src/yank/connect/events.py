"""Coalesced change notifications for SSE clients."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from typing import Any


class EventHub:
    """Thread-safe version counter bumped on queue/progress changes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self._last_payload: dict[str, Any] = {}

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def bump(self, *, kind: str = "change", extra: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._version += 1
            self._last_payload = {"type": kind, "version": self._version, **(extra or {})}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return (
                dict(self._last_payload)
                if self._last_payload
                else {"type": "init", "version": self._version}
            )

    def iter_sse(self, poll_s: float = 25.0) -> Iterator[bytes]:
        """Yield SSE heartbeats; payload events are sent by the API layer."""
        seen = self.version
        while True:
            with self._lock:
                current = self._version
            if current != seen:
                seen = current
                payload = self.snapshot()
                data = json.dumps(payload, separators=(",", ":"))
                yield f"event: queue\ndata: {data}\n\n".encode()
            else:
                yield b": ping\n\n"
            time.sleep(poll_s)
