"""Shared enqueue logic for Connect (single, batch, playlist)."""

from __future__ import annotations

import shutil
import time
from typing import Any

from yank.connect.cookies_util import with_session_cookies
from yank.connect.options import build_download_options
from yank.connect.runtime import ConnectRuntime
from yank.connect.schemas import BatchEnqueueBody, EnqueueBody
from yank.connect.serializers import download_item_json
from yank.engine.downloader import DownloadItem, DownloadStatus
from yank.engine.formats import (
    FormatExtractError,
    FormatInfo,
    VideoMeta,
    extract_formats,
    extract_playlist_entries,
    is_valid_url,
    pick_best_format,
)


def _overrides_from_body(
    body: EnqueueBody | BatchEnqueueBody,
    *,
    persistent_cookie: str | None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if body.note:
        overrides["note"] = body.note
    if persistent_cookie:
        overrides["cookiefile"] = persistent_cookie
    if body.options:
        overrides.update(body.options.model_dump(exclude_none=True))
    return overrides


def extract_meta(url: str, runtime: ConnectRuntime, subject: str) -> VideoMeta:
    def _inner(cookiefile: str | None) -> VideoMeta:
        return extract_formats(url, config=runtime.config, cookiefile=cookiefile)

    return with_session_cookies(runtime, subject, _inner)


def _pick_format(
    meta: VideoMeta,
    runtime: ConnectRuntime,
    format_id: str | None,
) -> FormatInfo:
    if format_id:
        fmt = next((f for f in meta.formats if f.format_id == format_id), None)
        if fmt is None:
            raise ValueError("Unknown format_id")
        return fmt
    best = pick_best_format(meta.formats, preference=runtime.config.format_preference)
    if best is None:
        raise ValueError("No formats available")
    return best


def _persist_job_cookies(runtime: ConnectRuntime, item_id: str, subject: str) -> str | None:
    src = runtime.cookie_jar.materialize(subject)
    if src is None:
        return None
    dest_dir = runtime.staging_dir / ".cookies"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{item_id}.txt"
    try:
        shutil.copy(src, dest)
        try:
            dest.chmod(0o600)
        except OSError:
            pass
        return str(dest)
    finally:
        try:
            src.unlink(missing_ok=True)
        except OSError:
            pass


def create_and_queue(
    runtime: ConnectRuntime,
    meta: VideoMeta,
    fmt: FormatInfo,
    body: EnqueueBody | BatchEnqueueBody,
    *,
    subject: str,
    url: str | None = None,
) -> DownloadItem:
    opts = build_download_options(
        runtime.config,
        staging_dir=str(runtime.staging_dir),
        format_info=fmt,
        extract_audio=body.extract_audio,
        audio_format=body.audio_format,
        overrides=_overrides_from_body(body, persistent_cookie=None),
    )
    item = DownloadItem.create(
        url=url or meta.url,
        title=meta.title,
        format_id=fmt.format_id,
        options=opts,
        meta=meta,
        selected_format=fmt,
    )
    cookie_path = _persist_job_cookies(runtime, item.id, subject)
    if cookie_path:
        item.options.cookiefile = cookie_path

    runtime.queue.add(item)

    if body.schedule_minutes and body.schedule_minutes > 0:
        item.status = DownloadStatus.PENDING
        for qi in runtime.queue.get_items():
            if qi.id == item.id:
                qi.status = DownloadStatus.PENDING.value
                qi.scheduled_at = time.time() + float(body.schedule_minutes) * 60.0
                break
        runtime.queue.save()

    return item


def enqueue_url(
    runtime: ConnectRuntime,
    body: EnqueueBody,
    subject: str,
) -> dict[str, Any]:
    url = body.url.strip()
    if not is_valid_url(url):
        raise ValueError("Invalid URL")
    meta = extract_meta(url, runtime, subject)
    fmt = _pick_format(meta, runtime, body.format_id)
    item = create_and_queue(runtime, meta, fmt, body, subject=subject)
    if body.auto_start and not (body.schedule_minutes and body.schedule_minutes > 0):
        runtime.manager.start(item.id)
    return download_item_json(item)


def enqueue_batch(
    runtime: ConnectRuntime,
    body: BatchEnqueueBody,
    subject: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for raw in body.urls:
        url = raw.strip()
        if not url or not is_valid_url(url):
            errors.append({"url": raw, "error": "Invalid URL"})
            continue
        try:
            single = EnqueueBody(
                url=url,
                format_id=body.format_id,
                extract_audio=body.extract_audio,
                audio_format=body.audio_format,
                auto_start=False,
                schedule_minutes=body.schedule_minutes,
                note=body.note,
                options=body.options,
            )
            items.append(enqueue_url(runtime, single, subject))
        except (FormatExtractError, ValueError) as exc:
            errors.append({"url": url, "error": str(exc)})

    if body.auto_start:
        runtime.manager.start_queued()

    return {"items": items, "errors": errors}


def playlist_entries(url: str, runtime: ConnectRuntime) -> list[dict[str, str]]:
    if not is_valid_url(url.strip()):
        raise ValueError("Invalid URL")
    pairs = extract_playlist_entries(url.strip())
    return [{"url": u, "title": t} for u, t in pairs]
