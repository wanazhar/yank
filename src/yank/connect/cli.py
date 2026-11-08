"""``yank connect`` command: start (default), status, stop."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from yank.connect.paths import CONNECT_LOG_PATH
from yank.connect.state import pick_port, pid_alive, read_state, wait_until_healthy
from yank.connect.tailscale import (
    build_listen_addresses,
    magic_link,
    tailscale_https_origin,
    tailscale_serve_local_port,
)
from yank.connect.teardown import teardown_connect_disk


def _module_cmd() -> list[str]:
    return [sys.executable, "-m", "yank.connect.server"]


def _start_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yank connect start", add_help=False)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=0, help="0 = auto-assign from 8787")
    p.add_argument("--foreground", "-f", action="store_true")
    p.add_argument("--no-tailscale-hint", action="store_true")
    p.add_argument(
        "--tailscale-https",
        action="store_true",
        help="Expose via tailscale serve (HTTPS magic DNS on your tailnet)",
    )
    return p


def _stop_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yank connect stop", add_help=False)
    p.add_argument("--timeout", type=float, default=10.0)
    return p


def print_help() -> None:
    print(
        """usage: yank connect [start|status|stop] [options]

  start (default)  Start API + web (background; use -f for foreground)
  status           Show pid, port, URLs, token
  stop             Stop server; cancel queue and clear staging

examples:
  uv run yank connect
  uv run yank connect status
  uv run yank connect stop
  uv run yank connect start --foreground
"""
    )


def cmd_status() -> None:
    state = read_state()
    if state is None:
        print("Yank Connect is not running.")
        raise SystemExit(1)

    addrs = build_listen_addresses(
        state.host,
        state.port,
        https_url=state.https_url or None,
    )
    code = state.pair_code
    print(f"Yank Connect is running (pid {state.pid})")
    print(f"  Started: {state.started_at}")
    print(f"  Port:    {state.port}")
    if code:
        print(f"  Local:   {magic_link(f'http://127.0.0.1:{state.port}', code)}")
        if state.https_url:
            print(f"  HTTPS:   {magic_link(state.https_url, code)}")
        elif addrs.tailnet_url:
            print(f"  Tailnet: {magic_link(addrs.tailnet_url, code)}")
    else:
        print(f"  Local:   http://127.0.0.1:{state.port}")
        if state.https_url:
            print(f"  HTTPS:   {state.https_url}")
        elif addrs.tailnet_url:
            print(f"  Tailnet: {addrs.tailnet_url}")


def cmd_stop(argv: list[str]) -> None:
    args = _stop_parser().parse_args(argv)

    state = read_state()
    if state is None or not pid_alive(state.pid if state else 0):
        teardown_connect_disk()
        print("Yank Connect is not running (cleaned up stale state).")
        return

    try:
        os.kill(state.pid, signal.SIGTERM)
    except OSError as exc:
        teardown_connect_disk()
        print(f"Could not signal pid {state.pid}: {exc}")
        raise SystemExit(1) from exc

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if not pid_alive(state.pid):
            print(f"Stopped Yank Connect (pid {state.pid}).")
            return
        time.sleep(0.15)

    try:
        os.kill(state.pid, signal.SIGKILL)
    except OSError:
        pass
    teardown_connect_disk()
    print(f"Stopped Yank Connect (pid {state.pid}, forced).")


def cmd_start(argv: list[str]) -> None:
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print(
            "Yank Connect needs FastAPI and uvicorn.\n"
            "From this repo: uv sync && uv run yank connect\n"
            "From PyPI: pip install 'yank-tui[connect]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    args = _start_parser().parse_args(argv)

    existing = read_state()
    if existing is not None:
        print(f"Yank Connect is already running (pid {existing.pid}, port {existing.port}).")
        print("Use `yank connect status` or `yank connect stop` first.")
        raise SystemExit(1)

    port = pick_port(args.port)
    host = args.host

    if args.foreground:
        from yank.connect.server import run_foreground

        run_foreground(host, port, no_tailscale_hint=args.no_tailscale_hint)
        return

    env = os.environ.copy()
    https_url = ""
    if args.tailscale_https:
        if tailscale_serve_local_port(port):
            https_url = tailscale_https_origin() or ""
        if https_url:
            env["YANK_CONNECT_HTTPS_URL"] = https_url

    CONNECT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(CONNECT_LOG_PATH, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [
            *_module_cmd(),
            "--host",
            host,
            "--port",
            str(port),
            "--no-banner",
        ]
        + (["--no-tailscale-hint"] if args.no_tailscale_hint else []),
        stdin=subprocess.DEVNULL,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(Path.cwd()),
        env=env,
    )
    log_f.close()

    if not wait_until_healthy(port):
        try:
            proc.kill()
        except OSError:
            pass
        print("Yank Connect failed to start (see connect/server.log).", file=sys.stderr)
        raise SystemExit(1)

    state = read_state()
    code = state.pair_code if state else ""
    addrs = build_listen_addresses(host, port, https_url=https_url or None)
    print("\n  yank connect started\n")
    print(f"  PID:     {proc.pid}")
    print(f"  Port:    {port}")
    if code:
        print(f"  Local:   {magic_link(f'http://127.0.0.1:{port}', code)}")
        if https_url:
            print(f"  HTTPS:   {magic_link(https_url, code)}")
        elif not args.no_tailscale_hint and addrs.tailnet_url:
            print(f"  Tailnet: {magic_link(addrs.tailnet_url, code)}")
        for ip in addrs.lan_ips[:3]:
            print(f"  LAN:     {magic_link(f'http://{ip}:{port}', code)}")
    print("\n  Open the magic link on your phone — no API token needed.\n")
    print("  yank connect status | yank connect stop\n")


def main(argv: list[str] | None = None) -> None:
    argv = list(argv or [])

    if "-h" in argv or "--help" in argv:
        print_help()
        return

    if not argv:
        cmd_start([])
        return

    cmd = argv[0]
    rest = argv[1:]

    if cmd == "status":
        cmd_status()
        return
    if cmd == "stop":
        cmd_stop(rest)
        return
    if cmd == "start":
        cmd_start(rest)
        return

    cmd_start(argv)
