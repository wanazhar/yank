"""History storage (JSON at ~/.local/share/yank/history.json)."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

DATA_DIR = Path.home() / ".local" / "share" / "yank"
HISTORY_PATH = DATA_DIR / "history.json"

Status = Literal["success", "error", "cancelled"]


@dataclass
class HistoryEntry:
    """A single past download record."""

    date: str  # ISO-8601
    title: str
    url: str
    format_id: str
    file_path: str
    status: Status
    error: str = ""
    filesize: int = 0

    @classmethod
    def create(
        cls,
        *,
        title: str,
        url: str,
        format_id: str,
        file_path: str,
        status: Status,
        error: str = "",
        filesize: int = 0,
    ) -> HistoryEntry:
        return cls(
            date=datetime.now(timezone.utc).isoformat(),
            title=title or "Unknown",
            url=url,
            format_id=format_id,
            file_path=file_path,
            status=status,
            error=error,
            filesize=filesize,
        )




_VALID_HISTORY_STATUSES = frozenset({"success", "error", "cancelled"})


def _coerce_history_status(raw: object) -> Status:
    """Coerce a loaded status value to a valid Status literal."""
    if isinstance(raw, str) and raw in _VALID_HISTORY_STATUSES:
        return raw  # type: ignore[return-value]
    return "error"


@dataclass
class HistoryStore:
    """Thread-safe history store backed by JSON."""

    path: Path = field(default_factory=lambda: HISTORY_PATH)
    entries: list[HistoryEntry] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def load(self) -> None:
        """Load history from disk."""
        with self._lock:
            if not self.path.exists():
                self.entries = []
                return
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    self.entries = []
                    return
                self.entries = []
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    try:
                        self.entries.append(
                            HistoryEntry(
                                date=str(item.get("date", "")),
                                title=str(item.get("title", "Unknown")),
                                url=str(item.get("url", "")),
                                format_id=str(item.get("format_id", "")),
                                file_path=str(item.get("file_path", "")),
                                status=_coerce_history_status(item.get("status")),
                                error=str(item.get("error", "")),
                                filesize=int(item.get("filesize", 0) or 0),
                            )
                        )
                    except (TypeError, ValueError):
                        continue
            except (OSError, json.JSONDecodeError):
                self.entries = []

    def save(self) -> None:
        """Persist history to disk."""
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = [asdict(e) for e in self.entries]
            self.path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    def add(self, entry: HistoryEntry) -> None:
        """Prepend an entry (newest first) and save."""
        with self._lock:
            self.entries.insert(0, entry)
            # Cap history size
            if len(self.entries) > 1000:
                self.entries = self.entries[:1000]
        self.save()

    def search(self, query: str) -> list[HistoryEntry]:
        """Filter entries by title or URL (case-insensitive)."""
        q = query.strip().lower()
        if not q:
            return list(self.entries)
        with self._lock:
            return [
                e
                for e in self.entries
                if q in e.title.lower() or q in e.url.lower()
            ]

    def clear(self) -> None:
        """Remove all history."""
        with self._lock:
            self.entries = []
        self.save()

    def to_list(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self.entries)
