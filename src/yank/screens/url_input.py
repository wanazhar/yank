"""URL input screen — startup screen, paste one or more URLs."""

from __future__ import annotations

import pyfiglet

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, TextArea

from yank.engine.formats import detect_platform, is_valid_url


class URLInputScreen(Screen):
    """First screen: paste URL(s) for single or batch queue."""

    BINDINGS = [
        Binding("escape", "app.quit", "Quit", show=True),
        Binding("ctrl+c", "app.quit", "Quit", show=False),
        Binding("f2", "open_queue", "Queue", show=True),
        Binding("f3", "open_history", "History", show=True),
        Binding("f4", "open_settings", "Settings", show=True),
    ]

    CSS = """
    URLInputScreen {
        align: center middle;
    }
    #url-container {
        width: 90%;
        max-width: 100;
        height: auto;
        max-height: 90%;
        border: round #a855f7;
        padding: 1 2;
        background: #0a0a0f;
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
        align: center middle;
        width: 100%;
    }
    #url-buttons Button {
        margin: 0 1;
        min-width: 14;
    }
    #nav-links {
        margin-top: 1;
        width: 100%;
        align: center middle;
        height: auto;
    }
    #nav-links Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="url-container"):
            with Vertical(id="logo-container"):
                # Generate ASCII art logo using pyfiglet
                logo_text = pyfiglet.figlet_format("yank", font="slant")
                yield Static(logo_text, id="ascii-logo")
                yield Label("yt-dlp TUI wrapper", id="subtitle")
            yield Label("Paste a video URL · or multiple URLs (one per line) for batch", id="url-hint")
            yield Input(
                placeholder="https://…",
                id="url-input",
            )
            yield TextArea(id="url-multi", classes="")
            yield Label("", id="platform-label")
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
            self.query_one("#url-hint", Label).update(
                "Batch mode: one URL per line, then Continue"
            )
        else:
            multi.remove_class("visible")
            single.focus()
            btn.label = "Batch mode"
            self.query_one("#url-hint", Label).update(
                "Paste a video URL · or multiple URLs (one per line) for batch"
            )

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
            self.query_one("#url-error", Label).update(
                "Paste at least one valid URL (https://…)."
            )
            return
        invalid = [u for u in urls if not is_valid_url(u)]
        if invalid:
            self.query_one("#url-error", Label).update(
                f"Invalid URL: {invalid[0][:60]}"
            )
            return

        self.query_one("#url-error", Label).update("")
        # First URL goes to format select; extras go to batch queue after options
        self._fetch_and_proceed(urls)

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
        return [single]

    @work(exclusive=True, thread=True)
    def _fetch_and_proceed(self, urls: list[str]) -> None:
        from yank.engine.formats import FormatExtractError, extract_formats
        from yank.screens.format_select import FormatSelectScreen

        self.app.call_from_thread(
            lambda: self.query_one("#url-error", Label).update(
                f"Fetching formats for {urls[0][:50]}…"
            )
        )
        try:
            meta = extract_formats(urls[0], timeout=30)
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
            self.app.call_from_thread(
                lambda m=msg: self.query_one("#url-error", Label).update(m)
            )
            return

        remaining = urls[1:]

        def _push() -> None:
            self.query_one("#url-error", Label).update("")
            self.app.push_screen(
                FormatSelectScreen(meta=meta, remaining_urls=remaining)
            )

        self.app.call_from_thread(_push)
