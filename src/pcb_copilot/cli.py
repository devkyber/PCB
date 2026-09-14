"""Command-line entry point for PCB Copilot."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pcb_copilot import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pcb-copilot")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(f"pcb-copilot {__version__}")
    else:
        parser.print_help()
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
