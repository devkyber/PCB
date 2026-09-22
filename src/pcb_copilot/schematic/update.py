"""Preview and apply a schematic to the single current project design."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcb_copilot.accept import accept_schematic, load_draft
from pcb_copilot.models import Project
from pcb_copilot.schematic.commands import draft_schematic
from pcb_copilot.schematic.parity import (
    candidate_board_parity,
    reconcile_board_net_names,
)


def _remove_transaction(path: Path, expected_parent: Path) -> None:
    if path.resolve().parent != expected_parent.resolve():
        raise ValueError(f'transaction path escapes project: {path}')
    if path.is_dir():
        shutil.rmtree(path)


def update_schematic(
    project: Project, intent_path: Path, apply: bool, *, reconcile_names: bool = False,
) -> dict:
    """Render once, show review artifacts, and optionally update current CAD."""
    report = draft_schematic(project, intent_path)
    draft = load_draft(project, report['draft_id'])
    preview_dir = project.root / '.pcb-copilot' / 'preview'
    preview_dir.mkdir(parents=True, exist_ok=True)
    copied = {}
    try:
        board_payload = None
        project_payload = None
        renamed_nets = 0
        if reconcile_names:
            candidate_board, candidate_settings, names = reconcile_board_net_names(
                project, draft.root,
            )
            renamed_nets = len(names)
            if names:
                board_payload = candidate_board
                if candidate_settings != project.pcb_path.with_suffix('.kicad_pro').read_bytes():
                    project_payload = candidate_settings
        parity_error = candidate_board_parity(project, draft.root)
        if parity_error is not None:
            report['findings'].append({
                'code': 'board-parity', 'message': parity_error,
                'reference': None, 'evidence_id': None, 'severity': 'block',
            })
            report['exit_code'] = 1
        for source_name, destination_name in (
            ('preview.pdf', 'schematic.pdf'),
            ('erc.json', 'schematic-erc.json'),
            ('metrics.json', 'schematic-metrics.json'),
        ):
            source = draft.root / source_name
            if source.is_file():
                target = preview_dir / destination_name
                shutil.copy2(source, target)
                copied[source_name] = str(target)
        result = {
            'applied': False,
            'schematic': str(project.schematic_path),
            'preview': copied.get('preview.pdf'),
            'erc_report': copied.get('erc.json'),
            'metrics': copied.get('metrics.json'),
            'findings': report['findings'],
            'exit_code': report['exit_code'],
            'renamed_nets': renamed_nets,
        }
        if apply:
            if report['exit_code']:
                return result
            accepted = accept_schematic(
                project, draft, record_legacy_owner=False,
                board_payload=board_payload, project_payload=project_payload,
            )
            result['applied'] = True
            result['lifecycle'] = accepted.lifecycle.value
            result['schematic'] = str(accepted.accepted_path)
            backup = project.root / '.pcb-copilot' / 'acceptances' / draft.id
            _remove_transaction(backup, project.root / '.pcb-copilot' / 'acceptances')
        (preview_dir / 'schematic-review.json').write_text(
            json.dumps(result, indent=2) + '\n', encoding='utf-8',
        )
        return result
    finally:
        _remove_transaction(draft.root, project.root / '.pcb-copilot' / 'drafts')
