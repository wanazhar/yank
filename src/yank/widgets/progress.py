"""Custom progress bar widget for download progress."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static

from yank.engine.downloader import DownloadItem, DownloadStatus
from yank.logging import get_logger

_logger = get_logger(__name__)


class DownloadProgressBar(Widget):
    """Shows title, progress bar, percent, speed, ETA, and status for one download."""

    DEFAULT_CSS = """
    DownloadProgressBar {
        height: auto;
        min-height: 4;
        padding: 0 1;
        margin-bottom: 1;
        border: solid #a855f7 30%;
        background: #0a0a0f;
    }
    DownloadProgressBar.selected {
        border: solid #06b6d4;
    }
    DownloadProgressBar .dp-title {
        text-style: bold;
        width: 1fr;
        color: #e2e8f0;
    }
    DownloadProgressBar .dp-meta {
        color: #64748b;
        width: auto;
    }
    DownloadProgressBar .dp-error {
        color: #ef4444;
        height: auto;
    }
    DownloadProgressBar .dp-file {
        color: #64748b;
        text-style: italic;
    }
    DownloadProgressBar .dp-row {
        height: 1;
        width: 100%;
    }
    DownloadProgressBar ProgressBar {
        width: 1fr;
        padding: 0 1 0 0;
        background: #1a1a2e;
        color: #a855f7;
    }
    DownloadProgressBar ProgressBar.complete {
        color: #22c55e;
    }
    DownloadProgressBar .dp-speed-fast {
        color: #22c55e;
    }
    DownloadProgressBar .dp-speed-medium {
        color: #eab308;
    }
    DownloadProgressBar .dp-speed-slow {
        color: #ef4444;
    }
    """

    percent: reactive[float] = reactive(0.0)
    status_label: reactive[str] = reactive("pending")

    def __init__(
        self,
        item: DownloadItem,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id or f"dp-{item.id}", classes=classes)
        self.item_id = item.id
        self._item = item

    def compose(self) -> ComposeResult:
        item = self._item
        with Vertical():
            with Horizontal(classes="dp-row"):
                yield Label(item.title or item.url, classes="dp-title")
                yield Label(self._status_text(item), classes="dp-meta", id="dp-status")
            with Horizontal(classes="dp-row"):
                yield ProgressBar(total=100, show_eta=False, id="dp-bar")
                yield Label("0.0%", classes="dp-meta", id="dp-pct")
                yield Label("⚡ —", classes="dp-meta", id="dp-speed")
                yield Label("⏱ —", classes="dp-meta", id="dp-eta")
            yield Label("", classes="dp-file", id="dp-file")
            yield Label("", classes="dp-error", id="dp-error")

    def on_mount(self) -> None:
        self.update_from_item(self._item)

    def update_from_item(self, item: DownloadItem) -> None:
        self._item = item
        self.percent = item.progress.percent
        try:
            bar = self.query_one("#dp-bar", ProgressBar)
            bar.update(progress=min(100.0, max(0.0, item.progress.percent)))

            # Update bar color based on completion
            if item.status == DownloadStatus.COMPLETED:
                bar.add_class("complete")
            else:
                bar.remove_class("complete")
        except Exception:
            _logger.debug("Failed to update progress bar for %s", item.id, exc_info=True)
        try:
            self.query_one("#dp-pct", Label).update(item.progress.percent_display)

            # Speed display with color coding
            speed_label = self.query_one("#dp-speed", Label)
            speed_label.update(f"⚡ {item.progress.speed_display}")

            # Color code speed
            speed_label.remove_class("dp-speed-fast")
            speed_label.remove_class("dp-speed-medium")
            speed_label.remove_class("dp-speed-slow")
            if item.progress.speed_mbps and item.progress.speed_mbps > 5.0:
                speed_label.add_class("dp-speed-fast")
            elif item.progress.speed_mbps and item.progress.speed_mbps > 1.0:
                speed_label.add_class("dp-speed-medium")
            elif item.progress.speed_mbps and item.progress.speed_mbps > 0:
                speed_label.add_class("dp-speed-slow")

            self.query_one("#dp-eta", Label).update(f"⏱ {item.progress.eta_display}")
            self.query_one("#dp-status", Label).update(self._status_text(item))

            # Show checkmark on complete
            if item.status == DownloadStatus.COMPLETED:
                self.query_one("#dp-status", Label).update("✔")

            file_label = item.progress.filename or item.file_path or ""
            # Show basename only
            if file_label:
                from pathlib import Path

                file_label = Path(file_label).name
            self.query_one("#dp-file", Label).update(file_label)
            err = item.error if item.status == DownloadStatus.ERROR else ""
            self.query_one("#dp-error", Label).update(err)
        except Exception:
            _logger.debug("Failed to update progress labels for %s", item.id, exc_info=True)

    @staticmethod
    def _status_text(item: DownloadItem) -> str:
        st = item.status
        if isinstance(st, DownloadStatus):
            return st.value
        return str(st)


class QueueProgressSummary(Static):
    """Compact total-queue progress line."""

    DEFAULT_CSS = """
    QueueProgressSummary {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def update_summary(self, count: int, active: int, percent: float) -> None:
        self.update(f"Queue: {count} item(s) · {active} active · overall {percent:.0f}%")
