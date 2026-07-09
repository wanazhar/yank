# Yank UI Overhaul — visual specification

## Design system

- **Background:** Very dark, almost black (#0a0a0f) — not terminal black (#000)
- **Accent gradient:** Deep purple → cyan (or purple → magenta → pink)
  - Primary: #a855f7 (purple)
  - Secondary: #06b6d4 (cyan)
  - Tertiary: #ec4899 (pink)
- **Text:** Warm white (#e2e8f0) with purple-tinted muted (#64748b → #7c3aed blended)
- **Borders:** Subtle 1px with accent color at 30% opacity
- **Selection highlight:** Purple background at 40% opacity + cyan border

## ASCII art logo

On the URL input screen, show a stylized ASCII "yank" logo at the top (not every screen — just the home screen):

```
    ██╗   ╔██╗   ╔██╗   ██╗   ██╗   ██╗
    ██║   ╚██╗   ╚██╗   ██║   ██║   ██║
    ██║   ██╔╝   ██╔╝   ██║   ██║   ██║
    ╚═╝   ╚═╝    ╚═╝    ╚═╝   ╚═╝    ╚═╝
```

(Or something better — use pyfiglet to generate a clean FIGlet in a rounded/slanted font like "Standard" or "Small Slant", colored in gradient cyan→purple)

## Loading / spinners

Replace all default Textual loading indicators with custom ones:
- **Idle / waiting:** A slow-pulsing cyan dot ⋆
- **Fetching formats:** A spinning helix of characters: `⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏` in purple
- **Downloading:** A pulsing bar that shifts color as speed changes:
  - Fast: cyan → green gradient
  - Normal: purple
  - Slow: magenta → pink
- **Completed:** Display a checkmark ✔ in green with a subtle pulse animation

## Progress bar redesign

Instead of a plain progress bar, use a segmented approach:
```
[████████████████░░░░░░░░░░] 45% ⚡ 2.3 MB/s ⏱ 1:23
```
- The filled portion uses the accent gradient (purple→cyan)
- The unfilled portion is very dim (dark gray, almost invisible)
- The percentage counter is bold cyan
- Speed is updated every 0.5s with color coding (green when fast, yellow when medium, red when slow)
- When complete, the entire bar turns green with a brief glow effect (transition)

## Transitions and animations

- Screen transitions: brief (200ms) fade in — use Textual's built-in CSS `transition` property
- When a download starts, the item should slide into the download list with a brief animation
- Status bar updates should be smooth (no flickering)
- Button hover/press states: subtle color shift with 150ms transition
- Error states: brief red border flash on the affected widget (500ms then fade)

## Spacing and typography

- Maximum content width: 120 characters (centered on wider terminals)
- Section headers: bold, uppercase, in muted purple, with a thin cyan line underneath
- URL input: a clean text field with a subtle glow on focus (cyan border)
- Format table: alternating row backgrounds (very subtle — 3% brightness difference)
- Buttons: rounded corners (border-radius), padding, colored text on dark background
  - Primary buttons: purple background
  - Danger buttons: red background
  - Download button: gradient purple→cyan background

## Layout structure (all screens)

Common elements on every screen:
1. **Header bar** (thin): "yank" in small purple text on the left, current screen name on the right
2. **Content area:** fills the middle
3. **Status bar** (bottom): shows active downloads count, disk space, yt-dlp version — styled with muted colors and thin separator lines

## CSS implementation

All styles should be in-app CSS (Textual CSS files or inline in `app.py`), not external files. Use Textual's built-in CSS features:
- `color`, `background`, `border`, `border-solid`, `border-thick`, `border-round`
- `transition` for smooth hover/state changes
- `opacity` for fading elements
- `padding`, `margin`, `width`, `height` for layout control
- `text-style` for bold/italic
- `min-width` / `max-width` to keep things readable on wide terminals

The app should look good whether it's 80 columns wide or 180. Don't hardcode widths — use percentages where possible.

## What NOT to do

- No blinking text (it's 2026, not 1996)
- No excessive animations that slow down interaction
- No emoji as the only indicator (ASCII/unicode works everywhere)
- No 3D/glow effects (terminal can't do them well)
- Keep it readable — contrast ratios matter even in a terminal