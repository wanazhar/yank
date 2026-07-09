Read STYLE.md for the full visual specification. Apply the complete UI overhaul by editing these files:

1. **src/yank/app.py** — Add/update YankApp.CSS with:
   - Dark background (#0a0a0f), purple (#a855f7) primary, cyan (#06b6d4) secondary, pink (#ec4899) tertiary
   - Text: warm white (#e2e8f0), muted: purple-tinted (#7c3aed blended with gray)
   - Header bar: thin, 'yank' in purple left, screen name right
   - Status bar bottom: muted colors, thin separators
   - Max content width 120 chars, centered
   - Global transition 200ms on hover/state changes
   - Button border-radius, purple primary buttons

2. **src/yank/screens/url_input.py** — Add ASCII art logo at top using pyfiglet with 'slant' font, colored purple. Below it "yt-dlp TUI wrapper" in dim text. The URL input field should have a subtle cyan glow on focus.

3. **src/yank/widgets/progress.py** — Redesign DownloadProgressBar:
   - Segmented bar: filled portion purple→cyan gradient (or as close as terminal supports), empty portion very dim
   - Show "⚡ speed" and "⏱ eta" text
   - Color-code speed: green when fast (>5MB/s), yellow medium, red slow
   - On complete: green bar with ✔

4. **src/yank/widgets/format_table.py** — Purple selection highlight, alternating row backgrounds (3% brightness difference), cyan headers

5. **src/yank/widgets/status_bar.py** — Muted colors, thin separator lines, shows active/queued count + yt-dlp version

6. **All screens** — Consistent padding, section headers in uppercase muted purple with cyan underline, clean spacing

After each file change, run: python3 -c "from yank.app import YankApp; print('OK')" to verify imports. If it fails, fix immediately. Keep going until the import check passes.