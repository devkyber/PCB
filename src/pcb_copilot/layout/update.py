"""Preview and apply a checked layout using a disposable project snapshot."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

from pcb_copilot.evidence.checks import check_evidence
from pcb_copilot.layout.commands import draft_layout
from pcb_copilot.layout.io import load_layout_intent
from pcb_copilot.layout.preview import inspect_layout, render_layout_preview
from pcb_copilot.layout.render import native_board, schematic_inventory
from pcb_copilot.layout.schematic_links import bind_missing_links
from pcb_copilot.models import Project
from pcb_copilot.preview_publication import publish_layout_artifacts
from pcb_copilot.project import load_project
from pcb_copilot.review.checks import check_parity, check_placement, drc_once
from pcb_copilot.review.routing_topology import describe, inspect_routing
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import (
    apply_files,
    contained,
    copy_inputs,
    project_lock,
    replace_bytes,
)
from pcb_copilot.update_guard import begin_update


def _finding(code, message, severity='block'):
    return {'code': code, 'message': message, 'severity': severity}


def nonregression_findings(before, after, *, unconnected, removed_parts=()):
    findings = []
    before_ids = {fp.get('uuid', ref) for ref, fp in before['footprints'].items()
                  if ref not in removed_parts}
    after_ids = {fp.get('uuid', ref) for ref, fp in after['footprints'].items()}
    if before_ids - after_ids:
        findings.append(_finding('layout.removed_parts', 'candidate removes existing physical parts'))
    if before['tracks'] and not after['tracks']:
        findings.append(_finding('layout.copper_loss', 'candidate discards all existing routing'))
    if before['zones'] and not after['zones']:
        findings.append(_finding('layout.zone_loss', 'candidate removes all existing copper pours'))
    if unconnected is None or unconnected:
        findings.append(_finding('layout.routing', f'routing is incomplete or unmeasured: {unconnected}'))
    if 0 < after['tracks'] < before['tracks'] and unconnected == 0:
        findings.append(_finding('layout.rerouted',
            'Candidate uses fewer copper segments/vias; native routing reports zero unconnected. '
            'Inspect the rendered copper changes before applying.', 'review'))
    return findings


def _bind_candidate_links(context, toolchain):
    """Repair absent identity only after full circuit/part parity on a staged PCB."""
    physical_ok, _ = check_parity(context, include_links=False)
    if not physical_ok:
        return []  # The strict parity gate below reports the circuit mismatch.
    parts, _ = schematic_inventory(toolchain, context.schematic_path)
    footprints = native_board(toolchain, context.pcb_path)['footprints']
    try:
        linked = bind_missing_links(context.pcb_path, parts, footprints)
    except ValueError as exc:
        return [_finding('layout.schematic_links', str(exc))]
    if linked:
        return [_finding('layout.schematic_links_added',
            'Bound missing schematic IDs on the candidate: ' + ', '.join(linked)
            + '. Copper, footprint UUIDs and positions were preserved.', 'review')]
    return []


def _prepare_candidate(snapshot, intent, candidate, route, output, *, schematic_change=False):
    toolchain = discover_toolchain(Path(__file__).resolve().parents[3])
    # A first layout has no accepted board to compare against. Only absence
    # permits an empty baseline: an existing malformed board must still fail.
    # An explicit native repair can start with an open/missing outline while
    # retaining the complete baseline inventory for copper/part-loss checks.
    # Generated placement and the finished candidate remain outline-strict.
    before = (native_board(toolchain, snapshot.pcb_path, require_outline=candidate is None,
                           **({'allow_duplicate_references': True} if candidate is not None else {}))
              if snapshot.pcb_path.exists()
              else {'footprints': {}, 'bounds': None, 'rectangular': None,
                    'tracks': 0, 'zones': 0, 'rule_areas': 0})
    findings = []
    if before.get('duplicate_references'):
        findings.append(_finding('layout.baseline_references',
            'Duplicate baseline references retained by footprint UUID: '
            + ', '.join(sorted(set(before['duplicate_references'])))
            + '. The finished candidate must have unique references.', 'review'))
    if before.get('outline_error'):
        findings.append(_finding('layout.baseline_outline',
            before['outline_error'] + '; native repair baseline inventory retained. '
            'The candidate still requires a valid outline and complete routing.', 'review'))
    if candidate is not None:
        if candidate.suffix != '.kicad_pcb' or not candidate.is_file():
            raise ValueError('candidate must be an existing .kicad_pcb file')
        shutil.copy2(candidate, snapshot.pcb_path)
        for suffix in ('.kicad_pro', '.kicad_dru'):
            companion = candidate.with_suffix(suffix)
            if companion.is_file():
                shutil.copy2(companion, snapshot.pcb_path.with_suffix(suffix))
        pcb = snapshot.pcb_path
        current_intent = snapshot.root / 'layout-intent.yaml'
        if current_intent.is_file() and not schematic_change:
            findings.extend(inspect_layout(snapshot, load_layout_intent(current_intent), pcb, toolchain)['findings'])
    else:
        report = draft_layout(snapshot, intent, route)
        findings.extend(report['findings'])
        pcb = Path(report['pcb'])
    if toolchain.kipython is None:
        raise RuntimeError('KiCad Python with pcbnew is required to fill candidate zones')
    fill = subprocess.run(
        [str(toolchain.kipython), '-I', '-c',
         'import pcbnew,sys; b=pcbnew.LoadBoard(sys.argv[1]); '
         'pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[1],b,True)', str(pcb)],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180,
    )
    if fill.returncode:
        raise RuntimeError(f'zone fill failed: {fill.stderr or fill.stdout}')
    # Use the snapshot schematic with the candidate PCB and candidate settings.
    context = replace(snapshot, pcb_path=pcb)
    # Old script-authored boards can have correct copper and no F8 identity.
    # Repair only absent metadata in this isolated candidate, after proving the
    # complete circuit and part identity. Existing conflicting links still block.
    findings.extend(_bind_candidate_links(context, toolchain))
    for name, check in (('parity', check_parity), ('placement', check_placement)):
        passed, detail = check(context)
        if not passed:
            findings.append(_finding(f'layout.{name}', detail))
    runs = [drc_once(pcb, output / f'layout-drc-{index}.json') for index in range(2)]
    if any(errors or unconnected for errors, _, unconnected in runs):
        findings.append(_finding('layout.drc', f'candidate DRC/routing results: {runs}'))
    topology = inspect_routing(pcb, toolchain)
    (output / 'routing-topology.json').write_text(json.dumps(topology, indent=2) + '\n', encoding='utf-8')
    findings.extend(_finding('layout.' + item['code'], describe(item), 'review')
                    for item in topology['findings'])
    after = native_board(toolchain, pcb)
    removed = ()
    if schematic_change:
        parts, _ = schematic_inventory(toolchain, snapshot.schematic_path)
        removed = set(before['footprints']) - set(parts)
    findings.extend(nonregression_findings(before, after, unconnected=max(run[2] for run in runs),
                                          removed_parts=removed))
    findings.extend(render_layout_preview(toolchain, pcb, output))
    for name in ('preview.svg', 'preview.step'):
        source = output / name
        if source.is_file():
            source.rename(output / name.replace('preview', 'layout'))
    findings.extend(_finding(item.code, item.message, item.severity)
                    for item in check_evidence(snapshot, ()))
    return pcb, findings, {'before': before, 'after': after, 'drc_runs': runs}


def update_layout(project: Project, intent_path: Path | None = None, apply: bool = False,
                  *, candidate: Path | None = None, route: str | None = None) -> dict:
    if (intent_path is None) == (candidate is None):
        raise ValueError('provide exactly one of --intent or --candidate')
    if route is not None and candidate is not None:
        raise ValueError('--route applies only to --intent')
    sources = {'intent.yaml': intent_path} if intent_path is not None else {
        'candidate' + suffix: candidate.with_suffix(suffix)
        for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru')}
    with project_lock(project) as workspace:
        guard = begin_update(project, workspace, 'layout', sources,
                             {'mode': 'candidate' if candidate is not None else 'intent', 'route': route},
                             apply=apply)
        if intent_path is not None and not intent_path.is_file():
            raise ValueError('intent must be an existing file')
        if candidate is not None and (candidate.suffix != '.kicad_pcb' or not candidate.is_file()):
            raise ValueError('candidate must be an existing .kicad_pcb file')
        expected = guard.expected
        with tempfile.TemporaryDirectory(prefix='pcb-layout-') as directory:
            transaction = Path(directory)
            staged = guard.stage(transaction / 'request')
            staged_root = transaction / project.root.name
            copy_inputs(project, staged_root, expected)
            snapshot = load_project(staged_root)
            output = transaction / 'preview'
            output.mkdir()
            staged_intent = staged['intent.yaml'] if intent_path is not None else None
            staged_candidate = staged['candidate.kicad_pcb'] if candidate is not None else None
            pcb, findings, comparison = _prepare_candidate(snapshot, staged_intent, staged_candidate, route, output)
            blocked = any(item['severity'] == 'block' for item in findings)
            guard.check(apply=apply)
            preview = contained(project.root, workspace / 'preview')
            preview.mkdir(exist_ok=True)
            published = publish_layout_artifacts(
                project.root, output, preview, additional_artifacts=output.iterdir(),
            )
            result = {'applied': False, 'exit_code': int(blocked), 'pcb': str(project.pcb_path),
                      'preview': published.get('layout.svg'),
                      'findings': findings, 'comparison': comparison, 'preview_binding': guard.binding}
            if apply and not blocked:
                changes = {project.pcb_path: pcb.read_bytes()}
                if staged_intent is not None:
                    normalized_intent = pcb.parent / 'layout-intent.yaml'
                    changes[project.root / 'layout-intent.yaml'] = (
                        normalized_intent if normalized_intent.is_file() else staged_intent).read_bytes()
                for suffix in ('.kicad_pro', '.kicad_dru'):
                    source = pcb.with_suffix(suffix)
                    if source.is_file():
                        changes[project.pcb_path.with_suffix(suffix)] = source.read_bytes()
                result.update(applied=True, lifecycle='DRAFT')
                changes[preview / 'layout-review.json'] = (json.dumps(result, indent=2) + '\n').encode()
                guard.check(apply=True)
                apply_files(project, changes, expected)
            else:
                guard.check()
                replace_bytes(preview / 'layout-review.json', (json.dumps(result, indent=2) + '\n').encode())
            return result
