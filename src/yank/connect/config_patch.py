"""Apply Connect settings updates to shared AppConfig."""

from __future__ import annotations

from yank.connect.schemas import ConfigPatch
from yank.models.config import AppConfig, save_config


def apply_config_patch(config: AppConfig, patch: ConfigPatch) -> AppConfig:
    for key, value in patch.model_dump(exclude_none=True).items():
        setattr(config, key, value)
    config.ensure_valid()
    save_config(config)
    return config
