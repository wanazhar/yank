"""Shared CSS constants used across all screens and widgets.

Import from here to avoid duplicating Input, DataTable, Button, and other
common styling rules in every screen file.
"""

from yank.constants import MAX_CONTENT_WIDTH

# ── Screen / global base ────────────────────────────────────────────────────
SCREEN_BASE = """
Screen {
    background: #0a0a0f;
    color: #e2e8f0;
}
"""

# ── Header ──────────────────────────────────────────────────────────────────
HEADER = """
Header {
    dock: top;
    background: #0a0a0f;
    color: #a855f7;
    text-style: bold;
    padding: 0 1;
    height: 1;
}
"""

# ── Footer ──────────────────────────────────────────────────────────────────
FOOTER = """
Footer {
    dock: bottom;
    background: #0a0a0f;
    color: #64748b;
}
"""

# ── StatusBar (global / widget augment) ─────────────────────────────────────
STATUS_BAR = """
StatusBar {
    dock: bottom;
    background: #0a0a0f;
    color: #64748b;
    border-top: solid #a855f7;
    padding: 0 1;
    height: 1;
}
"""

# ── Flat buttons (no Textual “tall” 3D frame — that was the inner rectangle) ───
BUTTONS = """
Button {
    text-style: bold;
    color: #e2e8f0;
    background: #a855f7;
    border: block #9333ea;
    tint: transparent 0%;
    background-tint: transparent 0%;
    padding: 0 1;
    height: auto;
    min-height: 2;
    width: auto;
    min-width: 8;
    content-align: center middle;
    text-align: center;
}

Button:hover {
    background: #9333ea;
    border: block #a855f7;
}

Button.-primary {
    background: #7c3aed;
    color: #e2e8f0;
    border: block #6d28d9;
}

Button.-primary:hover {
    background: #6d28d9;
    border: block #7c3aed;
}

Button:focus {
    background-tint: transparent 0%;
    border: block #c084fc;
}

Button.-active {
    tint: transparent 0%;
}
"""

PHONE_BUTTONS = """
.-vp-phone Button {
    min-width: 7;
    min-height: 2;
    padding: 0 0;
}
.-vp-phone .set-profile-row,
.-vp-phone .set-ytdlp-row {
    align: center middle;
    width: 100%;
}
.-vp-phone .set-profile-row Button,
.-vp-phone .set-ytdlp-row Button {
    width: auto;
    min-width: 11;
}
"""

# ── Input fields ────────────────────────────────────────────────────────────
INPUTS = """
Input {
    border: solid #06b6d4;
    background: #0a0a0f;
    color: #e2e8f0;
    padding: 0 1;
}

Input:focus {
    border: solid #06b6d4;
    background: #0a0a0f;
}
"""

# ── DataTable (global / widget) ─────────────────────────────────────────────
DATA_TABLE = """
DataTable {
    background: #0a0a0f;
}

DataTable > .datatable--header {
    background: #0a0a0f;
    color: #06b6d4;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #a855f7 40%;
    border: solid #06b6d4;
}
"""

# ── ProgressBar ─────────────────────────────────────────────────────────────
PROGRESS_BAR = """
ProgressBar {
    background: #1a1a2e;
    color: #a855f7;
}

ProgressBar.complete {
    color: #22c55e;
}
"""

# ── Scroll containers ───────────────────────────────────────────────────────
SCROLL = f"""
VerticalScroll, HorizontalScroll {{
    max-width: {MAX_CONTENT_WIDTH};
}}
"""

# ── Action-row buttons (shared by queue/history/download) ───────────────────
ACTION_BUTTONS = """
#q-actions Button, #hist-actions Button, #dl-actions Button,
#opt-actions Button, #set-actions Button, #fmt-actions Button {
    margin-right: 1;
}
"""

# ── Full shared bundle (used by YankApp.CSS) ────────────────────────────────
THEME_LIGHT = """
.theme-light {
    background: #f8fafc;
    color: #0f172a;
}
.theme-light Screen {
    background: #f8fafc;
    color: #0f172a;
}
.theme-light Header {
    background: #f8fafc;
    color: #7c3aed;
}
.theme-light Footer {
    background: #f8fafc;
    color: #475569;
}
.theme-light Input, .theme-light TextArea {
    background: #ffffff;
    color: #0f172a;
    border: solid #7c3aed;
}
"""

COMPACT_MODE = """
.compact-mode Screen { padding: 0; }
"""

HIGH_CONTRAST = """
.high-contrast { background: #000000; color: #ffffff; }
.high-contrast Screen { background: #000000; color: #ffffff; }
.high-contrast Button { background: #ffffff; color: #000000; border: solid #ffffff; }
"""

# Fluid panels: same chrome everywhere, sized to the terminal (no alternate layouts).
FIT_WINDOW = """
#quit-dialog, #welcome-dialog, #help-dialog, #log-dialog {
    width: 1fr;
    max-width: 100%;
}
"""

PHONE_SHELL = """
SettingsScreen.-vp-phone #set-body,
OptionsScreen.-vp-phone #opt-body,
QueueScreen.-vp-phone #q-body,
HistoryScreen.-vp-phone #hist-body {
    height: 1fr;
    layout: vertical;
}
SettingsScreen.-vp-phone #set-scroll,
OptionsScreen.-vp-phone #opt-scroll {
    height: 1fr;
    min-height: 1;
    padding: 0 1;
}
SettingsScreen #set-actions {
    layout: vertical;
    height: auto;
}
SettingsScreen .set-actions-row {
    width: 100%;
    height: auto;
    layout: horizontal;
}
SettingsScreen .set-actions-row,
SettingsScreen .set-profile-row,
SettingsScreen .set-ytdlp-row {
    height: auto;
    align: left middle;
}
SettingsScreen .set-actions-row Button,
SettingsScreen .set-profile-row Button,
SettingsScreen .set-ytdlp-row Button {
    width: 1fr;
    min-width: 0;
    margin: 0 1 1 0;
}
SettingsScreen #set-self-update {
    width: 1fr;
    min-width: 0;
    margin-bottom: 1;
}
SettingsScreen #set-profile-row {
    width: 100%;
    height: auto;
    layout: horizontal;
    margin-bottom: 0;
}
SettingsScreen #set-ytdlp-box {
    margin-top: 1;
    padding: 0 1;
}
SettingsScreen .set-ytdlp-row {
    width: 100%;
    height: auto;
    layout: horizontal;
}
SettingsScreen.-vp-phone #set-actions {
    padding: 0 1;
    width: 100%;
}
SettingsScreen.-vp-phone .set-label {
    margin-top: 0;
}
SettingsScreen.-vp-phone #set-self-update {
    width: 100%;
    margin-bottom: 0;
}
"""

APP_CSS = (
    SCREEN_BASE
    + HEADER
    + FOOTER
    + STATUS_BAR
    + BUTTONS
    + PHONE_BUTTONS
    + SCROLL
    + INPUTS
    + DATA_TABLE
    + PROGRESS_BAR
    + ACTION_BUTTONS
    + THEME_LIGHT
    + COMPACT_MODE
    + HIGH_CONTRAST
    + FIT_WINDOW
    + PHONE_SHELL
)
