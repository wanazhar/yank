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
    tomli_w = None  # type: ignore[assignment]


CONFIG_DIR = Path.home() / ".config" / "yank"
CONFIG_PATH = CONFIG_DIR / "config.toml"

FormatPreference = Literal["best", "best_video_audio", "audio_only"]
UpdateCheckInterval = Literal["always", "ask", "never"]


@dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    download_dir: str = field(
        default_factory=lambda: str(Path.home() / "Downloads")
    )
    filename_template: str = "%(title)s.%(ext)s"
    format_preference: FormatPreference = "best"
    max_concurrent: int = 1
    default_subtitle_lang: str = "en"
    update_check_interval: UpdateCheckInterval = "ask"
    download_thumbnail: bool = False
    embed_metadata: bool = True
    embed_subtitles: bool = False
    audio_format: str = "mp3"
    last_update_check: float = 0.0  # unix timestamp

    def ensure_valid(self) -> AppConfig:
        """Clamp values to valid ranges and normalize paths."""
        self.max_concurrent = max(1, min(5, int(self.max_concurrent)))
        if self.format_preference not in ("best", "best_video_audio", "audio_only"):
            self.format_preference = "best"
        if self.update_check_interval not in ("always", "ask", "never"):
            self.update_check_interval = "ask"
        if self.audio_format not in ("mp3", "m4a", "opus", "flac"):
            self.audio_format = "mp3"
        # Expand ~ in download dir
        self.download_dir = str(Path(self.download_dir).expanduser())
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
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        elif isinstance(value, float):
            lines.append(f"{key} = {value}")
        elif isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def ensure_download_dir(cfg: AppConfig) -> Path:
    """Ensure the download directory exists and return it."""
    d = Path(cfg.download_dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d
