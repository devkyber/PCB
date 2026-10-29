"""Recorded example artifacts must follow current sources and exact archive bytes."""

import hashlib
import json
import os
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
    assert result['capture_unchanged_during_verification'] is True
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


@pytest.mark.parametrize('target', ['schematic.png', 'SOURCE.json'])
def test_capture_changed_during_final_source_check_is_not_reported_verified(example, monkeypatch, target):
    repository, _, output, current, _ = example
    calls = 0

    def current_inputs(_project):
        nonlocal calls
        calls += 1
        if calls == 2:
            path = output / target
            path.write_bytes(path.read_bytes() + b'\nCHANGED DURING VERIFICATION\n')
        return current.copy()

    monkeypatch.setattr(checker, 'input_hashes', current_inputs)
    with pytest.raises((OSError, ValueError, RuntimeError), match='capture changed during verification'):
        checker.check_example(repository, 'rs485-interface')


@pytest.mark.parametrize('target', ['schematic.png', 'SOURCE.json'])
def test_identical_byte_replacement_during_check_invalidates_observed_capture(example, monkeypatch, target):
    repository, _, output, current, _ = example
    calls = 0

    def current_inputs(_project):
        nonlocal calls
        calls += 1
        if calls == 2:
            path = output / target
            replacement = output / 'new-publisher-file'
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)
        return current.copy()

    monkeypatch.setattr(checker, 'input_hashes', current_inputs)
    with pytest.raises(RuntimeError, match='capture changed during verification'):
        checker.check_example(repository, 'rs485-interface')


@pytest.mark.parametrize('target', ['schematic.png', 'SOURCE.json'])
@pytest.mark.parametrize('during_check', [False, True])
def test_manifest_and_artifact_hardlink_aliases_cannot_pass(example, monkeypatch, target, during_check):
    repository, _, output, current, _ = example
    calls = 0

    def alias():
        os.link(output / target, repository / 'second-name-for-published-file')

    def current_inputs(_project):
        nonlocal calls
        calls += 1
        if calls == 2:
            alias()
        return current.copy()

    if during_check:
        monkeypatch.setattr(checker, 'input_hashes', current_inputs)
    else:
        alias()
    with pytest.raises((ValueError, RuntimeError), match='aliased|capture changed during verification'):
        checker.check_example(repository, 'rs485-interface')


def test_selected_example_reparse_point_is_rejected_before_project_loading(tmp_path, monkeypatch):
    root = tmp_path / 'examples/rs485-interface'
    root.mkdir(parents=True)
    original = checker.Path.lstat

    def lstat(path):
        if path == root:
            return SimpleNamespace(st_mode=original(path).st_mode, st_file_attributes=0x400)
        return original(path)

    monkeypatch.setattr(checker.Path, 'lstat', lstat)
    monkeypatch.setattr(checker, 'load_project', lambda _: pytest.fail('redirected project was loaded'))
    with pytest.raises(ValueError, match='aliased'):
        checker.check_example(tmp_path, 'rs485-interface')


@pytest.mark.parametrize('version', [True, False, 1.0, '1'])
def test_manifest_schema_version_must_be_an_integer(example, version):
    repository, _, output, _, manifest = example
    manifest['schema_version'] = version
    (output / 'SOURCE.json').write_bytes(json.dumps(manifest).encode())
    with pytest.raises(ValueError, match='stale or has no preserved source identity'):
        checker.check_example(repository, 'rs485-interface')


def test_empty_recorded_log_is_still_a_valid_artifact(example):
    repository, _, output, _, manifest = example
    (output / 'empty.stderr.txt').write_bytes(b'')
    manifest['outputs']['empty.stderr.txt'] = {'sha256': hashlib.sha256(b'').hexdigest(), 'bytes': 0}
    (output / 'SOURCE.json').write_bytes(json.dumps(manifest).encode())
    assert checker.check_example(repository, 'rs485-interface')['captured_artifacts_verified'] == 6


def test_legacy_gpio_capture_still_uses_project_relative_artifact_paths(example, monkeypatch):
    repository, root, output, current, manifest = example
    # Keep the shared synthetic project; this exercises only the legacy schema
    # and path boundary, with source loading already isolated by the fixture.
    legacy = {'schema_version': 1, 'inputs': current,
              'outputs': {'output/' + name: record['sha256'] for name, record in manifest['outputs'].items()}}
    (output / 'SOURCE.json').write_bytes(json.dumps(legacy).encode())
    monkeypatch.setattr(checker, 'load_project', lambda _: SimpleNamespace(root=root))
    result = checker.check_example(repository, 'gpio-indicator')
    assert result['captured_artifacts_verified'] == 5
    assert result['capture_unchanged_during_verification'] is True
