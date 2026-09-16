"""Command-line entry point for PCB Copilot."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from pcb_copilot import __version__
from pcb_copilot.evidence.commands import (
    Downloader,
    add_evidence,
    download_url,
    extract_evidence,
    render_research_result,
    verify_evidence,
)
from pcb_copilot.evidence.models import EvidenceRole, TrustTier
from pcb_copilot.project import ProjectFormatError, load_project
from pcb_copilot.status import collect_status, render_status


def main(
    argv: Sequence[str] | None = None,
    *,
    downloader: Downloader = download_url,
) -> int:
    parser = argparse.ArgumentParser(prog="pcb-copilot")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    status_parser = subparsers.add_parser("status", help="show read-only project status")
    status_parser.add_argument("project_path", type=Path)
    draft_parser = subparsers.add_parser('draft-schematic', help='create a schematic draft and review artifacts')
    draft_parser.add_argument('project_path', type=Path)
    draft_parser.add_argument('--intent', required=True, type=Path)
    accept_parser = subparsers.add_parser('accept', help='accept a reviewed schematic draft')
    accept_parser.add_argument('project_path', type=Path)
    accept_parser.add_argument('draft_id')
    research_parser = subparsers.add_parser(
        "research", help="verify, archive, or extract cited project evidence"
    )
    research_parser.add_argument("project_path", type=Path)
    operation = research_parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--verify", action="store_true")
    operation.add_argument("--add", nargs=2, metavar=("PART", "URL"))
    operation.add_argument("--extract", metavar="PART")
    research_parser.add_argument(
        "--role", choices=[item.value for item in EvidenceRole]
    )
    research_parser.add_argument(
        "--trust-tier",
        choices=[item.value for item in TrustTier],
        default=TrustTier.MANUFACTURER.value,
    )
    args = parser.parse_args(argv)

    if args.version:
        print(f"pcb-copilot {__version__}")
    elif args.command == "status":
        try:
            project = load_project(args.project_path)
        except ProjectFormatError as exc:
            parser.error(str(exc))
        print(render_status(collect_status(project)))
    elif args.command == 'accept':
        from pcb_copilot.accept import accept_schematic, load_draft

        try:
            project = load_project(args.project_path)
            draft = load_draft(project, args.draft_id)
            print(f'Accepting {draft.root} into {project.schematic_path}; '
                  f'base schematic {draft.base_schematic_hash}; base PCB {draft.base_pcb_hash}')
            result = accept_schematic(project, draft)
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(f'Accepted {result.accepted_path} ({result.accepted_hash}); '
              f'{result.lifecycle.value}')
    elif args.command == 'draft-schematic':
        from pcb_copilot.schematic.commands import draft_schematic
        from pcb_copilot.toolchain import ToolchainDiscoveryError

        try:
            result = draft_schematic(load_project(args.project_path), args.intent)
        except (ValueError, OSError, ToolchainDiscoveryError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return result['exit_code']
    elif args.command == "research":
        try:
            project = load_project(args.project_path)
        except ProjectFormatError as exc:
            parser.error(str(exc))
        if args.add:
            if not args.role:
                parser.error("--add requires --role")
            part_number, url = args.add
            result = add_evidence(
                project,
                part_number,
                url,
                EvidenceRole(args.role),
                downloader=downloader,
                trust_tier=TrustTier(args.trust_tier),
            )
        elif args.extract:
            result = extract_evidence(project, args.extract)
        else:
            result = verify_evidence(project)
        print(render_research_result(result))
        return result.exit_code
    else:
        parser.print_help()
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
