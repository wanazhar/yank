"""Download progress screen — real-time progress for active downloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

if TYPE_CHECKING:
    from yank.app import YankApp

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.dom import DOMNode
from textual.events import Click
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Button, Footer, Header, Label

from yank.constants import DOWNLOAD_POLL_INTERVAL
from yank.engine.downloader import DownloadStatus
from yank.logging import get_logger
from yank.widgets.progress import DownloadProgressBar, QueueProgressSummary

_logger = get_logger(__name__)


class DownloadScreen(Screen):
    """Live progress bars for downloads; pause/cancel per item."""

    @property
    def _app(self) -> YankApp:
        """Narrow ``self.app`` to the known ``YankApp`` subtype."""
        return cast("YankApp", self.app)

    BINDINGS: ClassVar = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("p", "pause_selected", "Pause", show=True),
        Binding("c", "cancel_selected", "Cancel", show=True),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("f2", "open_queue", "Queue", show=True),
    ]

    CSS = """
    DownloadScreen {
        layout: vertical;
    }
    #dl-header {
        height: auto;
        padding: 0 1;
        text-style: bold;
        color: #a855f7;
    }
    #dl-list {
        height: 1fr;
        padding: 1;
    }
    #dl-empty {
        color: #64748b;
        text-align: center;
        width: 100%;
        padding: 2;
    }
    #dl-actions {
        height: auto;
        padding: 1;
        dock: bottom;
    }
    #dl-actions Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        *,
        focus_id: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.focus_id = focus_id
        self._selected_id: str | None = focus_id
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("Downloads", id="dl-header")
        yield QueueProgressSummary(id="dl-summary")
        with VerticalScroll(id="dl-list"):
            yield Label("No active downloads.", id="dl-empty")
        with Horizontal(id="dl-actions"):
            yield Button("Pause", id="btn-pause")
            yield Button("Cancel", id="btn-cancel", variant="error")
            yield Button("Pause all", id="btn-pause-all")
            yield Button("Start all", id="btn-start-all", variant="primary")
            yield Button("Queue", id="btn-queue")
            yield Button("New URL", id="btn-home")
            yield Button("Back", id="btn-back")
        yield Footer()

    async def on_mount(self) -> None:
        await self.rebuild_list()
        # Poll progress ~4 Hz
        self._timer = self.set_interval(DOWNLOAD_POLL_INTERVAL, self._tick_refresh)

    def _tick_refresh(self) -> None:
        """Refresh progress only when this screen is visible."""
        if self.app.screen is self:
            self.refresh_progress()

    async def on_screen_resume(self) -> None:
        await self.rebuild_list()

    async def rebuild_list(self) -> None:
        manager = self._app.manager
        items = manager.all_items()
        # Show non-cancelled recent items, newest/active first
        items = sorted(
            items,
            key=lambda i: (
                0 if i.status == DownloadStatus.DOWNLOADING else 1,
                -i.created_at,
            ),
        )
        container = self.query_one("#dl-list", VerticalScroll)
        # Await removal so IDs are freed before remounting (avoids DuplicateIds).
        await container.remove_children()

        if not items:
            await container.mount(Label("No downloads yet. Paste a URL to start.", id="dl-empty"))
        else:
            bars: list[DownloadProgressBar] = []
            for item in items:
                bar = DownloadProgressBar(item)
                if item.id == self._selected_id:
                    bar.add_class("selected")
                bars.append(bar)
            await container.mount(*bars)

        self._update_summary()

    def refresh_progress(self) -> None:
        manager = self._app.manager
        for bar in self.query(DownloadProgressBar):
            item = manager.get(bar.item_id)
            if item:
                bar.update_from_item(item)
        self._update_summary()
        self._app.refresh_status_bar()

    def _update_summary(self) -> None:
        queue = self._app.queue
        try:
            self.query_one("#dl-summary", QueueProgressSummary).update_summary(
                queue.size(),
                queue.active_size(),
                queue.total_progress(),
            )
        except Exception:
            _logger.debug("Failed to update download summary widget", exc_info=True)

    def _selected_item_id(self) -> str | None:
        if self._selected_id:
            return self._selected_id
        bars = list(self.query(DownloadProgressBar))
        if bars:
            return bars[0].item_id
        return None

    def on_click(self, event: Click) -> None:
        # Select progress bar under click
        widget: DOMNode | None = event.widget
        while widget is not None:
            if isinstance(widget, DownloadProgressBar):
                self._selected_id = widget.item_id
                for bar in self.query(DownloadProgressBar):
                    bar.remove_class("selected")
                widget.add_class("selected")
                break
            widget = widget.parent

    @on(Button.Pressed, "#btn-pause")
    def action_pause_selected(self) -> None:
        item_id = self._selected_item_id()
        if not item_id:
            self.notify("No download selected.", severity="warning")
            return
        self._app.manager.pause(item_id)
        di = self._app.manager.get(item_id)
        if di:
            self._app.queue.sync_from_manager(di)
        self.refresh_progress()

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel_selected(self) -> None:
        item_id = self._selected_item_id()
        if not item_id:
            self.notify("No download selected.", severity="warning")
            return
        self._app.manager.cancel(item_id)
        di = self._app.manager.get(item_id)
        if di:
            self._app.queue.sync_from_manager(di)
        self.refresh_progress()

    @on(Button.Pressed, "#btn-pause-all")
    def on_pause_all(self) -> None:
        self._app.queue.pause_all()
        self.refresh_progress()

    @on(Button.Pressed, "#btn-start-all")
    def on_start_all(self) -> None:
        self._app.queue.start_all()
        self.refresh_progress()

    def action_open_queue(self) -> None:
        from yank.screens.queue import QueueScreen

        self.app.push_screen(QueueScreen())

    @on(Button.Pressed, "#btn-queue")
    def on_queue(self) -> None:
        self.action_open_queue()

    @on(Button.Pressed, "#btn-home")
    def on_home(self) -> None:
        # Pop back to URL input (clear screen stack)
        self.app.pop_screen()  # Pop download screen
        # Pop any intermediate screens (format select, options) to get back to URL input
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()

    async def action_refresh(self) -> None:
        await self.rebuild_list()
