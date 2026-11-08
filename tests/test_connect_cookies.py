"""Connect per-session cookie jar."""

from __future__ import annotations

import pytest

from yank.connect.cookie_jar import ConnectCookieJar, validate_netscape_cookie_file

_HEADER = "# Netscape HTTP Cookie File\n"
_LINE = ".youtube.com\tTRUE\t/\tTRUE\t2000000000\tSID\tvalue\n"


def test_validate_accepts_youtube_cookie() -> None:
    text = _HEADER + _LINE
    out = validate_netscape_cookie_file(text)
    assert "youtube.com" in out


def test_validate_rejects_other_domains() -> None:
    bad = _HEADER + ".evil.com\tTRUE\t/\tTRUE\t0\tx\ty\n"
    with pytest.raises(ValueError, match="youtube"):
        validate_netscape_cookie_file(bad)


def test_jar_roundtrip() -> None:
    jar = ConnectCookieJar()
    jar.set("u1", _HEADER + _LINE)
    path = jar.materialize("u1")
    assert path is not None
    assert "SID" in path.read_text(encoding="utf-8")
    path.unlink(missing_ok=True)
    jar.clear("u1")
    assert jar.materialize("u1") is None
