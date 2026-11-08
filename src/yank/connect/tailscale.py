"""Tailscale / tailnet address helpers."""

from __future__ import annotations

import json
import re
import socket
import subprocess
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass(frozen=True)
class ListenAddresses:
    """URLs to print when ``yank connect`` starts."""

    host: str
    port: int
    local_url: str
    tailnet_url: str | None
    https_url: str | None
    lan_ips: tuple[str, ...]


def tailscale_ipv4() -> str | None:
    """Return the machine's Tailscale IPv4 (100.x.x.x), if any."""
    try:
        proc = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        ip = line.strip()
        if ip.startswith("100."):
            return ip
    return None


def tailscale_dns_name() -> str | None:
    try:
        proc = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
        name = (data.get("Self") or {}).get("DNSName") or ""
        name = str(name).strip().rstrip(".")
        return name or None
    except (json.JSONDecodeError, TypeError):
        return None


def tailscale_serve_local_port(local_port: int, *, background: bool = True) -> bool:
    """Expose *local_port* on the tailnet via ``tailscale serve``."""
    target = f"http://127.0.0.1:{local_port}"
    cmd = ["tailscale", "serve"]
    if background:
        cmd.append("--bg")
    cmd.append(target)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def tailscale_serve_reset() -> None:
    try:
        subprocess.run(
            ["tailscale", "serve", "reset"],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def tailscale_https_origin() -> str | None:
    """Best-effort HTTPS magic DNS URL for this node (Tailscale Serve)."""
    dns = tailscale_dns_name()
    if not dns:
        return None
    try:
        proc = subprocess.run(
            ["tailscale", "serve", "status"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return f"https://{dns}/"
    if proc.returncode != 0:
        return f"https://{dns}/"
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("https://") and "tail" in line and "(tailnet" in line:
            base = line.split()[0]
            return base if base.endswith("/") else base + "/"
    return f"https://{dns}/"


def magic_link(base_url: str, pair_code: str) -> str:
    base = base_url if base_url.endswith("/") else base_url + "/"
    return urljoin(base, f"?pair={pair_code}")


def _local_ipv4s() -> list[str]:
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = str(info[4][0])
            if not addr.startswith("127.") and addr not in ips:
                ips.append(addr)
    except OSError:
        pass
    return ips


def build_listen_addresses(
    host: str,
    port: int,
    *,
    https_url: str | None = None,
) -> ListenAddresses:
    local = f"http://127.0.0.1:{port}"
    tail_ip = tailscale_ipv4()
    tailnet = f"http://{tail_ip}:{port}" if tail_ip else None
    lan = tuple(_local_ipv4s())
    return ListenAddresses(
        host=host,
        port=port,
        local_url=local,
        tailnet_url=tailnet,
        https_url=https_url,
        lan_ips=lan,
    )


def serve_status_mentions_port(local_port: int) -> bool:
    try:
        text = subprocess.run(
            ["tailscale", "serve", "status"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    pattern = rf"127\.0\.0\.1:{local_port}\b"
    return bool(re.search(pattern, text))
