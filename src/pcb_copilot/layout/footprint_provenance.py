"""Hash-bound provenance for local footprints derived from manufacturer drawings.

This establishes source lineage and pad coverage, not mechanical acceptance.
An author receipt is never a shared human sign-off.
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import yaml
from kicad_claude.adapters import sch_io

from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.evidence.models import EvidenceRole, TrustTier
from pcb_copilot.models import Project

DRAWING_DERIVED_DESCRIPTION = (
    'manufacturer drawing-derived footprints; see libs/footprint-provenance.yaml'
)


def drawing_receipt(project: Project, path: Path) -> dict:
    manifest = project.root / 'libs/footprint-provenance.yaml'
    if not manifest.is_file():
        raise ValueError(f'drawing-derived footprint has no provenance manifest: {path}')
    try:
        data = yaml.safe_load(manifest.read_text(encoding='utf-8'))
    except yaml.YAMLError as exc:
        raise ValueError('malformed footprint provenance YAML') from exc
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('invalid footprint provenance schema')
    records = data.get('records')
    if not isinstance(records, list):
        raise ValueError('footprint provenance records must be a list')  # noqa: TRY004 -- invalid file content
    relative = path.resolve().relative_to(project.root.resolve()).as_posix()
    matches = [r for r in records if isinstance(r, dict) and r.get('path') == relative]
    if len(matches) != 1:
        raise ValueError(f'footprint needs exactly one drawing provenance receipt: {relative}')
    receipt = matches[0]
    if receipt.get('sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f'footprint provenance hash mismatch: {relative}')
    for key in ('author', 'reviewed_on', 'derived_from', 'limitations'):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            raise ValueError(f'footprint provenance missing {key}: {relative}')
    try:
        date.fromisoformat(receipt['reviewed_on'])
    except ValueError as exc:
        raise ValueError(f'invalid footprint provenance review date: {relative}') from exc
    if receipt.get('owner_signoff') is not False:
        raise ValueError('footprint author provenance must not claim owner sign-off')
    functions = receipt.get('pad_functions')
    tree = sch_io.parse_file(path)
    pads = {str(pad[1]) for pad in sch_io.find_children(tree, 'pad') if str(pad[1])}
    if (not isinstance(functions, dict) or set(functions) != pads or
            any(not isinstance(v, str) or not v.strip() for v in functions.values())):
        raise ValueError(f'footprint provenance pad-function coverage mismatch: {relative}')
    ids = receipt.get('evidence_ids')
    if (not isinstance(ids, list) or not ids or
            any(not isinstance(v, str) for v in ids) or len(set(ids)) != len(ids)):
        raise ValueError(f'footprint provenance needs unique source evidence IDs: {relative}')
    numbers = receipt.get('part_numbers')
    if (not isinstance(numbers, list) or not numbers or
            any(not isinstance(v, str) or not v.strip() for v in numbers)):
        raise ValueError(f'footprint provenance needs selected part identity: {relative}')
    index = load_evidence_index(project.evidence_index_path)
    covered = set()
    for evidence_id in ids:
        source = next((r for r in index.records if r.id == evidence_id), None)
        if source is None or source.trust_tier not in {TrustTier.MANUFACTURER, TrustTier.MANUFACTURER_EVM}:
            raise ValueError(f'footprint provenance source is not manufacturer evidence: {evidence_id}')
        if not source.source_url:
            raise ValueError(f'footprint provenance source has no origin URL: {evidence_id}')
        if not source.roles.intersection({EvidenceRole.DATASHEET, EvidenceRole.FOOTPRINT_DRAWING,
                                          EvidenceRole.MODULE_PINOUT}):
            raise ValueError(f'footprint provenance source has no drawing/pinout role: {evidence_id}')
        payload_path = project.evidence_index_path.parent / source.path
        if not payload_path.is_file() or hashlib.sha256(payload_path.read_bytes()).hexdigest() != source.sha256:
            raise ValueError(f'footprint provenance source hash mismatch: {evidence_id}')
        covered.update(source.part_numbers)
    if not set(numbers).issubset(covered):
        raise ValueError(f'footprint provenance selected part is absent from source identities: {relative}')
    return receipt
