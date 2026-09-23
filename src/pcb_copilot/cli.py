"""Command-line entry point for PCB Copilot."""

from __future__ import annotations

import argparse
import json
import sys
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
    update_parser = subparsers.add_parser('update-schematic', help='preview or apply the current schematic')
    update_parser.add_argument('project_path', type=Path)
    update_parser.add_argument('--intent', required=True, type=Path)
    update_parser.add_argument('--apply', action='store_true')
    update_parser.add_argument('--reconcile-board-names', action='store_true')
    update_parser.add_argument('--pcb', type=Path, help='matching routed PCB for an atomic circuit change')
    current_review_parser = subparsers.add_parser('review', help='check the current root design without changing it')
    current_review_parser.add_argument('project_path', type=Path)
    current_review_parser.add_argument('--format', choices=('text', 'json', 'markdown'), default='text')
    current_review_parser.add_argument('--output', type=Path)
    signoff_parser = subparsers.add_parser('prepare-signoff', help='create an unsigned current-design review worksheet')
    signoff_parser.add_argument('project_path', type=Path)
    layout_parser = subparsers.add_parser('update-layout', help='preview or apply a checked current layout')
    layout_parser.add_argument('project_path', type=Path)
    source = layout_parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--intent', type=Path)
    source.add_argument('--candidate', type=Path, help='an already edited/routed KiCad board')
    layout_parser.add_argument('--route', choices=['human', 'critical_only', 'candidate_all'])
    layout_parser.add_argument('--apply', action='store_true')
    release_parser = subparsers.add_parser('release', help='review and export the exact current design')
    release_parser.add_argument('project_path', type=Path)
    research_parser = subparsers.add_parser(
        "research", help="verify, archive, or extract cited project evidence"
    )
    research_parser.add_argument("project_path", type=Path)
    operation = research_parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--verify", action="store_true")
    operation.add_argument("--add", nargs=2, metavar=("PART", "URL"))
    operation.add_argument("--extract", metavar="PART")
    operation.add_argument('--inspect-reference', nargs=2, metavar=('SCHEMATIC_ID', 'PCB_ID'))
    operation.add_argument('--search-plan', metavar='PART')
    research_parser.add_argument(
        "--role", choices=[item.value for item in EvidenceRole]
    )
    research_parser.add_argument(
        "--trust-tier",
        choices=[item.value for item in TrustTier],
        default=TrustTier.MANUFACTURER.value,
    )
    parts_parser = subparsers.add_parser('parts', help='look up or import exact LCSC supplier parts')
    parts_parser.add_argument('project_path', type=Path)
    part_operation = parts_parser.add_mutually_exclusive_group(required=True)
    part_operation.add_argument('--lookup', metavar='C_NUMBER')
    part_operation.add_argument('--import', dest='import_lcsc', metavar='C_NUMBER')
    parts_parser.add_argument('--mpn', help='expected manufacturer part number, required for import')
    args = parser.parse_args(argv)

    if args.version:
        print(f"pcb-copilot {__version__}")
    elif args.command == 'parts':
        from pcb_copilot.parts import import_part, lookup_part

        try:
            project = load_project(args.project_path)
            if args.import_lcsc:
                if not args.mpn:
                    parser.error('parts --import requires --mpn to check the exact part identity')
                result = import_part(project, args.import_lcsc, args.mpn, downloader=downloader)
            else:
                result, _, _ = lookup_part(args.lookup, downloader=downloader)
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
    elif args.command == "status":
        try:
            project = load_project(args.project_path)
        except ProjectFormatError as exc:
            parser.error(str(exc))
        print(render_status(collect_status(project)))
    elif args.command == 'update-schematic':
        from pcb_copilot.schematic.update import update_schematic
        from pcb_copilot.toolchain import ToolchainDiscoveryError

        try:
            result = update_schematic(
                load_project(args.project_path), args.intent, args.apply,
                reconcile_names=args.reconcile_board_names,
                pcb_candidate=args.pcb,
            )
        except (ValueError, OSError, RuntimeError, ToolchainDiscoveryError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return result['exit_code']
    elif args.command == 'review':
        from pcb_copilot.review.commands import (
            render_review_json,
            render_review_markdown,
            render_review_text,
            review_project,
            write_review_report,
        )

        try:
            report = review_project(load_project(args.project_path))
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        rendered = {
            'json': render_review_json,
            'markdown': render_review_markdown,
            'text': render_review_text,
        }[args.format](report)
        if args.output:
            try:
                print(write_review_report(load_project(args.project_path), args.output, rendered))
            except (ValueError, OSError) as exc:
                parser.error(str(exc))
        else:
            print(rendered)
        return int(report.blocking)
    elif args.command == 'prepare-signoff':
        from pcb_copilot.review.signoff import prepare_signoff

        try:
            path = prepare_signoff(load_project(args.project_path))
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(f'Unsigned review worksheet: {path}')
        return 0
    elif args.command == 'update-layout':
        from pcb_copilot.layout.update import update_layout
        try:
            result = update_layout(load_project(args.project_path), args.intent, args.apply,
                                   candidate=args.candidate, route=args.route)
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return result['exit_code']
    elif args.command == 'release':
        from pcb_copilot.release import release_project
        try:
            result = release_project(load_project(args.project_path))
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return result['exit_code']
    elif args.command == "research":
        try:
            project = load_project(args.project_path)
        except ProjectFormatError as exc:
            parser.error(str(exc))
        if args.search_plan:
            from pcb_copilot.evidence.references import reference_search_plan

            print(json.dumps(reference_search_plan(args.search_plan), indent=2))
            return 0
        if args.inspect_reference:
            from pcb_copilot.evidence.commands import inspect_reference_pair

            try:
                inspection = inspect_reference_pair(project, *args.inspect_reference)
            except (ValueError, OSError) as exc:
                parser.error(str(exc))
            print(json.dumps(inspection, indent=2))
            return int(bool(inspection['mismatches']))
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
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
