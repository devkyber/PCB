import json
from pathlib import Path

import pytest

from pcb_copilot import release
from pcb_copilot.models import Lifecycle
from pcb_copilot.project import load_project
from pcb_copilot.review.models import CheckResult, CheckScope, ReviewReport
from pcb_copilot.state import effective_lifecycle


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
        return {'tool': 'fixture'}
    monkeypatch.setattr(release, 'export_manufacturing', export)
    monkeypatch.setattr(release, 'review_project', lambda project: report(project))
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
                                   'evidence/index.yaml'])
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


@pytest.mark.slow
def test_native_release_on_disposable_fixture(project_copy):
    """Synthetic decisions exercise the gate; these are never real approvals."""
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
    assert result['released'], result
    assert effective_lifecycle(project) is Lifecycle.RELEASED
    output = project.root / 'fabrication'
    assert (output / 'gerbers/baro-bmp390-F_Cu.gbr').stat().st_size
    assert (output / 'sources/review-signoff.yaml').read_bytes() == worksheet.read_bytes()
    assert json.loads((output / 'SOURCE.json').read_text())['outputs'] == release.output_hashes(output)
