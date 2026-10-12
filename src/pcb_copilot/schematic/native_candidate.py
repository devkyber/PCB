"""Check and install owner-edited native sheets without regenerating the drawing."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

from pcb_copilot.evidence.checks import Finding, check_evidence
from pcb_copilot.models import Project
from pcb_copilot.preview_publication import publish_layout_artifacts
from pcb_copilot.project import load_project
from pcb_copilot.review.checks import check_parity
from pcb_copilot.schematic.netmap import extract
from pcb_copilot.schematic.preview import render_schematic_preview, schematic_files
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import (
    apply_files,
    contained,
    copy_inputs,
    project_lock,
    replace_bytes,
)
from pcb_copilot.update_guard import begin_update


def _capture_request(project: Project, candidate: Path, pcb_candidate: Path | None):
    candidate = candidate.resolve()
    if candidate.suffix != '.kicad_sch' or candidate.name != project.schematic_path.name:
        raise ValueError('native candidate must use the current root .kicad_sch filename')
    if pcb_candidate is not None and (pcb_candidate.suffix != '.kicad_pcb' or not pcb_candidate.is_file()):
        raise ValueError('paired PCB must be an existing .kicad_pcb file')
    current_sheets = set(schematic_files(project.schematic_path))
    files = schematic_files(candidate)
    if any(path.suffix != '.kicad_sch' for path in files):
        raise ValueError('every native candidate sheet must be a .kicad_sch file')
    sources = {'schematic/' + path.relative_to(candidate.parent).as_posix(): path for path in files}
    targets = {
        key: contained(project.root, project.schematic_path.parent / path.relative_to(candidate.parent))
        for key, path in sources.items()
    }
    for key, target in targets.items():
        if target not in current_sheets:
            if target.exists():
                raise ValueError(f'new sheet would overwrite unrelated file: {target}')
            # Bind absence so a newly created owner file also invalidates preview.
            sources['new-target/' + key] = target
    if pcb_candidate is not None:
        sources.update({'candidate' + suffix: pcb_candidate.with_suffix(suffix)
                        for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru')})
    return candidate, sources, targets


def update_native_schematic(project: Project, candidate: Path, apply: bool = False,
                            *, pcb_candidate: Path | None = None) -> dict:
    with project_lock(project) as workspace:
        try:
            candidate, sources, targets = _capture_request(project, candidate, pcb_candidate)
        except BaseException:
            # Even malformed hierarchies/requests consume an older preview.
            contained(project.root, workspace / 'preview/schematic-review.json').unlink(missing_ok=True)
            raise
        guard = begin_update(project, workspace, 'schematic', sources,
                             {'mode': 'native', 'paired_pcb': pcb_candidate is not None}, apply=apply)
        with tempfile.TemporaryDirectory(prefix='pcb-native-sch-') as directory:
            temporary = Path(directory)
            staged = guard.stage(temporary / 'request')
            # Parse the captured hierarchy, not a mix of later source edits and old sheets.
            captured = schematic_files(staged['schematic/' + candidate.name])
            if set(captured) != {staged[key] for key in targets}:
                raise RuntimeError('candidate hierarchy changed while capturing; run preview again')
            root = temporary / 'project'
            copy_inputs(project, root, guard.expected)
            snapshot = load_project(root)
            sheet_payloads = {}
            for key, target in targets.items():
                copied = root / target.relative_to(project.root)
                copied.parent.mkdir(parents=True, exist_ok=True)
                payload = staged[key].read_bytes()
                copied.write_bytes(payload)
                sheet_payloads[copied] = payload

            output = temporary / 'artifacts'
            preview = render_schematic_preview(
                discover_toolchain(Path(__file__).resolve().parents[3]), snapshot.schematic_path, output,
            )
            findings = [asdict(item) for item in preview.findings]
            findings.extend(asdict(replace(item, severity='review'))
                            for item in check_evidence(snapshot, ()))
            try:
                netmap = extract(snapshot.schematic_path)
                snapshot.netmap_path.write_text(json.dumps(netmap, indent=2) + '\n', encoding='utf-8')
            except (OSError, RuntimeError, ValueError) as exc:
                findings.append(asdict(Finding('netlist-extraction-failed', str(exc))))

            if pcb_candidate is not None:
                from pcb_copilot.layout.update import _prepare_candidate

                _, paired_findings, _ = _prepare_candidate(
                    snapshot, None, staged['candidate.kicad_pcb'], None, output, schematic_change=True,
                )
                findings.extend(paired_findings)
            else:
                from pcb_copilot.layout.update import _bind_candidate_links

                findings.extend(_bind_candidate_links(
                    snapshot, discover_toolchain(Path(__file__).resolve().parents[3])))
            try:
                passed, detail = check_parity(snapshot)
                if not passed:
                    findings.append(asdict(Finding('board-parity', detail)))
            except (OSError, RuntimeError, ValueError) as exc:
                findings.append(asdict(Finding('board-parity', str(exc))))
            for path, payload in sheet_payloads.items():
                if path.read_bytes() != payload:
                    raise RuntimeError('native schematic bytes changed during validation')
            guard.check(apply=apply)

            published = {}
            for name, source in (('schematic.pdf', preview.pdf_path),
                                 ('schematic-erc.json', preview.erc_report_path),
                                 ('schematic-metrics.json', preview.metrics_path)):
                target = contained(project.root, guard.report_path.parent / name)
                if source is not None and source.is_file():
                    replace_bytes(target, source.read_bytes())
                    published[name] = str(target)
                else:
                    target.unlink(missing_ok=True)
            if pcb_candidate is not None:
                publish_layout_artifacts(
                    project.root, output, guard.report_path.parent,
                    additional_artifacts=(source for source in output.glob('layout*')
                                          if source.suffix in {'.json', '.svg', '.step'}),
                )
            result = {
                'applied': False, 'schematic': str(project.schematic_path),
                'source_mode': 'native', 'intent_status': 'historical; unchanged and not used to redraw CAD',
                'human_review': 'pending',
                'preview': published.get('schematic.pdf'), 'erc_report': published.get('schematic-erc.json'),
                'metrics': published.get('schematic-metrics.json'), 'findings': findings,
                'exit_code': int(any(item['severity'] == 'block' for item in findings)),
                'preview_binding': guard.binding,
            }
            if apply and not result['exit_code']:
                paths = [*sheet_payloads, snapshot.netmap_path]
                if pcb_candidate is not None:
                    paths.extend(snapshot.pcb_path.with_suffix(suffix)
                                 for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru')
                                 if snapshot.pcb_path.with_suffix(suffix).is_file())
                elif any(item['code'] == 'layout.schematic_links_added' for item in findings):
                    paths.append(snapshot.pcb_path)
                changes = {}
                for path in paths:
                    target = contained(project.root, project.root / path.relative_to(snapshot.root))
                    payload = path.read_bytes()
                    if not target.is_file() or target.read_bytes() != payload:
                        changes[target] = payload
                result.update(applied=True, lifecycle='DRAFT')
                changes[guard.report_path] = (json.dumps(result, indent=2) + '\n').encode()
                guard.check(apply=True)
                # Carry preview-bound absence into the transaction itself. A new
                # owner file can appear after guard.check and before its first write.
                new_targets = {path: None for key, (path, _payload) in guard.sources.items()
                               if key.startswith('new-target/')}
                apply_files(project, changes, guard.expected, expected_targets=new_targets)
            else:
                guard.check()
                replace_bytes(guard.report_path, (json.dumps(result, indent=2) + '\n').encode())
            return result
