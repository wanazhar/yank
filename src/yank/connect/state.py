"""On-disk state for a running Yank Connect server."""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from yank.connect.paths import CONNECT_STATE_PATH


@dataclass
class ConnectState:
    pid: int
    host: str
    port: int
    started_at: str
    https_url: str = ""
    pair_code: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConnectState | None:
        try:
            return cls(
                pid=int(data["pid"]),
                host=str(data["host"]),
                port=int(data["port"]),
                started_at=str(data.get("started_at") or ""),
                https_url=str(data.get("https_url") or ""),
                pair_code=str(data.get("pair_code") or ""),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _port_bindable(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def pick_port(preferred: int = 0, *, start: int = 8787, attempts: int = 128) -> int:
    """Return a bindable port. ``preferred`` > 0 is used when free, else scan from ``start``."""
    if preferred > 0 and _port_bindable(preferred):
        return preferred
    for port in range(start, start + attempts):
        if _port_bindable(port):
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("0.0.0.0", 0))
        return int(sock.getsockname()[1])


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def write_state(state: ConnectState, path: Path = CONNECT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")


def read_state(path: Path = CONNECT_STATE_PATH) -> ConnectState | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    state = ConnectState.from_dict(data)
    if state is None:
        return None
    if not pid_alive(state.pid):
        return None
    return state


def clear_state(path: Path = CONNECT_STATE_PATH) -> None:
    path.unlink(missing_ok=True)


def new_state(
    pid: int,
    host: str,
    port: int,
    *,
    https_url: str = "",
    pair_code: str = "",
) -> ConnectState:
    return ConnectState(
        pid=pid,
        host=host,
        port=port,
        started_at=datetime.now(UTC).isoformat(),
        https_url=https_url,
        pair_code=pair_code,
    )


def wait_until_healthy(port: int, *, timeout_s: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.1)
    return False
