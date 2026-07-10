"""History screen — chronological past downloads with search and re-download."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

from yank.models.history import HistoryEntry


class HistoryScreen(Screen):
    """Past downloads: Date, Title, URL, Format, File path, Status."""

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
    #hist-table > .datatable--header {
        background: #0a0a0f;
        color: #06b6d4;
        text-style: bold;
    }
    #hist-table > .datatable--cursor {
        background: #a855f7 40%;
        border: solid #06b6d4;
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
    #hist-detail {
        height: auto;
        max-height: 4;
        padding: 0 1;
        color: #64748b;
    }
    .section-header {
        text-style: bold;
        color: #7c3aed;
        /* text-transform: uppercase; not supported by Textual */
        border-bottom: solid #06b6d4;
        padding: 1 0;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("History", id="hist-header")
        yield Input(placeholder="Search title or URL…", id="hist-search")
        yield DataTable(id="hist-table", zebra_stripes=True, cursor_type="row")
        yield Label("", id="hist-detail")
        with Horizontal(id="hist-actions"):
            yield Button("Re-download", variant="primary", id="btn-redownload")
            yield Button("Copy info", id="btn-copy")
            yield Button("Clear history", id="btn-clear", variant="error")
            yield Button("Back", id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#hist-table", DataTable)
        table.add_columns("Date", "Title", "URL", "Format", "File", "Status")
        self._entries: list[HistoryEntry] = []
        self.refresh_table()
        table.focus()

    def refresh_table(self, query: str = "") -> None:
        store = self.app.history  # type: ignore[attr-defined]
        store.load()
        if query.strip():
            entries = store.search(query)
        else:
            entries = store.to_list()
        self._entries = entries
        table = self.query_one("#hist-table", DataTable)
        table.clear()
        for e in entries:
            date = e.date[:19].replace("T", " ") if e.date else "—"
            table.add_row(
                date,
                (e.title or "—")[:36],
                (e.url or "—")[:36],
                (e.format_id or "—")[:10],
                (e.file_path or "—")[:28],
                e.status,
            )
        self.query_one("#hist-detail", Label).update(
            f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
        )

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
            meta = extract_formats(entry.url, timeout=30)
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
            f"Date: {entry.date}"
        )
        try:
            self.app.copy_to_clipboard(text)
            self.notify("Copied to clipboard.", severity="information")
        except Exception:
            # Fallback: show in detail
            self.query_one("#hist-detail", Label).update(text.replace("\n", " · ")[:150])
            self.notify("Clipboard unavailable; details shown below.", severity="warning")

    @on(Button.Pressed, "#btn-clear")
    def on_clear(self) -> None:
        self.app.history.clear()  # type: ignore[attr-defined]
        self.refresh_table()
        self.notify("History cleared.", severity="information")

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()
