"""Explicit acceptance with stale checks, recoverable backups and rollback."""

from __future__ import annotations

import importlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pcb_copilot.drafts import _DRAFT_ID, _project_root
from pcb_copilot.evidence.checks import check_evidence
from pcb_copilot.models import DraftKind, DraftRecord, Lifecycle, Project
from pcb_copilot.schematic.io import load_schematic_intent
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.state import accepted_file_hashes, canonical_design_hash, file_digest


class StaleDraftError(ValueError):
    """The accepted files changed after the draft was created."""


@dataclass(frozen=True)
class AcceptanceResult:
    kind: DraftKind
    accepted_path: Path
    accepted_hash: str
    netmap_path: Path
    lifecycle: Lifecycle


def load_draft(project: Project, draft_id: str) -> DraftRecord:
    if not _DRAFT_ID.fullmatch(draft_id):
        raise ValueError('invalid draft ID')
    root = project.root / '.pcb-copilot/drafts' / draft_id
    if root.resolve().parent != (project.root / '.pcb-copilot/drafts').resolve():
        raise ValueError('invalid draft root')
    data = json.loads((root / 'draft.json').read_text(encoding='utf-8'))
    if data['id'] != draft_id or data['project'] != project.manifest.name:
        raise ValueError('draft does not belong to this project')
    return DraftRecord(
        draft_id, DraftKind(data['kind']), data['project'],
        data['base_schematic_hash'], data['base_pcb_hash'],
        datetime.fromisoformat(data['created_utc'].replace('Z', '+00:00')), root,
    )


def _replace_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name('.' + target.name + '.accepting')
    with temporary.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def accept_schematic(project: Project, draft: DraftRecord) -> AcceptanceResult:
    if _project_root(draft) != project.root or draft != load_draft(project, draft.id):
        raise ValueError('invalid draft root or metadata')
    if draft.kind != DraftKind.SCHEMATIC:
        raise ValueError('only schematic drafts can be accepted here')
    metadata = json.loads((draft.root / 'draft.json').read_text(encoding='utf-8'))

    def check_base():
        if (metadata.get('base_files') != accepted_file_hashes(project)
                or draft.base_schematic_hash != canonical_design_hash(project.schematic_path)
                or draft.base_pcb_hash != canonical_design_hash(project.pcb_path)):
            raise StaleDraftError('accepted files changed since this draft was created')

    check_base()
    report = json.loads((draft.root / 'review.json').read_text(encoding='utf-8'))
    schematic = draft.root / project.schematic_path.name
    files = schematic_files(schematic)
    required = {*files, draft.root / 'schematic-intent.yaml', draft.root / 'preview.pdf',
                draft.root / 'erc.json', draft.root / 'metrics.json'}
    current_hashes = {p.relative_to(draft.root).as_posix(): file_digest(p) for p in required}
    if report.get('artifact_hashes') != current_hashes or None in current_hashes.values():
        raise ValueError('review artifacts changed or are missing; regenerate the draft review')
    if report.get('exit_code') != 0 or any(f['severity'] == 'block' for f in report['findings']):
        raise ValueError('draft has blocking review findings')
    if check_evidence(project, ()):
        raise ValueError('project evidence no longer passes integrity checks')

    # Extract using KiCad before any accepted-file replacement. This import
    # follows the existing repository helper path established by the renderer.
    from pcb_copilot.schematic import render  # noqa: F401

    netmap = importlib.import_module('extract_netmap').extract(schematic)
    intent = load_schematic_intent(draft.root / 'schematic-intent.yaml')
    expected = {c.ref: {pin: connection.net for pin, connection in c.pins.items()}
                for c in intent.components if c.pins}
    if netmap['nets'] != expected:
        raise ValueError('draft netlist differs from schematic intent')

    changes = {project.schematic_path.parent / p.relative_to(schematic.parent): p.read_bytes()
               for p in files}
    for target in changes:
        if not target.resolve().is_relative_to(project.root):
            raise ValueError('acceptance target escapes project')
        relative = target.relative_to(project.root).as_posix()
        if target.exists() and relative not in metadata['base_files']:
            raise ValueError(f'new child would overwrite an unrelated file: {relative}')
    changes[project.netmap_path] = (json.dumps(netmap, indent=2) + '\n').encode()
    changes[project.root / 'SCHEMATIC_OWNER'] = b'human\n'
    state_path = project.root / '.pcb-copilot/review.json'
    backup = project.root / '.pcb-copilot/acceptances' / draft.id
    lock = project.root / '.pcb-copilot/accept.lock'
    # A persistent lock on interruption prevents a second partial transaction.
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(draft.id)
    before = {}
    applied = []
    recoverable = False
    try:
        check_base()
        backup.mkdir(parents=True, exist_ok=False)
        for target in [*changes, state_path]:
            before[target] = target.read_bytes() if target.exists() else None
            if target.exists():
                destination = backup / target.relative_to(project.root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, destination)
        transaction = {
            'draft_id': draft.id, 'status': 'prepared',
            'targets': {p.relative_to(project.root).as_posix(): data is not None
                        for p, data in before.items()},
        }
        journal = backup / 'transaction.json'
        journal.write_text(json.dumps(transaction, indent=2), encoding='utf-8')
        for target, payload in changes.items():
            _replace_bytes(target, payload)
            applied.append(target)
        review = {
            'schema_version': 1, 'lifecycle': Lifecycle.HUMAN_REVIEWED.value,
            'draft_id': draft.id, 'schematic_hash': canonical_design_hash(project.schematic_path),
            'pcb_hash': canonical_design_hash(project.pcb_path),
            'accepted_files': accepted_file_hashes(project),
        }
        _replace_bytes(state_path, (json.dumps(review, indent=2) + '\n').encode())
        applied.append(state_path)
        transaction['status'] = 'completed'
        _replace_bytes(journal, json.dumps(transaction, indent=2).encode())
        recoverable = True
    except Exception:
        for target in reversed(applied):
            payload = before[target]
            if payload is None:
                target.unlink(missing_ok=True)
            else:
                _replace_bytes(target, payload)
        recoverable = True
        raise
    finally:
        if recoverable:
            lock.unlink(missing_ok=True)
    return AcceptanceResult(DraftKind.SCHEMATIC, project.schematic_path,
                            canonical_design_hash(project.schematic_path),
                            project.netmap_path, Lifecycle.HUMAN_REVIEWED)
