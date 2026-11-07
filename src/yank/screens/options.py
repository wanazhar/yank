"""Download options screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

if TYPE_CHECKING:
    from yank.app import YankApp

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Select,
)

from yank.constants import FORMAT_TIMEOUT
from yank.engine.downloader import DownloadItem, DownloadOptions, DownloadStatus
from yank.engine.formats import FormatInfo, VideoMeta, format_selector_for
from yank.logging import get_logger

_logger = get_logger(__name__)


class OptionsScreen(Screen):
    """Configure output path, template, thumbnails, subs, audio extract, etc."""

    @property
    def _app(self) -> YankApp:
        """Narrow ``self.app`` to the known ``YankApp`` subtype."""
        return cast("YankApp", self.app)

    BINDINGS: ClassVar = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("enter", "start_download", "Download", show=True),
    ]

    CSS = """
    OptionsScreen {
        layout: vertical;
    }
    #opt-scroll {
        height: 1fr;
        padding: 1 2;
    }
    #opt-title {
        text-style: bold;
        color: #a855f7;
        margin-bottom: 1;
        height: auto;
    }
    .opt-label {
        margin-top: 1;
        color: #64748b;
        height: 1;
    }
    .opt-row {
        height: auto;
        margin-bottom: 0;
        width: 100%;
        color: #e2e8f0;
    }
    #opt-actions {
        height: auto;
        padding: 1 2;
        dock: bottom;
    }
    #opt-actions Button {
        margin-right: 1;
    }
    #opt-error {
        color: #ef4444;
        height: auto;
        padding: 0 2;
    }
    .hidden {
        display: none;
    }
    """

    def __init__(
        self,
        meta: VideoMeta,
        selected_format: FormatInfo,
        *,
        remaining_urls: list[str] | None = None,
        playlist_mode: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.meta = meta
        self.selected_format = selected_format
        self.remaining_urls = remaining_urls or []
        self.playlist_mode = playlist_mode

    def compose(self) -> ComposeResult:
        cfg = self._app.config
        has_subs = self.meta.has_subtitles
        sub_langs = self.meta.available_subtitle_langs

        yield Header(show_clock=True)
        with VerticalScroll(id="opt-scroll"):
            yield Label(f"Options — {self.meta.title[:60]}", id="opt-title")
            yield Label(
                f"Format: {self.selected_format.format_id} · "
                f"{self.selected_format.resolution} · {self.selected_format.ext}",
                classes="opt-row",
            )

            yield Label("Output directory", classes="opt-label")
            yield Input(
                value=cfg.download_dir,
                placeholder="~/Downloads",
                id="opt-outdir",
            )

            yield Label("Filename template", classes="opt-label")
            yield Input(
                value=cfg.filename_template,
                placeholder="%(title)s.%(ext)s",
                id="opt-template",
            )

            yield Checkbox(
                "Download thumbnail",
                value=cfg.download_thumbnail,
                id="opt-thumb",
            )
            yield Checkbox(
                "Embed metadata",
                value=cfg.embed_metadata,
                id="opt-meta",
            )

            yield Checkbox(
                "Embed subtitles",
                value=cfg.embed_subtitles and has_subs,
                id="opt-subs",
                classes="" if has_subs else "hidden",
            )

            sub_options: list[tuple[str, str]] = [(lang, lang) for lang in sub_langs]
            if not sub_options:
                sub_options = [("en", "en")]
            default_lang = cfg.default_subtitle_lang
            if default_lang not in dict(sub_options):
                default_lang = sub_options[0][1]

            yield Label(
                "Subtitle language",
                classes="opt-label" + ("" if has_subs else " hidden"),
                id="opt-sublang-label",
            )
            yield Select(
                sub_options,
                value=default_lang,
                id="opt-sublang",
                classes="" if has_subs else "hidden",
                allow_blank=False,
            )

            yield Checkbox(
                "Extract audio only",
                value=cfg.format_preference == "audio_only",
                id="opt-audio-only",
            )
            yield Label("Audio format", classes="opt-label", id="opt-aformat-label")
            yield Select(
                [
                    ("mp3", "mp3"),
                    ("m4a", "m4a"),
                    ("opus", "opus"),
                    ("flac", "flac"),
                ],
                value=cfg.audio_format,
                id="opt-aformat",
                allow_blank=False,
            )

            yield Label(
                "Custom format string (power users — overrides selection)",
                classes="opt-label",
            )
            yield Input(
                value="",
                placeholder="e.g. bestvideo[height<=1080]+bestaudio/best",
                id="opt-custom-fmt",
            )

            yield Label("Proxy URL (overrides global; blank uses default)", classes="opt-label")
            yield Input(
                value="",
                placeholder="http://proxy:port",
                id="opt-proxy",
            )

            yield Label("Metadata title override", classes="opt-label")
            yield Input(value="", placeholder="", id="opt-meta-title")

            yield Label("Metadata artist override", classes="opt-label")
            yield Input(value="", placeholder="", id="opt-meta-artist")

            yield Label("Download note (saved to history)", classes="opt-label")
            yield Input(value="", placeholder="", id="opt-note")

            yield Label("Tag (for queue grouping)", classes="opt-label")
            yield Input(value="", placeholder="music", id="opt-tag")

            yield Label("Schedule in minutes (0 = now)", classes="opt-label")
            yield Input(value="0", placeholder="0", id="opt-schedule")

            yield Label("Playlist items (e.g. 1-5,7)", classes="opt-label")
            yield Input(
                value=cfg.playlist_items,
                placeholder="1-5,7",
                id="opt-playlist-items",
            )

            yield Label("SponsorBlock remove (comma categories, e.g. sponsor,intro)", classes="opt-label")
            yield Input(
                value="",
                placeholder="sponsor,intro,outro",
                id="opt-sponsorblock",
            )

            yield Label("Download sections (e.g. *00:01:00-00:02:00)", classes="opt-label")
            yield Input(
                value="",
                placeholder="*00:01:00-00:02:00",
                id="opt-sections",
            )

            yield Checkbox(
                "Save subtitles as separate file",
                value=False,
                id="opt-write-subs",
            )

            yield Checkbox(
                "Normalize audio (loudnorm)",
                value=False,
                id="opt-normalize",
            )

            yield Checkbox(
                "Split by chapters",
                value=False,
                id="opt-split",
            )

        yield Label("", id="opt-error")
        with Horizontal(id="opt-actions"):
            yield Button("Download", variant="primary", id="btn-download")
            yield Button("Add to queue only", id="btn-queue-only")
            yield Button("Back", id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        self._update_audio_visibility()
        has_subs = self.meta.has_subtitles
        if not has_subs:
            for wid in ("opt-subs", "opt-sublang", "opt-sublang-label"):
                try:
                    self.query_one(f"#{wid}").add_class("hidden")
                except Exception:
                    _logger.debug("Failed to hide widget %s", wid, exc_info=True)

    @on(Checkbox.Changed, "#opt-audio-only")
    def on_audio_only_changed(self, event: Checkbox.Changed) -> None:
        self._update_audio_visibility()

    def _update_audio_visibility(self) -> None:
        try:
            audio_only = self.query_one("#opt-audio-only", Checkbox).value
            for wid in ("opt-aformat", "opt-aformat-label"):
                w = self.query_one(f"#{wid}")
                if audio_only:
                    w.remove_class("hidden")
                else:
                    w.add_class("hidden")
        except Exception:
            _logger.debug("Failed to update audio visibility", exc_info=True)

    def _build_options(self) -> DownloadOptions | None:
        if self.selected_format is None:
            self.query_one("#opt-error", Label).update("No format selected.")
            return None
        cfg = self._app.config
        outdir = self.query_one("#opt-outdir", Input).value.strip()
        if not outdir:
            outdir = cfg.download_dir
        outdir = str(Path(outdir).expanduser())

        try:
            Path(outdir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.query_one("#opt-error", Label).update(f"Cannot use that directory: {exc}")
            return None

        template = self.query_one("#opt-template", Input).value.strip() or cfg.filename_template
        thumb = self.query_one("#opt-thumb", Checkbox).value
        embed_meta = self.query_one("#opt-meta", Checkbox).value
        audio_only = self.query_one("#opt-audio-only", Checkbox).value

        embed_subs = False
        sub_langs: list[str] = []
        if self.meta.has_subtitles:
            embed_subs = self.query_one("#opt-subs", Checkbox).value

        write_subs_file = False
        try:
            write_subs_file = self.query_one("#opt-write-subs", Checkbox).value
        except Exception:
            _logger.debug("Failed to read write-subs checkbox", exc_info=True)
        if self.meta.has_subtitles and (embed_subs or write_subs_file):
            try:
                lang = self.query_one("#opt-sublang", Select).value
                if lang and lang != Select.BLANK:
                    sub_langs = [str(lang)]
            except Exception:
                sub_langs = [cfg.default_subtitle_lang]

        normalize_audio = False
        try:
            normalize_audio = self.query_one("#opt-normalize", Checkbox).value
        except Exception:
            _logger.debug("Failed to read normalize checkbox", exc_info=True)

        split_chapters = False
        try:
            split_chapters = self.query_one("#opt-split", Checkbox).value
        except Exception:
            _logger.debug("Failed to read split checkbox", exc_info=True)

        audio_format = cfg.audio_format
        try:
            af = self.query_one("#opt-aformat", Select).value
            if af and af != Select.BLANK:
                audio_format = str(af)
        except Exception:
            _logger.debug("Failed to read audio format select", exc_info=True)

        custom = self.query_one("#opt-custom-fmt", Input).value.strip() or None
        try:
            proxy_val = self.query_one("#opt-proxy", Input).value.strip()
        except Exception:
            proxy_val = ""
        try:
            meta_title_val = self.query_one("#opt-meta-title", Input).value.strip()
        except Exception:
            meta_title_val = ""
        try:
            meta_artist_val = self.query_one("#opt-meta-artist", Input).value.strip()
        except Exception:
            meta_artist_val = ""
        try:
            note_val = self.query_one("#opt-note", Input).value.strip()
        except Exception:
            note_val = ""
        try:
            tag_val = self.query_one("#opt-tag", Input).value.strip()
        except Exception:
            tag_val = ""
        try:
            playlist_items_val = self.query_one("#opt-playlist-items", Input).value.strip()
        except Exception:
            playlist_items_val = ""
        try:
            sponsorblock_val = self.query_one("#opt-sponsorblock", Input).value.strip()
        except Exception:
            sponsorblock_val = ""
        try:
            sections_val = self.query_one("#opt-sections", Input).value.strip()
        except Exception:
            sections_val = ""
        selector = format_selector_for(
            self.selected_format,
            audio_only=audio_only,
            custom=custom,
        )

        return DownloadOptions(
            output_dir=outdir,
            filename_template=template,
            format_selector=selector,
            download_thumbnail=thumb,
            embed_metadata=embed_meta,
            embed_subtitles=embed_subs,
            subtitle_langs=sub_langs,
            write_subtitles_file=write_subs_file,
            subtitle_format=cfg.subtitle_format,
            extract_audio=audio_only,
            audio_format=audio_format,
            custom_format=custom,
            proxy=proxy_val,
            playlist_items=playlist_items_val,
            sponsorblock_remove=sponsorblock_val,
            audio_normalize=normalize_audio or cfg.audio_normalize,
            split_chapters=split_chapters or cfg.split_chapters,
            download_sections=sections_val,
            meta_title=meta_title_val,
            meta_artist=meta_artist_val,
            note=note_val,
            tag=tag_val,
        )

    def _make_item(self, opts: DownloadOptions) -> DownloadItem:
        return DownloadItem.create(
            url=self.meta.url,
            title=self.meta.title,
            format_id=self.selected_format.format_id,
            options=opts,
            meta=self.meta,
            selected_format=self.selected_format,
        )

    def _selected_playlist_urls(self, opts: DownloadOptions) -> list[str] | None:
        urls = [self.meta.url, *self.remaining_urls]
        if not self.playlist_mode or not opts.playlist_items:
            return urls
        from yt_dlp.utils import PlaylistEntries

        try:
            entries = PlaylistEntries(None, {"entries": urls})
            selected = [
                url for part in entries.parse_playlist_items(opts.playlist_items)
                for _, url in entries[part]
            ]
        except ValueError as exc:
            self.query_one("#opt-error", Label).update(f"Invalid playlist items: {exc}")
            return None
        if not selected:
            self.query_one("#opt-error", Label).update("Playlist selection is empty.")
            return None
        return selected

    @on(Button.Pressed, "#btn-download")
    def on_download(self) -> None:
        self.action_start_download()

    def action_start_download(self) -> None:
        opts = self._build_options()
        if opts is None:
            return
        urls = self._selected_playlist_urls(opts)
        if urls is None:
            return
        if urls[0] != self.meta.url:
            try:
                delay = max(0.0, float(self.query_one("#opt-schedule", Input).value.strip() or "0"))
            except ValueError:
                delay = 0.0
            self._enqueue_remaining(urls, opts, start_first=True, delay=delay)
            from yank.screens.queue import QueueScreen
            self.app.push_screen(QueueScreen())
            return
        item = self._make_item(opts)
        qi = self._app.queue.add(item)
        # Schedule support
        try:
            mins = float(self.query_one("#opt-schedule", Input).value.strip() or "0")
        except ValueError:
            mins = 0.0
        if mins and mins > 0:
            import time as _t

            qi.scheduled_at = _t.time() + mins * 60
            qi.status = "pending"
            item.status = DownloadStatus.PENDING
            self._app.queue.sync_from_manager(item) if False else None
            self._app.queue._emit()
        else:
            # Start only the newly added item, not all queued items
            self._app.manager.start(item.id)
        self._app.refresh_status_bar()

        # Enqueue remaining batch URLs with same options (best effort async)
        if len(urls) > 1:
            self._enqueue_remaining(urls[1:], opts)

        from yank.screens.download import DownloadScreen

        self.app.push_screen(DownloadScreen(focus_id=item.id))

    @on(Button.Pressed, "#btn-queue-only")
    def on_queue_only(self) -> None:
        opts = self._build_options()
        if opts is None:
            return
        urls = self._selected_playlist_urls(opts)
        if urls is None:
            return
        if urls[0] != self.meta.url:
            self._enqueue_remaining(urls, opts)
            from yank.screens.queue import QueueScreen
            self.app.push_screen(QueueScreen())
            return
        item = self._make_item(opts)
        self._app.queue.add(item)
        self._app.refresh_status_bar()
        if len(urls) > 1:
            self._enqueue_remaining(urls[1:], opts)
        self.notify(f"Added to queue: {item.title[:40]}", severity="information")
        from yank.screens.queue import QueueScreen

        self.app.push_screen(QueueScreen())

    @work(thread=True)
    def _enqueue_remaining(
        self, urls: list[str], opts: DownloadOptions, *, start_first: bool = False, delay: float = 0.0
    ) -> None:
        from yank.engine.formats import FormatExtractError, extract_formats, pick_best_format

        for url in urls:
            try:
                meta = extract_formats(url, timeout=FORMAT_TIMEOUT)
                if not meta.formats:
                    self.app.call_from_thread(
                        self.notify, f"Batch skip: No formats for {url[:40]}", severity="warning"
                    )
                    continue
                best = pick_best_format(meta.formats, "best")
                if best is None:
                    self.app.call_from_thread(
                        self.notify,
                        f"Batch skip: No suitable format for {url[:40]}",
                        severity="warning",
                    )
                    continue
                selector = format_selector_for(
                    best,
                    audio_only=opts.extract_audio,
                    custom=opts.custom_format,
                )
                item_opts = DownloadOptions(
                    output_dir=opts.output_dir,
                    filename_template=opts.filename_template,
                    format_selector=selector,
                    download_thumbnail=opts.download_thumbnail,
                    embed_metadata=opts.embed_metadata,
                    embed_subtitles=opts.embed_subtitles,
                    subtitle_langs=list(opts.subtitle_langs),
                    write_subtitles_file=opts.write_subtitles_file,
                    subtitle_format=opts.subtitle_format,
                    extract_audio=opts.extract_audio,
                    audio_format=opts.audio_format,
                    custom_format=opts.custom_format,
                    proxy=opts.proxy,
                    playlist_items=opts.playlist_items,
                    sponsorblock_remove=opts.sponsorblock_remove,
                    audio_normalize=opts.audio_normalize,
                    split_chapters=opts.split_chapters,
                    download_sections=opts.download_sections,
                    meta_title=opts.meta_title,
                    meta_artist=opts.meta_artist,
                    note=opts.note,
                    tag=opts.tag,
                )
                item = DownloadItem.create(
                    url=url,
                    title=meta.title,
                    format_id=best.format_id,
                    options=item_opts,
                    meta=meta,
                    selected_format=best,
                )

                def _add(it=item, start=start_first):
                    qi = self._app.queue.add(it)
                    if start and delay:
                        import time
                        qi.scheduled_at = time.time() + delay * 60
                        self._app.queue._emit()
                    elif start:
                        self._app.manager.start(it.id)
                    self._app.refresh_status_bar()

                self.app.call_from_thread(_add)
                start_first = False
            except FormatExtractError as exc:
                self.app.call_from_thread(
                    self.notify, f"Batch skip: {exc.message}", severity="warning"
                )
            except Exception as exc:
                from yank.engine.formats import _humanize_ytdlp_error

                self.app.call_from_thread(
                    self.notify,
                    f"Batch skip: {_humanize_ytdlp_error(str(exc))}",
                    severity="warning",
                )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()
