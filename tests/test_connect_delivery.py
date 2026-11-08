"""Connect client delivery (staging paths, stream route)."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from yank.connect.api import create_app
from yank.connect.auth import load_or_create_token, reset_token
from yank.connect.delivery import media_kind_for_path, resolve_completed_path
from yank.connect.runtime import ConnectRuntime
from yank.connect.session_auth import issue_session_value
from yank.engine.downloader import DownloadItem, DownloadStatus


def test_media_kind() -> None:
    assert media_kind_for_path(__import__("pathlib").Path("a.mp4")) == "video"
    assert media_kind_for_path(__import__("pathlib").Path("a.mp3")) == "audio"
    assert media_kind_for_path(__import__("pathlib").Path("a.zip")) == "file"


def test_stream_rejects_outside_staging(tmp_path, monkeypatch) -> None:
    token_path = tmp_path / "token"
    staging = tmp_path / "dl"
    staging.mkdir()
    outside = tmp_path / "evil.bin"
    outside.write_bytes(b"x")

    monkeypatch.setattr("yank.connect.paths.CONNECT_TOKEN_PATH", token_path)
    monkeypatch.setattr("yank.connect.auth.CONNECT_TOKEN_PATH", token_path)
    monkeypatch.setattr("yank.connect.paths.CONNECT_STAGING_DIR", staging)
    monkeypatch.setattr("yank.connect.runtime.CONNECT_STAGING_DIR", staging)
    monkeypatch.setattr(
        "yank.engine.updater.YtDlpManager.ensure_installed",
        lambda self, *a, **k: None,
    )
    reset_token(token_path)

    runtime = ConnectRuntime()
    runtime.token = load_or_create_token(token_path)
    item = DownloadItem(
        id="t1",
        url="https://example.com",
        title="t",
        format_id="best",
        status=DownloadStatus.COMPLETED,
        file_path=str(outside),
    )
    runtime.manager.register(item)

    with pytest.raises(PermissionError):
        resolve_completed_path(item)

    inside = staging / "clip.mp4"
    inside.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    item.file_path = str(inside)
    path = resolve_completed_path(item)
    assert path == inside.resolve()

    app = create_app(runtime)
    client = TestClient(app)
    session = issue_session_value(runtime.token)
    r = client.get(
        "/api/downloads/t1/stream",
        cookies={"yank_connect_session": session},
    )
    assert r.status_code == 200
    assert "video" in (r.headers.get("content-type") or "")
