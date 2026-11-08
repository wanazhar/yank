"""URL input screen — startup screen, paste one or more URLs."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

if TYPE_CHECKING:
    from yank.app import YankApp

import pyfiglet
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalGroup
from textual.events import Resize
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static, TextArea

from yank.constants import FORMAT_TIMEOUT
from yank.engine.formats import detect_platform, is_valid_url
from yank.viewport import (
    apply_screen_viewport,
    figlet_yank,
    fit_height_slack,
    in_herdr_pane,
    is_herdr_canvas,
    is_phone_canvas,
    logo_font_for_tier,
    phone_button_labels,
    sync_fit_tier_classes,
    wordmark_line,
)
from yank.i18n import LocalizedButton as Button
from yank.i18n import LocalizedCheckbox as Checkbox
from yank.i18n import LocalizedLabel as Label


class URLInputScreen(Screen):
    """First screen: paste URL(s) for single or batch queue."""

    @property
    def _app(self) -> YankApp:
        """Narrow ``self.app`` to the known ``YankApp`` subtype."""
        return cast("YankApp", self.app)

    BINDINGS: ClassVar = [
        Binding("escape", "app.quit", "Quit", show=True),
        Binding("ctrl+c", "app.quit", "Quit", show=False),
        Binding("ctrl+v", "paste_clipboard", "Paste", show=True),
        Binding("f2", "open_queue", "Queue", show=True),
        Binding("f3", "open_history", "History", show=True),
        Binding("f4", "open_settings", "Settings", show=True),
    ]

    CSS = """
    URLInputScreen {
        layout: vertical;
    }
    #url-body {
        height: 1fr;
        width: 100%;
        align: center middle;
    }
    #url-container {
        width: 1fr;
        max-width: 100;
        height: auto;
        border: round #a855f7;
        padding: 1 1;
        background: #0a0a0f;
    }
    URLInputScreen.-vf-1 #url-container,
    URLInputScreen.-vf-0 #url-container {
        padding: 0 1;
    }
    URLInputScreen.-vf-0 #logo-container,
    URLInputScreen.-vf-1 #logo-container,
    URLInputScreen.-vf-2 #logo-container {
        margin-bottom: 0;
    }
    URLInputScreen.-vf-0 #url-hint,
    URLInputScreen.-vf-0 #url-input,
    URLInputScreen.-vf-0 #opt-playlist,
    URLInputScreen.-vf-1 #url-hint,
    URLInputScreen.-vf-1 #url-input {
        margin-bottom: 0;
    }
    URLInputScreen.-vf-0 #ascii-logo {
        display: none;
    }
    URLInputScreen.-vp-phone #url-container {
        padding: 0 1;
    }
    URLInputScreen.-vp-phone #logo-container,
    URLInputScreen.-vp-phone #subtitle,
    URLInputScreen.-vp-phone #url-hint,
    URLInputScreen.-vp-phone #url-input,
    URLInputScreen.-vp-phone #opt-playlist,
    URLInputScreen.-vp-phone #platform-label,
    URLInputScreen.-vp-phone #url-error {
        margin-bottom: 0;
    }
    URLInputScreen.-vp-phone #url-buttons,
    URLInputScreen.-vp-phone #nav-links {
        height: auto;
    }
    URLInputScreen.-vp-herdr #url-container {
        border: solid #a855f7;
        padding: 0 0;
    }
    URLInputScreen.-vp-herdr #subtitle {
        display: none;
    }
    URLInputScreen.-vp-herdr #url-hint {
        height: auto;
        max-height: 2;
    }
    URLInputScreen.-vw-stack #url-buttons,
    URLInputScreen.-vw-stack #nav-links {
        layout: vertical;
        height: auto;
    }
    URLInputScreen.-vw-stack #url-buttons Button,
    URLInputScreen.-vw-stack #nav-links Button {
        width: 100%;
        margin: 0 0 1 0;
    }
    #logo-container {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }
    #ascii-logo {
        color: #a855f7;
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 0;
    }
    #subtitle {
        color: #64748b;
        text-style: dim;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }
    #url-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: #a855f7;
    }
    #url-hint {
        color: #64748b;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }
    #clip-hint {
        color: #22c55e;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
        height: auto;
    }
    #url-input {
        width: 100%;
        margin-bottom: 1;
        border: solid #06b6d4;
        background: #0a0a0f;
        color: #e2e8f0;
    }
    #url-input:focus {
        border: solid #06b6d4;
        background: #0a0a0f;
    }
    #url-multi {
        width: 100%;
        height: 8;
        margin-bottom: 1;
        display: none;
        border: solid #06b6d4;
        background: #0a0a0f;
        color: #e2e8f0;
    }
    #url-multi.visible {
        display: block;
    }
    #platform-label {
        color: #22c55e;
        margin-bottom: 1;
        height: auto;
    }
    #url-error {
        color: #ef4444;
        margin-bottom: 1;
        height: auto;
    }
    #url-buttons {
        height: auto;
        width: 100%;
        layout: horizontal;
    }
    #url-buttons,
    #nav-links {
        align: center middle;
    }
    #url-buttons Button,
    #nav-links Button {
        margin: 0 1 1 0;
        width: 1fr;
        min-width: 0;
        min-height: 2;
    }
    #nav-links {
        margin-top: 1;
        width: 100%;
        layout: horizontal;
        height: auto;
    }
    #nav-links Button {
        margin: 0 1 0 0;
        width: 1fr;
        min-width: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="url-body"):
            with VerticalGroup(id="url-container"):
                with VerticalGroup(id="logo-container"):
                    logo_text = pyfiglet.figlet_format("yank", font="slant")
                    yield Static(logo_text, id="ascii-logo")
                    yield Label("yank the web", id="subtitle")
                yield Label(
                    "Paste a video URL · or multiple URLs (one per line) for batch",
                    id="url-hint",
                )
                yield Label("", id="clip-hint")
                yield Input(
                    placeholder="https://…",
                    id="url-input",
                )
                yield TextArea(id="url-multi", classes="")
                yield Label("", id="platform-label")
                yield Checkbox("Playlist mode (fetch all entries)", value=False, id="opt-playlist")
                yield Label("", id="url-error")
                with Horizontal(id="url-buttons"):
                    yield Button("Continue", variant="primary", id="btn-continue")
                    yield Button("Batch mode", id="btn-batch")
                    yield Button("Clear", id="btn-clear")
                with Horizontal(id="nav-links"):
                    yield Button("Queue [F2]", id="btn-queue", variant="default")
                    yield Button("History [F3]", id="btn-history")
                    yield Button("Settings [F4]", id="btn-settings")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#url-input", Input).focus()
        self._batch_mode = False
        self._fit_tier: int | None = None
        self._fit_size: tuple[int, int] | None = None
        self._resize_timer = None
        try:
            self.query_one("#opt-playlist", Checkbox).value = bool(
                getattr(self._app.config, "download_playlist", False)
            )
        except Exception:
            pass
        self._apply_viewport_fit()
        self._detect_clipboard_url()

    def on_resize(self, event: Resize) -> None:
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(0.12, self._apply_viewport_fit)

    def _apply_viewport_fit(self) -> None:
        """Largest density tier that fits the live layout (58×30 Termius, 57×28 Herdr)."""
        self._resize_timer = None
        size = self.app.size
        size_key = (size.width, size.height)
        if size_key == self._fit_size and self._fit_tier is not None:
            return

        apply_screen_viewport(self)
        phone = is_phone_canvas(size.width, size.height)
        herdr = is_herdr_canvas(size.width, size.height, in_herdr=in_herdr_pane())
        self.set_class(size.width < 32, "-vw-stack")

        if not phone and not herdr and size.width >= 100 and size.height >= 24:
            sync_fit_tier_classes(self, 3)
            self._apply_tier_visuals(3, size.width, phone=False, herdr=False)
            self._fit_tier = 3
            self._fit_size = size_key
            return

        slack = fit_height_slack(herdr=herdr)
        body = self.query_one("#url-body")
        chosen = 0
        for tier in range(3, -1, -1):
            sync_fit_tier_classes(self, tier)
            self._apply_tier_visuals(tier, size.width, phone=phone, herdr=herdr)
            self.refresh(layout=True)
            box_h = self.query_one("#url-container").size.height
            if box_h <= body.size.height - slack:
                chosen = tier
                break
            chosen = tier
        self._fit_tier = chosen
        self._fit_size = size_key
        self._apply_tier_visuals(chosen, size.width, phone=phone, herdr=herdr)

    def _apply_tier_visuals(
        self, tier: int, width: int, *, phone: bool, herdr: bool = False
    ) -> None:
        font = logo_font_for_tier(tier, width, phone=phone, herdr=herdr)
        try:
            logo = self.query_one("#ascii-logo", Static)
            if font is not None:
                logo.update(figlet_yank(font))
            elif phone and tier > 0:
                logo.update(wordmark_line())
            else:
                logo.update("")
        except Exception:
            pass

        if phone:
            labels = phone_button_labels(getattr(self, "_batch_mode", False))
            for btn_id, text in labels.items():
                btn = self.query_one(f"#{btn_id}", Button)
                btn.label = text
        else:
            self.query_one("#btn-batch", Button).label = (
                "Single mode" if getattr(self, "_batch_mode", False) else "Batch mode"
            )
            for btn_id, text in (
                ("btn-queue", "Queue [F2]"),
                ("btn-history", "History [F3]"),
                ("btn-settings", "Settings [F4]"),
            ):
                self.query_one(f"#{btn_id}", Button).label = text

        try:
            self.query_one("#url-multi", TextArea).styles.height = 4 if tier <= 1 else 8
        except Exception:
            pass

    def _detect_clipboard_url(self) -> None:
        """Check system clipboard for a valid URL and pre-fill the input."""
        try:
            text = self.app.clipboard.strip()
        except Exception:
            return
        if not text:
            return
        # Take the first URL-like line
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for line in lines:
            if is_valid_url(line):
                inp = self.query_one("#url-input", Input)
                if not inp.value.strip():
                    inp.value = line
                    self.query_one("#clip-hint", Label).update("URL detected from clipboard")
                return

    def action_paste_clipboard(self) -> None:
        """Paste system clipboard content into the URL input (Ctrl+V)."""
        try:
            text = self.app.clipboard.strip()
        except Exception:
            self.notify("Cannot read clipboard.", severity="warning")
            return
        if not text:
            return
        inp = self.query_one("#url-input", Input)
        inp.value = text
        inp.focus()
        inp.action_end()
        self.query_one("#clip-hint", Label).update("Pasted from clipboard")

    @on(Input.Changed, "#url-input")
    def on_url_changed(self, event: Input.Changed) -> None:
        url = event.value.strip()
        self.query_one("#url-error", Label).update("")
        if not url:
            self.query_one("#platform-label", Label).update("")
            return
        if is_valid_url(url):
            platform = detect_platform(url)
            self.query_one("#platform-label", Label).update(f"Platform: {platform}")
        else:
            self.query_one("#platform-label", Label).update("")

    @on(Input.Submitted, "#url-input")
    def on_url_submitted(self, event: Input.Submitted) -> None:
        self.action_continue()

    @on(Button.Pressed, "#btn-continue")
    def on_continue(self) -> None:
        self.action_continue()

    @on(Button.Pressed, "#btn-batch")
    def on_batch_toggle(self) -> None:
        self._batch_mode = not getattr(self, "_batch_mode", False)
        multi = self.query_one("#url-multi", TextArea)
        single = self.query_one("#url-input", Input)
        btn = self.query_one("#btn-batch", Button)
        if self._batch_mode:
            multi.add_class("visible")
            # Seed from single input
            if single.value.strip() and not multi.text.strip():
                multi.load_text(single.value.strip())
            multi.focus()
            btn.label = "Single mode"
            self.query_one("#url-hint", Label).update("Batch mode: one URL per line, then Continue")
            self._apply_viewport_fit()
        else:
            multi.remove_class("visible")
            single.focus()
            btn.label = "Batch mode"
            self.query_one("#url-hint", Label).update(
                "Paste a video URL · or multiple URLs (one per line) for batch"
            )
            self._apply_viewport_fit()

    @on(Button.Pressed, "#btn-clear")
    def on_clear(self) -> None:
        self.query_one("#url-input", Input).value = ""
        self.query_one("#url-multi", TextArea).load_text("")
        self.query_one("#platform-label", Label).update("")
        self.query_one("#url-error", Label).update("")

    @on(Button.Pressed, "#btn-queue")
    def action_open_queue(self) -> None:
        from yank.screens.queue import QueueScreen

        self.app.push_screen(QueueScreen())

    @on(Button.Pressed, "#btn-history")
    def action_open_history(self) -> None:
        from yank.screens.history import HistoryScreen

        self.app.push_screen(HistoryScreen())

    @on(Button.Pressed, "#btn-settings")
    def action_open_settings(self) -> None:
        from yank.screens.settings import SettingsScreen

        self.app.push_screen(SettingsScreen())

    def action_continue(self) -> None:
        urls = self._collect_urls()
        if not urls:
            self.query_one("#url-error", Label).update("Paste at least one valid URL (https://…).")
            return
        invalid = [u for u in urls if not is_valid_url(u)]
        if invalid:
            self.query_one("#url-error", Label).update(f"Invalid URL: {invalid[0][:60]}")
            return

        self.query_one("#url-error", Label).update("")
        playlist_mode = False
        try:
            playlist_mode = self.query_one("#opt-playlist", Checkbox).value
        except Exception:
            pass
        # First URL goes to format select; extras go to batch queue after options
        self._fetch_and_proceed(urls, playlist_mode=playlist_mode)

    def _collect_urls(self) -> list[str]:
        if getattr(self, "_batch_mode", False):
            text = self.query_one("#url-multi", TextArea).text
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            return lines
        single = self.query_one("#url-input", Input).value.strip()
        if not single:
            return []
        # Allow pasting multi-line into single input too
        if "\n" in single:
            return [ln.strip() for ln in single.splitlines() if ln.strip()]
        # Batch import from a local file path
        from pathlib import Path

        p = Path(single).expanduser()
        if p.is_file():
            try:
                lines = [
                    ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()
                ]
                if lines:
                    return lines
            except OSError:
                pass
        return [single]

    @work(exclusive=True, thread=True)
    def _fetch_and_proceed(self, urls: list[str], playlist_mode: bool = False) -> None:
        from yank.engine.formats import (
            FormatExtractError,
            extract_formats,
            extract_playlist_entries,
        )
        from yank.screens.format_select import FormatSelectScreen

        expanded_playlist = False
        if playlist_mode and len(urls) == 1:
            try:
                entries = extract_playlist_entries(urls[0], timeout=FORMAT_TIMEOUT)
                if entries:
                    urls = [u for u, _ in entries]
                    expanded_playlist = True
            except Exception:
                pass

        self.app.call_from_thread(
            lambda: self.query_one("#url-error", Label).update(
                f"Fetching formats for {urls[0][:50]}…"
            )
        )
        try:
            meta = extract_formats(urls[0], timeout=FORMAT_TIMEOUT)
            if not meta.formats:
                self.app.call_from_thread(
                    lambda: self.query_one("#url-error", Label).update(
                        "No formats available for this video."
                    )
                )
                return
        except FormatExtractError as exc:
            self.app.call_from_thread(
                lambda m=exc.message: self.query_one("#url-error", Label).update(m)
            )
            return
        except Exception as exc:
            from yank.engine.formats import _humanize_ytdlp_error

            msg = _humanize_ytdlp_error(str(exc))
            self.app.call_from_thread(lambda m=msg: self.query_one("#url-error", Label).update(m))
            return

        remaining = urls[1:]

        def _push() -> None:
            self.query_one("#url-error", Label).update("")
            self.app.push_screen(
                FormatSelectScreen(
                    meta=meta, remaining_urls=remaining, playlist_mode=expanded_playlist
                )
            )

        self.app.call_from_thread(_push)
