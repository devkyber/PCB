"""Command-line entry point for PCB Copilot."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from pcb_copilot import __version__
from pcb_copilot.project import ProjectFormatError, load_project
from pcb_copilot.status import collect_status, render_status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pcb-copilot")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    status_parser = subparsers.add_parser("status", help="show read-only project status")
    status_parser.add_argument("project_path", type=Path)
    args = parser.parse_args(argv)

    if args.version:
        print(f"pcb-copilot {__version__}")
    elif args.command == "status":
        try:
            project = load_project(args.project_path)
        except ProjectFormatError as exc:
            parser.error(str(exc))
        print(render_status(collect_status(project)))
    else:
        parser.print_help()
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
