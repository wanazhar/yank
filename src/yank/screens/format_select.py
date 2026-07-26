"""Format selection screen with metadata side panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

if TYPE_CHECKING:
    from yank.app import YankApp

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from yank.constants import MAX_SUBTITLE_DISPLAY
from yank.engine.formats import FormatInfo, VideoMeta, pick_best_format
from yank.logging import get_logger
from yank.widgets.format_table import FormatTable

_logger = get_logger(__name__)


class FormatSelectScreen(Screen):
    """Show formats in a table; side panel with video metadata."""

    @property
    def _app(self) -> YankApp:
        """Narrow ``self.app`` to the known ``YankApp`` subtype."""
        return cast("YankApp", self.app)

    BINDINGS: ClassVar = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("enter", "confirm", "Select", show=True),
        Binding("space", "toggle_select", "Select format", show=True),
    ]

    CSS = """
    FormatSelectScreen {
        layout: vertical;
    }
    #fmt-main {
        height: 1fr;
        width: 100%;
    }
    #fmt-table-wrap {
        width: 2fr;
        height: 100%;
        border: solid #a855f7 30%;
        padding: 0 1;
        background: #0a0a0f;
    }
    #fmt-side {
        width: 1fr;
        height: 100%;
        border: solid #a855f7 30%;
        padding: 1;
        background: #0a0a0f;
    }
    #fmt-side .meta-title {
        text-style: bold;
        color: #a855f7;
        margin-bottom: 1;
        height: auto;
    }
    #fmt-side .meta-row {
        height: auto;
        margin-bottom: 0;
        color: #64748b;
    }
    #fmt-side .meta-value {
        color: #e2e8f0;
        margin-bottom: 1;
        height: auto;
    }
    #fmt-header {
        height: auto;
        padding: 0 1;
        margin-bottom: 0;
    }
    #fmt-actions {
        height: auto;
        padding: 1;
        align: left middle;
    }
    #fmt-actions Button {
        margin-right: 1;
    }
    #fmt-hint {
        color: #64748b;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        meta: VideoMeta,
        *,
        remaining_urls: list[str] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.meta = meta
        self.remaining_urls = remaining_urls or []
        self._selected: FormatInfo | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(
            f"Formats — {self.meta.platform or 'Media'} · ↑↓ navigate · Space select · Enter continue",
            id="fmt-header",
        )
        with Horizontal(id="fmt-main"):
            with Vertical(id="fmt-table-wrap"):
                yield FormatTable(id="format-table")
            with VerticalScroll(id="fmt-side"):
                yield Label(self.meta.title, classes="meta-title")
                yield Label("Duration", classes="meta-row")
                yield Label(self.meta.duration_display, classes="meta-value", id="meta-duration")
                yield Label("Uploader", classes="meta-row")
                yield Label(self.meta.uploader or "—", classes="meta-value", id="meta-uploader")
                yield Label("Upload date", classes="meta-row")
                yield Label(self.meta.upload_date_display, classes="meta-value", id="meta-date")
                yield Label("Subtitles", classes="meta-row")
                subs = (
                    ", ".join(self.meta.available_subtitle_langs[:MAX_SUBTITLE_DISPLAY])
                    if self.meta.has_subtitles
                    else "none"
                )
                if (
                    self.meta.has_subtitles
                    and len(self.meta.available_subtitle_langs) > MAX_SUBTITLE_DISPLAY
                ):
                    subs += "…"
                yield Label(subs, classes="meta-value", id="meta-subs")
                yield Label("URL", classes="meta-row")
                yield Label(self.meta.url[:60], classes="meta-value")
                if self.meta.view_count is not None:
                    yield Label("Views", classes="meta-row")
                    yield Label(f"{self.meta.view_count:,}", classes="meta-value")
        with Horizontal(id="fmt-actions"):
            yield Button("Continue", variant="primary", id="btn-confirm")
            yield Button("Back", id="btn-back")
            yield Label(
                f"{len(self.meta.formats)} format(s)"
                + (
                    f" · {len(self.remaining_urls)} more URL(s) in batch"
                    if self.remaining_urls
                    else ""
                ),
                id="fmt-hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#format-table", FormatTable)
        preference = "best"
        try:
            preference = self._app.config.format_preference
        except Exception:
            _logger.debug("Failed to read format_preference from config", exc_info=True)
        best = pick_best_format(self.meta.formats, preference) if self.meta.formats else None
        selected_id = best.format_id if best else None
        self._selected = best
        table.set_formats(self.meta.formats, selected_id=selected_id)
        if not self.meta.formats:
            self.notify("No formats available for this video.", severity="error")
        table.focus()

    @on(FormatTable.FormatSelected)
    def on_format_selected(self, event: FormatTable.FormatSelected) -> None:
        self._selected = event.format_info

    def action_toggle_select(self) -> None:
        table = self.query_one("#format-table", FormatTable)
        self._selected = table.select_highlighted()

    def action_confirm(self) -> None:
        self._do_confirm()

    @on(Button.Pressed, "#btn-confirm")
    def on_confirm_btn(self) -> None:
        self._do_confirm()

    def _do_confirm(self) -> None:
        if not self.meta.formats:
            self.notify("No formats available for this video.", severity="error")
            return
        table = self.query_one("#format-table", FormatTable)
        fmt = table.get_selected_format() or self._selected
        if fmt is None:
            self.notify("Select a format first.", severity="warning")
            return
        from yank.screens.options import OptionsScreen

        self.app.push_screen(
            OptionsScreen(
                meta=self.meta,
                selected_format=fmt,
                remaining_urls=self.remaining_urls,
            )
        )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()
