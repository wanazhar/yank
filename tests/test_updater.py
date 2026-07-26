"""Tests for yt-dlp updater version comparison and helpers."""

from __future__ import annotations

from packaging.version import Version

from yank.engine.updater import YtDlpManager  # keep import for module visibility


class TestVersionComparison:
    """Test Version comparison with real yt-dlp version formats."""

    def test_simple_newer(self):
        assert Version("2024.1.0") > Version("2023.12.31")

    def test_simple_older(self):
        assert Version("2023.1.0") < Version("2024.1.0")

    def test_same_version(self):
        assert not (Version("2024.1.0") > Version("2024.1.0"))

    def test_minor_bump(self):
        assert Version("2024.2.0") > Version("2024.1.0")

    def test_patch_bump(self):
        assert Version("2024.1.1") > Version("2024.1.0")

    def test_nightly_newer(self):
        """Nightly versions like 2024.01.01.232536 should compare correctly."""
        assert Version("2024.01.02") > Version("2024.01.01.232536")

    def test_nightly_older(self):
        assert Version("2024.01.01") < Version("2024.01.01.232536")

    def test_post_release(self):
        """Post-release suffixes are treated as newer than base (PEP 440)."""
        assert Version("2024.1.0.post1") > Version("2024.1.0")

    def test_prerelease_is_older(self):
        """Pre-release markers are treated as older than release."""
        assert Version("2024.1.0a1") < Version("2024.1.0")

    def test_different_length_padded(self):
        """Different-length version tuples compare correctly."""
        assert Version("2024.1.0.1") > Version("2024.1.0")

    def test_leading_zeros(self):
        """Leading zeros in version segments."""
        assert Version("2024.01.10") > Version("2024.1.9")

    def test_handles_complex_suffixes(self):
        """Dashes converted to dots for chunking."""
        # packaging.version handles these natively
        assert Version("2024.1.0") > Version("2024.1.0b1")

    def test_ragged_versions(self):
        """Ragged version strings with mixed numbers/text."""
        assert Version("2024.12.25") > Version("2024.6.1")
        assert not (Version("2024.6.1") > Version("2024.12.25"))

    def test_fallback_on_parse_error(self):
        """If parsing fails, InvalidVersion is raised."""
        import pytest as _pytest
        from packaging.version import InvalidVersion

        with _pytest.raises(InvalidVersion):
            Version("weird-version")


class TestVersionComparisonEdgeCases:
    def test_single_segment(self):
        assert Version("2") > Version("1")
        assert not (Version("1") > Version("2"))

    def test_major_version_jump(self):
        assert Version("2025.1.0") > Version("2024.12.31")

    def test_equal_after_padding(self):
        """2024.1 == 2024.1.0 after normalization."""
        assert not (Version("2024.1") > Version("2024.1.0"))

    def test_text_vs_number_priority(self):
        """Numeric segments are greater than text segments."""
        assert Version("2024.1") > Version("2024.a")

    def test_multiple_dash_segments(self):
        """Versions with dashes handled."""
        assert Version("2024.1.0") > Version("2024.1.0-alpha-2")

    def test_post_suffix_specific(self):
        assert Version("2024.1.0.post2") > Version("2024.1.0.post1")


# ── YtDlpManager: is_installed / current_version ─────────────────────────────


class TestYtDlpManagerInstalled:
    def test_is_installed_when_importable(self, monkeypatch):
        """is_installed returns True when yt_dlp is importable."""
        from yank.models.config import AppConfig

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        assert mgr.is_installed() is True

    def test_current_version_returns_string(self):
        """current_version returns a non-empty version string."""
        from yank.models.config import AppConfig

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        ver = mgr.current_version()
        assert isinstance(ver, str)
        assert len(ver) > 0
        assert ver != "not installed"

    def test_current_version_when_not_installed(self, monkeypatch):
        """current_version returns 'not installed' when not importable."""
        import builtins
        import importlib.metadata

        from yank.models.config import AppConfig

        monkeypatch.setattr(
            importlib.metadata,
            "version",
            lambda pkg: (_ for _ in ()).throw(importlib.metadata.PackageNotFoundError),
        )

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yt_dlp":
                raise ImportError("No module named 'yt_dlp'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        ver = mgr.current_version()
        assert ver == "not installed"

        assert Version("2024.1.0.post2") > Version("2024.1.0.post1")


# ── check_for_updates tests ──────────────────────────────────────────────────


class TestCheckForUpdates:
    def test_not_installed_returns_false(self, monkeypatch):
        """check_for_updates returns installed=False when yt-dlp missing."""
        import builtins

        from yank.models.config import AppConfig

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yt_dlp":
                raise ImportError("No module named 'yt_dlp'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        result = mgr.check_for_updates()
        assert result.installed is False
        assert "not installed" in result.message.lower()

    def test_update_available_when_newer(self, monkeypatch):
        """check_for_updates returns update_available=True when newer version exists."""
        from yank.models.config import AppConfig

        cfg = AppConfig(update_check_interval="always")
        cfg.last_update_check = 0
        mgr = YtDlpManager(cfg)

        def fake_fetch(self):
            return "9999.99.99", ""

        monkeypatch.setattr(
            "yank.engine.updater.YtDlpManager._fetch_latest_version",
            fake_fetch,
        )
        monkeypatch.setattr(
            "yank.engine.updater.save_config",
            lambda cfg, path=None: None,
        )

        result = mgr.check_for_updates(force=True)
        assert result.update_available is True
        assert result.latest_version == "9999.99.99"

    def test_up_to_date_when_same_version(self, monkeypatch):
        """check_for_updates returns update_available=False when same version."""
        from yank.models.config import AppConfig

        cfg = AppConfig(update_check_interval="always")
        cfg.last_update_check = 0
        mgr = YtDlpManager(cfg)

        current = mgr.current_version()

        def fake_fetch(self):
            return current, ""

        monkeypatch.setattr(
            "yank.engine.updater.YtDlpManager._fetch_latest_version",
            fake_fetch,
        )
        monkeypatch.setattr(
            "yank.engine.updater.save_config",
            lambda cfg, path=None: None,
        )

        result = mgr.check_for_updates(force=True)
        assert result.update_available is False
        assert "up to date" in result.message.lower()

    def test_never_interval_skips(self, monkeypatch):
        """check_for_updates with 'never' interval returns early."""
        from yank.models.config import AppConfig

        cfg = AppConfig(update_check_interval="never")
        mgr = YtDlpManager(cfg)
        result = mgr.check_for_updates()
        assert "disabled" in result.message.lower()
        assert result.update_available is False

    def test_fetch_error_returns_message(self, monkeypatch):
        """check_for_updates handles PyPI fetch errors gracefully."""
        from yank.models.config import AppConfig

        cfg = AppConfig(update_check_interval="always")
        cfg.last_update_check = 0
        mgr = YtDlpManager(cfg)

        def fake_fetch(self):
            return None, "Connection refused"

        monkeypatch.setattr(
            "yank.engine.updater.YtDlpManager._fetch_latest_version",
            fake_fetch,
        )
        monkeypatch.setattr(
            "yank.engine.updater.save_config",
            lambda cfg, path=None: None,
        )

        result = mgr.check_for_updates(force=True)
        assert result.error == "Connection refused"
        assert "could not check" in result.message.lower()


# ── ensure_installed tests ───────────────────────────────────────────────────


class TestEnsureInstalled:
    def test_already_installed_returns_true(self):
        """ensure_installed returns True when yt-dlp is already importable."""
        from yank.models.config import AppConfig

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        assert mgr.ensure_installed() is True

    def test_not_installed_attempts_pip(self, monkeypatch):
        """ensure_installed calls pip install when yt-dlp is not importable."""
        import builtins

        from yank.models.config import AppConfig

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yt_dlp":
                raise ImportError("No module named 'yt_dlp'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        def fake_pip_install(self, package, upgrade=False):
            return False, "pip not available"

        monkeypatch.setattr(
            "yank.engine.updater.YtDlpManager._pip_install",
            fake_pip_install,
        )

        statuses = []
        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        result = mgr.ensure_installed(on_status=lambda s: statuses.append(s))
        assert result is False
        assert len(statuses) >= 1


# ── should_check_on_startup tests ────────────────────────────────────────────


class TestShouldCheckOnStartup:
    def test_never_returns_false(self):
        from yank.models.config import AppConfig

        cfg = AppConfig(update_check_interval="never")
        mgr = YtDlpManager(cfg)
        assert mgr.should_check_on_startup() is False

    def test_always_returns_true(self):
        from yank.models.config import AppConfig

        cfg = AppConfig(update_check_interval="always")
        cfg.last_update_check = 0
        mgr = YtDlpManager(cfg)
        assert mgr.should_check_on_startup() is True

    def test_ask_within_24h_returns_false(self):
        import time

        from yank.models.config import AppConfig

        cfg = AppConfig(update_check_interval="ask")
        cfg.last_update_check = time.time()
        mgr = YtDlpManager(cfg)
        assert mgr.should_check_on_startup() is False


# ── _pip_install tests ───────────────────────────────────────────────────────


class TestPipInstall:
    def test_successful_install(self, monkeypatch):
        """_pip_install returns (True, message) on success."""
        import subprocess

        from yank.models.config import AppConfig

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, capture_output, text, timeout, check):
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        ok, msg = mgr._pip_install("yt-dlp")
        assert ok is True
        assert "installed" in msg.lower()

    def test_os_error(self, monkeypatch):
        """_pip_install handles OSError."""
        import subprocess

        from yank.models.config import AppConfig

        def fake_run(cmd, capture_output, text, timeout, check):
            raise OSError("No such file: pip")

        monkeypatch.setattr(subprocess, "run", fake_run)

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        ok, msg = mgr._pip_install("yt-dlp")
        assert ok is False
        assert "pip" in msg.lower()

    def test_upgrade_flag(self, monkeypatch):
        """_pip_install with upgrade=True adds -U flag."""
        import subprocess

        from yank.models.config import AppConfig

        captured_cmd = []

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, capture_output, text, timeout, check):
            captured_cmd.extend(cmd)
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        mgr._pip_install("yt-dlp", upgrade=True)
        assert "-U" in captured_cmd

    def test_failed_install(self, monkeypatch):
        """_pip_install returns (False, message) on failure."""
        import subprocess

        from yank.models.config import AppConfig

        class FakeResult:
            returncode = 1
            stdout = ""
            stderr = "ERROR: Could not find a version"

        def fake_run(cmd, capture_output, text, timeout, check):
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        ok, msg = mgr._pip_install("yt-dlp")
        assert ok is False
        assert len(msg) > 0

    def test_timeout_expired(self, monkeypatch):
        """_pip_install handles subprocess.TimeoutExpired."""
        import subprocess

        from yank.models.config import AppConfig

        def fake_run(cmd, capture_output, text, timeout, check):
            raise subprocess.TimeoutExpired(cmd="pip", timeout=180)

        monkeypatch.setattr(subprocess, "run", fake_run)

        cfg = AppConfig()
        mgr = YtDlpManager(cfg)
        ok, msg = mgr._pip_install("yt-dlp")
        assert ok is False
        assert "timed out" in msg.lower()
