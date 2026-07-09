"""yt-dlp installation and update management."""

from __future__ import annotations

import importlib
import importlib.metadata
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

from yank.models.config import AppConfig, save_config

TWENTY_FOUR_HOURS = 24 * 3600


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
            if interval == "ask" and elapsed < TWENTY_FOUR_HOURS:
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

        update_available = bool(latest) and _version_is_newer(latest, current)
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
        return elapsed >= TWENTY_FOUR_HOURS

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
                timeout=180,
                check=False,
            )
            if result.returncode == 0:
                return True, f"{'Updated' if upgrade else 'Installed'} {package}."
            err = (result.stderr or result.stdout or "pip failed").strip()
            # Prefer last non-empty line
            lines = [ln for ln in err.splitlines() if ln.strip()]
            short = lines[-1] if lines else "pip install failed."
            if len(short) > 200:
                short = short[:197] + "..."
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
            return None, str(exc)[:200]


def _version_is_newer(latest: str, current: str) -> bool:
    """Compare version strings; return True if latest > current."""
    def parts(v: str) -> list[int | str]:
        out: list[int | str] = []
        for chunk in v.replace("-", ".").split("."):
            if chunk.isdigit():
                out.append(int(chunk))
            else:
                # split digits and text
                buf = ""
                for ch in chunk:
                    if ch.isdigit():
                        if buf and not buf.isdigit():
                            out.append(buf)
                            buf = ""
                        buf += ch
                    else:
                        if buf and buf.isdigit():
                            out.append(int(buf))
                            buf = ""
                        buf += ch
                if buf:
                    out.append(int(buf) if buf.isdigit() else buf)
        return out

    try:
        a = parts(latest)
        b = parts(current)
        # Pad
        n = max(len(a), len(b))
        a.extend([0] * (n - len(a)))
        b.extend([0] * (n - len(b)))
        for x, y in zip(a, b):
            if type(x) is type(y):
                if x > y:  # type: ignore[operator]
                    return True
                if x < y:  # type: ignore[operator]
                    return False
            else:
                # int > str for simplicity
                if isinstance(x, int) and not isinstance(y, int):
                    return True
                if not isinstance(x, int) and isinstance(y, int):
                    return False
        return False
    except Exception:
        return latest != current
