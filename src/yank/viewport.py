"""Fit the standard URL screen into fixed Termius / Herdr pane sizes (no scrollbars).

Validated canvas sizes (``stty``):
- Termius SSH: 58x30
- Herdr pane on the same phone: 57x28
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

import pyfiglet
from textual.dom import DOMNode

if TYPE_CHECKING:
    from textual.screen import Screen

# Header + footer within the screen (status bar is docked on the app).
SCREEN_CHROME_ROWS = 2

# ``stty`` sizes reported on iOS Termius (user-measured).
TERMius_COLS = 58
TERMius_ROWS = 30
HERDR_COLS = 57
HERDR_ROWS = 28


def in_herdr_pane() -> bool:
    return os.environ.get("HERDR_ENV", "").strip() == "1"


def is_phone_canvas(width: int, height: int) -> bool:
    """Termius phone canvas (direct SSH or nested Herdr pane)."""
    return width <= TERMius_COLS and height <= TERMius_ROWS


def is_herdr_canvas(width: int, height: int, *, in_herdr: bool) -> bool:
    """Tighter layout for the smaller Herdr pane and its inner borders."""
    if in_herdr:
        return True
    return width <= HERDR_COLS and height <= HERDR_ROWS


def fit_height_slack(*, herdr: bool) -> int:
    """Extra rows reserved so round borders + status bar do not clip the panel."""
    return 3 if herdr else 1


def content_body_rows(term_height: int) -> int:
    return max(8, term_height - SCREEN_CHROME_ROWS)


def logo_font_for_tier(tier: int, width: int, *, phone: bool, herdr: bool = False) -> str | None:
    """ASCII font for density tier; ``None`` uses a one-line wordmark on phone/Herdr."""
    if tier <= 0:
        return None
    if phone or herdr:
        return None
    if tier == 1:
        return "mini" if width < 60 else "small"
    if tier == 2:
        return "small" if width < 80 else "standard"
    if width >= 90:
        return "slant"
    if width >= 55:
        return "standard"
    return "small"


def logo_line_count(font: str | None) -> int:
    if font is None:
        return 0
    try:
        text = pyfiglet.figlet_format("yank", font=font)
    except Exception:
        return 0
    return len(text.splitlines())


def wordmark_line() -> str:
    return " yank "


@lru_cache(maxsize=8)
def figlet_yank(font: str) -> str:
    try:
        return pyfiglet.figlet_format("yank", font=font)
    except Exception:
        return wordmark_line()


def apply_screen_viewport(screen: Screen) -> None:
    """Toggle shared ``-vp-phone`` / ``-vp-herdr`` classes from terminal size."""
    size = screen.app.size
    phone = is_phone_canvas(size.width, size.height)
    herdr = is_herdr_canvas(size.width, size.height, in_herdr=in_herdr_pane())
    screen.set_class(phone, "-vp-phone")
    screen.set_class(herdr, "-vp-herdr")


FIT_CLASS_PREFIX = "-vf-"


def fit_tier_class(tier: int) -> str:
    return f"{FIT_CLASS_PREFIX}{tier}"


def all_fit_tier_classes() -> list[str]:
    return [fit_tier_class(t) for t in range(4)]


def sync_fit_tier_classes(node: DOMNode, tier: int) -> None:
    """Set exactly one ``-vf-N`` class on a DOM node."""
    mapping = {name: name == fit_tier_class(tier) for name in all_fit_tier_classes()}
    node.update_classes(mapping, animate=False)


def phone_button_labels(batch_mode: bool) -> dict[str, str]:
    """Short labels so three buttons stay on one row at 57-58 columns."""
    return {
        "btn-continue": "Continue",
        "btn-batch": "Single" if batch_mode else "Batch",
        "btn-clear": "Clear",
        "btn-queue": "Queue",
        "btn-history": "History",
        "btn-settings": "Settings",
    }


PHONE_SETTINGS_LABELS: dict[str, str] = {
    "btn-self-update": "App update",
    "btn-save-profile": "Save prof",
    "btn-load-profile": "Load prof",
    "btn-check-update": "Check",
    "btn-update": "Update",
    "btn-install": "Install",
    "btn-save": "Save",
    "btn-log": "Log",
    "btn-health": "Health",
    "btn-backup": "Backup",
    "btn-restore": "Restore",
    "btn-diagnostics": "Diag",
    "btn-back": "Back",
}

DESKTOP_SETTINGS_LABELS: dict[str, str] = {
    "btn-self-update": "Update yank itself",
    "btn-save-profile": "Save profile",
    "btn-load-profile": "Load profile",
    "btn-check-update": "Check for updates",
    "btn-update": "Update yt-dlp",
    "btn-install": "Install yt-dlp",
    "btn-save": "Save",
    "btn-log": "View log",
    "btn-health": "Health check",
    "btn-backup": "Backup",
    "btn-restore": "Restore",
    "btn-diagnostics": "Diagnostics",
    "btn-back": "Back",
}
