"""Yank Connect — web UI + API for remote downloads over Tailscale or LAN."""

from __future__ import annotations

from typing import Any

__all__ = ["ConnectRuntime", "create_app"]


def __getattr__(name: str) -> Any:  # PEP 562
    if name == "create_app":
        from yank.connect.api import create_app

        return create_app
    if name == "ConnectRuntime":
        from yank.connect.runtime import ConnectRuntime

        return ConnectRuntime
    raise AttributeError(name)
