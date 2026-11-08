"""Long-running Connect server process (foreground)."""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import sys

from yank.connect.state import clear_state, new_state, write_state


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yank connect server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--no-tailscale-hint", action="store_true")
    p.add_argument("--no-banner", action="store_true", help=argparse.SUPPRESS)
    return p


def run_foreground(
    host: str,
    port: int,
    *,
    print_banner: bool = True,
    no_tailscale_hint: bool = False,
) -> None:
    try:
        import uvicorn
    except ImportError:
        print(
            "Yank Connect needs FastAPI and uvicorn.\n"
            "From this repo: uv sync && uv run yank connect\n"
            "From PyPI: pip install 'yank-tui[connect]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    from yank.connect.api import create_app
    from yank.connect.runtime import ConnectRuntime
    from yank.connect.tailscale import build_listen_addresses, magic_link
    from yank.connect.teardown import teardown_runtime

    runtime = ConnectRuntime()
    runtime.active_pair_code = runtime.pairing.mint_link_path()
    app = create_app(runtime)

    https_url = os.environ.get("YANK_CONNECT_HTTPS_URL", "")
    write_state(
        new_state(
            os.getpid(),
            host,
            port,
            https_url=https_url,
            pair_code=runtime.active_pair_code or "",
        )
    )

    shut_down = False

    def _shutdown() -> None:
        nonlocal shut_down
        if shut_down:
            return
        shut_down = True
        try:
            teardown_runtime(runtime)
        finally:
            clear_state()

    atexit.register(_shutdown)

    def _on_signal(signum: int, _frame: object) -> None:
        _shutdown()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    if print_banner:
        addrs = build_listen_addresses(host, port, https_url=https_url or None)
        code = runtime.active_pair_code or ""
        print("\n  yank connect\n")
        print(f"  Local:   http://127.0.0.1:{port}")
        if https_url:
            print(f"  HTTPS:   {magic_link(https_url, code)}")
        elif not no_tailscale_hint and addrs.tailnet_url:
            print(f"  Tailnet: {magic_link(addrs.tailnet_url, code)}")
        for ip in addrs.lan_ips[:3]:
            print(f"  LAN:     {magic_link(f'http://{ip}:{port}', code)}")
        print("\n  Open the magic link on your phone (logs you in once).\n")
        print("  yank connect stop\n")

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    try:
        server.run()
    finally:
        _shutdown()


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run_foreground(
        args.host,
        args.port,
        print_banner=not args.no_banner,
        no_tailscale_hint=args.no_tailscale_hint,
    )


if __name__ == "__main__":
    main()
