"""Textual application class for yank."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import TextArea
from yank.i18n import LocalizedButton as Button, LocalizedLabel as Label

from yank.engine.downloader import DownloadItem, DownloadManager, DownloadStatus
from yank.engine.queue import QueueEngine
from yank.engine.updater import YtDlpManager
from yank.logging import get_logger
from yank.models.config import AppConfig, load_config, save_config
from yank.models.history import HistoryEntry, HistoryStore
from yank.notify import send_notification
from yank.screens.url_input import URLInputScreen
from yank.services import AppServices
from yank.styles import APP_CSS
from yank.widgets.status_bar import StatusBar

_logger = get_logger(__name__)


class QuitConfirmScreen(ModalScreen[bool]):
    """Modal confirmation dialog shown before exiting yank."""

    CSS = """
    QuitConfirmScreen {
        align: center middle;
    }
    #quit-dialog {
        width: 40;
        height: auto;
        padding: 1 2;
        border: round #a855f7;
        background: #0a0a0f;
    }
    #quit-dialog Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        color: #e2e8f0;
    }
    #quit-dialog Horizontal {
        align: center middle;
        height: auto;
    }
    #quit-dialog Button {
        margin: 0 1;
        width: 12;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-dialog"):
            yield Label("Quit yank?")
            with Horizontal():
                yield Button("Yes", variant="error", id="btn-yes")
                yield Button("No", variant="primary", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(False)
            event.stop()


_PALETTE_COMMANDS = [
    ("Open Queue", "action_open_queue_palette", "Show download queue"),
    ("Open History", "action_open_history_palette", "Show download history"),
    ("Open Settings", "action_open_settings_palette", "Open settings"),
    ("Start all downloads", "action_start_all_palette", "Start queued items"),
    ("Pause all downloads", "action_pause_all_palette", "Pause active downloads"),
    ("Go home", "action_go_home_palette", "Return to URL input"),
    ("Toggle theme", "action_toggle_theme_palette", "Switch dark/light theme"),
    ("Check for updates", "action_check_updates_palette", "Check yt-dlp updates"),
    ("Help", "action_help_palette", "Show keybindings"),
    ("Quit", "action_quit", "Exit yank"),
]


class YankCommandProvider(Provider):
    """Command palette entries for yank."""

    async def discover(self) -> Hits:
        for name, method, help_text in _PALETTE_COMMANDS:
            callback = getattr(self.app, method)
            yield DiscoveryHit(name, callback, help=help_text)
        api = getattr(self.app, "plugin_api", None)
        for name, callback, help_text in api.commands() if api else ():
            yield DiscoveryHit(name, callback, help=help_text)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, method, help_text in _PALETTE_COMMANDS:
            if (score := matcher.match(name)) > 0:
                callback = getattr(self.app, method)
                yield Hit(score, matcher.highlight(name), callback, help=help_text)
        api = getattr(self.app, "plugin_api", None)
        for name, callback, help_text in api.commands() if api else ():
            if (score := matcher.match(name)) > 0:
                yield Hit(score, matcher.highlight(name), callback, help=help_text)


class WelcomeScreen(ModalScreen[None]):
    """First-run welcome modal."""

    CSS = """
    WelcomeScreen { align: center middle; }
    #welcome-dialog { width: 60; height: auto; border: round #a855f7; background: #0a0a0f; padding: 2; }
    #welcome-dialog Label { width: 100%; text-align: center; margin-bottom: 1; color: #e2e8f0; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-dialog"):
            yield Label("Welcome to yank!")
            yield Label("Paste a URL, pick a format, download.")
            yield Label("Press ? or Ctrl+P for help.")
            yield Button("Get started", variant="primary", id="btn-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()


class HelpScreen(ModalScreen[None]):
    """Modal showing keybindings and help."""

    CSS = """
    HelpScreen { align: center middle; }
    #help-dialog { width: 70; height: 80%; border: round #a855f7; background: #0a0a0f; padding: 1; }
    #help-text { height: 1fr; }
    """

    HELP_TEXT = (
        "yank — keybindings\\n\\n"
        "Global:\\n"
        "  Ctrl+Q / Ctrl+C  Quit (with confirmation)\\n"
        "  Ctrl+P           Command palette\\n"
        "  F2               Queue view\\n"
        "  F3               History\\n"
        "  F4               Settings\\n\\n"
        "URL input:\\n"
        "  Enter            Continue\\n"
        "  Esc              Quit\\n\\n"
        "Format selection:\\n"
        "  ↑↓               Navigate\\n"
        "  Space/Enter      Select format\\n"
        "  Esc              Back\\n\\n"
        "Queue:\\n"
        "  u/d              Move up/down\\n"
        "  Delete           Remove\\n"
        "  s                Start all\\n"
        "  p                Pause all\\n"
        "  Esc              Back\\n\\n"
        "History:\\n"
        "  r                Re-download\\n"
        "  y                Copy info\\n"
        "  /                Search\\n"
        "  Esc              Back\\n"
    )

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield TextArea(self.HELP_TEXT, id="help-text", read_only=True)
            yield Button("Close", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()


class LogViewerScreen(ModalScreen[None]):
    """Modal showing the application log."""

    CSS = """
    LogViewerScreen { align: center middle; }
    #log-dialog { width: 90%; height: 80%; border: round #a855f7; background: #0a0a0f; padding: 1; }
    #log-text { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        from yank.logging import LOG_FILE

        text = ""
        try:
            if LOG_FILE.exists():
                text = LOG_FILE.read_text(encoding="utf-8")[-50000:]
        except OSError:
            text = "Could not read log file."
        with Vertical(id="log-dialog"):
            yield TextArea(text, id="log-text", read_only=True)
            yield Button("Close", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            event.stop()


class YankApp(App):
    """yank — yank the web.

    Startup shows URL input immediately. Shared services (config, history,
    download manager, queue, yt-dlp manager) live on the ``.services``
    attribute and as direct typed properties on the app instance.
    """

    TITLE = "yank"
    SUB_TITLE = "yank the web"
    CSS = APP_CSS
    ENABLE_COMMAND_PALETTE = True
    COMMANDS: ClassVar = {YankCommandProvider}

    BINDINGS: ClassVar = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    # ── Typed attributes (set in __init__) ──────────────────────────────────
    config: AppConfig
    history: HistoryStore
    manager: DownloadManager
    queue: QueueEngine
    ytdlp: YtDlpManager
    services: AppServices
    _status_bar: StatusBar | None
    _update_notice: str

    def __init__(self) -> None:
        super().__init__()
        import threading

        self._watch_lock = threading.Lock()
        self.config = load_config()
        self.restore_backup_on_exit = None
        self.plugin_api: Any = None
        from yank.i18n import set_language

        set_language(self.config.language)
        self.history = HistoryStore()
        self.history.load()
        try:
            self.history.prune_older_than(self.config.history_retention_days)
        except Exception:
            _logger.debug("History prune failed", exc_info=True)

        self.manager = DownloadManager(
            self.config,
            on_progress=self._on_download_progress,
            on_finished=self._on_download_finished,
        )
        self.queue = QueueEngine(
            self.config,
            self.manager,
            on_change=self._on_queue_change,
        )
        self.ytdlp = YtDlpManager(self.config)
        self._update_notice = ""

        self.services = AppServices(
            config=self.config,
            history=self.history,
            manager=self.manager,
            queue=self.queue,
            ytdlp=self.ytdlp,
        )

    def compose(self) -> ComposeResult:
        yield StatusBar(id="app-status")

    def on_mount(self) -> None:
        self._startup_ytdlp()
        self.queue.load()
        self.push_screen(URLInputScreen())
        if not getattr(self.config, "seen_welcome", False):
            self.config.seen_welcome = True
            try:
                save_config(self.config)
            except OSError:
                pass
            self.push_screen(WelcomeScreen())
        try:
            if self.queue.size() > 0:
                self.call_from_thread(
                    self.notify,
                    f"Restored {self.queue.size()} queued item(s).",
                    severity="information",
                )
        except Exception:
            pass
        self._apply_theme()
        try:
            from yank.plugins import load_plugins

            _count, api = load_plugins(self)
            self.plugin_api = api
        except Exception:
            _logger.debug("Plugin loading failed", exc_info=True)
            self.plugin_api = None
        self.refresh_status_bar()
        self.set_interval(5.0, self._watch_folder_tick)
        self.set_interval(10.0, lambda: self.queue.release_scheduled())

    def get_status_bar(self) -> StatusBar | None:
        try:
            return self.query_one("#app-status", StatusBar)
        except Exception:
            _logger.debug("StatusBar query failed", exc_info=True)
            return None

    def refresh_status_bar(self) -> None:
        bar = self.get_status_bar()
        if bar is None:
            return
        bar.set_status(
            ytdlp_version=self.ytdlp.current_version(),
            queue_size=self.queue.active_size(),
            download_dir=self.config.download_dir,
            notification=self._update_notice,
        )

    # ── Startup ─────────────────────────────────────────────────────────────

    @work(thread=True)
    def _startup_ytdlp(self) -> None:
        """Install yt-dlp if missing; check for updates if due."""
        try:
            if not self.ytdlp.is_installed():
                self.call_from_thread(self._set_notice, "Installing yt-dlp…")
                ok = self.ytdlp.ensure_installed()
                if ok:
                    self.call_from_thread(
                        self._set_notice, f"yt-dlp {self.ytdlp.current_version()} installed."
                    )
                else:
                    self.call_from_thread(
                        self._set_notice, "yt-dlp missing — open Settings to install."
                    )
                self.call_from_thread(self.refresh_status_bar)
                return

            if self.ytdlp.should_check_on_startup():
                result = self.ytdlp.check_for_updates(force=True)
                if result.update_available:
                    notice = f"Update available: yt-dlp {result.latest_version}"
                    self.call_from_thread(self._set_notice, notice)
                    self.call_from_thread(
                        self.notify,
                        f"yt-dlp update available: {result.current_version} → {result.latest_version}",
                        severity="warning",
                        timeout=8,
                    )
                self.call_from_thread(self.refresh_status_bar)
        except Exception:
            _logger.debug("Startup yt-dlp task failed", exc_info=True)
            self.call_from_thread(
                self._set_notice, "yt-dlp startup check failed — open Settings."
            )

    def _set_notice(self, text: str) -> None:
        self._update_notice = text
        self.refresh_status_bar()
        # Clear notice after a while via timer on main thread
        self.set_timer(12.0, lambda: self._clear_notice_if(text))

    def _clear_notice_if(self, text: str) -> None:
        if self._update_notice == text:
            self._update_notice = ""
            self.refresh_status_bar()

    # ── Download callbacks (may run on worker threads) ──────────────────────

    def _on_download_progress(self, item: DownloadItem) -> None:
        self.queue.sync_from_manager(item)
        # UI widgets poll themselves; just refresh status occasionally
        try:
            self.call_from_thread(self.refresh_status_bar)
        except Exception:
            _logger.debug("call_from_thread(refresh_status_bar) failed", exc_info=True)

    def _on_download_finished(self, item: DownloadItem) -> None:
        self.queue.sync_from_manager(item)

        status_map: dict[DownloadStatus, Literal["success", "error", "cancelled"]] = {
            DownloadStatus.COMPLETED: "success",
            DownloadStatus.ERROR: "error",
            DownloadStatus.CANCELLED: "cancelled",
        }
        hist_status: Literal["success", "error", "cancelled"] = status_map.get(item.status, "error")
        if item.status in (
            DownloadStatus.COMPLETED,
            DownloadStatus.ERROR,
            DownloadStatus.CANCELLED,
        ):
            # Calculate filesize if available
            filesize = 0
            if item.progress.total_bytes:
                filesize = item.progress.total_bytes
            elif item.progress.downloaded_bytes > 0:
                filesize = item.progress.downloaded_bytes

            # Calculate checksum if file exists
            checksum = ""
            if item.file_path:
                import hashlib
                from pathlib import Path

                p = Path(item.file_path)
                if p.is_file():
                    try:
                        h = hashlib.sha256()
                        with open(p, "rb") as f:
                            for chunk in iter(lambda: f.read(65536), b""):
                                h.update(chunk)
                        checksum = h.hexdigest()
                    except OSError:
                        pass

            entry = HistoryEntry.create(
                title=item.title,
                url=item.url,
                format_id=item.format_id,
                file_path=item.file_path,
                status=hist_status,
                error=item.error,
                filesize=filesize,
                checksum=checksum,
                note=item.options.note if hasattr(item, "options") else "",
            )
            try:
                self.history.add(entry)
            except Exception:
                _logger.debug("Failed to add history entry for %s", item.title, exc_info=True)

            webhook = getattr(self.config, "webhook_url", "") or ""
            if webhook.strip():
                self._send_webhook(webhook.strip(), item, hist_status)

            if getattr(self.config, "email_notify", False):
                self._send_email(item, hist_status)

            api = getattr(self, "plugin_api", None)
            if api is not None:
                try:
                    api.emit("download_finished", item)
                except Exception:
                    _logger.debug("Plugin emit failed", exc_info=True)

        def _notify() -> None:
            self.refresh_status_bar()
            if item.status == DownloadStatus.COMPLETED:
                self.notify(f"Done: {item.title[:50]}", severity="information")
                if self.config.enable_notifications:
                    send_notification("yank — Download complete", item.title[:80])
            elif item.status == DownloadStatus.ERROR:
                self.notify(
                    f"Failed: {item.error or item.title[:40]}",
                    severity="error",
                    timeout=8,
                )
                if self.config.enable_notifications:
                    send_notification(
                        "yank — Download failed",
                        (item.error or item.title)[:80],
                    )

        try:
            self.call_from_thread(_notify)
        except Exception:
            _logger.debug("call_from_thread(_notify) failed", exc_info=True)

    def _on_queue_change(self) -> None:
        try:
            self.call_from_thread(self.refresh_status_bar)
        except Exception:
            _logger.debug(
                "call_from_thread(refresh_status_bar) failed from _on_queue_change", exc_info=True
            )

    def action_open_queue_palette(self) -> None:
        from yank.screens.queue import QueueScreen

        self.push_screen(QueueScreen())

    def action_open_history_palette(self) -> None:
        from yank.screens.history import HistoryScreen

        self.push_screen(HistoryScreen())

    def action_open_settings_palette(self) -> None:
        from yank.screens.settings import SettingsScreen

        self.push_screen(SettingsScreen())

    def action_start_all_palette(self) -> None:
        self.queue.start_all()
        self.refresh_status_bar()

    def action_pause_all_palette(self) -> None:
        self.queue.pause_all()
        self.refresh_status_bar()

    def action_go_home_palette(self) -> None:
        while len(self.screen_stack) > 1 and not isinstance(self.screen, URLInputScreen):
            self.pop_screen()
        if not isinstance(self.screen, URLInputScreen):
            self.push_screen(URLInputScreen())

    def action_toggle_theme_palette(self) -> None:
        self.config.theme = "light" if self.config.theme == "dark" else "dark"
        self.config.ensure_valid()
        try:
            save_config(self.config)
        except OSError:
            pass
        self._apply_theme()
        self.refresh_status_bar()

    def action_check_updates_palette(self) -> None:
        self._startup_ytdlp()

    def action_help_palette(self) -> None:
        self.push_screen(HelpScreen())

    def _apply_theme(self) -> None:
        if self.config.theme == "light":
            self.add_class("theme-light")
            self.remove_class("theme-dark")
        else:
            self.add_class("theme-dark")
            self.remove_class("theme-light")
        if getattr(self.config, "compact_mode", False):
            self.add_class("compact-mode")
        else:
            self.remove_class("compact-mode")
        if getattr(self.config, "high_contrast", False):
            self.add_class("high-contrast")
        else:
            self.remove_class("high-contrast")

    def _send_webhook(self, url: str, item: DownloadItem, status: str) -> None:
        import json
        import urllib.request

        payload = {
            "title": item.title,
            "url": item.url,
            "status": status,
            "file_path": item.file_path,
            "error": item.error,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
            urllib.request.urlopen(req, timeout=10).close()
        except Exception:
            _logger.debug("Webhook delivery failed", exc_info=True)

    def _send_email(self, item: DownloadItem, status: str) -> None:
        import smtplib
        from email.message import EmailMessage

        cfg = self.config
        host = getattr(cfg, "smtp_host", "") or ""
        if not host:
            return
        try:
            msg = EmailMessage()
            msg["Subject"] = f"yank download {status}: {item.title}"
            msg["From"] = getattr(cfg, "smtp_user", "") or "yank@localhost"
            msg["To"] = getattr(cfg, "email_to", "") or getattr(cfg, "smtp_user", "")
            msg.set_content(f"Title: {item.title}\nURL: {item.url}\nStatus: {status}\nFile: {item.file_path}\nError: {item.error}")
            with smtplib.SMTP(host, getattr(cfg, "smtp_port", 587), timeout=15) as s:
                s.starttls()
                user = getattr(cfg, "smtp_user", "") or ""
                pwd = getattr(cfg, "smtp_password", "") or ""
                if user:
                    s.login(user, pwd)
                s.send_message(msg)
        except Exception:
            _logger.debug("Email delivery failed", exc_info=True)

    @work(thread=True)
    def _watch_folder_tick(self) -> None:
        if not self._watch_lock.acquire(blocking=False):
            return
        try:
            self._process_watch_folder()
        finally:
            self._watch_lock.release()

    def _process_watch_folder(self) -> None:
        import shutil
        from pathlib import Path

        folder = getattr(self.config, "watch_folder", "") or ""
        if not folder.strip():
            return
        p = Path(folder).expanduser()
        if not p.is_dir():
            return
        for f in sorted(p.glob("*.txt")) + sorted(p.glob("*.url")):
            try:
                urls = [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
            except (OSError, UnicodeError):
                _logger.warning("Cannot read watch file %s", f, exc_info=True)
                continue
            failed = []
            for url in urls:
                from yank.engine.formats import is_valid_url

                if not is_valid_url(url):
                    failed.append(url)
                    continue
                try:
                    from yank.engine.downloader import DownloadItem, DownloadOptions
                    from yank.engine.formats import (
                        extract_formats,
                        format_selector_for,
                        pick_best_format,
                    )

                    meta = extract_formats(url, timeout=30)
                    if not meta.formats:
                        failed.append(url)
                        continue
                    best = pick_best_format(meta.formats, "best")
                    if best is None:
                        failed.append(url)
                        continue
                    selector = format_selector_for(best)
                    item = DownloadItem.create(
                        url=url,
                        title=meta.title,
                        format_id=best.format_id,
                        options=DownloadOptions(format_selector=selector),
                        meta=meta,
                        selected_format=best,
                    )
                    self.queue.add(item)
                except Exception:
                    failed.append(url)
                    _logger.debug("Watch folder enqueue failed", exc_info=True)
            if failed:
                if len(failed) != len(urls):
                    try:
                        tmp = f.with_name(f.name + ".tmp")
                        tmp.write_text("\n".join(failed) + "\n", encoding="utf-8")
                        tmp.replace(f)
                    except OSError:
                        _logger.warning("Cannot update watch file %s", f, exc_info=True)
                continue
            # Move processed file
            try:
                processed = p / "processed"
                processed.mkdir(exist_ok=True)
                shutil.move(str(f), str(processed / f.name))
            except OSError:
                pass

    @work
    async def action_quit(self) -> None:
        confirmed = await self.push_screen_wait(QuitConfirmScreen())
        if not confirmed:
            return
        try:
            self.manager.cancel_all()
        except Exception:
            _logger.debug("manager.cancel_all() failed during quit", exc_info=True)
        try:
            self.queue.save()
            save_config(self.config)
        except Exception:
            _logger.debug("queue.save() / save_config() failed during quit", exc_info=True)
        if self.restore_backup_on_exit is not None:
            import shutil
            from yank.paths import CONFIG_PATH, HISTORY_PATH, QUEUE_PATH

            try:
                for dst in (CONFIG_PATH, HISTORY_PATH, QUEUE_PATH):
                    src = self.restore_backup_on_exit / dst.name
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
            except OSError as exc:
                self.notify(f"Restore failed: {exc}", severity="error")
                return
        self.exit()
