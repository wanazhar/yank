"""Build DownloadOptions for Connect jobs from API payloads."""

from __future__ import annotations

from typing import Any

from yank.engine.downloader import DownloadOptions
from yank.engine.formats import FormatInfo, format_selector_for
from yank.models.config import AppConfig


def build_download_options(
    config: AppConfig,
    *,
    staging_dir: str,
    format_info: FormatInfo,
    extract_audio: bool = False,
    audio_format: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> DownloadOptions:
    ov = overrides or {}
    audio_only = extract_audio or format_info.is_audio_only
    selector = format_selector_for(format_info, audio_only=audio_only)
    return DownloadOptions(
        output_dir=staging_dir,
        filename_template=str(ov.get("filename_template") or config.filename_template),
        format_selector=selector,
        download_thumbnail=bool(ov.get("download_thumbnail", config.download_thumbnail)),
        embed_metadata=bool(ov.get("embed_metadata", config.embed_metadata)),
        embed_subtitles=bool(ov.get("embed_subtitles", config.embed_subtitles)),
        subtitle_langs=list(ov.get("subtitle_langs") or [config.default_subtitle_lang]),
        write_subtitles_file=bool(ov.get("write_subtitles_file", False)),
        subtitle_format=str(ov.get("subtitle_format") or config.subtitle_format),
        extract_audio=audio_only,
        audio_format=str(audio_format or ov.get("audio_format") or config.audio_format),
        custom_format=ov.get("custom_format"),
        proxy=str(ov.get("proxy") or config.proxy),
        rate_limit=str(ov.get("rate_limit") or config.rate_limit),
        playlist_items=str(ov.get("playlist_items") or config.playlist_items),
        sponsorblock_remove=str(ov.get("sponsorblock_remove") or config.sponsorblock_remove),
        audio_normalize=bool(ov.get("audio_normalize", config.audio_normalize)),
        split_chapters=bool(ov.get("split_chapters", config.split_chapters)),
        download_sections=str(ov.get("download_sections") or config.download_sections),
        meta_title=str(ov.get("meta_title") or ""),
        meta_artist=str(ov.get("meta_artist") or ""),
        note=str(ov.get("note") or ""),
        tag=str(ov.get("tag") or ""),
        cookiefile=str(ov["cookiefile"]) if ov.get("cookiefile") else None,
    )
