"""History screen — chronological past downloads with search and re-download."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from yank.app import YankApp

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

from yank.constants import FORMAT_TIMEOUT
from yank.models.history import HistoryEntry

# ── Helpers ──────────────────────────────────────────────────────────────────


def _format_size(size: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024.0
    return f"{size:.1f} PB"


def _open_with_system(path: str) -> None:
    """Open a file or directory with the system default handler."""
    system = sys.platform
    if system == "darwin":
        subprocess.run(["open", path], check=True)
    elif system == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", path], check=True)


class HistoryScreen(Screen):
    """Past downloads: Date, Title, URL, Format, File path, Status, Size."""

    @property
    def _app(self) -> YankApp:  # type: ignore[name-defined]
        """Narrow ``self.app`` to the known ``YankApp`` subtype."""
        return cast("YankApp", self.app)

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("r", "redownload", "Re-download", show=True),
        Binding("y", "copy_info", "Copy info", show=True),
        Binding("slash", "focus_search", "Search", show=True),
    ]

    CSS = """
    HistoryScreen {
        layout: vertical;
    }
    #hist-header {
        height: auto;
        padding: 0 1;
        text-style: bold;
        color: #a855f7;
    }
    #hist-search {
        margin: 0 1 1 1;
        width: 100%;
        border: solid #06b6d4;
        background: #0a0a0f;
        color: #e2e8f0;
    }
    #hist-search:focus {
        border: solid #06b6d4;
        background: #0a0a0f;
    }
    #hist-table {
        height: 1fr;
        margin: 0 1;
        background: #0a0a0f;
    }
    #hist-table > .datatable--odd-row {
        background: #0d0d12;
    }
    #hist-table > .datatable--even-row {
        background: #0a0a0f;
    }
    #hist-actions {
        height: auto;
        padding: 1;
    }
    #hist-actions Button {
        margin-right: 1;
    }
    #hist-file-actions {
        height: auto;
        padding: 0 1 1 1;
    }
    #hist-file-actions Button {
        margin-right: 1;
    }
    #hist-detail {
        height: auto;
        max-height: 4;
        padding: 0 1;
        color: #64748b;
    }
    """

    COLUMNS = ("Date", "Title", "URL", "Format", "File", "Status", "Size")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("History", id="hist-header")
        yield Input(placeholder="Search title or URL…", id="hist-search")
        yield DataTable(id="hist-table", zebra_stripes=True, cursor_type="row")
        yield Label("", id="hist-detail")
        with Horizontal(id="hist-file-actions"):
            yield Button("Open file", id="btn-open-file", variant="primary")
            yield Button("Open folder", id="btn-open-folder")
            yield Button("Copy path", id="btn-copy-path")
        with Horizontal(id="hist-actions"):
            yield Button("Re-download", variant="primary", id="btn-redownload")
            yield Button("Copy info", id="btn-copy")
            yield Button("Clear history", id="btn-clear", variant="error")
            yield Button("Back", id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#hist-table", DataTable)
        table.add_columns(*self.COLUMNS)
        self._entries: list[HistoryEntry] = []
        self._sort_column: str | None = "Date"
        self._sort_reverse: bool = True  # newest first by default
        self._search_query: str = ""
        self.refresh_table()
        table.focus()

    # ── Column sorting ───────────────────────────────────────────────────────

    @on(DataTable.HeaderSelected, "#hist-table")
    def on_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle column header click for sorting."""
        col_idx = event.column_index
        if col_idx < 0 or col_idx >= len(self.COLUMNS):
            return
        col_name = self.COLUMNS[col_idx]

        if self._sort_column == col_name:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = col_name
            self._sort_reverse = False

        self.refresh_table(self._search_query)

    def _sort_entries(self, entries: list[HistoryEntry]) -> list[HistoryEntry]:
        """Sort entries based on current sort state."""
        col = self._sort_column
        if col is None:
            return entries

        if col == "Date":
            key = lambda e: e.date or ""
        elif col == "Title":
            key = lambda e: (e.title or "").lower()
        elif col == "URL":
            key = lambda e: (e.url or "").lower()
        elif col == "Format":
            key = lambda e: (e.format_id or "").lower()
        elif col == "File":
            key = lambda e: (e.file_path or "").lower()
        elif col == "Status":
            key = lambda e: (e.status or "").lower()
        elif col == "Size":
            key = lambda e: e.filesize or 0
        else:
            key = lambda e: ""

        rev = self._sort_reverse
        return sorted(entries, key=key, reverse=rev)

    def _build_column_headers(self) -> list[str]:
        """Return column labels with sort indicators."""
        headers = list(self.COLUMNS)
        if self._sort_column:
            arrow = " ▼" if self._sort_reverse else " ▲"
            for i, h in enumerate(headers):
                if h == self._sort_column:
                    headers[i] = h + arrow
        return headers

    # ── Table refresh ────────────────────────────────────────────────────────

    def refresh_table(self, query: str = "") -> None:
        store = self._app.history
        self._search_query = query
        if query.strip():
            entries = store.search(query)
        else:
            entries = store.to_list()
        entries = self._sort_entries(entries)
        self._entries = entries

        table = self.query_one("#hist-table", DataTable)
        table.clear(columns=False)

        # Update column labels with sort indicators
        new_headers = self._build_column_headers()
        for i, h in enumerate(new_headers):
            table.ordered_columns[i].label = h  # type: ignore[union-attr]

        for e in entries:
            date = e.date[:19].replace("T", " ") if e.date else "—"
            table.add_row(
                date,
                (e.title or "—")[:36],
                (e.url or "—")[:36],
                (e.format_id or "—")[:10],
                (e.file_path or "—")[:28],
                e.status,
                _format_size(e.filesize),
            )
        self.query_one("#hist-detail", Label).update(
            f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
        )

    # ── Search ────────────────────────────────────────────────────────────────

    @on(Input.Changed, "#hist-search")
    def on_search(self, event: Input.Changed) -> None:
        self.refresh_table(event.value)

    def action_focus_search(self) -> None:
        self.query_one("#hist-search", Input).focus()

    def _selected_entry(self) -> HistoryEntry | None:
        table = self.query_one("#hist-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    @on(DataTable.RowHighlighted, "#hist-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        entry = self._selected_entry()
        if entry:
            detail = f"{entry.title} · {entry.url}"
            if entry.error:
                detail += f" · error: {entry.error}"
            if entry.file_path:
                detail += f" · {entry.file_path}"
            self.query_one("#hist-detail", Label).update(detail[:120])

    # ── Post-download actions ────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-open-file")
    def action_open_file(self) -> None:
        """Open the downloaded file with the system default application."""
        entry = self._selected_entry()
        if entry is None:
            self.notify("Select a history entry first.", severity="warning")
            return
        file_path = entry.file_path
        if not file_path or not Path(file_path).exists():
            self.notify("File not found on disk.", severity="error")
            return
        try:
            _open_with_system(file_path)
            self.notify(f"Opening: {Path(file_path).name}", severity="information")
        except Exception as exc:
            self.notify(f"Could not open file: {exc}", severity="error")

    @on(Button.Pressed, "#btn-open-folder")
    def action_open_folder(self) -> None:
        """Open the containing directory in the file manager."""
        entry = self._selected_entry()
        if entry is None:
            self.notify("Select a history entry first.", severity="warning")
            return
        file_path = entry.file_path
        if not file_path:
            self.notify("No file path recorded.", severity="warning")
            return
        folder = str(Path(file_path).parent)
        if not Path(folder).is_dir():
            self.notify("Containing folder not found.", severity="error")
            return
        try:
            _open_with_system(folder)
            self.notify(f"Opening folder: {folder}", severity="information")
        except Exception as exc:
            self.notify(f"Could not open folder: {exc}", severity="error")

    @on(Button.Pressed, "#btn-copy-path")
    def action_copy_path(self) -> None:
        """Copy the file path to clipboard."""
        entry = self._selected_entry()
        if entry is None:
            self.notify("Select a history entry first.", severity="warning")
            return
        file_path = entry.file_path
        if not file_path:
            self.notify("No file path recorded.", severity="warning")
            return
        try:
            self.app.copy_to_clipboard(file_path)
            self.notify("File path copied to clipboard.", severity="information")
        except Exception:
            self.query_one("#hist-detail", Label).update(f"Path: {file_path}"[:150])
            self.notify("Clipboard unavailable; path shown below.", severity="warning")

    # ── Re-download ──────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-redownload")
    def action_redownload(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.notify("Select a history entry first.", severity="warning")
            return
        self._do_redownload(entry)

    @work(thread=True)
    def _do_redownload(self, entry: HistoryEntry) -> None:
        from yank.engine.formats import FormatExtractError, extract_formats, pick_best_format
        from yank.screens.format_select import FormatSelectScreen

        self.app.call_from_thread(
            self.notify, f"Fetching {entry.url[:40]}…", severity="information"
        )
        try:
            meta = extract_formats(entry.url, timeout=FORMAT_TIMEOUT)
            if not meta.formats:
                self.app.call_from_thread(
                    self.notify, "No formats available for this video.", severity="error"
                )
                return
        except FormatExtractError as exc:
            self.app.call_from_thread(self.notify, exc.message, severity="error")
            return
        except Exception as exc:
            from yank.engine.formats import _humanize_ytdlp_error
            self.app.call_from_thread(
                self.notify, _humanize_ytdlp_error(str(exc)), severity="error"
            )
            return

        def _push() -> None:
            self.app.push_screen(FormatSelectScreen(meta=meta))

        self.app.call_from_thread(_push)

    # ── Copy info ────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-copy")
    def action_copy_info(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.notify("Select a history entry first.", severity="warning")
            return
        text = (
            f"Title: {entry.title}\n"
            f"URL: {entry.url}\n"
            f"Format: {entry.format_id}\n"
            f"Path: {entry.file_path}\n"
            f"Status: {entry.status}\n"
            f"Date: {entry.date}\n"
            f"Size: {_format_size(entry.filesize)}"
        )
        try:
            self.app.copy_to_clipboard(text)
            self.notify("Copied to clipboard.", severity="information")
        except Exception:
            self.query_one("#hist-detail", Label).update(text.replace("\n", " · ")[:150])
            self.notify("Clipboard unavailable; details shown below.", severity="warning")

    # ── Clear / Back ─────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-clear")
    def on_clear(self) -> None:
        self._app.history.clear()
        self.refresh_table()
        self.notify("History cleared.", severity="information")

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()
