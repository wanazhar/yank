"""Tests for Yank Connect helpers and API."""

from __future__ import annotations

import os

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from yank.connect.api import create_app
from yank.connect.auth import load_or_create_token, reset_token, verify_token
from yank.connect.runtime import ConnectRuntime
from yank.connect.session_auth import issue_session_value
from yank.connect.state import clear_state, new_state, pick_port, read_state, write_state


def test_verify_token() -> None:
    assert verify_token("abc", "abc")
    assert not verify_token("abc", "def")
    assert not verify_token(None, "abc")


def test_api_health_and_auth(tmp_path, monkeypatch) -> None:
    token_path = tmp_path / "token"
    staging = tmp_path / "dl"
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
    app = create_app(runtime)
    client = TestClient(app)

    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/api/queue")
    assert r.status_code == 401

    session = issue_session_value(runtime.token)
    r = client.get("/api/queue", cookies={"yank_connect_session": session})
    assert r.status_code == 200
    assert r.json()["items"] == []

    r = client.get("/api/queue", headers={"Authorization": f"Bearer {runtime.token}"})
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_pick_port_and_state(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("yank.connect.state.CONNECT_STATE_PATH", state_path)

    port = pick_port(0)
    assert port >= 8787

    write_state(new_state(os.getpid(), "0.0.0.0", port), path=state_path)
    loaded = read_state(path=state_path)
    assert loaded is not None
    assert loaded.port == port

    clear_state(path=state_path)
    assert read_state(path=state_path) is None
