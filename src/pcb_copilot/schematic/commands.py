"""Orchestrate evidence-linked schematic drafts and their review artifacts."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

from pcb_copilot.accept import (
    assert_draft_base_current,
    load_draft,
    review_draft_command,
    validate_schematic_draft,
)
from pcb_copilot.drafts import create_draft
from pcb_copilot.evidence.checks import Finding, check_evidence
from pcb_copilot.evidence.index import EvidenceFormatError, load_evidence_index
from pcb_copilot.models import DraftKind, DraftRecord, Project
from pcb_copilot.schematic.io import load_schematic_intent, save_schematic_intent
from pcb_copilot.schematic.models import SchematicIntent
from pcb_copilot.schematic.netlist import normalize_intent_netmap
from pcb_copilot.schematic.preview import (
    render_schematic_preview,
    schematic_files,
)
from pcb_copilot.schematic.render import render_schematic_draft
from pcb_copilot.state import file_digest
from pcb_copilot.toolchain import ToolchainPaths, discover_toolchain


def draft_schematic(project: Project, intent_path: Path) -> dict:
    intent = load_schematic_intent(intent_path)
    toolchain = discover_toolchain(Path(__file__).resolve().parents[3])
    draft = create_draft(project, DraftKind.SCHEMATIC)
    render_schematic_draft(project, intent, draft)
    save_schematic_intent(intent, draft.root / 'schematic-intent.yaml')
    return _review_schematic(project, draft, toolchain)


def review_draft(project: Project, draft_id: str) -> dict:
    """Regenerate review artifacts for an existing, manually edited draft."""
    draft = load_draft(project, draft_id)
    metadata = validate_schematic_draft(project, draft)
    assert_draft_base_current(project, draft, metadata)
    toolchain = discover_toolchain(Path(__file__).resolve().parents[3])
    return _review_schematic(project, draft, toolchain)


def _review_schematic(
    project: Project, draft: DraftRecord, toolchain: ToolchainPaths,
) -> dict:
    metadata = validate_schematic_draft(project, draft)
    assert_draft_base_current(project, draft, metadata)
    schematic = draft.root / project.schematic_path.name
    intent_path = draft.root / 'schematic-intent.yaml'
    files = schematic_files(schematic)
    input_paths = (*files, intent_path)
    input_hashes = {
        path.relative_to(draft.root).as_posix(): file_digest(path)
        for path in input_paths
    }
    intent = load_schematic_intent(intent_path)

    with tempfile.TemporaryDirectory(prefix='.reviewing-', dir=draft.root) as temporary:
        staging = Path(temporary)
        preview = render_schematic_preview(toolchain, schematic, staging)
        findings = _review_findings(project, intent, schematic, preview.findings)

        _assert_review_snapshot_current(
            project, draft, metadata, files, intent_path, input_hashes,
        )

        final_pdf = draft.root / 'preview.pdf'
        final_erc = draft.root / 'erc.json'
        final_metrics = draft.root / 'metrics.json'
        _publish_review_output(preview.erc_report_path, final_erc)
        _publish_review_output(preview.metrics_path, final_metrics)
        if preview.pdf_path is None:
            final_pdf.unlink(missing_ok=True)
        else:
            _publish_review_output(preview.pdf_path, final_pdf)

        artifact_hashes = dict(input_hashes)
        artifact_hashes.update({
            path.relative_to(draft.root).as_posix(): file_digest(path)
            for path in (final_erc, final_metrics, final_pdf)
        })
        _assert_review_snapshot_current(
            project, draft, metadata, files, intent_path, input_hashes,
        )
        report = {
            'schema_version': 1,
            'draft_id': draft.id,
            'schematic': str(schematic),
            'pdf': str(final_pdf) if final_pdf.is_file() else None,
            'erc_report': str(final_erc),
            'metrics': str(final_metrics),
            'findings': [asdict(f) for f in findings],
            'human_review': 'pending',
            'exit_code': int(any(f.severity == 'block' for f in findings)),
            'artifact_hashes': artifact_hashes,
        }
        review_path = draft.root / 'review.json'
        temporary_report = staging / 'review.json'
        temporary_report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        _publish_review_output(temporary_report, review_path)
        return report


def _publish_review_output(source: Path, target: Path) -> None:
    """Publish one staged output without exposing partially written bytes."""
    os.replace(source, target)


def _assert_review_snapshot_current(
    project: Project,
    draft: DraftRecord,
    metadata: dict,
    files: tuple[Path, ...],
    intent_path: Path,
    input_hashes: dict[str, str | None],
) -> None:
    current_files = schematic_files(draft.root / project.schematic_path.name)
    current_hashes = {
        path.relative_to(draft.root).as_posix(): file_digest(path)
        for path in (*current_files, intent_path)
    }
    assert_draft_base_current(project, draft, metadata)
    if current_files != files or current_hashes != input_hashes:
        raise RuntimeError(
            'draft schematic or intent changed during review; rerun '
            f'{review_draft_command(project, draft.id)}'
        )


def _review_findings(
    project: Project,
    intent: SchematicIntent,
    schematic: Path,
    preview_findings: tuple[Finding, ...],
) -> list[Finding]:
    findings = list(preview_findings) + [
        replace(finding, severity='review') for finding in check_evidence(project, ())
    ]
    try:
        extracted = importlib.import_module('extract_netmap').extract(schematic)
        try:
            normalized = normalize_intent_netmap(intent, extracted['nets'])
            if normalized != extracted['nets']:
                findings.append(Finding('sheet-qualified-net-names',
                                        'Local net membership is preserved, but KiCad adds sheet paths. '
                                        'PCB net names must be reconciled before release.', severity='review'))
        except ValueError as exc:
            findings.append(Finding('intent-netlist-mismatch',
                                    str(exc)))
    except (OSError, RuntimeError, ValueError) as exc:
        findings.append(Finding('netlist-extraction-failed', str(exc)))
    try:
        records = {record.id: record for record in load_evidence_index(project.evidence_index_path).records}
    except EvidenceFormatError:
        records = {}
    for component in intent.components:
        record = records.get(component.pin_map_evidence_id)
        if record is None or component.evidence_part_number.casefold() not in {
            part.casefold() for part in record.part_numbers
        }:
            findings.append(Finding('intent-evidence-unresolved',
                                    component.pin_map_review_note or
                                    'Pin-map citation is absent or does not identify this part',
                                    component.ref, component.pin_map_evidence_id, severity='review'))
    return findings
