import json
from types import SimpleNamespace

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


@pytest.mark.parametrize('kind', ['candidate-bytes', 'source-schematic', 'source-rules'])
def test_native_drift_injects_only_one_newline_in_disposable_declared_input(repo_root, tmp_path, kind):
    source = source_project(repo_root)
    expected = input_hashes(source)
    snapshot = evaluate.snapshot_project(source, tmp_path, kind, expected)
    target = snapshot.pcb_path.with_suffix('.kicad_dru') if kind == 'source-rules' else snapshot.schematic_path
    original = target.read_bytes()
    injection = evaluate.inject_fault(snapshot, kind)
    after = input_hashes(snapshot)
    relative = target.relative_to(snapshot.root).as_posix()
    assert {name for name in expected if expected[name] != after[name]} == {relative}
    assert target.read_bytes() == original + b'\n'
    assert injection['before_sha256'] == expected[relative]
    assert injection['after_sha256'] == after[relative]
    assert input_hashes(source) == expected


def test_missing_preview_also_preserves_separate_candidate_project(repo_root, tmp_path):
    source = source_project(repo_root)
    expected = input_hashes(source)
    snapshot = evaluate.snapshot_project(source, tmp_path, 'saved', expected)
    candidate = evaluate.snapshot_project(source, tmp_path, 'candidate', expected)
    case, _ = evaluate._case(
        source, tmp_path, 'candidate-without-preview', expected, interface='native-cli', expected_code=2,
        diagnostic=evaluate.GUARD_MESSAGE, project=snapshot, candidate=candidate, fault='candidate-bytes',
        arguments=['update-schematic', str(snapshot.root), '--candidate', str(candidate.schematic_path), '--apply'],
    )
    assert case['outcome'] == 'met_expectation'
    assert case['checks_preserved_inputs'] and case['checks_preserved_candidate']
    assert case['candidate_inputs_before'] != case['candidate_inputs_after_injection']
    assert case['candidate_inputs_after_checks'] == input_hashes(candidate)
    assert case['injection']['after_check_sha256'] == case['injection']['after_sha256']
    assert input_hashes(source) == expected == input_hashes(snapshot)


def test_expected_rejection_cannot_hide_a_candidate_write(repo_root, tmp_path, monkeypatch):
    source = source_project(repo_root)
    expected = input_hashes(source)
    snapshot = evaluate.snapshot_project(source, tmp_path, 'saved', expected)
    candidate = evaluate.snapshot_project(source, tmp_path, 'candidate', expected)

    def writes_candidate(output, name, interface, arguments, *, timeout):
        rules = candidate.pcb_path.with_suffix('.kicad_dru')
        rules.write_bytes(rules.read_bytes() + b'\nUNEXPECTED WRITE\n')
        (output / 'stdout.txt').write_text('', encoding='utf-8')
        (output / 'stderr.txt').write_text(evaluate.GUARD_MESSAGE, encoding='utf-8')
        return {'interface': interface, 'exit_code': 2, 'error': None,
                'stdout': 'stdout.txt', 'stderr': 'stderr.txt'}

    monkeypatch.setattr(evaluate, 'run_process', writes_candidate)
    case, _ = evaluate._case(
        source, tmp_path, 'candidate-write', expected, interface='native-cli', expected_code=2,
        diagnostic=evaluate.GUARD_MESSAGE, project=snapshot, candidate=candidate, fault='candidate-bytes',
        arguments=['update-schematic', str(snapshot.root), '--candidate', str(candidate.schematic_path), '--apply'],
    )
    assert case['outcome'] == 'harness_error'
    assert not case['checks_preserved_candidate']
    assert 'changed declared snapshot or candidate inputs' in case['actual']['error']
    assert input_hashes(source) == expected == input_hashes(snapshot)


@pytest.mark.parametrize('changes', [
    {'exit_code': False}, {'applied': True}, {'findings': None},
    {'findings': [{'severity': 'block'}]}, {'findings': [{}]},
])
def test_native_positive_control_rejects_contradictory_success_payload(changes):
    payload = {'exit_code': 0, 'applied': False, 'source_mode': 'native', 'findings': []}
    payload.update(changes)
    actual = {'interface': 'native-cli', 'exit_code': 0, 'error': None}
    assert evaluate.classify_result(actual, json.dumps(payload), '', 0, 'native') == 'harness_error'


@pytest.mark.parametrize('change', ['inputs', 'sources', 'project', 'options', 'version', None])
def test_native_control_requires_exact_current_binding(repo_root, tmp_path, change):
    source = source_project(repo_root)
    expected = input_hashes(source)
    snapshot = evaluate.snapshot_project(source, tmp_path, 'saved', expected)
    candidate = evaluate.snapshot_project(source, tmp_path, 'candidate', expected)
    binding = {
        'version': 1, 'project': str(snapshot.root.resolve()), 'inputs': expected,
        'options': {'mode': 'native', 'paired_pcb': False},
        'sources': {'schematic/' + candidate.schematic_path.name:
                    {'path': str(candidate.schematic_path.resolve()),
                     'sha256': expected[candidate.schematic_path.name]}},
    }
    if change:
        binding[change] = None
    (tmp_path / 'preview.json').write_text(json.dumps({'preview_binding': binding}), encoding='utf-8')
    control = {'outcome': 'met_expectation', 'actual': {'stdout': 'preview.json', 'error': None}}
    evaluate._check_native_control(control, tmp_path, expected, snapshot, candidate)
    assert control['outcome'] == ('harness_error' if change else 'met_expectation')
    assert input_hashes(source) == expected


def test_failed_independent_native_controls_skip_their_own_faults(repo_root, tmp_path, monkeypatch):
    source = source_project(repo_root)
    expected = input_hashes(source)
    calls = []
    monkeypatch.setattr('pcb_copilot.toolchain.discover_toolchain',
                        lambda _root: SimpleNamespace(kicad_cli='not-executed', kipython='not-executed'))
    monkeypatch.setattr(evaluate.subprocess, 'run',
                        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=b'10.0.6'))

    def failed_control(_source, _output, name, _expected, **kwargs):
        assert kwargs.get('fault') is None
        project, candidate = kwargs['project'], kwargs['candidate']
        calls.append((name, project.root, candidate.root))
        assert input_hashes(project) == input_hashes(candidate) == expected
        return {'name': name, 'outcome': 'mismatch', 'actual': {'error': None}}, project

    monkeypatch.setattr(evaluate, '_case', failed_control)
    cases = evaluate._native_cases(source, tmp_path, expected)
    assert tuple(case['name'] for case in cases) == evaluate.NATIVE_CASE_NAMES
    assert len({project for _name, project, _candidate in calls}) == 3
    assert len({candidate for _name, _project, candidate in calls}) == 3
    assert all(case['outcome'] == 'mismatch' for case in cases[::2])
    assert all(case['outcome'] == 'skipped' and case['depends_on'] == cases[index - 1]['name']
               for index, case in enumerate(cases) if index % 2)
    assert input_hashes(source) == expected
