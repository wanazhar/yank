"""Shared runtime for Yank Connect (no Textual UI)."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Literal

from yank.connect.auth import load_or_create_token
from yank.connect.cookie_jar import ConnectCookieJar
from yank.connect.events import EventHub
from yank.connect.paths import CONNECT_HISTORY_PATH, CONNECT_QUEUE_PATH, CONNECT_STAGING_DIR
from yank.connect.session_auth import PairingStore
from yank.engine.downloader import DownloadItem, DownloadManager, DownloadStatus
from yank.engine.queue import QueueEngine
from yank.engine.updater import YtDlpManager
from yank.logging import get_logger
from yank.models.config import load_config
from yank.models.history import HistoryEntry, HistoryStore
from yank.services import AppServices

_logger = get_logger(__name__)


class ConnectRuntime:
    """Bootstraps the same engines as the TUI without Textual."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.config = load_config()
        self.staging_dir = CONNECT_STAGING_DIR
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        # Staging dir keeps server copies for streaming to phones; not the desktop Downloads folder.
        self.config.download_dir = str(self.staging_dir)

        self.history = HistoryStore(path=CONNECT_HISTORY_PATH)
        self.history.load()
        try:
            self.history.prune_older_than(self.config.history_retention_days)
        except Exception:
            _logger.debug("History prune failed", exc_info=True)

        self.events = EventHub()
        self.token = load_or_create_token()
        self.pairing = PairingStore()
        self.cookie_jar = ConnectCookieJar()
        self.active_pair_code: str | None = None

        self.manager = DownloadManager(
            self.config,
            on_progress=self._on_progress,
            on_finished=self._on_finished,
        )
        self.queue = QueueEngine(
            self.config,
            self.manager,
            path=CONNECT_QUEUE_PATH,
            on_change=self._on_queue_change,
        )
        self.ytdlp = YtDlpManager(self.config)
        self.services = AppServices(
            config=self.config,
            history=self.history,
            manager=self.manager,
            queue=self.queue,
            ytdlp=self.ytdlp,
        )

    def startup(self) -> None:
        self.ytdlp.ensure_installed()
        self.queue.load()

    def _on_progress(self, _item: DownloadItem) -> None:
        self.events.bump(kind="progress")

    def _on_queue_change(self) -> None:
        self.events.bump(kind="queue")

    def _on_finished(self, item: DownloadItem) -> None:
        self.queue.sync_from_manager(item)
        status_map: dict[DownloadStatus, Literal["success", "error", "cancelled"]] = {
            DownloadStatus.COMPLETED: "success",
            DownloadStatus.ERROR: "error",
            DownloadStatus.CANCELLED: "cancelled",
        }
        hist_status: Literal["success", "error", "cancelled"] = status_map.get(item.status, "error")
        if item.status in (
            DownloadStatus.COMPLETED,
            DownloadStatus.ERROR,
            DownloadStatus.CANCELLED,
        ):
            filesize = 0
            if item.progress.total_bytes:
                filesize = item.progress.total_bytes
            elif item.progress.downloaded_bytes > 0:
                filesize = item.progress.downloaded_bytes

            checksum = ""
            if item.file_path:
                p = Path(item.file_path)
                if p.is_file():
                    try:
                        h = hashlib.sha256()
                        with open(p, "rb") as f:
                            for chunk in iter(lambda: f.read(65536), b""):
                                h.update(chunk)
                        checksum = h.hexdigest()
                    except OSError:
                        pass

            entry = HistoryEntry.create(
                title=item.title,
                url=item.url,
                format_id=item.format_id,
                file_path=item.file_path,
                status=hist_status,
                error=item.error,
                filesize=filesize,
                checksum=checksum,
                note=item.options.note,
            )
            self.history.add(entry)

        self.events.bump(kind="finished", extra={"id": item.id, "status": str(item.status)})
