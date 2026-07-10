
"""Tests for config save/load roundtrip, TOML serialization, and type validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from yank.models.config import (
    AppConfig,
    _toml_value,
    _write_toml_manual,
    load_config,
    save_config,
)


@pytest.fixture
def tmp_config_path():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td) / "config.toml"


# ── AppConfig validation ────────────────────────────────────────────────────


class TestAppConfigValidation:
    def test_defaults_are_valid(self):
        cfg = AppConfig()
        cfg.ensure_valid()
        assert cfg.max_concurrent == 1
        assert cfg.format_preference == "best"

    def test_clamps_max_concurrent_low(self):
        cfg = AppConfig(max_concurrent=0)
        cfg.ensure_valid()
        assert cfg.max_concurrent == 1

    def test_clamps_max_concurrent_high(self):
        cfg = AppConfig(max_concurrent=10)
        cfg.ensure_valid()
        assert cfg.max_concurrent == 5

    def test_invalid_format_preference_reset(self):
        cfg = AppConfig(format_preference="invalid_option")  # type: ignore
        cfg.ensure_valid()
        assert cfg.format_preference == "best"

    def test_invalid_update_interval_reset(self):
        cfg = AppConfig(update_check_interval="hourly")  # type: ignore
        cfg.ensure_valid()
        assert cfg.update_check_interval == "ask"

    def test_invalid_audio_format_reset(self):
        cfg = AppConfig(audio_format="wav")  # type: ignore
        cfg.ensure_valid()
        assert cfg.audio_format == "mp3"

    def test_expanduser_in_download_dir(self):
        cfg = AppConfig(download_dir="~/Videos")
        cfg.ensure_valid()
        assert not cfg.download_dir.startswith("~")


# ── Config save/load roundtrip ──────────────────────────────────────────────


class TestConfigRoundtrip:
    def test_roundtrip_defaults(self, tmp_config_path):
        """Default config survives save → load."""
        cfg = AppConfig().ensure_valid()
        save_config(cfg, tmp_config_path)
        loaded = load_config(tmp_config_path)
        assert loaded.download_dir == cfg.download_dir
        assert loaded.max_concurrent == cfg.max_concurrent
        assert loaded.format_preference == cfg.format_preference
        assert loaded.filename_template == cfg.filename_template

    def test_roundtrip_custom_values(self, tmp_config_path):
        """Custom config values survive save → load."""
        cfg = AppConfig(
            download_dir="/custom/output",
            filename_template="%(title)s-%(id)s.%(ext)s",
            max_concurrent=3,
            format_preference="audio_only",
            update_check_interval="never",
            audio_format="opus",
            default_subtitle_lang="fr",
        ).ensure_valid()
        save_config(cfg, tmp_config_path)
        loaded = load_config(tmp_config_path)
        assert loaded.download_dir == cfg.download_dir
        assert loaded.filename_template == cfg.filename_template
        assert loaded.max_concurrent == 3
        assert loaded.format_preference == "audio_only"
        assert loaded.update_check_interval == "never"
        assert loaded.audio_format == "opus"
        assert loaded.default_subtitle_lang == "fr"

    def test_load_nonexistent_returns_defaults(self, tmp_config_path):
        """Loading nonexistent file returns defaults."""
        cfg = load_config(tmp_config_path)
        assert cfg.max_concurrent == 1
        assert cfg.format_preference == "best"

    def test_load_corrupt_file_returns_defaults(self, tmp_config_path):
        """Corrupt TOML returns defaults silently."""
        tmp_config_path.write_text("this is not valid toml {{{")
        cfg = load_config(tmp_config_path)
        assert cfg.max_concurrent == 1

    def test_save_creates_parent_dirs(self, tmp_config_path):
        """Saving creates parent directories automatically."""
        nested = tmp_config_path / "subdir" / "deep" / "config.toml"
        cfg = AppConfig().ensure_valid()
        save_config(cfg, nested)
        assert nested.exists()

    def test_roundtrip_boolean_fields(self, tmp_config_path):
        """Boolean fields serialize correctly."""
        cfg = AppConfig(
            download_thumbnail=True,
            embed_metadata=False,
            embed_subtitles=True,
        ).ensure_valid()
        save_config(cfg, tmp_config_path)
        loaded = load_config(tmp_config_path)
        assert loaded.download_thumbnail is True
        assert loaded.embed_metadata is False
        assert loaded.embed_subtitles is True


# ── TOML manual serialization ───────────────────────────────────────────────


class TestTomlSerialization:
    def test_bool_serialization(self):
        assert _toml_value(True) == "true"
        assert _toml_value(False) == "false"

    def test_int_serialization(self):
        assert _toml_value(42) == "42"
        assert _toml_value(-7) == "-7"

    def test_float_serialization(self):
        assert _toml_value(3.14) == "3.14"

    def test_str_serialization(self):
        assert _toml_value("hello") == '"hello"'

    def test_str_escapes_quotes(self):
        result = _toml_value('say "hello"')
        assert '\\"' in result

    def test_str_escapes_backslash(self):
        result = _toml_value(r"C:\path\to\file")
        assert "\\\\" in result

    def test_unsupported_type_raises(self):
        with pytest.raises(TypeError):
            _toml_value(object())

    def test_write_list_value(self, tmp_config_path):
        """Writing a dict with a list value should serialize as TOML array."""
        data = {"languages": ["en", "fr", "de"]}
        _write_toml_manual(data, tmp_config_path)
        content = tmp_config_path.read_text()
        assert "languages" in content
        assert "en" in content
        assert "fr" in content

    def test_write_dict_value(self, tmp_config_path):
        """Writing a nested dict should serialize as TOML inline table."""
        data = {"meta": {"author": "test", "version": 1}}
        _write_toml_manual(data, tmp_config_path)
        content = tmp_config_path.read_text()
        assert "meta" in content
        assert "author" in content

    def test_unsupported_type_in_dict_raises(self, tmp_config_path):
        """Writing an unsupported value type should raise TypeError."""
        data = {"bad_key": object()}
        with pytest.raises(TypeError):
            _write_toml_manual(data, tmp_config_path)

    def test_write_creates_valid_toml(self, tmp_config_path):
        """Written TOML should be reloadable by tomllib."""
        import tomllib
        data = {
            "download_dir": "/home/user/Downloads",
            "max_concurrent": 3,
            "embed_metadata": True,
            "filename_template": "%(title)s.%(ext)s",
        }
        _write_toml_manual(data, tmp_config_path)
        # Should not raise
        reloaded = tomllib.loads(tmp_config_path.read_text())
        assert reloaded["max_concurrent"] == 3


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestConfigEdgeCases:
    def test_extra_keys_ignored_on_load(self, tmp_config_path):
        """Unknown keys in TOML file are silently ignored."""
        tmp_config_path.write_text(
            'download_dir = "/tmp"\nmax_concurrent = 2\nunknown_field = "ignored"\n'
        )
        cfg = load_config(tmp_config_path)
        assert cfg.max_concurrent == 2

    def test_empty_file_returns_defaults(self, tmp_config_path):
        tmp_config_path.write_text("")
        cfg = load_config(tmp_config_path)
        assert cfg.max_concurrent == 1

    def test_last_update_check_preserved(self, tmp_config_path):
        cfg = AppConfig(last_update_check=1234567890.0)
        save_config(cfg, tmp_config_path)
        loaded = load_config(tmp_config_path)
        assert loaded.last_update_check == 1234567890.0
