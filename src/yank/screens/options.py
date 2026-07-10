"""Download options screen."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from yank.engine.downloader import DownloadItem, DownloadOptions
from yank.engine.formats import FormatInfo, VideoMeta, format_selector_for


class OptionsScreen(Screen):
    """Configure output path, template, thumbnails, subs, audio extract, etc."""

    BINDINGS = [
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
    Input {
        border: solid #06b6d4;
        background: #0a0a0f;
        color: #e2e8f0;
    }
    Input:focus {
        border: solid #06b6d4;
        background: #0a0a0f;
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

    def __init__(
        self,
        meta: VideoMeta,
        selected_format: FormatInfo,
        *,
        remaining_urls: list[str] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.meta = meta
        self.selected_format = selected_format
        self.remaining_urls = remaining_urls or []

    def compose(self) -> ComposeResult:
        cfg = self.app.config  # type: ignore[attr-defined]
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

            sub_options: list[tuple[str, str]] = [
                (lang, lang) for lang in sub_langs
            ]
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
                    pass

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
            pass

    def _build_options(self) -> DownloadOptions | None:
        if self.selected_format is None:
            self.query_one("#opt-error", Label).update("No format selected.")
            return None
        cfg = self.app.config  # type: ignore[attr-defined]
        outdir = self.query_one("#opt-outdir", Input).value.strip()
        if not outdir:
            outdir = cfg.download_dir
        outdir = str(Path(outdir).expanduser())

        try:
            Path(outdir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.query_one("#opt-error", Label).update(
                f"Cannot use that directory: {exc}"
            )
            return None

        template = self.query_one("#opt-template", Input).value.strip() or cfg.filename_template
        thumb = self.query_one("#opt-thumb", Checkbox).value
        embed_meta = self.query_one("#opt-meta", Checkbox).value
        audio_only = self.query_one("#opt-audio-only", Checkbox).value

        embed_subs = False
        sub_langs: list[str] = []
        if self.meta.has_subtitles:
            embed_subs = self.query_one("#opt-subs", Checkbox).value
            if embed_subs:
                try:
                    lang = self.query_one("#opt-sublang", Select).value
                    if lang and lang != Select.BLANK:
                        sub_langs = [str(lang)]
                except Exception:
                    sub_langs = [cfg.default_subtitle_lang]

        audio_format = cfg.audio_format
        try:
            af = self.query_one("#opt-aformat", Select).value
            if af and af != Select.BLANK:
                audio_format = str(af)
        except Exception:
            pass

        custom = self.query_one("#opt-custom-fmt", Input).value.strip() or None
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
            extract_audio=audio_only,
            audio_format=audio_format,
            custom_format=custom,
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

    @on(Button.Pressed, "#btn-download")
    def on_download(self) -> None:
        self.action_start_download()

    def action_start_download(self) -> None:
        opts = self._build_options()
        if opts is None:
            return
        item = self._make_item(opts)
        app = self.app
        app.queue.add(item)  # type: ignore[attr-defined]
        # Start only the newly added item, not all queued items
        app.manager.start(item.id)  # type: ignore[attr-defined]
        app.refresh_status_bar()  # type: ignore[attr-defined]

        # Enqueue remaining batch URLs with same options (best effort async)
        if self.remaining_urls:
            self._enqueue_remaining(list(self.remaining_urls), opts)

        from yank.screens.download import DownloadScreen

        self.app.push_screen(DownloadScreen(focus_id=item.id))

    @on(Button.Pressed, "#btn-queue-only")
    def on_queue_only(self) -> None:
        opts = self._build_options()
        if opts is None:
            return
        item = self._make_item(opts)
        self.app.queue.add(item)  # type: ignore[attr-defined]
        self.app.refresh_status_bar()  # type: ignore[attr-defined]
        if self.remaining_urls:
            self._enqueue_remaining(list(self.remaining_urls), opts)
        self.notify(f"Added to queue: {item.title[:40]}", severity="information")
        from yank.screens.queue import QueueScreen

        self.app.push_screen(QueueScreen())

    @work(thread=True)
    def _enqueue_remaining(self, urls: list[str], opts: DownloadOptions) -> None:
        from yank.engine.formats import FormatExtractError, extract_formats, pick_best_format

        for url in urls:
            try:
                meta = extract_formats(url, timeout=30)
                if not meta.formats:
                    self.app.call_from_thread(
                        self.notify, f"Batch skip: No formats for {url[:40]}", severity="warning"
                    )
                    continue
                best = pick_best_format(meta.formats, "best")
                if best is None:
                    self.app.call_from_thread(
                        self.notify, f"Batch skip: No suitable format for {url[:40]}", severity="warning"
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
                    extract_audio=opts.extract_audio,
                    audio_format=opts.audio_format,
                    custom_format=opts.custom_format,
                )
                item = DownloadItem.create(
                    url=url,
                    title=meta.title,
                    format_id=best.format_id,
                    options=item_opts,
                    meta=meta,
                    selected_format=best,
                )

                def _add(it=item):
                    self.app.queue.add(it)  # type: ignore[attr-defined]
                    self.app.refresh_status_bar()  # type: ignore[attr-defined]

                self.app.call_from_thread(_add)
            except FormatExtractError as exc:
                self.app.call_from_thread(
                    self.notify, f"Batch skip: {exc.message}", severity="warning"
                )
            except Exception as exc:
                from yank.engine.formats import _humanize_ytdlp_error
                self.app.call_from_thread(
                    self.notify, f"Batch skip: {_humanize_ytdlp_error(str(exc))}", severity="warning"
                )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.action_go_back()
