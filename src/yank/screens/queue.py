"""Queue management screen — reorder, remove, batch start/pause."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from yank.app import YankApp

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label

from yank.constants import QUEUE_POLL_INTERVAL
from yank.engine.downloader import DownloadStatus
from yank.logging import get_logger
from yank.widgets.progress import QueueProgressSummary

_logger = get_logger(__name__)


class QueueScreen(Screen):
    """Tab/panel showing all queued downloads with reorder and batch controls."""

    @property
    def _app(self) -> YankApp:  # type: ignore[name-defined]
        """Narrow ``self.app`` to the known ``YankApp`` subtype."""
        return cast("YankApp", self.app)

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("delete", "remove_item", "Remove", show=True),
        Binding("u", "move_up", "Move up", show=True),
        Binding("d", "move_down", "Move down", show=True),
        Binding("s", "start_all", "Start all", show=True),
        Binding("p", "pause_all", "Pause all", show=True),
    ]

    CSS = """
    QueueScreen {
        layout: vertical;
    }
    #q-header {
        height: auto;
        padding: 0 1;
        text-style: bold;
        color: #a855f7;
    }
    #q-table {
        height: 1fr;
        margin: 1;
        background: #0a0a0f;
    }
    #q-table > .datatable--odd-row {
        background: #0d0d12;
    }
    #q-table > .datatable--even-row {
        background: #0a0a0f;
    }
    #q-actions {
        height: auto;
        padding: 1;
    }
    #q-actions Button {
        margin-right: 1;
    }
    #q-hint {
        color: #64748b;
        padding: 0 1;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("Download Queue", id="q-header")
        yield QueueProgressSummary(id="q-summary")
        yield Label(
            "↑↓ select · u/d reorder · Delete remove · s start all · p pause all",
            id="q-hint",
        )
        yield DataTable(id="q-table", zebra_stripes=True, cursor_type="row")
        with Horizontal(id="q-actions"):
            yield Button("Start all", variant="primary", id="btn-start")
            yield Button("Pause all", id="btn-pause")
            yield Button("Remove", id="btn-remove", variant="error")
            yield Button("Move up", id="btn-up")
            yield Button("Move down", id="btn-down")
            yield Button("Clear finished", id="btn-clear")
            yield Button("Downloads", id="btn-downloads")
            yield Button("Back", id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#q-table", DataTable)
        table.add_columns("#", "Title", "Status", "Format", "URL")
        self.refresh_table()
        self.set_interval(QUEUE_POLL_INTERVAL, self._tick_refresh)
        table.focus()

    def on_screen_resume(self) -> None:
        self.refresh_table()

    def _tick_refresh(self) -> None:
        """Refresh table only when this screen is visible."""
        if self.app.screen is self:
            self.refresh_table()

    def refresh_table(self) -> None:
        queue = self._app.queue
        manager = self._app.manager
        table = self.query_one("#q-table", DataTable)
        # Remember cursor
        cursor = table.cursor_row
        table.clear()
        items = queue.get_items()
        for i, qi in enumerate(items):
            di = manager.get(qi.id)
            status = qi.status
            if di:
                status = (
                    di.status.value
                    if isinstance(di.status, DownloadStatus)
                    else str(di.status)
                )
                if di.status == DownloadStatus.DOWNLOADING:
                    status = f"dl {di.progress.percent:.0f}%"
                elif di.status == DownloadStatus.ERROR and di.error:
                    status = f"error: {di.error[:30]}"
            title = (qi.title or "Unknown")[:40]
            url = qi.url[:40]
            table.add_row(
                str(i + 1),
                title,
                status,
                qi.format_id[:12],
                url,
                key=qi.id,
            )

        if items and cursor is not None and cursor < len(items):
            table.move_cursor(row=cursor)

        try:
            self.query_one("#q-summary", QueueProgressSummary).update_summary(
                queue.size(),
                queue.active_size(),
                queue.total_progress(),
            )
        except Exception:
            _logger.debug("Failed to update queue summary widget", exc_info=True)
        self._app.refresh_status_bar()  

    def _selected_id(self) -> str | None:
        table = self.query_one("#q-table", DataTable)
        if not table.row_count:
            return None
        row = table.cursor_row
        if row is None or row < 0:
            return None
        try:
            from textual.coordinate import Coordinate
            from textual.widgets._data_table import CellKey

            cell_key: CellKey = table.coordinate_to_cell_key(Coordinate(row, 0))
            return cell_key.row_key.value
        except Exception:
            _logger.debug("coordinate_to_cell_key failed for row %s", row, exc_info=True)
        # Fallback via queue order
        items = self._app.queue.get_items()  
        if 0 <= (row or 0) < len(items):
            return items[row].id
        return None

    @on(Button.Pressed, "#btn-start")
    def action_start_all(self) -> None:
        self._app.queue.start_all()  
        self.refresh_table()
        self.notify("Started queue.", severity="information")

    @on(Button.Pressed, "#btn-pause")
    def action_pause_all(self) -> None:
        self._app.queue.pause_all()  
        self.refresh_table()
        self.notify("Paused all downloads.", severity="information")

    @on(Button.Pressed, "#btn-remove")
    def action_remove_item(self) -> None:
        item_id = self._selected_id()
        if not item_id:
            self.notify("Select an item first.", severity="warning")
            return
        self._app.queue.remove(item_id)  
        self.refresh_table()

    @on(Button.Pressed, "#btn-up")
    def action_move_up(self) -> None:
        item_id = self._selected_id()
        if not item_id:
            return
        self._app.queue.move_up(item_id)  
        self.refresh_table()
        # Move cursor up
        table = self.query_one("#q-table", DataTable)
        if table.cursor_row and table.cursor_row > 0:
            table.move_cursor(row=table.cursor_row - 1)

    @on(Button.Pressed, "#btn-down")
    def action_move_down(self) -> None:
        item_id = self._selected_id()
        if not item_id:
            return
        self._app.queue.move_down(item_id)  
        self.refresh_table()
        table = self.query_one("#q-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < table.row_count - 1:
            table.move_cursor(row=table.cursor_row + 1)

    @on(Button.Pressed, "#btn-clear")
    def on_clear(self) -> None:
        self._app.queue.clear_finished()  
        self.refresh_table()

    @on(Button.Pressed, "#btn-downloads")
    def on_downloads(self) -> None:
        from yank.screens.download import DownloadScreen

        self.app.push_screen(DownloadScreen())

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()
