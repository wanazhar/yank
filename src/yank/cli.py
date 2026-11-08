"""Top-level yank CLI: TUI (default) or ``connect`` subcommand."""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "connect":
        from yank.connect.cli import main as connect_main

        connect_main(sys.argv[2:])
        return

    from yank.app import YankApp

    app = YankApp()
    app.run()
