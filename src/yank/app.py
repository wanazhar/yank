"""Textual application class for yank."""

from __future__ import annotations

from typing import ClassVar, Literal

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding

from yank.engine.downloader import DownloadItem, DownloadManager, DownloadStatus
from yank.engine.queue import QueueEngine
from yank.engine.updater import YtDlpManager
from yank.logging import get_logger
from yank.models.config import AppConfig, load_config, save_config
from yank.models.history import HistoryEntry, HistoryStore
from yank.notify import send_notification
from yank.screens.url_input import URLInputScreen
from yank.services import AppServices
from yank.styles import APP_CSS
from yank.widgets.status_bar import StatusBar

_logger = get_logger(__name__)


class YankApp(App):
    """yank — yank the web.

    Startup shows URL input immediately. Shared services (config, history,
    download manager, queue, yt-dlp manager) live on the ``.services``
    attribute and as direct typed properties on the app instance.
    """

    TITLE = "yank"
    SUB_TITLE = "yank the web"
    CSS = APP_CSS

    BINDINGS: ClassVar = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    # ── Typed attributes (set in __init__) ──────────────────────────────────
    config: AppConfig
    history: HistoryStore
    manager: DownloadManager
    queue: QueueEngine
    ytdlp: YtDlpManager
    services: AppServices
    _status_bar: StatusBar | None
    _update_notice: str

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.history = HistoryStore()
        self.history.load()

        self.manager = DownloadManager(
            self.config,
            on_progress=self._on_download_progress,
            on_finished=self._on_download_finished,
        )
        self.queue = QueueEngine(
            self.config,
            self.manager,
            on_change=self._on_queue_change,
        )
        self.ytdlp = YtDlpManager(self.config)
        self._update_notice = ""

        self.services = AppServices(
            config=self.config,
            history=self.history,
            manager=self.manager,
            queue=self.queue,
            ytdlp=self.ytdlp,
        )

    def compose(self) -> ComposeResult:
        yield StatusBar(id="app-status")

    def on_mount(self) -> None:
        self._startup_ytdlp()
        self.queue.load()
        self.refresh_status_bar()
        self.push_screen(URLInputScreen())

    def get_status_bar(self) -> StatusBar | None:
        try:
            return self.query_one("#app-status", StatusBar)
        except Exception:
            _logger.debug("StatusBar query failed", exc_info=True)
            return None

    def refresh_status_bar(self) -> None:
        bar = self.get_status_bar()
        if bar is None:
            return
        bar.set_status(
            ytdlp_version=self.ytdlp.current_version(),
            queue_size=self.queue.active_size(),
            download_dir=self.config.download_dir,
            notification=self._update_notice,
        )

    # ── Startup ─────────────────────────────────────────────────────────────

    @work(thread=True)
    def _startup_ytdlp(self) -> None:
        """Install yt-dlp if missing; check for updates if due."""
        try:
            if not self.ytdlp.is_installed():
                self.call_from_thread(self._set_notice, "Installing yt-dlp…")
                ok = self.ytdlp.ensure_installed()
                if ok:
                    self.call_from_thread(
                        self._set_notice, f"yt-dlp {self.ytdlp.current_version()} installed."
                    )
                else:
                    self.call_from_thread(
                        self._set_notice, "yt-dlp missing — open Settings to install."
                    )
                self.call_from_thread(self.refresh_status_bar)
                return

            if self.ytdlp.should_check_on_startup():
                result = self.ytdlp.check_for_updates(force=True)
                if result.update_available:
                    notice = f"Update available: yt-dlp {result.latest_version}"
                    self.call_from_thread(self._set_notice, notice)
                    self.call_from_thread(
                        self.notify,
                        f"yt-dlp update available: {result.current_version} → {result.latest_version}",
                        severity="warning",
                        timeout=8,
                    )
                self.call_from_thread(self.refresh_status_bar)
        except Exception:
            _logger.debug("Startup yt-dlp task failed", exc_info=True)
            self.call_from_thread(
                self._set_notice, "yt-dlp startup check failed — open Settings."
            )

    def _set_notice(self, text: str) -> None:
        self._update_notice = text
        self.refresh_status_bar()
        # Clear notice after a while via timer on main thread
        self.set_timer(12.0, lambda: self._clear_notice_if(text))

    def _clear_notice_if(self, text: str) -> None:
        if self._update_notice == text:
            self._update_notice = ""
            self.refresh_status_bar()

    # ── Download callbacks (may run on worker threads) ──────────────────────

    def _on_download_progress(self, item: DownloadItem) -> None:
        self.queue.sync_from_manager(item)
        # UI widgets poll themselves; just refresh status occasionally
        try:
            self.call_from_thread(self.refresh_status_bar)
        except Exception:
            _logger.debug("call_from_thread(refresh_status_bar) failed", exc_info=True)

    def _on_download_finished(self, item: DownloadItem) -> None:
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
            # Calculate filesize if available
            filesize = 0
            if item.progress.total_bytes:
                filesize = item.progress.total_bytes
            elif item.progress.downloaded_bytes > 0:
                filesize = item.progress.downloaded_bytes

            entry = HistoryEntry.create(
                title=item.title,
                url=item.url,
                format_id=item.format_id,
                file_path=item.file_path,
                status=hist_status,
                error=item.error,
                filesize=filesize,
            )
            try:
                self.history.add(entry)
            except Exception:
                _logger.debug("Failed to add history entry for %s", item.title, exc_info=True)

        def _notify() -> None:
            self.refresh_status_bar()
            if item.status == DownloadStatus.COMPLETED:
                self.notify(f"Done: {item.title[:50]}", severity="information")
                if self.config.enable_notifications:
                    send_notification("yank — Download complete", item.title[:80])
            elif item.status == DownloadStatus.ERROR:
                self.notify(
                    f"Failed: {item.error or item.title[:40]}",
                    severity="error",
                    timeout=8,
                )
                if self.config.enable_notifications:
                    send_notification(
                        "yank — Download failed",
                        (item.error or item.title)[:80],
                    )

        try:
            self.call_from_thread(_notify)
        except Exception:
            _logger.debug("call_from_thread(_notify) failed", exc_info=True)

    def _on_queue_change(self) -> None:
        try:
            self.call_from_thread(self.refresh_status_bar)
        except Exception:
            _logger.debug(
                "call_from_thread(refresh_status_bar) failed from _on_queue_change", exc_info=True
            )

    async def action_quit(self) -> None:
        try:
            self.manager.cancel_all()
        except Exception:
            _logger.debug("manager.cancel_all() failed during quit", exc_info=True)
        try:
            self.queue.save()
            save_config(self.config)
        except Exception:
            _logger.debug("queue.save() / save_config() failed during quit", exc_info=True)
        self.exit()
