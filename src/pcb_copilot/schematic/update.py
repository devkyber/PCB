"""Preview/apply the current schematic in a disposable project transaction."""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from pcb_copilot.accept import accept_schematic, load_draft
from pcb_copilot.models import Project
from pcb_copilot.preview_publication import publish_layout_artifacts
from pcb_copilot.project import load_project
from pcb_copilot.schematic.commands import draft_schematic
from pcb_copilot.schematic.parity import (
    candidate_board_parity,
    reconcile_board_net_names,
)
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import (
    apply_files,
    contained,
    copy_inputs,
    project_lock,
    replace_bytes,
)
from pcb_copilot.update_guard import begin_update


def update_schematic(project: Project, intent_path: Path, apply: bool,
                     *, reconcile_names: bool = False, pcb_candidate: Path | None = None) -> dict:
    if reconcile_names and pcb_candidate is not None:
        raise ValueError('--pcb and --reconcile-board-names are alternatives')
    sources = {'intent.yaml': intent_path}
    if pcb_candidate is not None:
        sources.update({'candidate' + suffix: pcb_candidate.with_suffix(suffix)
                        for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru')})
    with project_lock(project) as workspace:
        guard = begin_update(project, workspace, 'schematic', sources,
                             {'mode': 'intent', 'reconcile_names': reconcile_names}, apply=apply)
        if not intent_path.is_file():
            raise ValueError('intent must be an existing file')
        if pcb_candidate is not None and (pcb_candidate.suffix != '.kicad_pcb' or not pcb_candidate.is_file()):
            raise ValueError('candidate must be an existing .kicad_pcb file')
        expected = guard.expected
        with tempfile.TemporaryDirectory(prefix='pcb-sch-') as directory:
            staged = guard.stage(Path(directory) / 'request')
            staged_root = Path(directory) / project.root.name
            copy_inputs(project, staged_root, expected)
            snapshot = load_project(staged_root)
            staged_intent = staged['intent.yaml']
            report = draft_schematic(snapshot, staged_intent)
            draft = load_draft(snapshot, report['draft_id'])
            board_payload = project_payload = None
            rules_payload = None
            paired_preview = None
            renamed_nets = 0
            if pcb_candidate is not None:
                from pcb_copilot.layout.update import _prepare_candidate

                paired_preview = Path(directory) / 'layout-preview'
                paired_preview.mkdir()
                paired_pcb = paired_preview / project.pcb_path.name
                for source in (snapshot.pcb_path, snapshot.pcb_path.with_suffix('.kicad_pro'),
                               snapshot.pcb_path.with_suffix('.kicad_dru')):
                    if source.is_file():
                        (paired_preview / source.name).write_bytes(source.read_bytes())
                context = replace(snapshot, schematic_path=draft.root / project.schematic_path.name,
                                  pcb_path=paired_pcb)
                checked, findings, _ = _prepare_candidate(
                    context, None, staged['candidate.kicad_pcb'], None, paired_preview, schematic_change=True,
                )
                report['findings'].extend(findings)
                report['exit_code'] = int(any(item['severity'] == 'block' for item in report['findings']))
                board_payload = checked.read_bytes()
                for suffix in ('.kicad_pro', '.kicad_dru'):
                    source = checked.with_suffix(suffix)
                    if source.is_file():
                        target = draft.root / project.pcb_path.with_suffix(suffix).relative_to(project.root)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(source.read_bytes())
                target = draft.root / project.pcb_path.relative_to(project.root)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(board_payload)
                if checked.with_suffix('.kicad_pro').is_file():
                    project_payload = checked.with_suffix('.kicad_pro').read_bytes()
                if checked.with_suffix('.kicad_dru').is_file():
                    rules_payload = checked.with_suffix('.kicad_dru').read_bytes()
            if reconcile_names:
                board, settings, names = reconcile_board_net_names(snapshot, draft.root)
                renamed_nets = len(names)
                if names:
                    board_payload, project_payload = board, settings
            if pcb_candidate is None:
                from pcb_copilot.layout.update import _bind_candidate_links

                context = replace(snapshot, schematic_path=draft.root / project.schematic_path.name,
                                  pcb_path=draft.root / project.pcb_path.relative_to(project.root))
                link_findings = _bind_candidate_links(context, discover_toolchain(project.root))
                report['findings'].extend(link_findings)
                if any(item['code'] == 'layout.schematic_links_added' for item in link_findings):
                    board_payload = context.pcb_path.read_bytes()
                if any(item['severity'] == 'block' for item in link_findings):
                    report['exit_code'] = 1
            parity_error = candidate_board_parity(snapshot, draft.root)
            if parity_error:
                report['findings'].append({'code': 'board-parity', 'message': parity_error,
                                           'severity': 'block'})
                report['exit_code'] = 1
            guard.check(apply=apply)
            preview = contained(project.root, workspace / 'preview')
            preview.mkdir(exist_ok=True)
            if paired_preview is not None:
                publish_layout_artifacts(
                    project.root, paired_preview, preview,
                    additional_artifacts=(source for source in paired_preview.iterdir()
                                          if source.suffix in {'.svg', '.step', '.json'}),
                )
            copied = {}
            for source_name, target_name in (
                ('preview.pdf', 'schematic.pdf'), ('erc.json', 'schematic-erc.json'),
                ('metrics.json', 'schematic-metrics.json'),
            ):
                source = draft.root / source_name
                target = contained(project.root, preview / target_name)
                if source.is_file():
                    replace_bytes(target, source.read_bytes())
                    copied[source_name] = str(target)
                else:
                    target.unlink(missing_ok=True)
            result = {'applied': False, 'schematic': str(project.schematic_path),
                      'preview': copied.get('preview.pdf'), 'erc_report': copied.get('erc.json'),
                      'metrics': copied.get('metrics.json'), 'findings': report['findings'],
                      'exit_code': report['exit_code'], 'renamed_nets': renamed_nets,
                      'preview_binding': guard.binding}
            if apply and not report['exit_code']:
                accept_schematic(snapshot, draft,
                                 board_payload=board_payload, project_payload=project_payload)
                paths = [*schematic_files(snapshot.schematic_path), snapshot.netmap_path]
                if board_payload is not None:
                    paths.append(snapshot.pcb_path)
                if project_payload is not None:
                    paths.append(snapshot.pcb_path.with_suffix('.kicad_pro'))
                changes = {project.root / path.relative_to(snapshot.root): path.read_bytes()
                           for path in paths}
                if rules_payload is not None:
                    changes[project.pcb_path.with_suffix('.kicad_dru')] = rules_payload
                changes[project.root / 'schematic-intent.yaml'] = (draft.root / 'schematic-intent.yaml').read_bytes()
                new_targets = {}
                for target in changes:
                    relative = target.relative_to(project.root).as_posix()
                    if relative not in expected:
                        if target.exists():
                            raise ValueError(f'new sheet would overwrite unrelated file: {relative}')
                        new_targets[target] = None
                result.update(applied=True, lifecycle='DRAFT')
                changes[preview / 'schematic-review.json'] = (json.dumps(result, indent=2) + '\n').encode()
                guard.check(apply=True)
                apply_files(project, changes, expected, expected_targets=new_targets)
            else:
                guard.check()
                replace_bytes(preview / 'schematic-review.json', (json.dumps(result, indent=2) + '\n').encode())
            return result
