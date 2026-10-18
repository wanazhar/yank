"""Configuration / settings screen + yt-dlp management."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

if TYPE_CHECKING:
    from yank.app import YankApp

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Select,
)

from yank.logging import get_logger
from yank.models.config import AppConfig, save_config

_logger = get_logger(__name__)


class SettingsScreen(Screen):
    """Edit app defaults and manage yt-dlp."""

    @property
    def _app(self) -> YankApp:
        """Narrow ``self.app`` to the known ``YankApp`` subtype."""
        return cast("YankApp", self.app)

    BINDINGS: ClassVar = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("ctrl+s", "save", "Save", show=True),
    ]

    CSS = """
    SettingsScreen {
        layout: vertical;
    }
    #set-scroll {
        height: 1fr;
        padding: 1 2;
    }
    #set-title {
        text-style: bold;
        color: #a855f7;
        margin-bottom: 1;
    }
    .set-label {
        margin-top: 1;
        color: #64748b;
        height: 1;
    }
    #set-ytdlp-box {
        margin-top: 2;
        padding: 1;
        border: solid #a855f7 30%;
        height: auto;
        background: #0a0a0f;
    }
    #set-ytdlp-ver {
        text-style: bold;
        height: auto;
        color: #e2e8f0;
    }
    #set-ytdlp-msg {
        color: #64748b;
        height: auto;
        margin-top: 1;
    }
    #set-actions {
        height: auto;
        padding: 1 2;
        dock: bottom;
    }
    #set-actions Button {
        margin-right: 1;
    }
    #set-status {
        height: auto;
        padding: 0 2;
        color: #22c55e;
    }
    #set-status.error {
        color: #ef4444;
    }
    """

    def compose(self) -> ComposeResult:
        cfg: AppConfig = self._app.config
        yield Header(show_clock=True)
        with VerticalScroll(id="set-scroll"):
            yield Label("Settings", id="set-title")

            yield Label("Default download directory", classes="set-label")
            yield Input(value=cfg.download_dir, id="set-dir")

            yield Label("Default format preference", classes="set-label")
            yield Select(
                [
                    ("Best available", "best"),
                    ("Best video+audio (prefer separate)", "best_video_audio"),
                    ("Audio only", "audio_only"),
                ],
                value=cfg.format_preference,
                id="set-format-pref",
                allow_blank=False,
            )

            yield Label("Max concurrent downloads (1-5)", classes="set-label")
            yield Select(
                [(str(i), str(i)) for i in range(1, 6)],
                value=str(cfg.max_concurrent),
                id="set-concurrent",
                allow_blank=False,
            )

            yield Label("Default filename template", classes="set-label")
            yield Input(value=cfg.filename_template, id="set-template")

            yield Label("Default subtitle language", classes="set-label")
            yield Input(value=cfg.default_subtitle_lang, id="set-sublang")

            yield Label("Proxy URL (e.g. http://127.0.0.1:8080)", classes="set-label")
            yield Input(value=cfg.proxy, placeholder="http://proxy:port", id="set-proxy")

            yield Label("Cookies from browser (chrome/firefox/edge/brave/safari)", classes="set-label")
            yield Input(value=cfg.cookies_browser, placeholder="chrome", id="set-cookies-browser")

            yield Label("Cookies file (Netscape cookies.txt)", classes="set-label")
            yield Input(value=cfg.cookies_file, placeholder="/path/to/cookies.txt", id="set-cookies-file")

            yield Label("Download archive file (skip already-downloaded)", classes="set-label")
            yield Input(value=cfg.download_archive, placeholder="/path/to/archive.txt", id="set-archive")

            yield Label("Rate limit (e.g. 1M, 500K)", classes="set-label")
            yield Input(value=cfg.rate_limit, placeholder="1M", id="set-rate-limit")

            yield Label("Retry count (0-10)", classes="set-label")
            yield Input(value=str(cfg.retry_count), placeholder="3", id="set-retry-count")

            yield Label("yt-dlp update check", classes="set-label")
            yield Select(
                [
                    ("Always (on startup if >1h)", "always"),
                    ("Ask / check daily", "ask"),
                    ("Never", "never"),
                ],
                value=cfg.update_check_interval,
                id="set-update-interval",
                allow_blank=False,
            )

            yield Label("Theme", classes="set-label")
            yield Select(
                [("Dark", "dark"), ("Light", "light")],
                value=cfg.theme,
                id="set-theme",
                allow_blank=False,
            )

            with Vertical(id="set-ytdlp-box"):
                yield Label("yt-dlp management", classes="set-label")
                yield Label("Version: …", id="set-ytdlp-ver")
                yield Label("", id="set-ytdlp-msg")
                with Horizontal():
                    yield Button("Check for updates", id="btn-check-update")
                    yield Button("Update yt-dlp", id="btn-update", variant="primary")
                    yield Button("Install yt-dlp", id="btn-install")

        yield Label("", id="set-status")
        with Horizontal(id="set-actions"):
            yield Button("Save", variant="primary", id="btn-save")
            yield Button("View log", id="btn-log")
            yield Button("Health check", id="btn-health")
            yield Button("Back", id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_ytdlp_version()

    def _refresh_ytdlp_version(self) -> None:
        mgr = self._app.ytdlp
        ver = mgr.current_version()
        installed = mgr.is_installed()
        self.query_one("#set-ytdlp-ver", Label).update(
            f"Version: {ver}" + ("" if installed else " (not installed)")
        )

    def action_save(self) -> None:
        self._save()

    @on(Button.Pressed, "#btn-save")
    def on_save(self) -> None:
        self._save()

    def _save(self) -> None:
        cfg: AppConfig = self._app.config
        status = self.query_one("#set-status", Label)
        status.remove_class("error")

        directory = self.query_one("#set-dir", Input).value.strip()
        if not directory:
            status.add_class("error")
            status.update("Download directory cannot be empty.")
            return
        directory = str(Path(directory).expanduser())
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            status.add_class("error")
            status.update(f"Cannot create directory: {exc}")
            return

        cfg.download_dir = directory
        cfg.filename_template = (
            self.query_one("#set-template", Input).value.strip() or "%(title)s.%(ext)s"
        )
        cfg.default_subtitle_lang = self.query_one("#set-sublang", Input).value.strip() or "en"

        proxy = self.query_one("#set-proxy", Input).value.strip()
        cfg.proxy = proxy

        cfg.cookies_browser = self.query_one("#set-cookies-browser", Input).value.strip()
        cfg.cookies_file = self.query_one("#set-cookies-file", Input).value.strip()
        cfg.download_archive = self.query_one("#set-archive", Input).value.strip()
        cfg.rate_limit = self.query_one("#set-rate-limit", Input).value.strip()
        try:
            cfg.retry_count = int(self.query_one("#set-retry-count", Input).value.strip() or "3")
        except ValueError:
            pass

        try:
            th = self.query_one("#set-theme", Select).value
            if th and th != Select.BLANK:
                cfg.theme = str(th)
        except Exception:
            _logger.debug("Failed to read theme from settings", exc_info=True)

        try:
            fp = self.query_one("#set-format-pref", Select).value
            if fp and fp != Select.BLANK:
                cfg.format_preference = str(fp)  # type: ignore[assignment]
        except Exception:
            _logger.debug("Failed to read format_preference from settings", exc_info=True)

        try:
            conc = self.query_one("#set-concurrent", Select).value
            if conc and conc != Select.BLANK:
                cfg.max_concurrent = int(str(conc))
        except ValueError:
            status.add_class("error")
            status.update("Invalid concurrency value — must be a number.")
            return

        try:
            ui = self.query_one("#set-update-interval", Select).value
            if ui and ui != Select.BLANK:
                cfg.update_check_interval = str(ui)  # type: ignore[assignment]
        except Exception:
            _logger.debug("Failed to read update_check_interval from settings", exc_info=True)

        cfg.ensure_valid()
        try:
            save_config(cfg)
        except OSError as exc:
            status.add_class("error")
            status.update(f"Could not save config: {exc}")
            return

        # Update in-memory config references
        self._app.config = cfg
        self._app.manager.config = cfg
        self._app.queue.config = cfg
        self._app.ytdlp.config = cfg
        if hasattr(self._app, "_apply_theme"):
            self._app._apply_theme()
        self._app.refresh_status_bar()
        status.update("Settings saved.")
        self.notify("Settings saved.", severity="information")

    @on(Button.Pressed, "#btn-check-update")
    def on_check_update(self) -> None:
        self._check_update()

    @work(thread=True, exclusive=True)
    def _check_update(self) -> None:
        mgr = self._app.ytdlp
        self.app.call_from_thread(
            lambda: self.query_one("#set-ytdlp-msg", Label).update("Checking…")
        )
        result = mgr.check_for_updates(force=True)

        def _apply() -> None:
            self._refresh_ytdlp_version()
            msg = result.message
            if result.error:
                msg = f"{msg} ({result.error})"
            self.query_one("#set-ytdlp-msg", Label).update(msg)
            if result.update_available:
                self.notify(result.message, severity="warning")
            else:
                self.notify(result.message, severity="information")
            self._app.refresh_status_bar()

        self.app.call_from_thread(_apply)

    @on(Button.Pressed, "#btn-update")
    def on_update(self) -> None:
        self._do_update()

    @work(thread=True, exclusive=True)
    def _do_update(self) -> None:
        mgr = self._app.ytdlp

        def status(msg: str) -> None:
            self.app.call_from_thread(
                lambda m=msg: self.query_one("#set-ytdlp-msg", Label).update(m)
            )

        ok, msg = mgr.update(on_status=status)

        def _apply() -> None:
            self._refresh_ytdlp_version()
            self.query_one("#set-ytdlp-msg", Label).update(msg)
            self.notify(msg, severity="information" if ok else "error")
            self._app.refresh_status_bar()

        self.app.call_from_thread(_apply)

    @on(Button.Pressed, "#btn-install")
    def on_install(self) -> None:
        self._do_install()

    @work(thread=True, exclusive=True)
    def _do_install(self) -> None:
        mgr = self._app.ytdlp

        def status(msg: str) -> None:
            self.app.call_from_thread(
                lambda m=msg: self.query_one("#set-ytdlp-msg", Label).update(m)
            )

        ok = mgr.ensure_installed(on_status=status)

        def _apply() -> None:
            self._refresh_ytdlp_version()
            msg = (
                f"yt-dlp {mgr.current_version()} ready."
                if ok
                else "Install failed. Try: pip install yt-dlp"
            )
            self.query_one("#set-ytdlp-msg", Label).update(msg)
            self.notify(msg, severity="information" if ok else "error")
            self._app.refresh_status_bar()

        self.app.call_from_thread(_apply)

    @on(Button.Pressed, "#btn-log")
    def on_view_log(self) -> None:
        from yank.app import LogViewerScreen

        self.app.push_screen(LogViewerScreen())

    @on(Button.Pressed, "#btn-health")
    def on_health(self) -> None:
        import shutil

        msgs = []
        # ffmpeg
        if shutil.which("ffmpeg"):
            msgs.append("ffmpeg: OK")
        else:
            msgs.append("ffmpeg: MISSING")
        # yt-dlp
        if self._app.ytdlp.is_installed():
            msgs.append(f"yt-dlp: {self._app.ytdlp.current_version()}")
        else:
            msgs.append("yt-dlp: MISSING")
        # network (quick)
        try:
            import urllib.request

            urllib.request.urlopen("https://pypi.org", timeout=5).close()
            msgs.append("network: OK")
        except Exception:
            msgs.append("network: FAIL")
        self.notify(" | ".join(msgs), severity="information", timeout=10)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()
