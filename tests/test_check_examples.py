"""Recorded example artifacts must follow current sources and exact archive bytes."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from tools import check_examples as checker


@pytest.fixture
def example(tmp_path, monkeypatch):
    root = tmp_path / 'examples/rs485-interface'
    output = root / 'output'
    output.mkdir(parents=True)
    project = SimpleNamespace(root=root)
    current = {'board.kicad_pcb': 'a' * 64, 'review-signoff.yaml': None}
    manifest = {'schema_version': 1, 'source_project': 'examples/rs485-interface',
                'source_inputs': current.copy(), 'source_cad_unchanged': True, 'outputs': {}}
    for name in ('schematic.pdf', 'schematic.png', 'assembly.png', 'top-copper.png', 'bottom-copper.png'):
        payload = ('native test boundary ' + name).encode()
        (output / name).write_bytes(payload)
        manifest['outputs'][name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
    (output / 'SOURCE.json').write_bytes(json.dumps(manifest).encode())
    monkeypatch.setattr(checker, 'load_project', lambda _: project)
    monkeypatch.setattr(checker, 'input_hashes', lambda _: current.copy())
    good = SimpleNamespace(exit_code=0)
    monkeypatch.setattr(checker, 'verify_evidence', lambda _: good)
    monkeypatch.setattr(checker, 'verify_schematic_evidence', lambda _: good)
    monkeypatch.setattr(checker, '_footprints', lambda _: 13)
    return tmp_path, root, output, current, manifest


def test_intact_capture_is_verified_without_claiming_native_rerun(example):
    repository, _, _, _, _ = example
    result = checker.check_example(repository, 'rs485-interface')
    assert result['physical_footprints_verified'] == 13
    assert result['captured_artifacts_verified'] == 5
    assert result['native_review_rerun'] is False


@pytest.mark.parametrize('fault', ['source', 'preservation', 'missing', 'changed', 'byte-count', 'escape', 'project'])
def test_stale_or_misleading_capture_is_rejected(example, fault):
    repository, _, output, current, manifest = example
    if fault == 'source':
        current['board.kicad_pcb'] = 'b' * 64
    elif fault == 'preservation':
        manifest['source_cad_unchanged'] = False
    elif fault == 'missing':
        (output / 'assembly.png').unlink()
    elif fault == 'changed':
        (output / 'assembly.png').write_bytes(b'tampered')
    elif fault == 'byte-count':
        manifest['outputs']['assembly.png']['bytes'] += 1
    elif fault == 'escape':
        manifest['outputs']['../owner.png'] = manifest['outputs'].pop('assembly.png')
    else:
        manifest['source_project'] = 'tests/fixtures/boards/retired'
    (output / 'SOURCE.json').write_bytes(json.dumps(manifest).encode())
    with pytest.raises((OSError, ValueError)):
        checker.check_example(repository, 'rs485-interface')


def test_archive_or_selected_part_failure_cannot_be_replaced_by_capture_hashes(example, monkeypatch):
    repository, _, _, _, _ = example
    bad = SimpleNamespace(exit_code=1, machine_failures=('selected-part datasheet missing',), conflicts=())
    monkeypatch.setattr(checker, 'verify_schematic_evidence', lambda _: bad)
    with pytest.raises(ValueError, match='selected-part datasheet missing'):
        checker.check_example(repository, 'rs485-interface')


def test_non_example_selection_is_rejected_before_loading(tmp_path, monkeypatch):
    monkeypatch.setattr(checker, 'load_project', lambda _: pytest.fail('unsupported project was loaded'))
    with pytest.raises(ValueError, match='documented active example'):
        checker.check_example(tmp_path, '../tests/fixtures/boards/retired')
