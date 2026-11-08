"""Serve completed downloads to the browser (stream / save) and optional server cleanup."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from yank.connect.paths import CONNECT_STAGING_DIR
from yank.connect.runtime import ConnectRuntime
from yank.engine.downloader import DownloadItem, DownloadStatus
from yank.logging import get_logger

_logger = get_logger(__name__)

_VIDEO_EXT = frozenset({".mp4", ".webm", ".mkv", ".mov", ".m4v"})
_AUDIO_EXT = frozenset({".mp3", ".m4a", ".opus", ".ogg", ".wav", ".flac", ".aac"})


def media_kind_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _VIDEO_EXT:
        return "video"
    if ext in _AUDIO_EXT:
        return "audio"
    return "file"


def resolve_completed_path(item: DownloadItem) -> Path:
    raw = (item.file_path or "").strip()
    if not raw:
        raise FileNotFoundError("No file path on item")
    path = Path(raw).resolve()
    staging = CONNECT_STAGING_DIR.resolve()
    if staging not in path.parents and path != staging:
        raise PermissionError("File is outside Connect staging")
    if not path.is_file():
        raise FileNotFoundError("File missing on server")
    return path


def guess_media_type(path: Path) -> str:
    media_type, _ = mimetypes.guess_type(path.name)
    return media_type or "application/octet-stream"


def purge_item_file(runtime: ConnectRuntime, item_id: str) -> None:
    """Remove staging copy after the client received the file."""
    item = runtime.manager.get(item_id)
    if item is None:
        return
    path = Path(item.file_path or "")
    if path.is_file():
        try:
            path.resolve().relative_to(CONNECT_STAGING_DIR.resolve())
        except ValueError:
            _logger.warning("Refusing to purge file outside Connect staging: %s", path)
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            _logger.debug("Failed to unlink staging file", exc_info=True)
    item.file_path = ""
    for qi in runtime.queue.get_items():
        if qi.id == item_id:
            qi.file_path = ""
    try:
        runtime.queue.save()
    except Exception:
        _logger.debug("queue save after purge failed", exc_info=True)


def delivery_meta(item: DownloadItem) -> dict[str, str | bool]:
    path = Path(item.file_path or "")
    kind = media_kind_for_path(path) if path.name else "file"
    ready = item.status == DownloadStatus.COMPLETED and path.is_file()
    return {
        "delivery": "client",
        "staging_only": True,
        "streamable": ready and kind in ("video", "audio"),
        "media_kind": kind,
    }
