"""Textual application class for yank."""

from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from yank.engine.downloader import DownloadItem, DownloadManager, DownloadStatus
from yank.engine.queue import QueueEngine
from yank.engine.updater import YtDlpManager
from yank.models.config import AppConfig, load_config, save_config
from yank.models.history import HistoryEntry, HistoryStore
from yank.screens.url_input import URLInputScreen
from yank.widgets.status_bar import StatusBar


class YankApp(App):
    """
    yank — yt-dlp TUI wrapper.

    Startup shows URL input immediately. Shared services (config, history,
    download manager, queue, yt-dlp manager) live on the app instance.
    """

    TITLE = "yank"
    SUB_TITLE = "yt-dlp TUI"
    CSS = """
    Screen {
        background: #0a0a0f;
        color: #e2e8f0;
    }

    /* Header styling */
    Header {
        dock: top;
        background: #0a0a0f;
        color: #a855f7;
        text-style: bold;
        padding: 0 1;
        height: 1;
    }

    /* Footer styling */
    Footer {
        dock: bottom;
        background: #0a0a0f;
        color: #64748b;
    }

    /* Status bar styling */
    StatusBar {
        dock: bottom;
        background: #0a0a0f;
        color: #64748b;
        border-top: solid #a855f7;
        padding: 0 1;
        height: 1;
    }

    /* Button styling */
    Button {
        background: #a855f7;
        color: #e2e8f0;
        padding: 0 2;
        border: solid #a855f7;
    }

    Button:hover {
        background: #9333ea;
        border: solid #9333ea;
    }

    /* Content width constraints */
    VerticalScroll, HorizontalScroll {
        max-width: 120;
    }


    /* Input fields */
    Input {
        border: solid #06b6d4;
        background: #0a0a0f;
        color: #e2e8f0;
        padding: 0 1;
    }

    Input:focus {
        border: solid #06b6d4;
        background: #0a0a0f;
    }

    /* Table styling */
    DataTable {
        background: #0a0a0f;
    }

    DataTable > .datatable--header {
        background: #0a0a0f;
        color: #06b6d4;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #a855f7 40%;
        border: solid #06b6d4;
    }

    /* Progress bar */
    ProgressBar {
        background: #1a1a2e;
        color: #a855f7;
    }

    ProgressBar.complete {
        color: #22c55e;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config: AppConfig = load_config()
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
        self._update_notice: str = ""

    def compose(self) -> ComposeResult:
        # Status bar is mounted on app level so it persists across screens.
        # Screens have their own Header/Footer; we still dock StatusBar.
        yield StatusBar(id="app-status")

    def on_mount(self) -> None:
        # Ensure yt-dlp present (async-ish via worker)
        self._startup_ytdlp()
        self.queue.load()
        self.refresh_status_bar()
        # Immediate URL input — no splash
        self.push_screen(URLInputScreen())

    def get_status_bar(self) -> StatusBar | None:
        try:
            return self.query_one("#app-status", StatusBar)
        except Exception:
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
        if not self.ytdlp.is_installed():
            self.call_from_thread(
                self._set_notice, "Installing yt-dlp…"
            )
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
            pass

    def _on_download_finished(self, item: DownloadItem) -> None:
        self.queue.sync_from_manager(item)

        status_map = {
            DownloadStatus.COMPLETED: "success",
            DownloadStatus.ERROR: "error",
            DownloadStatus.CANCELLED: "cancelled",
        }
        hist_status = status_map.get(item.status, "error")
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
                pass

        def _notify() -> None:
            self.refresh_status_bar()
            if item.status == DownloadStatus.COMPLETED:
                self.notify(f"Done: {item.title[:50]}", severity="information")
            elif item.status == DownloadStatus.ERROR:
                self.notify(
                    f"Failed: {item.error or item.title[:40]}",
                    severity="error",
                    timeout=8,
                )

        try:
            self.call_from_thread(_notify)
        except Exception:
            pass

    def _on_queue_change(self) -> None:
        try:
            self.call_from_thread(self.refresh_status_bar)
        except Exception:
            pass

    def action_quit(self) -> None:
        try:
            self.manager.cancel_all()
        except Exception:
            pass
        try:
            self.queue.save()
            save_config(self.config)
        except Exception:
            pass
        self.exit()