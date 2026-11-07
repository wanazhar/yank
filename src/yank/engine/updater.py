"""yt-dlp installation and update management."""

from __future__ import annotations

import importlib
import importlib.metadata
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from packaging.version import Version

from yank.constants import ERROR_MSG_MAX_LEN, PIP_TIMEOUT, SECONDS_PER_DAY
from yank.logging import get_logger
from yank.models.config import AppConfig, save_config

_logger = get_logger(__name__)


@dataclass
class UpdateCheckResult:
    installed: bool
    current_version: str
    update_available: bool
    latest_version: str = ""
    message: str = ""
    error: str = ""


class YtDlpManager:
    """Manage yt-dlp as a pip dependency: detect, install, update."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def is_installed(self) -> bool:
        try:
            import yt_dlp  # noqa: F401

            return True
        except ImportError:
            return False

    def current_version(self) -> str:
        try:
            return importlib.metadata.version("yt-dlp")
        except importlib.metadata.PackageNotFoundError:
            pass
        try:
            import yt_dlp

            ver = getattr(yt_dlp, "version", None)
            if ver is not None:
                return str(getattr(ver, "__version__", ver))
        except ImportError:
            pass
        return "not installed"

    def ensure_installed(
        self,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> bool:
        """
        Ensure yt-dlp is importable. Install via pip if missing.
        Returns True if available after this call.
        """
        if self.is_installed():
            return True
        if on_status:
            on_status("Installing yt-dlp…")
        ok, msg = self._pip_install("yt-dlp")
        if on_status:
            on_status(msg)
        if not ok:
            return False
        # Invalidate import caches and force re-check
        importlib.invalidate_caches()
        return self.is_installed()

    def check_for_updates(self, *, force: bool = False) -> UpdateCheckResult:
        """
        Check whether a newer yt-dlp is available on PyPI.

        Respects config.update_check_interval unless *force*.
        Updates config.last_update_check.
        """
        installed = self.is_installed()
        current = self.current_version() if installed else "not installed"

        if not installed:
            return UpdateCheckResult(
                installed=False,
                current_version=current,
                update_available=False,
                message="yt-dlp is not installed.",
            )

        if not force:
            interval = self.config.update_check_interval
            if interval == "never":
                return UpdateCheckResult(
                    installed=True,
                    current_version=current,
                    update_available=False,
                    message="Update checks disabled.",
                )
            elapsed = time.time() - (self.config.last_update_check or 0)
            if interval == "ask" and elapsed < SECONDS_PER_DAY:
                return UpdateCheckResult(
                    installed=True,
                    current_version=current,
                    update_available=False,
                    message="Checked recently.",
                )
            if interval == "always" and elapsed < 3600:
                # Don't hammer PyPI more than hourly even on "always"
                return UpdateCheckResult(
                    installed=True,
                    current_version=current,
                    update_available=False,
                    message="Checked recently.",
                )

        latest, err = self._fetch_latest_version()
        self.config.last_update_check = time.time()
        try:
            save_config(self.config)
        except OSError:
            pass

        if err:
            return UpdateCheckResult(
                installed=True,
                current_version=current,
                update_available=False,
                error=err,
                message="Could not check for updates.",
            )

        if latest:
            update_available = Version(latest) > Version(current)
        else:
            update_available = False
        msg = (
            f"Update available: {current} → {latest}"
            if update_available
            else f"yt-dlp {current} is up to date."
        )
        return UpdateCheckResult(
            installed=True,
            current_version=current,
            update_available=update_available,
            latest_version=latest or "",
            message=msg,
        )

    def update(
        self,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> tuple[bool, str]:
        """Run pip install -U yt-dlp. Returns (success, message)."""
        if on_status:
            on_status("Updating yt-dlp…")
        ok, msg = self._pip_install("yt-dlp", upgrade=True)
        importlib.invalidate_caches()
        new_ver = self.current_version()
        if ok:
            return True, f"yt-dlp updated to {new_ver}."
        return False, msg

    def should_check_on_startup(self) -> bool:
        interval = self.config.update_check_interval
        if interval == "never":
            return False
        if not self.is_installed():
            return True
        elapsed = time.time() - (self.config.last_update_check or 0)
        return elapsed >= SECONDS_PER_DAY

    # ── Internals ───────────────────────────────────────────────────────────

    def _pip_install(self, package: str, *, upgrade: bool = False) -> tuple[bool, str]:
        cmd = [sys.executable, "-m", "pip", "install"]
        if upgrade:
            cmd.append("-U")
        cmd.append(package)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=PIP_TIMEOUT,
                check=False,
            )
            if result.returncode == 0:
                return True, f"{'Updated' if upgrade else 'Installed'} {package}."
            err = (result.stderr or result.stdout or "pip failed").strip()
            # Prefer last non-empty line
            lines = [ln for ln in err.splitlines() if ln.strip()]
            short = lines[-1] if lines else "pip install failed."
            if len(short) > ERROR_MSG_MAX_LEN:
                short = short[: ERROR_MSG_MAX_LEN - 3] + "..."
            return False, short
        except subprocess.TimeoutExpired:
            return False, "pip install timed out."
        except OSError as exc:
            return False, f"Could not run pip: {exc}"

    def _fetch_latest_version(self) -> tuple[str | None, str]:
        """Query PyPI JSON API for the latest yt-dlp version."""
        try:
            import json
            import urllib.request

            req = urllib.request.Request(
                "https://pypi.org/pypi/yt-dlp/json",
                headers={"User-Agent": "yank/0.1"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            ver = data.get("info", {}).get("version")
            if ver:
                return str(ver), ""
            return None, "Unexpected PyPI response."
        except Exception as exc:
            return None, str(exc)[:ERROR_MSG_MAX_LEN]


class SelfUpdater:
    """Check for and install updates to yank itself via pip."""

    PACKAGE = "yank-tui"

    def __init__(self) -> None:
        self._current = _yank_version()

    def current_version(self) -> str:
        return self._current

    def check_for_updates(self) -> tuple[bool, str, str]:
        """Return (update_available, latest_version, message)."""
        try:
            import json
            import urllib.request

            req = urllib.request.Request(
                f"https://pypi.org/pypi/{self.PACKAGE}/json",
                headers={"User-Agent": "yank-self-updater"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("info", {}).get("version", "")
            if not latest:
                return False, "", "Could not determine latest version."
            from packaging.version import Version

            update = Version(latest) > Version(self._current)
            msg = (
                f"Update available: {self._current} → {latest}" if update else "yank is up to date."
            )
            return update, latest, msg
        except Exception as exc:
            return False, "", f"Update check failed: {exc}"

    def update(self) -> tuple[bool, str]:
        import subprocess
        import sys

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", self.PACKAGE],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0:
                return True, "yank updated. Restart to apply."
            err = (result.stderr or result.stdout or "pip failed").strip()
            lines = [ln for ln in err.splitlines() if ln.strip()]
            short = lines[-1] if lines else "pip install failed."
            return False, short
        except Exception as exc:
            return False, str(exc)


def _yank_version() -> str:
    try:
        from yank import __version__

        return __version__
    except Exception:
        return "0.0.0"
