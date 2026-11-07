"""Bottom status bar: yt-dlp version, queue size, disk space."""

from __future__ import annotations

import shutil
from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget

from yank.i18n import LocalizedLabel as Label
from yank.logging import get_logger

_logger = get_logger(__name__)


class StatusBar(Widget):
    """Fixed bottom bar showing version, queue, and free disk space."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        width: 100%;
        background: #0a0a0f;
        color: #64748b;
        padding: 0 1;
        layout: horizontal;
        border-top: solid #a855f7 30%;
    }
    StatusBar .sb-left {
        width: 1fr;
        color: #64748b;
    }
    StatusBar .sb-mid {
        width: auto;
        margin: 0 2;
        color: #64748b;
    }
    StatusBar .sb-right {
        width: auto;
        text-align: right;
        color: #64748b;
    }
    StatusBar .sb-notify {
        color: #eab308;
        margin: 0 1;
    }
    """

    ytdlp_version: reactive[str] = reactive("…")
    queue_size: reactive[int] = reactive(0)
    download_dir: reactive[str] = reactive("")
    notification: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Label("", id="sb-left", classes="sb-left")
        yield Label("", id="sb-notify", classes="sb-notify")
        yield Label("", id="sb-mid", classes="sb-mid")
        yield Label("", id="sb-right", classes="sb-right")

    def on_mount(self) -> None:
        self.refresh_disk()
        self._refresh_display()

    def watch_ytdlp_version(self, _value: str) -> None:
        self._refresh_display()

    def watch_queue_size(self, _value: int) -> None:
        self._refresh_display()

    def watch_download_dir(self, _value: str) -> None:
        self.refresh_disk()
        self._refresh_display()

    def watch_notification(self, _value: str) -> None:
        self._refresh_display()

    def refresh_disk(self) -> None:
        self._disk_display = _disk_free(self.download_dir or str(Path.home()))

    def set_status(
        self,
        *,
        ytdlp_version: str | None = None,
        queue_size: int | None = None,
        download_dir: str | None = None,
        notification: str | None = None,
    ) -> None:
        if ytdlp_version is not None:
            self.ytdlp_version = ytdlp_version
        if queue_size is not None:
            self.queue_size = queue_size
        if download_dir is not None:
            self.download_dir = download_dir
        if notification is not None:
            self.notification = notification
        self.refresh_disk()
        self._refresh_display()

    def _refresh_display(self) -> None:
        try:
            self.query_one("#sb-left", Label).update(f"yt-dlp {self.ytdlp_version}")
            self.query_one("#sb-mid", Label).update(f"queue: {self.queue_size}")
            disk = getattr(self, "_disk_display", "—")
            self.query_one("#sb-right", Label).update(f"disk: {disk}")
            self.query_one("#sb-notify", Label).update(self.notification or "")
        except Exception:
            _logger.debug("StatusBar _render failed", exc_info=True)


def _disk_free(path: str) -> str:
    try:
        p = Path(path).expanduser()
        # Walk up until path exists
        while not p.exists() and p != p.parent:
            p = p.parent
        usage = shutil.disk_usage(str(p))
        free = usage.free
        return _human_size(free) + " free"
    except OSError:
        return "—"


def _human_size(n: int) -> str:
    n_f = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n_f < 1024:
            return f"{n_f:.1f} {unit}" if unit != "B" else f"{int(n_f)} B"
        n_f /= 1024.0
    return f"{n_f:.1f} PiB"
