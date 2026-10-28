import json

import pytest

from pcb_copilot.evidence.commands import verify_evidence
from pcb_copilot.layout.footprints import resolve_footprint
from pcb_copilot.project import load_project
from pcb_copilot.transaction import input_hashes
from tools import evaluate


def source_project(repo_root):
    return load_project(repo_root / 'examples/gpio-indicator')


def test_evaluation_output_is_new_and_external(tmp_path):
    repository = tmp_path / 'repository'
    repository.mkdir()
    with pytest.raises(ValueError, match='outside'):
        evaluate.new_output_directory(repository / 'evaluation', repository)
    existing = tmp_path / 'owner-files'
    existing.mkdir()
    (existing / 'notes.txt').write_bytes(b'owner work')
    with pytest.raises(FileExistsError):
        evaluate.new_output_directory(existing, repository)
    assert (existing / 'notes.txt').read_bytes() == b'owner work'


def test_snapshot_is_exact_and_omits_generated_outputs(repo_root, tmp_path):
    source = source_project(repo_root)
    expected = input_hashes(source)
    snapshot = evaluate.snapshot_project(source, tmp_path, 'control', expected)
    assert input_hashes(snapshot) == expected == input_hashes(source)
    assert not (snapshot.root / 'output').exists()
    assert not (snapshot.root / '.pcb-copilot').exists()
    with pytest.raises(ValueError, match='outside the source'):
        evaluate.snapshot_project(source, source.root / 'evaluation', 'unsafe', expected)


def test_direct_entrypoint_rejects_repository_output_before_any_write(repo_root):
    with pytest.raises(ValueError, match='outside'):
        evaluate.evaluate(repo_root, repo_root)


@pytest.mark.parametrize(('fault', 'message'), [
    ('footprint-geometry', 'beyond allowed model URI replacements'),
    ('model-corruption', 'hash mismatch'),
    ('selected-mpn', 'does not match the exact selected native MPN'),
])
def test_fault_injectors_reach_the_declared_validator_boundary(repo_root, tmp_path, fault, message):
    source = source_project(repo_root)
    expected = input_hashes(source)
    snapshot = evaluate.snapshot_project(source, tmp_path, fault, expected)
    _, _, selected = evaluate._targets(snapshot)
    assert resolve_footprint(snapshot, *selected).fidelity == 'real'
    injection = evaluate.inject_fault(snapshot, fault)
    assert injection['kind'] == fault
    after_injection = input_hashes(snapshot)
    assert after_injection != expected
    with pytest.raises(ValueError, match=message):
        resolve_footprint(snapshot, *selected)
    assert input_hashes(snapshot) == after_injection
    assert input_hashes(source) == expected


def test_evidence_injector_causes_real_archive_hash_failure(repo_root, tmp_path):
    source = source_project(repo_root)
    expected = input_hashes(source)
    snapshot = evaluate.snapshot_project(source, tmp_path, 'evidence', expected)
    assert verify_evidence(snapshot).exit_code == 0
    evaluate.inject_fault(snapshot, 'evidence-corruption')
    result = verify_evidence(snapshot)
    assert result.exit_code == 1
    assert any('archive.hash_mismatch' in item for item in result.machine_failures)
    assert input_hashes(source) == expected


@pytest.mark.parametrize(('interface', 'code', 'stdout', 'stderr', 'error', 'expected'), [
    ('cli', 2, '', evaluate.GUARD_MESSAGE, None, 'met_expectation'),
    ('cli', 2, '', 'a different argparse failure', None, 'mismatch'),
    ('cli', 0, '', evaluate.GUARD_MESSAGE, None, 'mismatch'),
    ('cli', None, '', '', 'timed out', 'harness_error'),
    ('validator-api', 1, 'Traceback only', '', None, 'harness_error'),
    ('validator-api', 1, json.dumps({'accepted': True}), '', None, 'mismatch'),
])
def test_unrelated_errors_and_acceptance_are_not_counted_as_expected_rejections(
    interface, code, stdout, stderr, error, expected,
):
    actual = {'interface': interface, 'exit_code': code, 'error': error}
    assert evaluate.classify_result(actual, stdout, stderr, 2, evaluate.GUARD_MESSAGE) == expected


def test_missing_preview_case_uses_real_cli_and_preserves_source(repo_root, tmp_path):
    source = source_project(repo_root)
    expected = input_hashes(source)
    case, snapshot = evaluate._case(source, tmp_path, 'missing-preview', expected,
                                    interface='cli', expected_code=2,
                                    diagnostic=evaluate.GUARD_MESSAGE)
    assert case['outcome'] == 'met_expectation'
    assert case['actual']['exit_code'] == 2
    assert case['checks_preserved_inputs']
    assert input_hashes(source) == expected == input_hashes(snapshot)
