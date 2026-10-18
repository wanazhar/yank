"""Configuration loading and saving (TOML at ~/.config/yank/config.toml)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

try:
    import tomli_w
except ImportError:
    tomli_w = None

from yank.constants import MAX_CONCURRENT
from yank.logging import get_logger
from yank.paths import CONFIG_PATH

_logger = get_logger(__name__)


FormatPreference = Literal["best", "best_video_audio", "audio_only"]
UpdateCheckInterval = Literal["always", "ask", "never"]


@dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    download_dir: str = field(default_factory=lambda: str(Path.home() / "Downloads"))
    filename_template: str = "%(title)s.%(ext)s"
    format_preference: FormatPreference = "best"
    max_concurrent: int = 1
    default_subtitle_lang: str = "en"
    update_check_interval: UpdateCheckInterval = "ask"
    download_thumbnail: bool = False
    embed_metadata: bool = True
    embed_subtitles: bool = False
    audio_format: str = "mp3"
    subtitle_format: str = "srt"
    download_playlist: bool = False
    theme: str = "dark"
    last_update_check: float = 0.0  # unix timestamp
    enable_notifications: bool = True
    proxy: str = ""
    cookies_browser: str = ""
    cookies_file: str = ""
    download_archive: str = ""
    rate_limit: str = ""
    playlist_items: str = ""
    audio_normalize: bool = False
    sponsorblock_remove: str = ""
    split_chapters: bool = False
    download_sections: str = ""
    concurrent_fragments: int = 4
    external_downloader: str = ""
    geo_bypass: bool = False
    continue_dl: bool = True
    source_address: str = ""
    live_from_start: bool = False
    no_check_certificate: bool = False
    age_limit: int = 0
    webhook_url: str = ""
    history_retention_days: int = 0
    language: str = "en"
    prefer_free_formats: bool = False
    sleep_interval: float = 0.0
    sponsorblock_mark: str = ""
    retry_count: int = 3

    def ensure_valid(self) -> AppConfig:
        """Clamp values to valid ranges and normalize paths."""
        self.max_concurrent = max(1, min(MAX_CONCURRENT, int(self.max_concurrent)))
        if self.format_preference not in ("best", "best_video_audio", "audio_only"):
            self.format_preference = "best"
        if self.update_check_interval not in ("always", "ask", "never"):
            self.update_check_interval = "ask"
        if self.audio_format not in ("mp3", "m4a", "opus", "flac"):
            self.audio_format = "mp3"
        if self.subtitle_format not in ("srt", "vtt", "ass", "lrc"):
            self.subtitle_format = "srt"
        if self.theme not in ("dark", "light"):
            self.theme = "dark"
        self.retry_count = max(0, min(10, int(self.retry_count)))
        self.concurrent_fragments = max(1, min(16, int(self.concurrent_fragments)))
        # Expand ~ in download dir
        self.download_dir = str(Path(self.download_dir).expanduser())

        # Validate download_dir: warn if doesn't exist or not writable
        dl_path = Path(self.download_dir)
        if not dl_path.exists():
            _logger.warning(
                "Download directory does not exist: %s — will attempt to create",
                self.download_dir,
            )
        elif not dl_path.is_dir():
            _logger.warning(
                "Download directory path is not a directory: %s — using default",
                self.download_dir,
            )
            self.download_dir = str(Path.home() / "Downloads")
        elif not os.access(str(dl_path), os.W_OK):
            _logger.warning(
                "Download directory is not writable: %s — downloads may fail",
                self.download_dir,
            )

        return self


def _config_to_toml_dict(cfg: AppConfig) -> dict[str, Any]:
    return asdict(cfg)


def _dict_to_config(data: dict[str, Any]) -> AppConfig:
    known = {f.name for f in fields(AppConfig)}
    filtered = {k: v for k, v in data.items() if k in known}
    return AppConfig(**filtered).ensure_valid()


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from TOML file, or return defaults if missing/invalid."""
    path = path or CONFIG_PATH
    if not path.exists():
        return AppConfig().ensure_valid()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        if not isinstance(data, dict):
            return AppConfig().ensure_valid()
        return _dict_to_config(data)
    except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
        return AppConfig().ensure_valid()


def _write_toml_manual(data: dict[str, Any], path: Path) -> None:
    """Write a simple TOML file without tomli_w dependency."""
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        elif isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        elif isinstance(value, list):
            parts = [_toml_value(v) for v in value]
            lines.append(f"{key} = [{', '.join(parts)}]")
        elif isinstance(value, dict):
            parts = [f"{k} = {_toml_value(v)}" for k, v in value.items()]
            lines.append(f"{key} = {{ {', '.join(parts)} }}")
        else:
            raise TypeError(
                f"Cannot serialize config key '{key}' of type {type(value).__name__}. "
                f"Only bool, int, float, str, list, and dict are supported."
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_value(value: Any) -> str:
    """Serialize a single TOML value (for use in inline arrays/tables)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    else:
        raise TypeError(f"Cannot serialize TOML value of type {type(value).__name__}")


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    """Persist config to TOML file, creating directories as needed."""
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = cfg.ensure_valid()
    data = _config_to_toml_dict(cfg)
    if tomli_w is not None:
        with open(path, "wb") as f:
            tomli_w.dump(data, f)
    else:
        _write_toml_manual(data, path)
