"""Transactional media publication without importing any rendering libraries."""

import hashlib
import json
import os

import pytest

from tools import media_publication as media


def bundle(directory, payloads, manifest_name='manifest.json'):
    directory.mkdir(exist_ok=True)
    manifest = {'outputs': {name: {'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
                            for name, payload in payloads.items()}}
    for name, payload in payloads.items():
        (directory / name).write_bytes(payload)
    (directory / manifest_name).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def files(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob('*') if path.is_file()}


@pytest.fixture
def prepared(tmp_path):
    destination, staged = tmp_path / 'media', tmp_path / 'staged'
    bundle(destination, {'a.png': b'old a', 'b.mp4': b'old b'})
    bundle(staged, {'a.png': b'new a', 'b.mp4': b'new b'})
    (destination / 'other-manifest.json').write_bytes(b'unrelated bundle')
    (destination / 'fonts').mkdir()
    (destination / 'fonts/font.ttf').write_bytes(b'unchanged font')
    return staged, destination


def test_success_publishes_manifest_last_and_preserves_unrelated_files(prepared, monkeypatch):
    staged, destination = prepared
    order = []
    replace = media._atomic_replace

    def record(path, payload):
        assert path.parent == destination
        order.append(path.name)
        replace(path, payload)

    monkeypatch.setattr(media, '_atomic_replace', record)
    sources = []
    result = media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: sources.append(True))
    assert order == ['a.png', 'b.mp4', 'manifest.json']
    assert len(sources) == 2
    assert (destination / 'manifest.json').read_bytes() == (staged / 'manifest.json').read_bytes()
    assert result == json.loads((destination / 'manifest.json').read_text())
    assert (destination / 'other-manifest.json').read_bytes() == b'unrelated bundle'
    assert (destination / 'fonts/font.ttf').read_bytes() == b'unchanged font'
    assert not list(destination.glob('.media-*'))


@pytest.mark.parametrize('failure', [OSError('encoder/publish failure'), KeyboardInterrupt()])
def test_failure_after_first_publish_restores_exact_previous_bundle(prepared, monkeypatch, failure):
    staged, destination = prepared
    before = files(destination)
    replace = media._atomic_replace
    calls = 0

    def interrupt(path, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise failure
        replace(path, payload)

    monkeypatch.setattr(media, '_atomic_replace', interrupt)
    with pytest.raises(type(failure)):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert files(destination) == before
    assert not list(destination.glob('.media-*'))


def test_post_publication_source_failure_rolls_back_new_files_and_old_manifest(tmp_path):
    destination, staged = tmp_path / 'media', tmp_path / 'staged'
    bundle(destination, {'b.mp4': b'old b'})
    bundle(staged, {'a.png': b'new file', 'b.mp4': b'new b'})
    before = files(destination)
    calls = 0

    def source_check():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('CAD changed concurrently')

    with pytest.raises(RuntimeError, match='CAD changed'):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=source_check)
    assert files(destination) == before
    assert not (destination / 'a.png').exists()


@pytest.mark.parametrize('tamper', ['hash', 'bytes', 'missing', 'extra', 'escape', 'alias', 'self', 'boolean-bytes'])
def test_invalid_staging_does_not_touch_destination(prepared, tamper):
    staged, destination = prepared
    before = files(destination)
    manifest = json.loads((staged / 'manifest.json').read_text())
    if tamper == 'hash':
        (staged / 'a.png').write_bytes(b'tampered')
    elif tamper == 'bytes':
        manifest['outputs']['a.png']['bytes'] += 1
    elif tamper == 'missing':
        (staged / 'a.png').unlink()
    elif tamper == 'extra':
        (staged / 'unlisted.txt').write_bytes(b'no silent publication')
    elif tamper == 'escape':
        manifest['outputs']['../outside.png'] = manifest['outputs'].pop('a.png')
    elif tamper == 'alias':
        manifest['outputs']['A.PNG'] = manifest['outputs']['a.png']
    elif tamper == 'self':
        manifest['outputs']['manifest.json'] = manifest['outputs']['a.png']
    else:
        manifest['outputs']['a.png']['bytes'] = True
    (staged / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert files(destination) == before


def test_existing_target_case_alias_is_rejected(prepared):
    staged, destination = prepared
    (destination / 'a.png').rename(destination / 'A.PNG')
    before = files(destination)
    with pytest.raises(ValueError, match='aliases'):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert files(destination) == before


@pytest.mark.parametrize('place', ['stage', 'target'])
def test_hardlinked_output_alias_is_rejected(prepared, tmp_path, place):
    staged, destination = prepared
    path = (staged if place == 'stage' else destination) / 'a.png'
    alias = tmp_path / 'owner-file.bin'
    try:
        os.link(path, alias)
    except OSError:
        pytest.skip('hard links unavailable on this filesystem')
    before = files(destination)
    with pytest.raises(ValueError, match='unaliased'):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert files(destination) == before
    assert alias.read_bytes() == (b'new a' if place == 'stage' else b'old a')


def test_target_symlink_is_not_replaced_or_followed(prepared, tmp_path):
    staged, destination = prepared
    owner = tmp_path / 'owner-file.bin'
    owner.write_bytes(b'owner bytes')
    (destination / 'a.png').unlink()
    try:
        (destination / 'a.png').symlink_to(owner)
    except OSError:
        pytest.skip('symlinks unavailable on this platform')
    with pytest.raises(ValueError, match='symlinks'):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert (destination / 'a.png').is_symlink()
    assert owner.read_bytes() == b'owner bytes'


def test_exclusive_lock_rejects_a_second_publisher(prepared, monkeypatch):
    staged, destination = prepared
    replace = media._atomic_replace
    attempted = False

    def concurrent(path, payload):
        nonlocal attempted
        if not attempted:
            attempted = True
            with pytest.raises(RuntimeError, match='lock already exists'):
                media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
        replace(path, payload)

    monkeypatch.setattr(media, '_atomic_replace', concurrent)
    media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert attempted and not (destination / '.media-publication.lock').exists()


@pytest.mark.parametrize('rollback_error', [OSError('rollback failed'), KeyboardInterrupt()])
def test_rollback_failure_retains_every_original_and_explicit_recovery_path(prepared, monkeypatch, rollback_error):
    staged, destination = prepared
    before = files(destination)
    replace = media._atomic_replace
    calls = 0

    def broken_disk(path, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('injected publication failure')
        if calls == 3:
            raise rollback_error
        replace(path, payload)

    monkeypatch.setattr(media, '_atomic_replace', broken_disk)
    with pytest.raises(media.MediaRecoveryRequired) as raised:
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    recovery = raised.value.recovery_path
    assert str(recovery) in str(raised.value)
    journal = json.loads((recovery / 'journal.json').read_text())
    for item in journal:
        assert (recovery / item['backup']).read_bytes() == before[item['name']]
    assert (destination / '.media-publication.lock').exists()
    assert (destination / 'other-manifest.json').read_bytes() == before['other-manifest.json']
    with pytest.raises(RuntimeError, match='retained recovery'):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)


@pytest.mark.parametrize('failure_name', ['original-0.bin', 'journal.json'])
def test_backup_or_journal_write_failure_cleans_only_owned_partial_files(prepared, monkeypatch, failure_name):
    staged, destination = prepared
    before = files(destination)
    write = media._write_recovery

    def disk_full(path, payload, owned):
        if path.name == failure_name:
            with path.open('xb') as stream:
                owned.append(path)
                stream.write(payload[:2])
            raise OSError('injected partial recovery write')
        write(path, payload, owned)

    monkeypatch.setattr(media, '_write_recovery', disk_full)
    with pytest.raises(OSError, match='partial recovery write'):
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert files(destination) == before
    assert not list(destination.glob('.media-*'))


def test_failed_cleanup_after_publication_retains_lock_and_reports_complete_bundle(prepared, monkeypatch):
    staged, destination = prepared

    def cannot_clean(_directory, _owned):
        raise OSError('backup cleanup blocked')

    monkeypatch.setattr(media, '_discard_recovery', cannot_clean)
    with pytest.raises(media.MediaRecoveryRequired, match='published and verified') as raised:
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert raised.value.published
    recovery = raised.value.recovery_path
    assert recovery.is_dir() and (recovery / 'journal.json').is_file()
    assert (destination / '.media-publication.lock').exists()
    for name in ('a.png', 'b.mp4', 'manifest.json'):
        assert (destination / name).read_bytes() == (staged / name).read_bytes()


def test_setup_cleanup_failure_is_explicit_and_assets_remain_untouched(prepared, monkeypatch):
    staged, destination = prepared
    before = files(destination)

    def cannot_write(_path, _payload, _owned):
        raise OSError('backup write failed')

    def cannot_clean(_directory, _owned):
        raise OSError('working-file cleanup failed')

    monkeypatch.setattr(media, '_write_recovery', cannot_write)
    monkeypatch.setattr(media, '_discard_recovery', cannot_clean)
    with pytest.raises(media.MediaRecoveryRequired, match='before any asset publication') as raised:
        media.publish_bundle(staged, destination, 'manifest.json', source_check=lambda: None)
    assert not raised.value.published
    assert raised.value.recovery_path.is_dir()
    assert (destination / '.media-publication.lock').exists()
    assert all((destination / name).read_bytes() == payload for name, payload in before.items())


def test_recovery_cleanup_never_deletes_an_unlisted_matching_filename(tmp_path):
    recovery = tmp_path / 'recovery'
    recovery.mkdir()
    owned = recovery / 'original-0.bin'
    owned.write_bytes(b'owned backup')
    unknown = recovery / 'original-owner.bin'
    unknown.write_bytes(b'not owned by this operation')
    with pytest.raises(RuntimeError, match='unexpected file'):
        media._discard_recovery(recovery, [owned])
    assert owned.read_bytes() == b'owned backup'
    assert unknown.read_bytes() == b'not owned by this operation'
