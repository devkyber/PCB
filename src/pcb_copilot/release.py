"""Review and export an exact current snapshot, then publish all outputs together."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from pcb_copilot.jlcpcb import check_jlcpcb
from pcb_copilot.manufacturing import export_manufacturing
from pcb_copilot.models import Project
from pcb_copilot.project import load_project
from pcb_copilot.review.commands import render_review_json, review_project
from pcb_copilot.review.fingerprint import pcb_digest, schematic_digest
from pcb_copilot.stock import check_stock
from pcb_copilot.transaction import (
    RecoveryRequired,
    assert_current,
    contained,
    copy_inputs,
    input_hashes,
    project_lock,
    recovery_directory,
    replace_bytes,
    unaliased_path,
)


def output_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*')) if path.is_file() and path != root / 'SOURCE.json'}


def _write_state(path: Path, document: dict) -> None:
    replace_bytes(path, (json.dumps(document, indent=2, sort_keys=True) + '\n').encode())


def release_project(project: Project, *, preview: bool = False, quantity: int = 1) -> dict:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError('Board quantity must be a positive integer')
    expected = input_hashes(project)
    destination = unaliased_path(project.root, project.root / ('output/jlcpcb-preview' if preview else 'fabrication'))
    with project_lock(project) as workspace, tempfile.TemporaryDirectory(prefix='pcb-release-') as directory:
        staging = Path(directory)
        snapshot_root = staging / project.root.name
        copy_inputs(project, snapshot_root, expected)
        snapshot = load_project(snapshot_root)
        report = review_project(snapshot)
        assert_current(project, expected)
        blocked = report.blocking or not report.results or any(not item.passed for item in report.results)
        if blocked and not preview:
            return {'released': False, 'exit_code': 1,
                    'review': json.loads(render_review_json(report))}
        if (report.schematic_hash != schematic_digest(snapshot.schematic_path)
                or report.pcb_hash != pcb_digest(snapshot.pcb_path)):
            raise RuntimeError('review does not describe the export snapshot')
        output = staging / 'output'
        tool_info = export_manufacturing(snapshot, output)
        dfm = check_jlcpcb(snapshot)
        (output / 'jlcpcb-dfm.json').write_text(json.dumps(dfm, indent=2) + '\n', encoding='utf-8')
        stock = check_stock(output / 'bom.csv', output, quantity=quantity)
        assembly = tool_info.get('assembly', {})
        assert_current(project, expected)
        assert_current(snapshot, expected)
        manufacturing_blocked = not dfm['passed'] or not stock['passed'] or not assembly.get('passed', False)
        if manufacturing_blocked and not preview:
            return {'released': False, 'exit_code': 1, 'review': json.loads(render_review_json(report)),
                    'jlcpcb_dfm': dfm, 'stock': stock, 'assembly': assembly}
        blocked = blocked or manufacturing_blocked
        if input_hashes(snapshot) != expected:
            raise RuntimeError('export changed reviewed source inputs')
        (output / 'review.json').write_text(render_review_json(report) + '\n', encoding='utf-8')
        if preview:
            failures = '\n'.join(f'- {item.check_id}: {item.detail}' for item in report.results if not item.passed)
            if not dfm['passed']:
                failures += '\n- JLCPCB baseline failed; see jlcpcb-dfm.json.'
            if not stock['passed']:
                failures += '\n- Retail stock shortage or unknown inventory; see stock.csv and stock.json.'
            if not assembly.get('passed', False):
                failures += '\n- Assembly rules/models or supplier placement review unresolved; see assembly.json and assembly-audit.json.'
            (output / 'PREVIEW.txt').write_text(
                'JLCPCB UPLOAD / QUOTATION REVIEW ONLY — NOT A FABRICATION RELEASE\n\n'
                'Files come from the saved native CAD. Review results are in review.json.\n'
                'The project lifecycle and any existing fabrication package are unchanged.\n'
                'Resolve release findings and verify supplier placement before ordering.\n\n'
                + (failures or 'No registered review failure; preview still does not grant release.') + '\n',
                encoding='utf-8')
        else:
            copy_inputs(snapshot, output / 'sources', expected)
        manifest = {
            'schema_version': 1, 'project': project.manifest.name,
            'purpose': 'upload-preview' if preview else 'fabrication-release',
            'board_quantity': quantity,
            'inputs': expected, 'outputs': output_hashes(output), 'toolchain': tool_info,
        }
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
        (output / 'SOURCE.json').write_bytes(manifest_bytes)
        assert_current(project, expected)
        record = {'schema_version': 2, 'lifecycle': 'RELEASED', 'inputs': expected,
                  'output': 'fabrication',
                  'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest()}
        state = unaliased_path(project.root, workspace / 'release.json')
        before_state = state.read_bytes() if state.is_file() else None
        with recovery_directory(project, 'release') as recovery:
            previous = recovery / 'previous-fabrication'
            # Native tools use a short temporary path. Final publication
            # must be staged on the project's volume for atomic rename.
            publishable = recovery / 'output'
            shutil.copytree(output, publishable)
            if (output_hashes(publishable) != manifest['outputs']
                    or (publishable / 'SOURCE.json').read_bytes() != manifest_bytes):
                raise RuntimeError('release copy changed before publication')
            output = publishable
            had_previous = destination.exists()
            if before_state is not None:
                replace_bytes(recovery / 'previous-release.json', before_state)
            replace_bytes(recovery / 'journal.json', json.dumps({
                'operation': 'release', 'had_previous': had_previous,
                'had_state': before_state is not None,
            }).encode())
            published = False
            try:
                assert_current(project, expected)
                unaliased_path(project.root, destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                unaliased_path(project.root, destination)
                if had_previous:
                    destination.rename(previous)
                output.rename(destination)
                published = True
                assert_current(project, expected)
                if not preview:
                    _write_state(state, record)
                assert_current(project, expected)
            except BaseException:
                try:
                    # Handle interruption immediately after rename as well.
                    if published or (not output.exists() and destination.exists()):
                        destination.rename(recovery / 'rejected-output')
                    if previous.exists():
                        previous.rename(destination)
                    if before_state is None:
                        state.unlink(missing_ok=True)
                    else:
                        replace_bytes(state, before_state)
                except BaseException as error:  # noqa: BLE001 -- Preserve recovery after interrupted rollback.
                    raise RecoveryRequired(
                        f'Release rollback incomplete; originals retained in {recovery}: {error}'
                    ) from None
                shutil.rmtree(contained(project.root, recovery))
                raise
    return {'released': not preview, 'prepared': True, 'review_blocked': bool(blocked),
            'board_quantity': quantity, 'dfm_passed': dfm['passed'], 'retail_stock_passed': stock['passed'],
            'assembly_inventory_confirmed': False,
            'assembly_passed': assembly.get('passed', False),
            'exit_code': int(bool(blocked)), 'output': str(destination),
            'manifest_sha256': record['manifest_sha256']}
