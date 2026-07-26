"""In-memory download queue with JSON crash-recovery persistence."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from yank._safe_types import (
    _coerce_float,
    _coerce_int,
    _coerce_optional_str,
    _coerce_str_list,
)
from yank.engine.downloader import (
    DownloadItem,
    DownloadManager,
    DownloadOptions,
    DownloadStatus,
)
from yank.logging import get_logger
from yank.models.config import AppConfig
from yank.paths import QUEUE_PATH

_logger = get_logger(__name__)



@dataclass
class QueueItem:
    """Serializable queue entry (lighter than full DownloadItem)."""

    id: str
    url: str
    title: str
    format_id: str
    status: str = "pending"
    output_dir: str = ""
    filename_template: str = "%(title)s.%(ext)s"
    format_selector: str = "best"
    download_thumbnail: bool = False
    embed_metadata: bool = True
    embed_subtitles: bool = False
    subtitle_langs: list[str] = field(default_factory=list)
    extract_audio: bool = False
    audio_format: str = "mp3"
    custom_format: str | None = None
    error: str = ""
    file_path: str = ""
    created_at: float = field(default_factory=time.time)
    order: int = 0

    def to_options(self) -> DownloadOptions:
        return DownloadOptions(
            output_dir=self.output_dir,
            filename_template=self.filename_template,
            format_selector=self.format_selector,
            download_thumbnail=self.download_thumbnail,
            embed_metadata=self.embed_metadata,
            embed_subtitles=self.embed_subtitles,
            subtitle_langs=list(self.subtitle_langs),
            extract_audio=self.extract_audio,
            audio_format=self.audio_format,
            custom_format=self.custom_format,
        )

    @classmethod
    def from_download_item(cls, item: DownloadItem, order: int = 0) -> QueueItem:
        opts = item.options
        return cls(
            id=item.id,
            url=item.url,
            title=item.title,
            format_id=item.format_id,
            status=item.status.value if isinstance(item.status, DownloadStatus) else str(item.status),
            output_dir=opts.output_dir,
            filename_template=opts.filename_template,
            format_selector=opts.format_selector,
            download_thumbnail=opts.download_thumbnail,
            embed_metadata=opts.embed_metadata,
            embed_subtitles=opts.embed_subtitles,
            subtitle_langs=list(opts.subtitle_langs),
            extract_audio=opts.extract_audio,
            audio_format=opts.audio_format,
            custom_format=opts.custom_format,
            error=item.error,
            file_path=item.file_path,
            created_at=item.created_at,
            order=order,
        )

    def to_download_item(self) -> DownloadItem:
        status = DownloadStatus.PENDING
        try:
            status = DownloadStatus(self.status)
        except ValueError:
            status = DownloadStatus.PENDING
        # Don't restore as actively downloading
        if status == DownloadStatus.DOWNLOADING:
            status = DownloadStatus.QUEUED
        item = DownloadItem(
            id=self.id,
            url=self.url,
            title=self.title,
            format_id=self.format_id,
            options=self.to_options(),
            status=status,
            error=self.error,
            file_path=self.file_path,
            created_at=self.created_at,
        )
        return item


ChangeCallback = Callable[[], None]


class QueueEngine:
    """
    Ordered download queue.

    Persists to JSON for crash recovery. Coordinates with DownloadManager.
    """

    def __init__(
        self,
        config: AppConfig,
        manager: DownloadManager,
        *,
        path: Path | None = None,
        on_change: ChangeCallback | None = None,
    ) -> None:
        self.config = config
        self.manager = manager
        self.path = path or QUEUE_PATH
        self.on_change = on_change
        self._items: list[QueueItem] = []
        self._lock = threading.Lock()

    # ── Persistence ─────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load queue from disk and re-register incomplete items with manager."""
        with self._lock:
            if not self.path.exists():
                self._items = []
                return
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    self._items = []
                    return
                items: list[QueueItem] = []
                for i, data in enumerate(raw):
                    if not isinstance(data, dict):
                        continue
                    try:
                        qi = QueueItem(
                            id=str(data.get("id") or uuid.uuid4().hex[:12]),
                            url=str(data.get("url", "")),
                            title=str(data.get("title", "Unknown")),
                            format_id=str(data.get("format_id", "")),
                            status=str(data.get("status", "pending")),
                            output_dir=str(data.get("output_dir", "")),
                            filename_template=str(
                                data.get("filename_template", "%(title)s.%(ext)s")
                            ),
                            format_selector=str(data.get("format_selector", "best")),
                            download_thumbnail=bool(data.get("download_thumbnail", False)),
                            embed_metadata=bool(data.get("embed_metadata", True)),
                            embed_subtitles=bool(data.get("embed_subtitles", False)),
                            subtitle_langs=_coerce_str_list(data.get("subtitle_langs")),
                            extract_audio=bool(data.get("extract_audio", False)),
                            audio_format=str(data.get("audio_format", "mp3")),
                            custom_format=_coerce_optional_str(data.get("custom_format")),
                            error=str(data.get("error", "")),
                            file_path=str(data.get("file_path", "")),
                            created_at=_coerce_float(data.get("created_at"), time.time()),
                            order=_coerce_int(data.get("order"), i),
                        )
                        # Skip completed/cancelled on restore? Keep them briefly
                        items.append(qi)
                    except (TypeError, ValueError):
                        continue
                items.sort(key=lambda x: x.order)
                self._items = items
            except (OSError, json.JSONDecodeError):
                self._items = []

        # Register non-terminal items with manager
        for qi in list(self._items):
            if qi.status in (
                DownloadStatus.COMPLETED.value,
                DownloadStatus.CANCELLED.value,
            ):
                continue
            di = qi.to_download_item()
            if qi.status == DownloadStatus.DOWNLOADING.value:
                di.status = DownloadStatus.QUEUED
                qi.status = DownloadStatus.QUEUED.value
            self.manager.register(di)
        self.save()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = []
            for i, item in enumerate(self._items):
                item.order = i
                d = asdict(item)
                data.append(d)
            try:
                self.path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass

    def _emit(self) -> None:
        self.save()
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                _logger.debug("on_change callback failed in queue._emit", exc_info=True)

    # ── Mutations ───────────────────────────────────────────────────────────

    def add(self, item: DownloadItem) -> QueueItem:
        """Add a download item to the queue and register with manager."""
        self.manager.register(item)
        with self._lock:
            order = len(self._items)
            qi = QueueItem.from_download_item(item, order=order)
            self._items.append(qi)
        self._emit()
        return qi

    def remove(self, item_id: str) -> None:
        di = self.manager.get(item_id)
        if di and di.status == DownloadStatus.DOWNLOADING:
            self.manager.cancel(item_id)
        with self._lock:
            self._items = [i for i in self._items if i.id != item_id]
        self._emit()

    def reorder(self, item_id: str, new_index: int) -> None:
        with self._lock:
            idx = next((i for i, x in enumerate(self._items) if x.id == item_id), None)
            if idx is None:
                return
            item = self._items.pop(idx)
            new_index = max(0, min(len(self._items), new_index))
            self._items.insert(new_index, item)
            for i, qi in enumerate(self._items):
                qi.order = i
        self._emit()

    def move_up(self, item_id: str) -> None:
        with self._lock:
            idx = next((i for i, x in enumerate(self._items) if x.id == item_id), None)
            if idx is None or idx == 0:
                return
            self._items[idx], self._items[idx - 1] = self._items[idx - 1], self._items[idx]
        self._emit()

    def move_down(self, item_id: str) -> None:
        with self._lock:
            idx = next((i for i, x in enumerate(self._items) if x.id == item_id), None)
            if idx is None or idx >= len(self._items) - 1:
                return
            self._items[idx], self._items[idx + 1] = self._items[idx + 1], self._items[idx]
        self._emit()

    def start_all(self) -> None:
        """Mark pending/paused items as queued and start downloads."""
        with self._lock:
            ids = [i.id for i in self._items]
        for item_id in ids:
            di = self.manager.get(item_id)
            if di is None:
                continue
            if di.status in (
                DownloadStatus.PENDING,
                DownloadStatus.PAUSED,
                DownloadStatus.QUEUED,
            ):
                self.manager.start(item_id)
                self.sync_from_manager(di)
        self._emit()

    def pause_all(self) -> None:
        self.manager.pause_all()
        for di in self.manager.all_items():
            self.sync_from_manager(di)
        self._emit()

    def sync_from_manager(self, di: DownloadItem) -> None:
        """Update queue item status from download manager item."""
        with self._lock:
            for qi in self._items:
                if qi.id == di.id:
                    qi.status = (
                        di.status.value
                        if isinstance(di.status, DownloadStatus)
                        else str(di.status)
                    )
                    qi.error = di.error
                    qi.file_path = di.file_path
                    qi.title = di.title or qi.title
                    break
        self.save()

    def get_items(self) -> list[QueueItem]:
        with self._lock:
            return list(self._items)

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def active_size(self) -> int:
        with self._lock:
            return sum(
                1
                for i in self._items
                if i.status
                in (
                    DownloadStatus.DOWNLOADING.value,
                    DownloadStatus.QUEUED.value,
                    DownloadStatus.PENDING.value,
                )
            )

    def total_progress(self) -> float:
        """Average percent across non-terminal items (0–100)."""
        items = self.get_items()
        if not items:
            return 0.0
        percents: list[float] = []
        for qi in items:
            di = self.manager.get(qi.id)
            if di is None:
                continue
            if di.status == DownloadStatus.COMPLETED:
                percents.append(100.0)
            elif di.status in (DownloadStatus.ERROR, DownloadStatus.CANCELLED):
                continue
            else:
                percents.append(di.progress.percent)
        if not percents:
            return 0.0
        return sum(percents) / len(percents)

    def clear_finished(self) -> None:
        with self._lock:
            self._items = [
                i
                for i in self._items
                if i.status
                not in (
                    DownloadStatus.COMPLETED.value,
                    DownloadStatus.CANCELLED.value,
                    DownloadStatus.ERROR.value,
                )
            ]
        self._emit()
