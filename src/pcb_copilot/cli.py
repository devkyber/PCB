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
    doctor_parser = subparsers.add_parser('doctor', help='probe required and optional tools without opening a project')
    doctor_parser.add_argument('--format', choices=('text', 'json'), default='text')
    status_parser = subparsers.add_parser("status", help="show read-only project status")
    status_parser.add_argument("project_path", type=Path)
    clean_parser = subparsers.add_parser(
        'clean', help='preview removal of reproducible project preview files'
    )
    clean_parser.add_argument('project_path', type=Path)
    clean_parser.add_argument('--apply', action='store_true')
    views_parser = subparsers.add_parser('views', help='export fresh source-bound assembly and copper SVGs')
    views_parser.add_argument('project_path', type=Path)
    update_parser = subparsers.add_parser('update-schematic', help='preview or apply the current schematic')
    update_parser.add_argument('project_path', type=Path)
    schematic_source = update_parser.add_mutually_exclusive_group(required=True)
    schematic_source.add_argument('--intent', type=Path)
    schematic_source.add_argument('--candidate', type=Path, help='owner-edited native root KiCad schematic and its child sheets')
    update_parser.add_argument('--apply', action='store_true')
    update_parser.add_argument('--reconcile-board-names', action='store_true')
    update_parser.add_argument('--pcb', type=Path, help='matching routed PCB for an atomic circuit change')
    current_review_parser = subparsers.add_parser('review', help='check the current root design without changing it')
    current_review_parser.add_argument('project_path', type=Path)
    current_review_parser.add_argument('--format', choices=('text', 'json', 'markdown'), default='text')
    current_review_parser.add_argument('--output', type=Path)
    report_parser = subparsers.add_parser('report', help='create a portable offline native review handover')
    report_parser.add_argument('project_path', type=Path)
    report_parser.add_argument('--output', type=Path, required=True, help='new directory outside the source project')
    verify_parser = subparsers.add_parser('verify-report', help='verify a saved handover without running native tools')
    verify_parser.add_argument('report_path', type=Path)
    verify_parser.add_argument('--project', type=Path, help='also compare current saved source input hashes')
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
    release_parser.add_argument('--quantity', type=int, default=1,
                                help='board count for fresh BOM stock checks (default: 1; no attrition allowance)')
    release_parser.add_argument('--preview', action='store_true',
                                help='prepare JLCPCB upload/review files without granting fabrication release')
    research_parser = subparsers.add_parser(
        "research", help="verify, archive, or extract cited project evidence"
    )
    research_parser.add_argument("project_path", type=Path)
    operation = research_parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--verify", action="store_true")
    operation.add_argument('--verify-schematic-parts', action='store_true',
                           help='verify selected-part evidence for every purchased schematic part, including passives')
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
    elif args.command == 'doctor':
        from pcb_copilot.doctor import collect_doctor, render_doctor

        report = collect_doctor()
        print(json.dumps(report, indent=2) if args.format == 'json' else render_doctor(report))
        return int(not report['ready'])
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
    elif args.command == 'views':
        from pcb_copilot.review.views import export_review_views

        try:
            path = export_review_views(load_project(args.project_path))
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(path)
        return 0
    elif args.command == 'clean':
        from pcb_copilot.cleanup import clean_project

        try:
            result = clean_project(load_project(args.project_path), apply=args.apply)
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return 0
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
            if args.candidate:
                if args.reconcile_board_names:
                    raise ValueError('--reconcile-board-names is supported only with --intent')
                from pcb_copilot.schematic.native_candidate import (
                    update_native_schematic,
                )

                result = update_native_schematic(load_project(args.project_path), args.candidate,
                                                 args.apply, pcb_candidate=args.pcb)
            else:
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
    elif args.command in {'report', 'verify-report'}:
        from pcb_copilot.review.report import create_report, verify_report

        try:
            if args.command == 'report':
                result = create_report(load_project(args.project_path), args.output)
            else:
                result = verify_report(args.report_path, load_project(args.project) if args.project else None)
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return result['exit_code']
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
            result = release_project(load_project(args.project_path), preview=args.preview, quantity=args.quantity)
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
        elif args.verify_schematic_parts:
            from pcb_copilot.evidence.commands import verify_schematic_evidence

            result = verify_schematic_evidence(project)
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
