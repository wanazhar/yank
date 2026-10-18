"""Download manager using yt-dlp YoutubeDL with progress hooks."""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from yank.constants import ERROR_MSG_MAX_LEN
from yank.engine.formats import FormatInfo, VideoMeta, format_selector_for
from yank.logging import get_logger
from yank.models.config import AppConfig

_logger = get_logger(__name__)


class DownloadStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class DownloadProgress:
    """Live progress snapshot for one download."""

    percent: float = 0.0
    speed: float = 0.0  # bytes/sec
    eta: float | None = None  # seconds
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    filename: str = ""
    status_text: str = ""

    @property
    def speed_display(self) -> str:
        if self.speed <= 0:
            return "—"
        return _human_rate(self.speed)

    @property
    def eta_display(self) -> str:
        if self.eta is None or self.eta < 0:
            return "—"
        total = int(self.eta)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h{m:02d}m"
        if m:
            return f"{m}m{s:02d}s"
        return f"{s}s"

    @property
    def percent_display(self) -> str:
        return f"{self.percent:.1f}%"

    @property
    def speed_mbps(self) -> float | None:
        """Speed in MB/s for color coding."""
        if self.speed <= 0:
            return None
        return self.speed / (1024 * 1024)


@dataclass
class DownloadOptions:
    """Per-download options chosen on the options screen."""

    output_dir: str = ""
    filename_template: str = "%(title)s.%(ext)s"
    format_selector: str = "best"
    download_thumbnail: bool = False
    embed_metadata: bool = True
    embed_subtitles: bool = False
    subtitle_langs: list[str] = field(default_factory=list)
    write_subtitles_file: bool = False
    subtitle_format: str = "srt"
    extract_audio: bool = False
    audio_format: str = "mp3"
    custom_format: str | None = None
    proxy: str = ""
    rate_limit: str = ""
    playlist_items: str = ""
    sponsorblock_remove: str = ""


@dataclass
class DownloadItem:
    """One download job."""

    id: str
    url: str
    title: str
    format_id: str
    options: DownloadOptions
    status: DownloadStatus = DownloadStatus.PENDING
    progress: DownloadProgress = field(default_factory=DownloadProgress)
    error: str = ""
    file_path: str = ""
    meta: VideoMeta | None = None
    selected_format: FormatInfo | None = None
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        url: str,
        title: str,
        format_id: str,
        options: DownloadOptions,
        *,
        meta: VideoMeta | None = None,
        selected_format: FormatInfo | None = None,
    ) -> DownloadItem:
        return cls(
            id=uuid.uuid4().hex[:12],
            url=url,
            title=title or "Unknown",
            format_id=format_id,
            options=options,
            meta=meta,
            selected_format=selected_format,
        )


ProgressCallback = Callable[[DownloadItem], None]
FinishedCallback = Callable[[DownloadItem], None]


class DownloadManager:
    """
    Manages concurrent yt-dlp downloads with progress hooks.

    Pause is cooperative (cancel + mark paused for re-queue).
    Cancel aborts the active download.
    """

    def __init__(
        self,
        config: AppConfig,
        *,
        on_progress: ProgressCallback | None = None,
        on_finished: FinishedCallback | None = None,
    ) -> None:
        self.config = config
        self.on_progress = on_progress
        self.on_finished = on_finished
        self._items: dict[str, DownloadItem] = {}
        self._lock = threading.Lock()
        self._cancel_flags: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._ydl_instances: dict[str, Any] = {}

    # ── Query ───────────────────────────────────────────────────────────────

    def get(self, item_id: str) -> DownloadItem | None:
        with self._lock:
            return self._items.get(item_id)

    def all_items(self) -> list[DownloadItem]:
        with self._lock:
            return list(self._items.values())

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for i in self._items.values() if i.status == DownloadStatus.DOWNLOADING)

    def register(self, item: DownloadItem) -> DownloadItem:
        with self._lock:
            self._items[item.id] = item
            self._cancel_flags[item.id] = threading.Event()
        return item

    # ── Control ─────────────────────────────────────────────────────────────

    def start(self, item_id: str) -> None:
        """Start (or resume) a download in a background thread."""
        item = self.get(item_id)
        if item is None:
            return

        with self._lock:
            # Guard: don't restart terminal items
            if item.status in (
                DownloadStatus.CANCELLED,
                DownloadStatus.COMPLETED,
                DownloadStatus.ERROR,
            ):
                return
            if item.status == DownloadStatus.DOWNLOADING:
                return

            # Enforce concurrency limit (inline — lock already held)
            active = sum(1 for i in self._items.values() if i.status == DownloadStatus.DOWNLOADING)
            if active >= self.config.max_concurrent:
                item.status = DownloadStatus.QUEUED
                queued = True
            else:
                cancel_flag = self._cancel_flags.setdefault(item_id, threading.Event())
                cancel_flag.clear()
                item.status = DownloadStatus.DOWNLOADING
                item.error = ""
                queued = False

        if queued:
            self._notify_progress(item)
            return

        self._notify_progress(item)

        t = threading.Thread(
            target=self._run_download,
            args=(item_id,),
            name=f"yank-dl-{item_id}",
            daemon=True,
        )
        with self._lock:
            self._threads[item_id] = t
        t.start()

    def cancel(self, item_id: str, *, _pump: bool = True) -> None:
        item = self.get(item_id)
        if item is None:
            return
        with self._lock:
            flag = self._cancel_flags.get(item_id)
            if flag:
                flag.set()
            if item.status in (
                DownloadStatus.DOWNLOADING,
                DownloadStatus.QUEUED,
                DownloadStatus.PENDING,
                DownloadStatus.PAUSED,
            ):
                item.status = DownloadStatus.CANCELLED
                item.progress.status_text = "Cancelled"
                cancelled = True
            else:
                cancelled = False
        if cancelled:
            self._notify_progress(item)
            self._notify_finished(item)
            if _pump:
                self._pump_queue()

    def pause(self, item_id: str, *, _pump: bool = True) -> None:
        """Cooperative pause: cancel current transfer, mark as paused."""
        item = self.get(item_id)
        if item is None:
            return
        notify = False
        should_pump = False
        with self._lock:
            if item.status != DownloadStatus.DOWNLOADING:
                if item.status == DownloadStatus.QUEUED:
                    item.status = DownloadStatus.PAUSED
                    notify = True
                return
            flag = self._cancel_flags.get(item_id)
            if flag:
                flag.set()
            item.status = DownloadStatus.PAUSED
            item.progress.status_text = "Paused"
            notify = True
            should_pump = True
        if notify:
            self._notify_progress(item)
        if should_pump and _pump:
            self._pump_queue()

    def start_queued(self) -> None:
        """Start as many queued items as concurrency allows."""
        self._pump_queue()

    def retry(self, item_id: str) -> None:
        """Reset a failed/cancelled item and restart it."""
        item = self.get(item_id)
        if item is None:
            return
        with self._lock:
            if item.status not in (DownloadStatus.ERROR, DownloadStatus.CANCELLED):
                return
            item.status = DownloadStatus.PENDING
            item.error = ""
            item.progress = DownloadProgress()
            flag = self._cancel_flags.setdefault(item_id, threading.Event())
            flag.clear()
        self.start(item_id)

    def pause_all(self) -> None:
        for item in self.all_items():
            if item.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED):
                self.pause(item.id, _pump=False)

    def cancel_all(self) -> None:
        for item in self.all_items():
            if item.status not in (
                DownloadStatus.COMPLETED,
                DownloadStatus.CANCELLED,
                DownloadStatus.ERROR,
            ):
                self.cancel(item.id, _pump=False)
        self._pump_queue()

    # ── Internals ───────────────────────────────────────────────────────────

    def _pump_queue(self) -> None:
        """Start queued items up to max_concurrent."""
        with self._lock:
            active = sum(1 for i in self._items.values() if i.status == DownloadStatus.DOWNLOADING)
            slots = max(0, self.config.max_concurrent - active)
            queued = [i for i in self._items.values() if i.status == DownloadStatus.QUEUED]
            queued.sort(key=lambda x: x.created_at)
            to_start = [i.id for i in queued[:slots]]

        for item_id in to_start:
            self.start(item_id)

    def _run_download(self, item_id: str) -> None:
        item = self.get(item_id)
        if item is None:
            return

        with self._lock:
            cancel_flag = self._cancel_flags.get(item_id)
        if cancel_flag is None:
            with self._lock:
                item.status = DownloadStatus.ERROR
                item.error = "Internal error: download state lost."
            self._notify_progress(item)
            self._notify_finished(item)
            self._pump_queue()
            return

        opts = item.options
        out_dir = Path(opts.output_dir or self.config.download_dir).expanduser()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            with self._lock:
                item.status = DownloadStatus.ERROR
                item.error = f"Cannot create download directory: {exc}"
            self._notify_progress(item)
            self._notify_finished(item)
            self._pump_queue()
            return

        fmt_selector = opts.format_selector
        if opts.custom_format:
            fmt_selector = opts.custom_format
        elif item.selected_format:
            fmt_selector = format_selector_for(
                item.selected_format,
                audio_only=opts.extract_audio,
                custom=opts.custom_format,
            )

        outtmpl = str(out_dir / (opts.filename_template or "%(title)s.%(ext)s"))

        ydl_opts: dict[str, Any] = {
            "format": fmt_selector,
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [lambda d: self._progress_hook(item_id, d, cancel_flag)],
            "noplaylist": True,
        }

        # Proxy support — per-download option overrides config default
        config_proxy = getattr(self.config, "proxy", "") or ""
        proxy_url = opts.proxy or config_proxy
        if proxy_url and str(proxy_url).strip():
            ydl_opts["proxy"] = str(proxy_url).strip()

        # Cookies
        cookies_browser = getattr(self.config, "cookies_browser", "") or ""
        cookies_file = getattr(self.config, "cookies_file", "") or ""
        if cookies_browser.strip():
            ydl_opts["cookiesfrombrowser"] = (cookies_browser.strip(),)
        elif cookies_file.strip():
            ydl_opts["cookiefile"] = cookies_file.strip()

        # Rate limit
        rate_limit = opts.rate_limit or getattr(self.config, "rate_limit", "") or ""
        if rate_limit.strip():
            ydl_opts["limit_rate"] = rate_limit.strip()

        # Download archive
        archive = getattr(self.config, "download_archive", "") or ""
        if archive.strip():
            ydl_opts["download_archive"] = archive.strip()

        # Retries
        retries = getattr(self.config, "retry_count", 0)
        if retries:
            ydl_opts["retries"] = retries
            ydl_opts["fragment_retries"] = retries

        # Playlist items range
        pl_items = opts.playlist_items or getattr(self.config, "playlist_items", "") or ""
        if pl_items.strip():
            ydl_opts["playlist_items"] = pl_items.strip()

        # SponsorBlock removal
        sb = opts.sponsorblock_remove or getattr(self.config, "sponsorblock_remove", "") or ""
        if sb.strip():
            ydl_opts["sponsorblock_remove"] = [x.strip() for x in sb.split(",") if x.strip()]

        postprocessors: list[dict[str, Any]] = []

        if opts.extract_audio:
            if opts.custom_format:
                ydl_opts["format"] = opts.custom_format
            elif item.selected_format is not None and item.selected_format.is_audio_only:
                ydl_opts["format"] = item.selected_format.format_id
            else:
                ydl_opts["format"] = "bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": opts.audio_format or "mp3",
                    "preferredquality": "192",
                }
            )

        if opts.embed_metadata:
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

        if opts.download_thumbnail:
            ydl_opts["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

        # Subtitle handling: sidecar file and/or embed
        if opts.write_subtitles_file or opts.embed_subtitles:
            ydl_opts["writesubtitles"] = True
            langs = opts.subtitle_langs if opts.subtitle_langs else ["en"]
            ydl_opts["subtitleslangs"] = langs
            ydl_opts["subtitlesformat"] = opts.subtitle_format or "srt"
            if opts.embed_subtitles:
                postprocessors.append({"key": "FFmpegEmbedSubtitle"})

        if postprocessors:
            ydl_opts["postprocessors"] = postprocessors

        try:
            import yt_dlp
        except ImportError:
            with self._lock:
                item.status = DownloadStatus.ERROR
                item.error = "yt-dlp is not installed."
            self._notify_progress(item)
            self._notify_finished(item)
            self._pump_queue()
            return

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                with self._lock:
                    self._ydl_instances[item_id] = ydl
                    if cancel_flag.is_set():
                        if item.status != DownloadStatus.PAUSED:
                            item.status = DownloadStatus.CANCELLED
                if cancel_flag.is_set():
                    return

                info = ydl.extract_info(item.url, download=True)

                with self._lock:
                    if cancel_flag.is_set():
                        if item.status == DownloadStatus.PAUSED:
                            return
                        item.status = DownloadStatus.CANCELLED
                        item.progress.status_text = "Cancelled"
                if cancel_flag.is_set():
                    return

                # Resolve final filepath
                file_path = ""
                if info:
                    if info.get("requested_downloads"):
                        file_path = info["requested_downloads"][0].get("filepath", "")
                    file_path = file_path or info.get("_filename") or info.get("filename") or ""
                    if not file_path and info.get("title"):
                        ext = info.get("ext") or "mp4"
                        file_path = str(out_dir / f"{info['title']}.{ext}")

                with self._lock:
                    item.file_path = file_path or item.progress.filename
                    item.status = DownloadStatus.COMPLETED
                    item.progress.percent = 100.0
                    item.progress.status_text = "Done"
                    item.title = (info or {}).get("title") or item.title
        except _CancelDownload:
            with self._lock:
                if item.status != DownloadStatus.PAUSED:
                    item.status = DownloadStatus.CANCELLED
                    item.progress.status_text = "Cancelled"
        except Exception as exc:
            with self._lock:
                if item.status != DownloadStatus.PAUSED:
                    if cancel_flag.is_set():
                        item.status = DownloadStatus.CANCELLED
                        item.progress.status_text = "Cancelled"
                    else:
                        item.status = DownloadStatus.ERROR
                        item.error = _humanize_download_error(str(exc))
                        item.progress.status_text = "Error"
        finally:
            with self._lock:
                self._ydl_instances.pop(item_id, None)
                self._cancel_flags.pop(item_id, None)
                self._threads.pop(item_id, None)
            self._notify_progress(item)
            if item.status not in (DownloadStatus.PAUSED, DownloadStatus.CANCELLED):
                self._notify_finished(item)
                self._pump_queue()

    def _progress_hook(
        self,
        item_id: str,
        d: dict[str, Any],
        cancel_flag: threading.Event,
    ) -> None:
        if cancel_flag.is_set():
            raise _CancelDownload()

        item = self.get(item_id)
        if item is None:
            raise _CancelDownload()

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed") or 0
            eta = d.get("eta")
            percent = 0.0
            if total and total > 0:
                percent = (downloaded / total) * 100.0
            elif d.get("_percent_str"):
                try:
                    percent = float(str(d["_percent_str"]).replace("%", "").strip())
                except ValueError:
                    with self._lock:
                        percent = item.progress.percent

            filename = d.get("filename") or d.get("tmpfilename") or ""
            with self._lock:
                item.progress = DownloadProgress(
                    percent=percent,
                    speed=float(speed or 0),
                    eta=float(eta) if eta is not None else None,
                    downloaded_bytes=int(downloaded),
                    total_bytes=int(total) if total else None,
                    filename=str(filename),
                    status_text="Downloading",
                )
                if filename:
                    item.file_path = str(filename)
            self._notify_progress(item)

        elif status == "finished":
            filename = d.get("filename") or ""
            with self._lock:
                item.progress.percent = 100.0
                item.progress.speed = 0
                item.progress.eta = 0
                item.progress.status_text = "Processing"
                if filename:
                    item.progress.filename = str(filename)
                    item.file_path = str(filename)
            self._notify_progress(item)

        elif status == "error":
            with self._lock:
                item.status = DownloadStatus.ERROR
                item.error = "Download failed."
                item.progress.status_text = "Error"
            self._notify_progress(item)

    def _notify_progress(self, item: DownloadItem) -> None:
        if self.on_progress:
            try:
                self.on_progress(item)
            except Exception:
                _logger.debug("on_progress callback failed for %s", item.id, exc_info=True)

    def _notify_finished(self, item: DownloadItem) -> None:
        if self.on_finished:
            try:
                self.on_finished(item)
            except Exception:
                _logger.debug("on_finished callback failed for %s", item.id, exc_info=True)


class _CancelDownload(Exception):
    """Raised from progress hook to abort a download."""


def _human_rate(bps: float) -> str:
    if bps < 1024:
        return f"{bps:.0f} B/s"
    for unit in ("KiB/s", "MiB/s", "GiB/s"):
        bps /= 1024.0
        if bps < 1024:
            return f"{bps:.1f} {unit}"
    return f"{bps:.1f} TiB/s"


def _humanize_download_error(raw: str) -> str:
    """Convert a raw download error into a concise human-readable message.

    Strips filesystem paths and other potentially sensitive information.
    """
    lower = raw.lower()
    if "no space" in lower or "disk quota" in lower or "errno 28" in lower:
        return "Disk full — free up space and try again."
    if "permission denied" in lower or "errno 13" in lower:
        return "Permission denied writing to the download directory."
    if "ffmpeg" in lower and ("not found" in lower or "not installed" in lower):
        return "ffmpeg is required for this format/option but was not found."
    if "timed out" in lower or "timeout" in lower:
        return "Download timed out. Check your connection."
    if "http error 403" in lower:
        return "Access forbidden while downloading."
    if "http error 404" in lower:
        return "File not found on server."
    # First line, strip ERROR: prefix
    line = raw.splitlines()[0] if raw else "Download failed."
    line = line.replace("ERROR:", "").strip()

    # --- Aggressive filesystem-path sanitization ---
    # Unix absolute paths: /home/user/..., /tmp/..., /var/..., /etc/..., /opt/...
    line = re.sub(
        r"(?:^|[\s'\"(])/(?:home|tmp|var|etc|opt|usr|mnt|media|run|srv|root)/[\S]*",
        " [path]",
        line,
    )
    # Other absolute paths starting with /
    line = re.sub(
        r"(?<!\w)/(?:[\w.-]+/)+[\w.-]+(?:\.\w{1,10})?",
        " [path]",
        line,
    )
    # Tilde-expanded paths: ~/Downloads/..., ~/.config/...
    line = re.sub(r"~/[\S]*", "[path]", line)
    # Windows paths: C:\..., D:\..., etc.
    line = re.sub(
        r"[A-Za-z]:\\(?:[\w\s.-]+\\)*[\w\s.-]+(?:\.\w{1,10})?",
        "[path]",
        line,
    )
    # Quoted paths that escaped previous patterns
    line = re.sub(r"'[/~][^']*'", "'[path]'", line)
    line = re.sub(r'"[/~][^"]*"', '"[path]"', line)

    # Collapse multiple consecutive [path] tokens
    line = re.sub(r"(?:\[path\]\s*){2,}", "[path] ", line)

    if len(line) > ERROR_MSG_MAX_LEN:
        line = line[: ERROR_MSG_MAX_LEN - 3] + "..."
    return line.strip() or "Download failed."
