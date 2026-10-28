"""Published evidence checks use synthetic files and a mocked hash boundary."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools import check_readme as checker


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def landing(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    monkeypatch.setattr(checker, 'ROOT', root)
    for name in checker.DOCUMENTS:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Start\n', encoding='utf-8')
    source = root / 'examples/board'
    source.mkdir(parents=True)
    (source / 'project.yaml').write_text(
        'schema_version: 1\nname: board\nlifecycle: DRAFT\n'
        'design:\n  schematic: board.kicad_sch\n  pcb: board.kicad_pcb\n  netmap: netmap.json\n'
        'evidence:\n  index: evidence/index.yaml\nmanufacturing:\n  profile: test\n', encoding='utf-8')
    current = {'board.kicad_sch': sha(b'current CAD\r\n'), 'review-signoff.yaml': None}
    monkeypatch.setattr(checker, 'input_hashes', lambda _project: current.copy())
    media = root / 'docs/media'
    manifests = {}
    for index, name in enumerate(checker.MEDIA_MANIFESTS):
        output_name = f'capture-{index}.bin'
        payload = f'published bytes {index}'.encode()
        (media / output_name).write_bytes(payload)
        manifest = {'schema_version': 1,
                    'outputs': {output_name: {'sha256': sha(payload), 'bytes': len(payload)}}}
        if name in checker.CAD_MANIFESTS:
            manifest.update(source_project='examples/board', source_cad_unchanged=True,
                            source_inputs=current.copy())
        manifests[name] = manifest
        (media / name).write_text(json.dumps(manifest), encoding='utf-8')
    evaluation = root / Path(checker.EVALUATION_MANIFESTS[0]).parent
    (evaluation / 'logs').mkdir()
    (evaluation / 'logs/run.stdout.txt').write_bytes(b'retained raw log')
    (evaluation / 'evaluation.png').write_bytes(b'retained chart image')
    evaluation_outputs = {path.relative_to(evaluation).as_posix():
                          {'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}
                          for path in evaluation.rglob('*') if path.is_file()}
    (evaluation / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'outputs': evaluation_outputs}))
    return root, media, manifests, current


def save(media: Path, name: str, manifest: dict) -> None:
    (media / name).write_text(json.dumps(manifest), encoding='utf-8')


def test_exact_inputs_and_all_three_named_manifests_pass_without_git_or_native_tools(landing, capsys):
    assert checker.main() == 0
    assert '4 required evidence manifests' in capsys.readouterr().out


@pytest.mark.parametrize('name', checker.MEDIA_MANIFESTS)
def test_each_named_manifest_is_required(landing, capsys, name):
    _root, media, _manifests, _current = landing
    (media / name).unlink()
    assert checker.main() == 1
    assert name in capsys.readouterr().out


def test_no_manifests_cannot_silently_pass(landing, capsys):
    _root, media, _manifests, _current = landing
    for name in checker.MEDIA_MANIFESTS:
        (media / name).unlink()
    assert checker.main() == 1
    output = capsys.readouterr().out
    assert all(name in output for name in checker.MEDIA_MANIFESTS)


@pytest.mark.parametrize('value', [False, 1, 'true', None])
def test_capture_requires_literal_preservation_true(landing, value):
    _root, media, manifests, _current = landing
    manifest = manifests['manifest.json']
    manifest['source_cad_unchanged'] = value
    save(media, 'manifest.json', manifest)
    assert checker.main() == 1


def test_proof_manifest_has_no_capture_only_requirements(landing):
    _root, _media, manifests, _current = landing
    assert set(manifests['proof-manifest.json']) == {'schema_version', 'outputs'}
    assert checker.main() == 0


@pytest.mark.parametrize('value', [{}, [], None, {'board.kicad_sch': 'not-a-sha'}])
def test_capture_requires_a_valid_nonempty_input_map(landing, value):
    _root, media, manifests, _current = landing
    manifests['manifest.json']['source_inputs'] = value
    save(media, 'manifest.json', manifests['manifest.json'])
    assert checker.main() == 1


def test_changed_current_hash_cannot_be_hidden_by_intact_output_media(landing, capsys):
    _root, _media, _manifests, current = landing
    current['board.kicad_sch'] = sha(b'new circuit')
    assert checker.main() == 1
    assert 'current project input hashes differ' in capsys.readouterr().out


@pytest.mark.parametrize('change', ['added', 'removed'])
def test_current_keyset_detects_added_or_removed_declared_inputs(landing, change, capsys):
    _root, _media, _manifests, current = landing
    if change == 'added':
        current['libs/new-symbol.kicad_sym'] = sha(b'new library')
    else:
        del current['review-signoff.yaml']
    assert checker.main() == 1
    assert 'current project input keys differ' in capsys.readouterr().out


def test_explicit_canonical_blob_hashes_allow_a_fresh_lf_checkout(landing):
    _root, media, manifests, current = landing
    for name in checker.CAD_MANIFESTS:
        canonical = manifests[name]['source_inputs'].copy()
        canonical['board.kicad_sch'] = sha(b'current CAD\n')
        manifests[name]['source_repository_inputs'] = canonical
        save(media, name, manifests[name])
    current['board.kicad_sch'] = sha(b'current CAD\n')
    assert checker.main() == 0


def test_no_implicit_newline_normalization_or_fallback_to_unrecorded_bytes(landing):
    _root, media, manifests, current = landing
    for name in checker.CAD_MANIFESTS:
        manifests[name]['source_repository_inputs'] = manifests[name]['source_inputs'].copy()
        manifests[name]['source_repository_inputs']['board.kicad_sch'] = sha(b'current CAD\n')
        save(media, name, manifests[name])
    current['board.kicad_sch'] = sha(b'current CAD\n\n')
    assert checker.main() == 1


@pytest.mark.parametrize('fault', ['extra_key', 'missing_key', 'bad_hash', 'changed_null', 'empty'])
def test_optional_repository_map_must_match_schema_keys_and_nulls(landing, fault):
    _root, media, manifests, _current = landing
    manifest = manifests['manifest.json']
    canonical = manifest['source_inputs'].copy()
    if fault == 'extra_key': canonical['extra'] = sha(b'extra')
    if fault == 'missing_key': del canonical['review-signoff.yaml']
    if fault == 'bad_hash': canonical['board.kicad_sch'] = 'bad'
    if fault == 'changed_null': canonical['review-signoff.yaml'] = sha(b'unsigned')
    if fault == 'empty': canonical = {}
    manifest['source_repository_inputs'] = canonical
    save(media, 'manifest.json', manifest)
    assert checker.main() == 1


@pytest.mark.parametrize('name', ['../outside.bin', '/absolute.bin', 'C:/outside.bin',
                                  'C:outside.bin', '..\\outside.bin', './capture-0.bin',
                                  'nested//capture.bin', '.', ''])
def test_manifest_output_names_are_canonical_and_contained_on_all_hosts(landing, name):
    _root, media, manifests, _current = landing
    manifest = manifests['manifest.json']
    record = next(iter(manifest['outputs'].values()))
    manifest['outputs'] = {name: record}
    save(media, 'manifest.json', manifest)
    assert checker.main() == 1


@pytest.mark.parametrize('field,value', [('sha256', 'bad'), ('sha256', 'F' * 64),
                                        ('bytes', True), ('bytes', -1), ('bytes', 0),
                                        ('bytes', 1.5), ('bytes', '17')])
def test_media_records_need_sha256_and_a_positive_integer_byte_count(landing, field, value):
    _root, media, manifests, _current = landing
    manifest = manifests['proof-manifest.json']
    next(iter(manifest['outputs'].values()))[field] = value
    save(media, 'proof-manifest.json', manifest)
    assert checker.main() == 1


@pytest.mark.parametrize('fault', ['missing_file', 'wrong_hash', 'wrong_byte_count', 'empty_outputs'])
def test_media_byte_and_hash_claims_are_both_enforced(landing, fault):
    _root, media, manifests, _current = landing
    manifest = manifests['proof-manifest.json']
    name, record = next(iter(manifest['outputs'].items()))
    if fault == 'missing_file': (media / name).unlink()
    if fault == 'wrong_hash': record['sha256'] = sha(b'other content')
    if fault == 'wrong_byte_count': record['bytes'] += 1
    if fault == 'empty_outputs': manifest['outputs'] = {}
    save(media, 'proof-manifest.json', manifest)
    assert checker.main() == 1


def test_duplicate_json_keys_are_rejected(landing, capsys):
    _root, media, manifests, _current = landing
    text = json.dumps(manifests['manifest.json'])
    text = text.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
    (media / 'manifest.json').write_text(text)
    assert checker.main() == 1
    assert 'duplicate manifest key' in capsys.readouterr().out


def test_evaluation_links_are_checked(landing, capsys):
    root, _media, _manifests, _current = landing
    (root / 'docs/EVALUATION.md').write_text('# Evaluation\n\n[missing](does-not-exist.md)\n')
    assert checker.main() == 1
    assert 'docs/EVALUATION.md: missing local target' in capsys.readouterr().out


def test_a_missing_required_document_is_an_actionable_failure(landing, capsys):
    root, _media, _manifests, _current = landing
    (root / 'docs/EVALUATION.md').unlink()
    assert checker.main() == 1
    assert 'docs/EVALUATION.md: cannot read required document' in capsys.readouterr().out


def test_media_symlink_cannot_escape_the_media_directory(landing, tmp_path):
    _root, media, manifests, _current = landing
    outside = tmp_path / 'outside.bin'
    outside.write_bytes(b'outside media')
    alias = media / 'alias.bin'
    try:
        alias.symlink_to(outside)
    except OSError:
        pytest.skip('symlinks unavailable on this host')
    manifests['proof-manifest.json']['outputs'] = {'alias.bin': {'sha256': sha(outside.read_bytes()), 'bytes': outside.stat().st_size}}
    save(media, 'proof-manifest.json', manifests['proof-manifest.json'])
    assert checker.main() == 1


def test_manifest_alias_cannot_bypass_named_capture_requirements(landing):
    _root, media, manifests, _current = landing
    alternate = media / 'noncapture.json'
    alternate.write_text(json.dumps(manifests['proof-manifest.json']))
    manifest = media / 'manifest.json'
    manifest.unlink()
    try:
        manifest.symlink_to(alternate)
    except OSError:
        pytest.skip('symlinks unavailable on this host')
    assert checker.main() == 1


@pytest.mark.parametrize('source', ['tests/fixtures/boards/frozen', '../outside', '/outside'])
def test_capture_sources_cannot_be_fixtures_or_outside_the_checkout(landing, source):
    _root, media, manifests, _current = landing
    manifest = copy.deepcopy(manifests['manifest.json'])
    manifest['source_project'] = source
    save(media, 'manifest.json', manifest)
    assert checker.main() == 1


def test_evaluation_manifest_is_required_independently_of_all_three_media_bundles(landing, capsys):
    root, _media, _manifests, _current = landing
    (root / checker.EVALUATION_MANIFESTS[0]).unlink()
    assert checker.main() == 1
    assert checker.EVALUATION_MANIFESTS[0] in capsys.readouterr().out


@pytest.mark.parametrize('name', ['report.md', 'logs/run.stdout.txt', 'evaluation.png'])
def test_evaluation_artifact_bytes_are_checked_in_their_own_bundle_root(landing, name, capsys):
    root, _media, _manifests, _current = landing
    bundle = root / Path(checker.EVALUATION_MANIFESTS[0]).parent
    path = bundle / name
    path.write_bytes(path.read_bytes() + b'changed')
    assert checker.main() == 1
    assert name in capsys.readouterr().out


def test_evaluation_report_links_are_checked(landing, capsys):
    root, _media, _manifests, _current = landing
    bundle = root / Path(checker.EVALUATION_MANIFESTS[0]).parent
    (bundle / 'report.md').write_text('# Report\n\n[raw log](logs/missing.txt)\n')
    assert checker.main() == 1
    assert 'report.md: missing local target' in capsys.readouterr().out


def test_unlisted_evaluation_image_or_log_cannot_bypass_integrity_checking(landing, capsys):
    root, _media, _manifests, _current = landing
    bundle = root / Path(checker.EVALUATION_MANIFESTS[0]).parent
    (bundle / 'unlisted-image.png').write_bytes(b'not hash bound')
    assert checker.main() == 1
    assert 'complete manifest output list' in capsys.readouterr().out


def test_empty_raw_evaluation_stream_is_valid_when_exact_empty_bytes_are_recorded(landing):
    root, _media, _manifests, _current = landing
    path = root / checker.EVALUATION_MANIFESTS[0]
    manifest = json.loads(path.read_text())
    log = path.parent / 'logs/run.stdout.txt'
    log.write_bytes(b'')
    manifest['outputs']['logs/run.stdout.txt'] = {'sha256': sha(b''), 'bytes': 0}
    path.write_text(json.dumps(manifest))
    assert checker.main() == 0
