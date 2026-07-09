"""Format fetching and parsing via yt-dlp as a library."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


# ── Platform detection ──────────────────────────────────────────────────────

_PLATFORM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("YouTube", re.compile(r"(?:youtube\.com|youtu\.be|youtube-nocookie\.com)", re.I)),
    ("TikTok", re.compile(r"(?:tiktok\.com|vm\.tiktok\.com)", re.I)),
    ("Twitter/X", re.compile(r"(?:twitter\.com|x\.com|t\.co)", re.I)),
    ("Instagram", re.compile(r"(?:instagram\.com|instagr\.am)", re.I)),
    ("Vimeo", re.compile(r"vimeo\.com", re.I)),
    ("Reddit", re.compile(r"(?:reddit\.com|redd\.it|v\.redd\.it)", re.I)),
    ("Twitch", re.compile(r"(?:twitch\.tv|clips\.twitch\.tv)", re.I)),
    ("Facebook", re.compile(r"(?:facebook\.com|fb\.watch|fb\.com)", re.I)),
    ("SoundCloud", re.compile(r"soundcloud\.com", re.I)),
    ("Bandcamp", re.compile(r"bandcamp\.com", re.I)),
    ("Dailymotion", re.compile(r"dailymotion\.com", re.I)),
    ("Bilibili", re.compile(r"bilibili\.com", re.I)),
    ("Niconico", re.compile(r"nicovideo\.jp", re.I)),
]


def detect_platform(url: str) -> str:
    """Return a human-readable platform name from a URL, or 'Unknown'."""
    url = url.strip()
    if not url:
        return "Unknown"
    for name, pattern in _PLATFORM_PATTERNS:
        if pattern.search(url):
            return name
    # Fall back to hostname
    try:
        host = urlparse(url).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        if host:
            return host.split(".")[0].title()
    except Exception:
        pass
    return "Unknown"


def is_valid_url(url: str) -> bool:
    """Basic URL sanity check."""
    url = url.strip()
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


# ── Data classes ────────────────────────────────────────────────────────────


@dataclass
class FormatInfo:
    """A single downloadable format."""

    format_id: str
    ext: str
    resolution: str
    filesize: int | None  # bytes, or None if unknown
    vcodec: str
    acodec: str
    note: str
    fps: float | None = None
    tbr: float | None = None  # total bitrate kbps
    abr: float | None = None
    vbr: float | None = None
    protocol: str = ""
    format_note: str = ""
    is_audio_only: bool = False
    is_video_only: bool = False
    is_combined: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def filesize_display(self) -> str:
        if self.filesize is None or self.filesize <= 0:
            # Estimate from bitrate if available
            return "?"
        return _human_size(self.filesize)

    @property
    def kind_label(self) -> str:
        if self.is_audio_only:
            return "audio"
        if self.is_video_only:
            return "video"
        if self.is_combined:
            return "av"
        return ""

    @property
    def codec_display(self) -> str:
        parts = []
        if self.vcodec and self.vcodec != "none":
            parts.append(self.vcodec.split(".")[0])
        if self.acodec and self.acodec != "none":
            parts.append(self.acodec.split(".")[0])
        return "+".join(parts) if parts else "—"


@dataclass
class VideoMeta:
    """Metadata about a video/media item."""

    url: str
    title: str = "Unknown"
    duration: float | None = None  # seconds
    uploader: str = ""
    upload_date: str = ""  # YYYYMMDD
    description: str = ""
    thumbnail: str = ""
    webpage_url: str = ""
    extractor: str = ""
    view_count: int | None = None
    like_count: int | None = None
    formats: list[FormatInfo] = field(default_factory=list)
    subtitles: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    automatic_captions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    platform: str = ""

    @property
    def has_subtitles(self) -> bool:
        return bool(self.subtitles) or bool(self.automatic_captions)

    @property
    def available_subtitle_langs(self) -> list[str]:
        langs = set(self.subtitles.keys()) | set(self.automatic_captions.keys())
        return sorted(langs)

    @property
    def duration_display(self) -> str:
        if self.duration is None:
            return "—"
        total = int(self.duration)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @property
    def upload_date_display(self) -> str:
        d = self.upload_date
        if len(d) == 8 and d.isdigit():
            return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
        return d or "—"


# ── Helpers ─────────────────────────────────────────────────────────────────


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        n_f = n / 1024.0
        if n_f < 1024:
            return f"{n_f:.1f} {unit}"
        n = int(n_f)
    return f"{n} PiB"


def _parse_format(f: dict[str, Any]) -> FormatInfo:
    vcodec = f.get("vcodec") or "none"
    acodec = f.get("acodec") or "none"
    has_video = vcodec != "none"
    has_audio = acodec != "none"

    resolution = f.get("resolution") or ""
    if not resolution:
        height = f.get("height")
        width = f.get("width")
        if height and width:
            resolution = f"{width}x{height}"
        elif height:
            resolution = f"{height}p"
        elif has_audio and not has_video:
            resolution = "audio only"
        else:
            resolution = "—"

    filesize = f.get("filesize") or f.get("filesize_approx")
    if filesize is not None:
        try:
            filesize = int(filesize)
        except (TypeError, ValueError):
            filesize = None

    note_parts: list[str] = []
    if f.get("format_note"):
        note_parts.append(str(f["format_note"]))
    if f.get("protocol") and f["protocol"] not in ("https", "http"):
        note_parts.append(str(f["protocol"]))

    return FormatInfo(
        format_id=str(f.get("format_id", "")),
        ext=str(f.get("ext", "")),
        resolution=resolution,
        filesize=filesize,
        vcodec=vcodec,
        acodec=acodec,
        note=" · ".join(note_parts),
        fps=f.get("fps"),
        tbr=f.get("tbr"),
        abr=f.get("abr"),
        vbr=f.get("vbr"),
        protocol=str(f.get("protocol") or ""),
        format_note=str(f.get("format_note") or ""),
        is_audio_only=has_audio and not has_video,
        is_video_only=has_video and not has_audio,
        is_combined=has_video and has_audio,
        raw=f,
    )


def _sort_key(fmt: FormatInfo) -> tuple:
    """Sort: combined first, then by resolution height desc, then bitrate."""
    height = 0
    m = re.search(r"(\d+)p", fmt.resolution)
    if m:
        height = int(m.group(1))
    else:
        m2 = re.search(r"x(\d+)", fmt.resolution)
        if m2:
            height = int(m2.group(1))

    kind = 0 if fmt.is_combined else (1 if fmt.is_video_only else 2)
    tbr = fmt.tbr or 0
    return (kind, -height, -(tbr or 0))


# ── Public API ──────────────────────────────────────────────────────────────


class FormatExtractError(Exception):
    """Human-readable format extraction failure."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def extract_formats(url: str, *, timeout: int = 60) -> VideoMeta:
    """
    Fetch available formats for *url* using yt-dlp as a library.

    Raises FormatExtractError with a human-readable message on failure.
    """
    url = url.strip()
    if not is_valid_url(url):
        raise FormatExtractError(
            "That doesn't look like a valid URL. "
            "Paste a full link starting with https://"
        )

    try:
        import yt_dlp
    except ImportError as exc:
        raise FormatExtractError(
            "yt-dlp is not installed. Open Settings to install it."
        ) from exc

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "socket_timeout": timeout,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        msg = _humanize_ytdlp_error(str(exc))
        raise FormatExtractError(msg) from exc
    except Exception as exc:  # network, DNS, etc.
        msg = _humanize_ytdlp_error(str(exc))
        raise FormatExtractError(msg) from exc

    if info is None:
        raise FormatExtractError("Could not extract video info from that URL.")

    # Playlist / multi-entry: take first entry if present
    if info.get("_type") == "playlist" and info.get("entries"):
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise FormatExtractError("Playlist is empty or unavailable.")
        info = entries[0]

    raw_formats = info.get("formats") or []
    formats = [_parse_format(f) for f in raw_formats if f.get("format_id")]
    # Filter out storyboard / image-only formats that aren't useful
    formats = [
        f
        for f in formats
        if f.ext not in ("mhtml", "sb")
        and not (f.vcodec == "none" and f.acodec == "none")
    ]
    formats.sort(key=_sort_key)

    meta = VideoMeta(
        url=url,
        title=str(info.get("title") or "Unknown"),
        duration=info.get("duration"),
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        upload_date=str(info.get("upload_date") or ""),
        description=str(info.get("description") or "")[:500],
        thumbnail=str(info.get("thumbnail") or ""),
        webpage_url=str(info.get("webpage_url") or url),
        extractor=str(info.get("extractor") or info.get("extractor_key") or ""),
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        formats=formats,
        subtitles=dict(info.get("subtitles") or {}),
        automatic_captions=dict(info.get("automatic_captions") or {}),
        platform=detect_platform(url),
    )
    return meta


def pick_best_format(
    formats: list[FormatInfo],
    preference: str = "best",
) -> FormatInfo | None:
    """
    Pre-select the best format based on preference.

    - best: best combined, or best video+audio merge candidate
    - best_video_audio: prefer separate video+audio (highest video)
    - audio_only: best audio-only format
    """
    if not formats:
        return None

    if preference == "audio_only":
        audio = [f for f in formats if f.is_audio_only]
        if not audio:
            # Fall back to any with audio
            audio = [f for f in formats if f.acodec and f.acodec != "none"]
        if not audio:
            return formats[0]
        # Prefer higher abr / tbr
        audio.sort(key=lambda f: -(f.abr or f.tbr or 0))
        return audio[0]

    combined = [f for f in formats if f.is_combined]
    video_only = [f for f in formats if f.is_video_only]

    if preference == "best_video_audio" and video_only:
        video_only.sort(key=_sort_key)
        return video_only[0]

    if combined:
        combined.sort(key=_sort_key)
        return combined[0]

    if video_only:
        video_only.sort(key=_sort_key)
        return video_only[0]

    return formats[0]


def format_selector_for(
    fmt: FormatInfo,
    *,
    audio_only: bool = False,
    custom: str | None = None,
) -> str:
    """Build a yt-dlp format selector string."""
    if custom and custom.strip():
        return custom.strip()
    if audio_only or fmt.is_audio_only:
        return f"{fmt.format_id}/bestaudio/best"
    if fmt.is_combined:
        return fmt.format_id
    if fmt.is_video_only:
        # Merge with best audio
        return f"{fmt.format_id}+bestaudio/best"
    return fmt.format_id or "best"


def _humanize_ytdlp_error(raw: str) -> str:
    """Convert yt-dlp exception text into a short human message."""
    lower = raw.lower()
    # Strip ERROR: prefix and long traces
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    short = lines[0] if lines else raw
    short = re.sub(r"^ERROR:\s*", "", short, flags=re.I)

    if "unable to download" in lower and "webpage" in lower:
        return "Could not reach that page. Check the URL and your internet connection."
    if "http error 404" in lower or "not found" in lower:
        return "Video not found (404). It may have been deleted or made private."
    if "http error 403" in lower or "forbidden" in lower:
        return "Access forbidden (403). The video may be region-locked or restricted."
    if "private video" in lower or "login required" in lower or "sign in" in lower:
        return "This video is private or requires login."
    if "unsupported url" in lower:
        return "This URL is not supported by yt-dlp."
    if "timed out" in lower or "timeout" in lower:
        return "Connection timed out. Check your internet and try again."
    if "name or service not known" in lower or "nodename" in lower or "dns" in lower:
        return "No internet connection or DNS failed."
    if "ssl" in lower or "certificate" in lower:
        return "SSL/certificate error while connecting."
    if "is not a valid url" in lower:
        return "Invalid URL."
    # Cap length
    if len(short) > 200:
        short = short[:197] + "..."
    return short or "Failed to fetch video info."
