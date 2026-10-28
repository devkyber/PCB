import json
import os
from pathlib import Path

import pytest

from pcb_copilot import release
from pcb_copilot.models import Lifecycle
from pcb_copilot.project import load_project
from pcb_copilot.review.models import CheckResult, CheckScope, ReviewReport
from pcb_copilot.state import effective_lifecycle


@pytest.mark.parametrize('preview,ancestor', [(False, False), (True, False), (True, True)])
def test_release_rejects_aliased_destination_without_touching_owner_directory(
    project_copy, monkeypatch, preview, ancestor,
):
    project = load_project(project_copy)
    owner = project.root / 'owner-notes'
    owner.mkdir()
    sentinel = owner / 'untracked-owner.txt'
    sentinel.write_bytes(b'unrelated owner bytes must survive')
    destination = project.root / ('output/jlcpcb-preview' if preview else 'fabrication')
    alias = destination.parent if ancestor else destination
    alias.parent.mkdir(exist_ok=True)
    try:
        alias.symlink_to(owner, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'directory symlinks unavailable: {exc}')
    monkeypatch.setattr(release, 'review_project', lambda *a: pytest.fail('aliased output reached review'))
    with pytest.raises(ValueError, match='symlink or reparse'):
        release.release_project(project, preview=preview)
    assert sentinel.read_bytes() == b'unrelated owner bytes must survive'
    assert alias.is_symlink()
    assert list(owner.iterdir()) == [sentinel]


def test_alias_created_during_export_cannot_redirect_publication(project_copy, exporter, monkeypatch):
    project = load_project(project_copy)
    owner = project.root / 'owner-notes'
    owner.mkdir()
    sentinel = owner / 'keep.txt'
    sentinel.write_bytes(b'owner')

    def redirected(snapshot, output):
        result = exporter(snapshot, output)
        (project.root / 'output').mkdir(exist_ok=True)
        try:
            os.symlink(owner, project.root / 'output/jlcpcb-preview', target_is_directory=True)
        except OSError as exc:
            pytest.skip(f'directory symlinks unavailable: {exc}')
        return result

    monkeypatch.setattr(release, 'export_manufacturing', redirected)
    with pytest.raises(ValueError, match='symlink or reparse'):
        release.release_project(project, preview=True)
    assert sentinel.read_bytes() == b'owner'
    assert list(owner.iterdir()) == [sentinel]


def test_blocked_review_cannot_return_stale_owner_results(project_copy, monkeypatch):
    project = load_project(project_copy)

    def edited(snapshot):
        result = report(snapshot, True)
        (project.root / 'DEVIATIONS.md').write_bytes(b'new owner decision')
        return result

    monkeypatch.setattr(release, 'review_project', edited)
    with pytest.raises(RuntimeError, match='inputs changed'):
        release.release_project(project)
    assert (project.root / 'DEVIATIONS.md').read_bytes() == b'new owner decision'
    assert not (project.root / 'fabrication').exists()


def test_blocked_manufacturing_cannot_return_stale_owner_results(project_copy, exporter, monkeypatch):
    project = load_project(project_copy)

    def edited(*args, **kwargs):
        (project.root / 'DEVIATIONS.md').write_bytes(b'changed during supplier checks')
        return {'passed': False}

    monkeypatch.setattr(release, 'check_stock', edited)
    with pytest.raises(RuntimeError, match='inputs changed'):
        release.release_project(project)
    assert (project.root / 'DEVIATIONS.md').read_bytes() == b'changed during supplier checks'


def test_release_state_alias_never_overwrites_owner_file(project_copy, exporter):
    project = load_project(project_copy)
    workspace = project.root / '.pcb-copilot'
    workspace.mkdir(exist_ok=True)
    owner = project.root / 'owner-note.json'
    owner.write_bytes(b'unrelated owner note')
    try:
        (workspace / 'release.json').symlink_to(owner)
    except OSError as exc:
        pytest.skip(f'symlinks unavailable: {exc}')
    with pytest.raises(ValueError, match='symlink or reparse'):
        release.release_project(project)
    assert owner.read_bytes() == b'unrelated owner note'
    assert not (project.root / 'fabrication').exists()


def report(project, blocked=False):
    from pcb_copilot.review.fingerprint import pcb_digest, schematic_digest
    scope = CheckScope('test fixture', 'hardware approval', True, False)
    return ReviewReport(project.manifest.name, schematic_digest(project.schematic_path),
                        pcb_digest(project.pcb_path),
                        (CheckResult('signoff', not blocked, 'fixture', scope),), (), blocked)


@pytest.fixture
def exporter(monkeypatch):
    def export(project, destination):
        assert not (project.root / '.pcb-copilot').exists()
        destination.mkdir()
        for name in ('board.gbr', 'board.drl', 'bom.csv', 'positions.csv'):
            (destination / name).write_text('fixture export\n')
        return {'tool': 'fixture', 'assembly': {'passed': True}}
    monkeypatch.setattr(release, 'export_manufacturing', export)
    monkeypatch.setattr(release, 'review_project', lambda project: report(project))
    monkeypatch.setattr(release, 'check_jlcpcb', lambda project: {'passed': True})
    monkeypatch.setattr(release, 'check_stock', lambda *a, **k: {'passed': True})
    return export


def test_release_refuses_blocked_review_without_export(project_copy, monkeypatch, tree_hash):
    before = tree_hash(project_copy)
    monkeypatch.setattr(release, 'review_project', lambda project: report(project, True))
    monkeypatch.setattr(release, 'export_manufacturing', lambda *a: pytest.fail('blocked design exported'))
    result = release.release_project(load_project(project_copy))
    assert result['exit_code'] == 1
    assert tree_hash(project_copy) == before


def test_release_publishes_verified_snapshot_and_detects_tampering(project_copy, exporter):
    project = load_project(project_copy)
    result = release.release_project(project)
    assert result['exit_code'] == 0
    output = Path(result['output'])
    manifest = json.loads((output / 'SOURCE.json').read_text())
    assert manifest['inputs'][project.pcb_path.name]
    assert manifest['outputs']['bom.csv']
    assert (output / 'review.json').is_file()
    assert (output / 'sources' / project.pcb_path.name).read_bytes() == project.pcb_path.read_bytes()
    assert effective_lifecycle(project) is Lifecycle.RELEASED
    (output / 'bom.csv').write_text('tampered')
    assert effective_lifecycle(project) is Lifecycle.DRAFT


@pytest.mark.parametrize('changed', ['DEVIATIONS.md', 'review-profile.yaml', 'baro-bmp390.kicad_pro',
                                   'evidence/index.yaml', 'jlcpcb-assembly.yaml'])
def test_release_is_stale_after_any_review_input_changes(project_copy, exporter, changed):
    project = load_project(project_copy)
    release.release_project(project)
    with (project.root / changed).open('a') as stream:
        stream.write('\n# changed\n')
    assert effective_lifecycle(project) is Lifecycle.DRAFT


def test_failed_export_preserves_previous_package_and_state(project_copy, exporter, monkeypatch, tree_hash):
    project = load_project(project_copy)
    release.release_project(project)
    before = tree_hash(project_copy)
    def fail(project, output):
        output.mkdir()
        (output / 'partial.gbr').write_text('partial')
        raise RuntimeError('export failed')
    monkeypatch.setattr(release, 'export_manufacturing', fail)
    with pytest.raises(RuntimeError, match='export failed'):
        release.release_project(project)
    assert tree_hash(project_copy) == before


def test_concurrent_edit_during_export_refuses_publication(project_copy, exporter, monkeypatch):
    project = load_project(project_copy)
    def edit(snapshot, output):
        result = exporter(snapshot, output)
        (project.root / 'DEVIATIONS.md').write_text('concurrent human edit')
        return result
    monkeypatch.setattr(release, 'export_manufacturing', edit)
    with pytest.raises(RuntimeError, match='changed'):
        release.release_project(project)
    assert not (project.root / 'fabrication').exists()
    assert not (project.root / '.pcb-copilot/release.json').exists()


def test_state_write_failure_rolls_back_release_publication(project_copy, exporter, monkeypatch, tree_hash):
    project = load_project(project_copy)
    release.release_project(project)
    before = tree_hash(project_copy)
    monkeypatch.setattr(release, '_write_state', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError, match='disk full'):
        release.release_project(project)
    assert tree_hash(project_copy) == before


def test_interrupt_restores_previous_release(project_copy, exporter, monkeypatch, tree_hash):
    project = load_project(project_copy)
    release.release_project(project)
    before = tree_hash(project_copy)
    monkeypatch.setattr(release, '_write_state', lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        release.release_project(project)
    assert tree_hash(project_copy) == before
    assert not (project.root / '.pcb-copilot/operation.lock').exists()


def test_nested_source_json_is_covered_by_output_hashes(tmp_path):
    (tmp_path / 'sources').mkdir()
    (tmp_path / 'sources/SOURCE.json').write_text('evidence')
    (tmp_path / 'SOURCE.json').write_text('manifest')
    assert set(release.output_hashes(tmp_path)) == {'sources/SOURCE.json'}


def test_preview_exports_blocked_review_without_granting_release(project_copy, exporter, monkeypatch):
    project = load_project(project_copy)
    monkeypatch.setattr(release, 'review_project', lambda project: report(project, True))
    result = release.release_project(project, preview=True)
    assert result['prepared'] and not result['released'] and result['review_blocked']
    assert result['exit_code'] == 1
    output = Path(result['output'])
    assert (output / 'PREVIEW.txt').is_file()
    manifest = json.loads((output / 'SOURCE.json').read_text())
    assert manifest['purpose'] == 'upload-preview'
    assert manifest['outputs'] == release.output_hashes(output)
    assert not (project.root / 'fabrication').exists()
    assert not (project.root / '.pcb-copilot/release.json').exists()
    assert effective_lifecycle(project) is Lifecycle.DRAFT


def test_preview_preserves_previous_release_and_state(project_copy, exporter, tree_hash):
    project = load_project(project_copy)
    release.release_project(project)
    before = tree_hash(project.root / 'fabrication')
    state = (project.root / '.pcb-copilot/release.json').read_bytes()
    result = release.release_project(project, preview=True)
    assert not result['released']
    assert tree_hash(project.root / 'fabrication') == before
    assert (project.root / '.pcb-copilot/release.json').read_bytes() == state
    assert effective_lifecycle(project) is Lifecycle.RELEASED


def test_failed_preview_preserves_previous_preview(project_copy, exporter, monkeypatch, tree_hash):
    project = load_project(project_copy)
    release.release_project(project, preview=True)
    before = tree_hash(project_copy)
    def fail(project, output):
        output.mkdir()
        (output / 'partial.gbr').write_text('partial')
        raise RuntimeError('export failed')
    monkeypatch.setattr(release, 'export_manufacturing', fail)
    with pytest.raises(RuntimeError, match='export failed'):
        release.release_project(project, preview=True)
    assert tree_hash(project_copy) == before


@pytest.mark.parametrize('gate', ['check_stock', 'check_jlcpcb'])
def test_manufacturing_failure_preserves_release_but_publishes_marked_preview(
    project_copy, exporter, monkeypatch, tree_hash, gate,
):
    project = load_project(project_copy)
    release.release_project(project)
    before = tree_hash(project.root / 'fabrication')
    state = (project.root / '.pcb-copilot/release.json').read_bytes()
    monkeypatch.setattr(release, gate, lambda *a, **k: {'passed': False})
    result = release.release_project(project, quantity=5)
    assert not result['released'] and result['exit_code'] == 1
    assert tree_hash(project.root / 'fabrication') == before
    preview = release.release_project(project, preview=True, quantity=5)
    assert preview['prepared'] and preview['review_blocked'] and preview['board_quantity'] == 5
    assert (Path(preview['output']) / 'jlcpcb-dfm.json').exists()
    assert (project.root / '.pcb-copilot/release.json').read_bytes() == state
    assert tree_hash(project.root / 'fabrication') == before


@pytest.mark.slow
def test_native_signoff_cannot_bypass_missing_assembly_contracts(project_copy):
    """A generic signoff does not approve unknown vendor angles/model inventory."""
    from datetime import UTC, datetime

    import yaml

    from pcb_copilot.review.signoff import prepare_signoff

    project = load_project(project_copy)
    blocked = release.release_project(project)
    assert not blocked['released']
    assert not (project.root / 'fabrication').exists()
    worksheet = prepare_signoff(project)
    document = yaml.safe_load(worksheet.read_text(encoding='utf-8'))
    for record in document['records']:
        record.update(reviewer='AUTOMATED TEST FIXTURE ONLY', decision='accepted',
                      note='Synthetic gate fixture; NOT an engineering approval.',
                      signed_on=datetime.now(UTC).date().isoformat())
    worksheet.write_text(yaml.safe_dump(document), encoding='utf-8')
    result = release.release_project(project)
    assert not result['released'], result
    assert not (project.root / 'fabrication').exists()
    assert any(r['check_id'] == 'assembly_contracts' and not r['passed'] for r in result['review']['results'])


def test_missing_supplier_assembly_review_blocks_release_and_preserves_previous(project_copy, exporter, monkeypatch, tree_hash):
    project = load_project(project_copy)
    release.release_project(project)
    before = tree_hash(project.root / 'fabrication')

    def unverified(snapshot, output):
        result = exporter(snapshot, output)
        result['assembly']['passed'] = False
        return result

    monkeypatch.setattr(release, 'export_manufacturing', unverified)
    result = release.release_project(project)
    assert not result['released'] and not result['assembly']['passed']
    assert tree_hash(project.root / 'fabrication') == before
    result = release.release_project(project, preview=True)
    assert result['prepared'] and not result['assembly_passed']
    assert 'supplier placement review unresolved' in (project.root / 'output/jlcpcb-preview/PREVIEW.txt').read_text(encoding='utf-8')
