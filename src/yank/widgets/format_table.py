"""Format list table widget with keyboard selection."""

from __future__ import annotations

from typing import Any

from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

from yank.engine.formats import FormatInfo
from yank.logging import get_logger

_logger = get_logger(__name__)


class FormatTable(DataTable):
    """
    Tabular list of formats: ID, Extension, Resolution, Filesize, Codec, Note.

    Arrow keys navigate; Space toggles selection (single-select).
    """

    DEFAULT_CSS = """
    FormatTable {
        background: #0a0a0f;
    }
    FormatTable > .datatable--header {
        background: #0a0a0f;
        color: #06b6d4;
        text-style: bold;
    }
    FormatTable > .datatable--cursor {
        background: #a855f7 40%;
        border: solid #06b6d4;
    }
    FormatTable > .datatable--odd-row {
        background: #0d0d12;
    }
    FormatTable > .datatable--even-row {
        background: #0a0a0f;
    }
    """

    class FormatSelected(Message):
        """Posted when the highlighted/selected format changes."""

        def __init__(self, format_info: FormatInfo | None) -> None:
            super().__init__()
            self.format_info = format_info

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._formats: list[FormatInfo] = []
        self._selected_id: str | None = None
        self._row_keys: list = []

    def on_mount(self) -> None:
        self.add_columns(
            "Sel",
            "ID",
            "Ext",
            "Resolution",
            "Size",
            "Codec",
            "Kind",
            "Note",
        )

    def set_formats(
        self,
        formats: list[FormatInfo],
        *,
        selected_id: str | None = None,
    ) -> None:
        """Populate table; optionally pre-select a format by id."""
        self.clear()
        self._formats = list(formats)
        self._row_keys = []
        self._selected_id = selected_id

        for fmt in formats:
            sel = "●" if selected_id and fmt.format_id == selected_id else " "
            kind = fmt.kind_label
            row_key = self.add_row(
                sel,
                fmt.format_id,
                fmt.ext,
                fmt.resolution,
                fmt.filesize_display,
                fmt.codec_display,
                kind,
                fmt.note[:40],
                key=fmt.format_id,
            )
            self._row_keys.append(row_key)

        # Move cursor to selected
        if selected_id and formats:
            for i, fmt in enumerate(formats):
                if fmt.format_id == selected_id:
                    self.move_cursor(row=i)
                    break

    def get_selected_format(self) -> FormatInfo | None:
        if self._selected_id is None:
            return self.get_highlighted_format()
        for fmt in self._formats:
            if fmt.format_id == self._selected_id:
                return fmt
        return self.get_highlighted_format()

    def get_highlighted_format(self) -> FormatInfo | None:
        if not self._formats:
            return None
        row = self.cursor_row
        if row is None or row < 0 or row >= len(self._formats):
            return None
        return self._formats[row]

    def select_highlighted(self) -> FormatInfo | None:
        """Select the currently highlighted row (Space / Enter)."""
        fmt = self.get_highlighted_format()
        if fmt is None:
            return None
        self._selected_id = fmt.format_id
        self._refresh_selection_marks()
        self.post_message(self.FormatSelected(fmt))
        return fmt

    def _refresh_selection_marks(self) -> None:
        for i, fmt in enumerate(self._formats):
            mark = "●" if fmt.format_id == self._selected_id else " "
            try:
                self.update_cell_at(Coordinate(i, 0), mark)
            except Exception:
                _logger.debug("update_cell_at failed at row %s", i, exc_info=True)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.select_highlighted()

    def action_select_cursor(self) -> None:
        """Override default to also mark selection."""
        super().action_select_cursor()
        self.select_highlighted()
