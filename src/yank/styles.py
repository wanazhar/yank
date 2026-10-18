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

# ── Buttons ─────────────────────────────────────────────────────────────────
BUTTONS = """
Button {
    background: #a855f7;
    color: #e2e8f0;
    padding: 0 2;
    border: solid #a855f7;
}

Button:hover {
    background: #9333ea;
    border: solid #9333ea;
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
.compact-mode Button { padding: 0 1; }
"""

HIGH_CONTRAST = """
.high-contrast { background: #000000; color: #ffffff; }
.high-contrast Screen { background: #000000; color: #ffffff; }
.high-contrast Button { background: #ffffff; color: #000000; border: solid #ffffff; }
"""

APP_CSS = (
    SCREEN_BASE
    + HEADER
    + FOOTER
    + STATUS_BAR
    + BUTTONS
    + SCROLL
    + INPUTS
    + DATA_TABLE
    + PROGRESS_BAR
    + THEME_LIGHT
    + COMPACT_MODE
    + HIGH_CONTRAST
)
