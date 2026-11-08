"""Use per-session Connect cookies with yt-dlp."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

from yank.connect.runtime import ConnectRuntime

T = TypeVar("T")


@contextmanager
def session_cookiefile(runtime: ConnectRuntime, subject: str) -> Iterator[str | None]:
    path = runtime.cookie_jar.materialize(subject)
    try:
        yield str(path) if path else None
    finally:
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def with_session_cookies(
    runtime: ConnectRuntime,
    subject: str,
    fn: Callable[[str | None], T],
) -> T:
    with session_cookiefile(runtime, subject) as cookiefile:
        return fn(cookiefile)
