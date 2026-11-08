"""Shared yt-dlp options from :class:`AppConfig` (extract + download)."""

from __future__ import annotations

from typing import Any

from yank.models.config import AppConfig


def apply_config_to_ydl_opts(ydl_opts: dict[str, Any], config: AppConfig | None) -> None:
    """Merge cookies, proxy, and network-related config into *ydl_opts* in place."""
    if config is None:
        return

    proxy = getattr(config, "proxy", "") or ""
    if proxy.strip():
        ydl_opts["proxy"] = proxy.strip()

    cookies_browser = getattr(config, "cookies_browser", "") or ""
    cookies_file = getattr(config, "cookies_file", "") or ""
    if cookies_browser.strip():
        ydl_opts["cookiesfrombrowser"] = (cookies_browser.strip(),)
    elif cookies_file.strip():
        ydl_opts["cookiefile"] = cookies_file.strip()

    if getattr(config, "geo_bypass", False):
        ydl_opts["geo_bypass"] = True

    if getattr(config, "no_check_certificate", False):
        ydl_opts["nocheckcertificate"] = True

    sa = getattr(config, "source_address", "") or ""
    if sa.strip():
        ydl_opts["source_address"] = sa.strip()

    if getattr(config, "prefer_free_formats", False):
        ydl_opts["prefer_free_formats"] = True
