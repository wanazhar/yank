"""JSON serializers for Connect API responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yank.connect.delivery import delivery_meta
from yank.engine.downloader import DownloadItem, DownloadStatus
from yank.engine.formats import FormatInfo, VideoMeta
from yank.engine.queue import QueueItem
from yank.models.config import AppConfig
from yank.models.history import HistoryEntry


def _format_json(fmt: FormatInfo) -> dict[str, Any]:
    return {
        "format_id": fmt.format_id,
        "ext": fmt.ext,
        "resolution": fmt.resolution,
        "filesize": fmt.filesize,
        "filesize_display": fmt.filesize_display,
        "vcodec": fmt.vcodec,
        "acodec": fmt.acodec,
        "note": fmt.note,
        "fps": fmt.fps,
        "kind": fmt.kind_label,
        "is_audio_only": fmt.is_audio_only,
        "is_video_only": fmt.is_video_only,
        "is_combined": fmt.is_combined,
    }


def video_meta_json(meta: VideoMeta) -> dict[str, Any]:
    return {
        "url": meta.url,
        "title": meta.title,
        "duration": meta.duration,
        "uploader": meta.uploader,
        "thumbnail": meta.thumbnail,
        "platform": meta.platform,
        "webpage_url": meta.webpage_url,
        "subtitle_langs": meta.available_subtitle_langs,
        "formats": [_format_json(f) for f in meta.formats],
    }


def download_item_json(item: DownloadItem) -> dict[str, Any]:
    prog = item.progress
    return {
        "id": item.id,
        "url": item.url,
        "title": item.title,
        "format_id": item.format_id,
        "status": item.status.value
        if isinstance(item.status, DownloadStatus)
        else str(item.status),
        "error": item.error,
        "file_path": item.file_path,
        "created_at": item.created_at,
        "progress": {
            "percent": prog.percent,
            "speed": prog.speed,
            "speed_display": prog.speed_display,
            "eta": prog.eta,
            "eta_display": prog.eta_display,
            "downloaded_bytes": prog.downloaded_bytes,
            "total_bytes": prog.total_bytes,
            "filename": prog.filename,
        },
        "downloadable": item.status == DownloadStatus.COMPLETED and bool(item.file_path),
        **delivery_meta(item),
        "filename": Path(item.file_path or "").name or prog.filename,
    }


def queue_item_json(qi: QueueItem, item: DownloadItem | None) -> dict[str, Any]:
    base = {
        "id": qi.id,
        "url": qi.url,
        "title": qi.title,
        "format_id": qi.format_id,
        "status": qi.status,
        "error": qi.error,
        "file_path": qi.file_path,
        "created_at": qi.created_at,
        "order": qi.order,
    }
    if item is not None:
        base.update(download_item_json(item))
    return base


def history_entry_json(entry: HistoryEntry) -> dict[str, Any]:
    return {
        "date": entry.date,
        "title": entry.title,
        "url": entry.url,
        "format_id": entry.format_id,
        "file_path": entry.file_path,
        "status": entry.status,
        "error": entry.error,
        "filesize": entry.filesize,
        "note": entry.note,
        "favorite": entry.favorite,
    }


def config_public_json(config: AppConfig) -> dict[str, Any]:
    return {
        "format_preference": config.format_preference,
        "max_concurrent": config.max_concurrent,
        "filename_template": config.filename_template,
        "extract_audio_default": config.format_preference == "audio_only",
        "audio_format": config.audio_format,
        "subtitle_format": config.subtitle_format,
        "embed_metadata": config.embed_metadata,
        "embed_subtitles": config.embed_subtitles,
        "default_subtitle_lang": config.default_subtitle_lang,
        "download_thumbnail": config.download_thumbnail,
        "download_playlist": config.download_playlist,
        "proxy": config.proxy,
        "rate_limit": config.rate_limit,
        "playlist_items": config.playlist_items,
        "sponsorblock_remove": config.sponsorblock_remove,
        "split_chapters": config.split_chapters,
        "audio_normalize": config.audio_normalize,
        "language": config.language,
    }


def queue_summary_json(runtime: Any) -> dict[str, Any]:
    from yank.engine.downloader import DownloadStatus

    items = runtime.queue.get_items()
    active = sum(1 for i in items if i.status == DownloadStatus.DOWNLOADING.value)
    return {
        "size": len(items),
        "active": active,
        "average_percent": runtime.queue.total_progress(),
    }
