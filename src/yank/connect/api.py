"""FastAPI application for Yank Connect."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from yank.connect.config_patch import apply_config_patch
from yank.connect.delivery import guess_media_type, purge_item_file, resolve_completed_path
from yank.connect.enqueue import enqueue_batch, enqueue_url, extract_meta, playlist_entries
from yank.connect.events import EventHub
from yank.connect.paths import web_out_dir
from yank.connect.request_auth import (
    auth_subject,
    require_auth,
    resolve_credential,
    tailscale_user_login,
)
from yank.connect.runtime import ConnectRuntime
from yank.connect.scheduler import start_queue_scheduler, stop_queue_scheduler
from yank.connect.schemas import (
    BatchEnqueueBody,
    ConfigPatch,
    EnqueueBody,
    ExtractBody,
    SessionCookiesBody,
)
from yank.connect.serializers import (
    config_public_json,
    history_entry_json,
    queue_item_json,
    queue_summary_json,
    video_meta_json,
)
from yank.connect.session_auth import (
    SESSION_COOKIE,
    issue_session_value,
    session_cookie_kwargs,
    verify_session_value,
)
from yank.engine.downloader import DownloadStatus
from yank.engine.formats import FormatExtractError, is_valid_url, pick_best_format

_RUNTIME: ConnectRuntime | None = None


def get_runtime() -> ConnectRuntime:
    if _RUNTIME is None:
        raise RuntimeError("Connect runtime not initialized")
    return _RUNTIME


def _require_auth(
    request: Request,
    runtime: Annotated[ConnectRuntime, Depends(get_runtime)],
) -> None:
    require_auth(request, runtime)


def _set_session_cookie(response: Response, request: Request, secret: str) -> None:
    secure = request.url.scheme == "https"
    response.set_cookie(
        SESSION_COOKIE,
        issue_session_value(secret),
        **session_cookie_kwargs(secure=secure),
    )


def create_app(runtime: ConnectRuntime | None = None) -> FastAPI:
    global _RUNTIME
    if runtime is None:
        runtime = ConnectRuntime()
    _RUNTIME = runtime

    app = FastAPI(title="Yank Connect", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auto_tailscale_session(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        if verify_session_value(request.cookies.get(SESSION_COOKIE), runtime.token):
            return response
        cred = resolve_credential(request, runtime)
        if cred is not None and cred.startswith("tailscale"):
            _set_session_cookie(response, request, runtime.token)
        return response

    @app.on_event("startup")
    def _startup() -> None:
        runtime.startup()
        if not runtime.active_pair_code:
            runtime.active_pair_code = runtime.pairing.mint_link_path()
        start_queue_scheduler(runtime)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        stop_queue_scheduler(runtime)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/session")
    def session(request: Request) -> dict[str, Any]:
        cred = resolve_credential(request, runtime)
        if cred is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        ts = tailscale_user_login(request)
        subject = auth_subject(request, runtime) or ""
        cookies = runtime.cookie_jar.status(subject)
        return {
            "authenticated": True,
            "method": cred.split(":", 1)[0],
            "tailscale_user": ts,
            "cookies": cookies,
        }

    @app.put("/api/session/cookies", dependencies=[Depends(_require_auth)])
    def put_session_cookies(request: Request, body: SessionCookiesBody) -> dict[str, Any]:
        subject = auth_subject(request, runtime)
        if subject is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            runtime.cookie_jar.set(subject, body.netscape)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **runtime.cookie_jar.status(subject)}

    @app.delete("/api/session/cookies", dependencies=[Depends(_require_auth)])
    def delete_session_cookies(request: Request) -> dict[str, str]:
        subject = auth_subject(request, runtime)
        if subject is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        runtime.cookie_jar.clear(subject)
        return {"ok": "cleared"}

    @app.get("/api/pair")
    def pair(request: Request, code: str) -> RedirectResponse:
        if not runtime.pairing.consume(code):
            raise HTTPException(status_code=400, detail="Invalid or expired link")
        target = "/"
        response = RedirectResponse(url=target, status_code=302)
        _set_session_cookie(response, request, runtime.token)
        return response

    @app.get("/api/info", dependencies=[Depends(_require_auth)])
    def info() -> dict[str, Any]:
        return {
            "name": "yank-connect",
            "staging_dir": str(runtime.staging_dir),
            "queue_size": runtime.queue.size(),
            "ytdlp_version": runtime.ytdlp.current_version(),
            "delivery": "client",
            "note": (
                "Downloads are staged under connect/ only — not the TUI Downloads folder. "
                "Play streams to your device; Save copies to your device and removes the server copy."
            ),
        }

    @app.get("/api/config", dependencies=[Depends(_require_auth)])
    def get_config() -> dict[str, Any]:
        return config_public_json(runtime.config)

    @app.patch("/api/config", dependencies=[Depends(_require_auth)])
    def patch_config(body: ConfigPatch) -> dict[str, Any]:
        apply_config_patch(runtime.config, body)
        return config_public_json(runtime.config)

    @app.post("/api/formats/extract", dependencies=[Depends(_require_auth)])
    async def post_extract(request: Request, body: ExtractBody) -> dict[str, Any]:
        url = body.url.strip()
        if not is_valid_url(url):
            raise HTTPException(status_code=400, detail="Invalid URL")
        subject = auth_subject(request, runtime) or ""
        try:
            if body.playlist or runtime.config.download_playlist:
                entries = await run_in_threadpool(playlist_entries, url, runtime)
                return {"playlist": True, "entries": entries}
            meta = await run_in_threadpool(extract_meta, url, runtime, subject)
        except (FormatExtractError, ValueError) as exc:
            msg = getattr(exc, "message", str(exc))
            raise HTTPException(status_code=422, detail=msg) from exc
        data = video_meta_json(meta)
        best = pick_best_format(meta.formats, preference=runtime.config.format_preference)
        data["suggested_format_id"] = best.format_id if best else None
        return data

    @app.get("/api/queue", dependencies=[Depends(_require_auth)])
    def list_queue(q: str = "") -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        qi_list = runtime.queue.get_items()
        if q.strip():
            ql = q.strip().lower()
            qi_list = [i for i in qi_list if ql in i.title.lower() or ql in i.url.lower()]
        for qi in qi_list:
            di = runtime.manager.get(qi.id)
            items.append(queue_item_json(qi, di))
        return {"items": items, "summary": queue_summary_json(runtime)}

    @app.get("/api/queue/summary", dependencies=[Depends(_require_auth)])
    def queue_summary() -> dict[str, Any]:
        return queue_summary_json(runtime)

    @app.post("/api/queue", dependencies=[Depends(_require_auth)])
    async def enqueue(request: Request, body: EnqueueBody) -> dict[str, Any]:
        subject = auth_subject(request, runtime) or ""
        try:
            return await run_in_threadpool(enqueue_url, runtime, body, subject)
        except (FormatExtractError, ValueError) as exc:
            msg = getattr(exc, "message", str(exc))
            raise HTTPException(status_code=422, detail=msg) from exc

    @app.post("/api/queue/batch", dependencies=[Depends(_require_auth)])
    async def enqueue_batch_route(request: Request, body: BatchEnqueueBody) -> dict[str, Any]:
        subject = auth_subject(request, runtime) or ""
        return await run_in_threadpool(enqueue_batch, runtime, body, subject)

    @app.post("/api/queue/start-all", dependencies=[Depends(_require_auth)])
    def queue_start_all() -> dict[str, Any]:
        runtime.queue.start_all()
        return {"status": "ok", "summary": queue_summary_json(runtime)}

    @app.post("/api/queue/pause-all", dependencies=[Depends(_require_auth)])
    def queue_pause_all() -> dict[str, Any]:
        runtime.queue.pause_all()
        return {"status": "ok"}

    @app.post("/api/queue/clear-finished", dependencies=[Depends(_require_auth)])
    def queue_clear_finished() -> dict[str, Any]:
        runtime.queue.clear_finished()
        return {"status": "ok", "summary": queue_summary_json(runtime)}

    @app.post("/api/queue/retry-failed", dependencies=[Depends(_require_auth)])
    def queue_retry_failed() -> dict[str, Any]:
        count = runtime.queue.retry_failed()
        runtime.manager.start_queued()
        return {"status": "ok", "retried": count}

    @app.post("/api/queue/{item_id}/move", dependencies=[Depends(_require_auth)])
    def queue_move(item_id: str, direction: str = "up") -> dict[str, str]:
        items = runtime.queue.get_items()
        idx = next((i for i, x in enumerate(items) if x.id == item_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail="Not found")
        new_idx = idx - 1 if direction == "up" else idx + 1
        runtime.queue.reorder(item_id, new_idx)
        return {"status": "ok"}

    @app.post("/api/queue/{item_id}/start", dependencies=[Depends(_require_auth)])
    def start_item(item_id: str) -> dict[str, str]:
        item = runtime.manager.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Not found")
        runtime.manager.start(item_id)
        return {"status": "ok"}

    @app.post("/api/queue/{item_id}/pause", dependencies=[Depends(_require_auth)])
    def pause_item(item_id: str) -> dict[str, str]:
        if runtime.manager.get(item_id) is None:
            raise HTTPException(status_code=404, detail="Not found")
        runtime.manager.pause(item_id)
        return {"status": "ok"}

    @app.post("/api/queue/{item_id}/cancel", dependencies=[Depends(_require_auth)])
    def cancel_item(item_id: str) -> dict[str, str]:
        if runtime.manager.get(item_id) is None:
            raise HTTPException(status_code=404, detail="Not found")
        runtime.manager.cancel(item_id)
        runtime.queue.remove(item_id)
        return {"status": "ok"}

    @app.get("/api/downloads/{item_id}/stream", dependencies=[Depends(_require_auth)])
    def stream_file(item_id: str) -> FileResponse:
        item = runtime.manager.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Not found")
        if item.status != DownloadStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="Download not complete")
        try:
            path = resolve_completed_path(item)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return FileResponse(
            path,
            media_type=guess_media_type(path),
            filename=path.name,
            content_disposition_type="inline",
        )

    @app.get("/api/downloads/{item_id}/file", dependencies=[Depends(_require_auth)])
    def download_file(
        item_id: str,
        background: BackgroundTasks,
        remove_from_server: bool = True,
    ) -> FileResponse:
        item = runtime.manager.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Not found")
        if item.status != DownloadStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="Download not complete")
        try:
            path = resolve_completed_path(item)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        response = FileResponse(
            path,
            media_type=guess_media_type(path),
            filename=path.name,
            content_disposition_type="attachment",
        )
        if remove_from_server:
            background.add_task(purge_item_file, runtime, item_id)
        return response

    @app.get("/api/history", dependencies=[Depends(_require_auth)])
    def get_history(q: str = "", status: str = "") -> dict[str, Any]:
        entries = runtime.history.search(q) if q.strip() else runtime.history.to_list()
        if status.strip():
            entries = [e for e in entries if e.status == status.strip()]
        return {"entries": [history_entry_json(e) for e in entries]}

    @app.post("/api/history/{index}/favorite", dependencies=[Depends(_require_auth)])
    def history_favorite(index: int) -> dict[str, Any]:
        fav = runtime.history.toggle_favorite(index)
        return {"favorite": fav}

    @app.delete("/api/history", dependencies=[Depends(_require_auth)])
    def history_clear() -> dict[str, str]:
        runtime.history.clear()
        return {"status": "cleared"}

    def _event_hub() -> EventHub:
        return runtime.events

    @app.get("/api/events")
    def sse_events(
        request: Request,
        hub: Annotated[EventHub, Depends(_event_hub)],
    ) -> StreamingResponse:
        require_auth(request, runtime)

        def stream() -> Any:
            for chunk in hub.iter_sse(poll_s=2.0):
                if request.is_disconnected:
                    break
                yield chunk

        return StreamingResponse(stream(), media_type="text/event-stream")

    out = web_out_dir()
    if out.is_dir() and (out / "index.html").is_file():
        assets = out / "_next"
        if assets.is_dir():
            app.mount("/_next", StaticFiles(directory=assets), name="next-assets")
        app.mount("/", StaticFiles(directory=out, html=True), name="web")
    else:

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        def build_hint() -> str:
            return """<!doctype html>
<html><head><meta charset="utf-8"><title>Yank Connect</title></head>
<body style="font-family:system-ui;background:#0a0a0f;color:#e2e8f0;padding:2rem">
<h1>Yank Connect API</h1>
<p>Build the web UI: <code>cd web && npm ci && npm run build</code>, then restart <code>yank connect</code>.</p>
<p>API docs: <a href="/docs" style="color:#a855f7">/docs</a></p>
</body></html>"""

    return app
