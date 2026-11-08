"""Session and pairing auth for Connect."""

from __future__ import annotations

from yank.connect.session_auth import (
    PairingStore,
    issue_session_value,
    verify_session_value,
)


def test_session_cookie_roundtrip() -> None:
    secret = "test-secret-value"
    val = issue_session_value(secret)
    assert verify_session_value(val, secret)
    assert not verify_session_value(val, "wrong")


def test_pairing_single_use() -> None:
    store = PairingStore()
    code = store.mint(ttl_s=60)
    assert store.consume(code)
    assert not store.consume(code)
