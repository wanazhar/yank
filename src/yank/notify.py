"""Desktop notification helper using platform-native commands."""

from __future__ import annotations

import os
import platform
import subprocess

from yank.logging import get_logger

_logger = get_logger(__name__)


def send_notification(title: str, body: str = "") -> bool:
    """Send a desktop notification using the platform's native mechanism.

    Returns ``True`` if the notification was sent successfully, ``False``
    otherwise (e.g. command not found or non-zero exit code).
    """
    system = platform.system()

    if system == "Linux":
        return _notify_linux(title, body)
    elif system == "Darwin":
        return _notify_macos(title, body)
    elif system == "Windows":
        return _notify_windows(title, body)
    else:
        _logger.debug("Unsupported platform for desktop notifications: %s", system)
        return False


def _notify_linux(title: str, body: str) -> bool:
    """Use ``notify-send`` (part of libnotify)."""
    try:
        cmd = ["notify-send", title, body]
        subprocess.run(cmd, timeout=5, check=True, capture_output=True)
        return True
    except FileNotFoundError:
        _logger.debug("notify-send not found; desktop notification skipped")
        return False
    except Exception:
        _logger.debug("notify-send failed", exc_info=True)
        return False


def _notify_macos(title: str, body: str) -> bool:
    """Use ``osascript`` to display a notification on macOS."""
    script = f'display notification "{_escape_applescript(body)}" with title "{_escape_applescript(title)}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            timeout=5,
            check=True,
            capture_output=True,
        )
        return True
    except FileNotFoundError:
        _logger.debug("osascript not found; desktop notification skipped")
        return False
    except Exception:
        _logger.debug("osascript notification failed", exc_info=True)
        return False


def _notify_windows(title: str, body: str) -> bool:
    """Use PowerShell to show a balloon tip via Windows.UI.Notifications
    or fall back to ``msg`` / ``wscript``."""
    # Try PowerShell toast via BurntToast if available
    ps_script = (
        f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
        f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        f'$textNodes = $template.GetElementsByTagName("text"); '
        f'$textNodes.Item(0).AppendChild($template.CreateTextNode("{_escape_powershell(title)}")) > $null; '
        f'$textNodes.Item(1).AppendChild($template.CreateTextNode("{_escape_powershell(body)}")) > $null; '
        f"$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
        f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("yank").Show($toast)'
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            timeout=10,
            check=True,
            capture_output=True,
        )
        return True
    except FileNotFoundError:
        _logger.debug("powershell not found; desktop notification skipped")
        return False
    except Exception:
        # PowerShell toast failed; try a simple msg.exe as fallback
        try:
            subprocess.run(
                ["msg", os.environ.get("USERNAME", "*"), f"{title}: {body}"],
                timeout=5,
                check=True,
                capture_output=True,
            )
            return True
        except Exception:
            _logger.debug("All Windows notification methods failed", exc_info=True)
            return False


def _escape_applescript(s: str) -> str:
    """Escape a string for use inside an AppleScript string literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _escape_powershell(s: str) -> str:
    """Escape a string for use inside a PowerShell double-quoted string."""
    return (
        s.replace("`", "``")
        .replace('"', '`"')
        .replace("$", "`$")
        .replace("\n", " ")
        .replace("\r", " ")
    )
