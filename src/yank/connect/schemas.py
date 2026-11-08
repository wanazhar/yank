"""Pydantic models for Connect API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DownloadOptionsIn(BaseModel):
    """Per-job overrides (same fields as TUI options screen)."""

    filename_template: str | None = None
    download_thumbnail: bool | None = None
    embed_metadata: bool | None = None
    embed_subtitles: bool | None = None
    write_subtitles_file: bool | None = None
    subtitle_langs: list[str] | None = None
    subtitle_format: str | None = None
    custom_format: str | None = None
    proxy: str | None = None
    rate_limit: str | None = None
    playlist_items: str | None = None
    sponsorblock_remove: str | None = None
    download_sections: str | None = None
    audio_normalize: bool | None = None
    split_chapters: bool | None = None
    meta_title: str | None = None
    meta_artist: str | None = None
    tag: str | None = None


class EnqueueBody(BaseModel):
    url: str
    format_id: str | None = None
    extract_audio: bool = False
    audio_format: str | None = None
    auto_start: bool = True
    schedule_minutes: float = 0
    note: str = ""
    options: DownloadOptionsIn | None = None


class BatchEnqueueBody(BaseModel):
    urls: list[str] = Field(min_length=1)
    format_id: str | None = None
    extract_audio: bool = False
    audio_format: str | None = None
    auto_start: bool = True
    schedule_minutes: float = 0
    note: str = ""
    options: DownloadOptionsIn | None = None


class ExtractBody(BaseModel):
    url: str
    playlist: bool = False


class ConfigPatch(BaseModel):
    format_preference: str | None = None
    max_concurrent: int | None = None
    filename_template: str | None = None
    default_subtitle_lang: str | None = None
    embed_metadata: bool | None = None
    embed_subtitles: bool | None = None
    download_thumbnail: bool | None = None
    audio_format: str | None = None
    subtitle_format: str | None = None
    proxy: str | None = None
    rate_limit: str | None = None
    playlist_items: str | None = None
    sponsorblock_remove: str | None = None
    split_chapters: bool | None = None
    audio_normalize: bool | None = None
    download_playlist: bool | None = None
    language: str | None = None


class SessionCookiesBody(BaseModel):
    netscape: str
