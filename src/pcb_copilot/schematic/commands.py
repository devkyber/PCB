"""Orchestrate evidence-linked schematic drafts and their review artifacts."""

from __future__ import annotations

import importlib
import json
from dataclasses import asdict, replace
from pathlib import Path

from pcb_copilot.drafts import create_draft
from pcb_copilot.evidence.checks import Finding, check_evidence
from pcb_copilot.evidence.index import EvidenceFormatError, load_evidence_index
from pcb_copilot.models import DraftKind, Project
from pcb_copilot.schematic.hierarchy import HierarchyDraft
from pcb_copilot.schematic.io import load_schematic_intent, save_schematic_intent
from pcb_copilot.schematic.netlist import normalize_intent_netmap
from pcb_copilot.schematic.preview import render_schematic_preview, schematic_files
from pcb_copilot.schematic.render import render_schematic_draft
from pcb_copilot.state import file_digest
from pcb_copilot.toolchain import discover_toolchain


def draft_schematic(project: Project, intent_path: Path) -> dict:
    intent = load_schematic_intent(intent_path)
    toolchain = discover_toolchain(Path(__file__).resolve().parents[3])
    draft = create_draft(project, DraftKind.SCHEMATIC)
    rendered = render_schematic_draft(project, intent, draft)
    schematic = rendered.root_schematic if isinstance(rendered, HierarchyDraft) else rendered
    save_schematic_intent(intent, draft.root / 'schematic-intent.yaml')
    preview = render_schematic_preview(toolchain, schematic, draft.root)
    findings = list(preview.findings) + [
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
    report = {
        'schema_version': 1,
        'draft_id': draft.id,
        'schematic': str(schematic),
        'pdf': str(preview.pdf_path) if preview.pdf_path else None,
        'erc_report': str(preview.erc_report_path),
        'metrics': str(preview.metrics_path),
        'findings': [asdict(f) for f in findings],
        'human_review': 'pending',
        'exit_code': int(any(f.severity == 'block' for f in findings)),
        'artifact_hashes': {
            path.relative_to(draft.root).as_posix(): file_digest(path)
            for path in (*schematic_files(schematic), draft.root / 'schematic-intent.yaml',
                         preview.erc_report_path, preview.metrics_path,
                         draft.root / 'preview.pdf')
        },
    }
    (draft.root / 'review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
