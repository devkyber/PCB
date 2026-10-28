"""Synthetic CLI packets exercise media claims without image or native tools."""

import copy
import hashlib
import json
import subprocess
from types import SimpleNamespace

import pytest

from tools import media_evidence


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def packet(tmp_path):
    root = tmp_path / 'capture'
    logs = root / 'logs'
    logs.mkdir(parents=True)
    snapshot = 'workspace/rover-pdb'
    commands = [
        ['pcb-copilot', 'status', snapshot],
        ['pcb-copilot', 'research', snapshot, '--verify'],
        ['pcb-copilot', 'update-schematic', snapshot, '--candidate',
         snapshot + '/rover-pdb.kicad_sch', '--apply'],
        ['pcb-copilot', 'review', snapshot, '--format', 'json'],
    ]
    review = {
        'schema_version': 1, 'project': 'rover-pdb', 'schematic_hash': 'f' * 64,
        'pcb_hash': 'b' * 64, 'blocking': True,
        'results': [{'check_id': name, 'passed': name != 'signoff', 'detail': 'synthetic scoped result'}
                    for name in ('research', 'datasheets', 'erc', 'schematic_ownership', 'netlist_parity',
                                 'placement', 'design_rules', 'drc', 'jlcpcb_dfm', 'assembly_contracts',
                                 'routing_settings', 'routing_topology', 'schematic_quality', 'signoff')],
        'findings': [{'check_id': 'signoff', 'kind': 'human_decision', 'blocking': True,
                      'detail': 'Synthetic review remains unsigned.'}],
    }
    evidence = ('1 evidence record(s) verified\n\nMACHINE FAILURES: none\n\n'
                'EXTRACTED FACTS: none\n\nREVIEW REQUIRED:\n- Archive identity is not circuit correctness.\n\n'
                'CONFLICTS: none\n\nPROPOSED DESIGN_BASIS ROWS: none\n')
    output = {'status': 'Project: rover-pdb\nLifecycle: DRAFT\n',
              'evidence': evidence, 'missing-preview': '', 'review': json.dumps(review)}
    steps = []
    for name, command, code in zip(('status', 'evidence', 'missing-preview', 'review'),
                                   commands, (0, 0, 2, 1), strict=True):
        (logs / f'{name}.stdout.txt').write_text(output[name], encoding='utf-8')
        (logs / f'{name}.stderr.txt').write_text(
            'pcb-copilot: error: ' + media_evidence.GUARD + '; run preview again\n'
            if name == 'missing-preview' else '', encoding='utf-8')
        steps.append({'name': name, 'command': command, 'exit_code': code, 'error': None,
                      'stdout': f'logs/{name}.stdout.txt', 'stderr': f'logs/{name}.stderr.txt'})
    inputs = {'rover-pdb.kicad_sch': 'a' * 64, 'rover-pdb.kicad_pcb': 'b' * 64,
              'rover-pdb.kicad_dru': None, 'evidence/index.yaml': 'c' * 64}
    cad = {key: value for key, value in inputs.items() if key.endswith(('.kicad_sch', '.kicad_pcb', '.kicad_dru'))}
    document = {'schema_version': 1, 'started_utc': '2026-10-29T00:00:00+00:00',
                'mode': 'full', 'source_project': 'projects/rover-pdb', 'error': None,
                'source_inputs_unchanged': True, 'source_cad_unchanged': True,
                'snapshot_inputs_unchanged': True, 'source_inputs_before': inputs,
                'source_inputs_after': dict(inputs), 'source_cad_before': cad,
                'source_cad_after': dict(cad), 'steps': steps, 'review': review, 'exit_code': 1}
    path = root / 'transcript.json'
    save(path, document)
    return path, document


def save(path, document):
    path.write_text(json.dumps(document), encoding='utf-8')


def write_review(path, document, review):
    (path.parent / document['steps'][3]['stdout']).write_text(json.dumps(review), encoding='utf-8')
    document['review'] = copy.deepcopy(review)
    save(path, document)


def test_valid_packet_retains_raw_log_hashes_and_blocked_results(tmp_path):
    path, document = packet(tmp_path)
    result = media_evidence.demo_data(path)
    assert result['demo_exit_code'] == 1
    assert result['review']['blocking'] is True
    assert sum(item['passed'] for item in result['review']['results']) == 13
    for record, original in zip(result['steps'], document['steps'], strict=True):
        for stream in ('stdout', 'stderr'):
            assert record[stream + '_sha256'] == sha((path.parent / original[stream]).read_bytes())


def test_forged_cached_pass_cannot_replace_blocked_raw_review(tmp_path):
    path, document = packet(tmp_path)
    document['review']['blocking'] = False
    document['review']['findings'] = []
    for result in document['review']['results']:
        result['passed'] = True
    save(path, document)
    with pytest.raises(ValueError, match='cached review'):
        media_evidence.demo_data(path)


@pytest.mark.parametrize('fault', ['blocking_flag', 'blocked_exit', 'blocking_finding',
                                  'string_blocker', 'duplicate_check', 'empty_results'])
def test_raw_review_inconsistencies_are_rejected_even_when_cache_matches(tmp_path, fault):
    path, document = packet(tmp_path)
    review = document['review']
    if fault == 'blocking_flag': review['blocking'] = False
    if fault == 'blocked_exit': document['steps'][3]['exit_code'] = document['exit_code'] = 0
    if fault in {'blocking_finding', 'string_blocker'}:
        for result in review['results']:
            result['passed'] = True
        review['blocking'] = False
        document['steps'][3]['exit_code'] = document['exit_code'] = 0
    if fault == 'string_blocker': review['findings'][0]['blocking'] = 'true'
    if fault == 'duplicate_check': review['results'].append(copy.deepcopy(review['results'][0]))
    if fault == 'empty_results': review['results'] = []
    write_review(path, document, review)
    with pytest.raises(ValueError):
        media_evidence.demo_data(path)


@pytest.mark.parametrize('name', ['../outside.txt', '/outside.txt', 'C:/outside.txt',
                                 'logs/../../outside.txt', 'logs\\status.stdout.txt', ''])
def test_log_paths_cannot_escape_or_use_ambiguous_platform_syntax(tmp_path, name):
    path, document = packet(tmp_path)
    document['steps'][0]['stdout'] = name
    save(path, document)
    with pytest.raises(ValueError, match='relative path'):
        media_evidence.demo_data(path)


@pytest.mark.parametrize('directory_link', [False, True])
def test_log_file_and_directory_symlinks_are_rejected(tmp_path, directory_link):
    path, document = packet(tmp_path)
    if directory_link:
        outside = tmp_path / 'outside'
        outside.mkdir()
        target = path.parent / 'linked-logs'
        document['steps'][0]['stdout'] = 'linked-logs/status.stdout.txt'
        (outside / 'status.stdout.txt').write_text('Project: rover-pdb', encoding='utf-8')
    else:
        outside = tmp_path / 'outside.txt'
        outside.write_text('Project: rover-pdb', encoding='utf-8')
        target = path.parent / document['steps'][0]['stdout']
        target.unlink()
    try:
        target.symlink_to(outside, target_is_directory=directory_link)
    except OSError:
        pytest.skip('symlink creation is unavailable on this host')
    save(path, document)
    with pytest.raises(ValueError, match='symlink'):
        media_evidence.demo_data(path)


@pytest.mark.parametrize('fault', ['quick', 'error', 'source', 'incomplete_steps', 'duplicate_steps',
                                  'reordered_steps', 'missing_stream', 'top_level_list'])
def test_only_a_completed_full_rover_packet_is_accepted(tmp_path, fault):
    path, document = packet(tmp_path)
    if fault == 'quick': document['mode'] = 'quick'
    if fault == 'error': document['error'] = 'command timed out'
    if fault == 'source': document['source_project'] = 'examples/other'
    if fault == 'incomplete_steps': document['steps'].pop()
    if fault == 'duplicate_steps': document['steps'][3] = copy.deepcopy(document['steps'][0])
    if fault == 'reordered_steps': document['steps'].reverse()
    if fault == 'missing_stream': del document['steps'][0]['stdout']
    if fault == 'top_level_list': document = []
    save(path, document)
    with pytest.raises(ValueError):
        media_evidence.demo_data(path)


@pytest.mark.parametrize('flag', ['source_inputs_unchanged', 'source_cad_unchanged', 'snapshot_inputs_unchanged'])
@pytest.mark.parametrize('value', [False, None, 'true'])
def test_preservation_flags_must_be_actual_true(tmp_path, flag, value):
    path, document = packet(tmp_path)
    document[flag] = value
    save(path, document)
    with pytest.raises(ValueError, match='unchanged'):
        media_evidence.demo_data(path)


@pytest.mark.parametrize('fault', ['input_after', 'bad_digest', 'missing_hashes', 'cad_before', 'cad_after'])
def test_input_and_cad_hash_maps_must_agree(tmp_path, fault):
    path, document = packet(tmp_path)
    if fault == 'input_after': document['source_inputs_after']['evidence/index.yaml'] = 'd' * 64
    if fault == 'bad_digest': document['source_inputs_before']['evidence/index.yaml'] = document['source_inputs_after']['evidence/index.yaml'] = 'bad'
    if fault == 'missing_hashes': document['source_inputs_before'] = document['source_inputs_after'] = {}
    if fault == 'cad_before': document['source_cad_before']['rover-pdb.kicad_pcb'] = 'd' * 64
    if fault == 'cad_after': document['source_cad_after'].pop('rover-pdb.kicad_sch')
    save(path, document)
    with pytest.raises(ValueError, match='hash maps'):
        media_evidence.demo_data(path)


@pytest.mark.parametrize('fault', ['command', 'execution_error', 'evidence_exit', 'status_exit', 'missing_guard',
                                  'guard_exit', 'demo_exit', 'bool_exit', 'missing_header', 'bad_headline',
                                  'nonempty_failures', 'hidden_failure_body', 'conflicts', 'duplicate_header'])
def test_commands_and_log_diagnostics_cannot_hide_failed_checks(tmp_path, fault):
    path, document = packet(tmp_path)
    evidence_path = path.parent / document['steps'][1]['stdout']
    evidence = evidence_path.read_text(encoding='utf-8')
    if fault == 'command': document['steps'][1]['command'][-1] = '--verify-schematic-parts'
    if fault == 'execution_error': document['steps'][1]['error'] = 'subprocess failed'
    if fault == 'evidence_exit': document['steps'][1]['exit_code'] = 1
    if fault == 'status_exit': document['steps'][0]['exit_code'] = 1
    if fault == 'missing_guard': (path.parent / document['steps'][2]['stderr']).write_text('unrelated argparse error', encoding='utf-8')
    if fault == 'guard_exit': document['steps'][2]['exit_code'] = 1
    if fault == 'demo_exit': document['exit_code'] = 0
    if fault == 'bool_exit': document['steps'][0]['exit_code'] = False
    if fault == 'missing_header': evidence = evidence.replace('MACHINE FAILURES: none', '')
    if fault == 'bad_headline': evidence = evidence.replace('1 evidence record(s) verified', 'verification aborted')
    if fault == 'nonempty_failures': evidence = evidence.replace('MACHINE FAILURES: none', 'MACHINE FAILURES:\n- archive.hash_mismatch')
    if fault == 'hidden_failure_body': evidence = evidence.replace('MACHINE FAILURES: none', 'MACHINE FAILURES: none\n- archive.hash_mismatch')
    if fault == 'conflicts': evidence = evidence.replace('CONFLICTS: none', 'CONFLICTS:\n- inconsistent source')
    if fault == 'duplicate_header': evidence += '\nMACHINE FAILURES: none\n'
    evidence_path.write_text(evidence, encoding='utf-8')
    save(path, document)
    with pytest.raises(ValueError):
        media_evidence.demo_data(path)


def repository_packet(tmp_path, monkeypatch, *, blob=b'line\n'):
    repository = tmp_path / 'repository'
    source = repository / 'projects/rover-pdb'
    source.mkdir(parents=True)
    path = source / 'rover-pdb.kicad_sch'
    path.write_bytes(b'line\r\n')
    expected = {path.name: sha(path.read_bytes()), 'absent.kicad_dru': None}
    monkeypatch.setattr(media_evidence.subprocess, 'check_output', lambda *args, **kwargs: b'a' * 40 + b'\n')

    def git_show(command, **kwargs):
        return SimpleNamespace(returncode=1 if command[-1].endswith('absent.kicad_dru') else 0, stdout=blob)

    monkeypatch.setattr(media_evidence.subprocess, 'run', git_show)
    return repository, source, path, expected


def test_optional_repository_binding_preserves_capture_hashes_and_records_exact_head_blobs(tmp_path, monkeypatch):
    repository, source, path, expected = repository_packet(tmp_path, monkeypatch)
    captured = dict(expected)
    result = media_evidence.repository_binding(repository, source, expected)
    assert result == {'source_repository_revision': 'a' * 40,
                      'source_repository_inputs': {path.name: sha(b'line\n'), 'absent.kicad_dru': None}}
    assert expected == captured and path.read_bytes() == b'line\r\n'


@pytest.mark.parametrize('fault', ['different_content', 'unavailable_git', 'timeout', 'unexpected_blob'])
def test_optional_repository_binding_is_omitted_without_exact_head_equivalence(tmp_path, monkeypatch, fault):
    repository, source, _, expected = repository_packet(tmp_path, monkeypatch,
                                                       blob=b'different\n' if fault == 'different_content' else b'line\n')
    if fault in {'unavailable_git', 'timeout'}:
        def failed_probe(*args, **kwargs):
            if fault == 'timeout':
                raise subprocess.TimeoutExpired('git', 15)
            raise FileNotFoundError('git unavailable')
        monkeypatch.setattr(media_evidence.subprocess, 'check_output', failed_probe)
    if fault == 'unexpected_blob':
        monkeypatch.setattr(media_evidence.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b'line\n'))
    assert media_evidence.repository_binding(repository, source, expected) == {}


def test_repository_binding_rejects_source_changed_after_capture(tmp_path, monkeypatch):
    repository, source, path, expected = repository_packet(tmp_path, monkeypatch)
    path.write_bytes(b'new owner save\n')
    with pytest.raises(ValueError, match='source changed'):
        media_evidence.repository_binding(repository, source, expected)
