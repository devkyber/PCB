"""Publish one validated media bundle with rollback and manifest-last ordering.

Individual replacements are atomic and use temporary files in the destination
folder. The bundle has a transactional final outcome, not a simultaneously
atomic view for readers opening multiple files during publication.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path


class MediaRecoveryRequired(RuntimeError):
    """Publication could not restore all originals; retain the named backups."""

    def __init__(self, recovery_path: Path, detail: str, *, published: bool = False):
        self.recovery_path = recovery_path
        self.published = published
        super().__init__(f'{detail}; retained media recovery directory: {recovery_path}')


def _name(value: str) -> str:
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', value)
            or value.endswith('.') or value.split('.')[0].upper() in
            {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{n}' for n in range(1, 10)],
             *[f'LPT{n}' for n in range(1, 10)]}):
        raise ValueError(f'media bundle requires unaliased flat filenames: {value!r}')
    return value


def _reject_link(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError(f'media paths must not be symlinks or reparse points: {path}')


def _directory(path: Path) -> Path:
    absolute = path.expanduser().absolute()
    for component in (*reversed(absolute.parents), absolute):
        _reject_link(component)
    return absolute.resolve()


def _read(path: Path) -> bytes | None:
    _reject_link(path)
    if not path.exists():
        return None
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f'media target must be an ordinary unaliased file: {path}')
    return path.read_bytes()


def _unique_pairs(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f'duplicate media manifest key: {key}')
        document[key] = value
    return document


def _capture(staged: Path, manifest_name: str) -> tuple[dict, dict[str, bytes]]:
    raw = _read(staged / manifest_name)
    if raw is None:
        raise ValueError('staged media manifest is missing')
    manifest = json.loads(raw, object_pairs_hook=_unique_pairs)
    outputs = manifest.get('outputs') if isinstance(manifest, dict) else None
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError('media manifest must list its expected outputs')
    names = [_name(name) for name in outputs]
    if len({name.casefold() for name in [*names, manifest_name]}) != len(names) + 1:
        raise ValueError('media output names alias each other or the manifest')
    if {path.name for path in staged.iterdir()} != {*names, manifest_name}:
        raise ValueError('staged directory has missing or unlisted media outputs')
    payloads = {}
    for name, record in outputs.items():
        if (not isinstance(record, dict) or not isinstance(record.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', record['sha256'])
                or type(record.get('bytes')) is not int or record['bytes'] < 0):
            raise ValueError(f'invalid media output hash/byte count: {name}')
        payload = _read(staged / name)
        if (payload is None or len(payload) != record['bytes']
                or hashlib.sha256(payload).hexdigest() != record['sha256']):
            raise ValueError(f'staged media does not match its manifest: {name}')
        payloads[name] = payload
    payloads[manifest_name] = raw  # Commit marker is always published last.
    return manifest, payloads


def _atomic_replace(target: Path, payload: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{target.name}.publish-', dir=target.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_recovery(path: Path, payload: bytes, owned: list[Path]) -> None:
    with path.open('xb') as stream:
        owned.append(path)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _discard_recovery(directory: Path, owned: list[Path]) -> None:
    # Only this operation's explicitly named files are removed; never recurse
    # through a computed destination or remove unrelated media/fonts/bundles.
    if set(directory.iterdir()) != set(owned):
        raise RuntimeError(f'unexpected file in media recovery directory: {directory}')
    for path in owned:
        _reject_link(path)
    # The journal is created last and remains available if an earlier backup
    # cannot be removed. No wildcard grants ownership of extra files.
    for path in owned:
        path.unlink()
    directory.rmdir()


def _check_source(source_check: Callable[[], None]) -> None:
    if source_check() is False:
        raise RuntimeError('media source check failed')


def publish_bundle(staged_dir: Path, destination: Path, manifest_name: str,
                   *, source_check: Callable[[], None]) -> dict:
    """Validate, publish, or restore exact bytes for one flat-file media bundle.

    ``staged_dir`` must contain exactly the manifest and its listed outputs.
    Output records require ``sha256`` and integer ``bytes``. ``source_check``
    must raise (or return False) on stale inputs; it runs before destination
    writes and after publication. Other destination files are untouched.

    A destination-wide exclusive lock serializes cooperating publishers. Any
    incomplete rollback retains that lock, original-byte backups and a journal
    at ``MediaRecoveryRequired.recovery_path`` for explicit recovery.
    If publication verified successfully but housekeeping cannot finish,
    ``MediaRecoveryRequired.published`` is True and the lock/path are retained.
    """
    manifest_name = _name(manifest_name)
    if not manifest_name.endswith('.json'):
        raise ValueError('media manifest filename must end with .json')
    staged, destination = _directory(Path(staged_dir)), _directory(Path(destination))
    if (staged == destination or staged.is_relative_to(destination)
            or destination.is_relative_to(staged)):
        raise ValueError('media staging and destination directories must be separate')
    manifest, payloads = _capture(staged, manifest_name)
    _check_source(source_check)
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / '.media-publication.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        recovery = ', '.join(str(path) for path in destination.glob('.media-recovery-*'))
        raise RuntimeError(f'media publication lock already exists: {lock}'
                           + (f'; inspect retained recovery: {recovery}' if recovery else '')) from exc
    keep_lock = False
    recovery = None
    owned_recovery = []
    before = {}
    attempted = []
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'pid': os.getpid(), 'manifest': manifest_name}, stream)
        retained = list(destination.glob('.media-recovery-*'))
        if retained:
            raise MediaRecoveryRequired(retained[0], 'an earlier media operation needs explicit inspection')
        # Reject Windows case aliases on every platform, including existing
        # differently cased target entries in a case-sensitive checkout.
        for path in destination.iterdir():
            if any(path.name.casefold() == name.casefold() and path.name != name for name in payloads):
                raise ValueError(f'existing destination filename aliases a bundle target: {path.name}')
        before = {name: _read(destination / name) for name in payloads}
        recovery = Path(tempfile.mkdtemp(prefix='.media-recovery-', dir=destination))
        journal = []
        for index, (name, original) in enumerate(before.items()):
            backup = f'original-{index}.bin' if original is not None else None
            if backup is not None:
                _write_recovery(recovery / backup, original, owned_recovery)
            journal.append({'name': name, 'backup': backup,
                            'original_sha256': hashlib.sha256(original).hexdigest() if original is not None else None,
                            'published_sha256': hashlib.sha256(payloads[name]).hexdigest()})
        _write_recovery(recovery / 'journal.json', (json.dumps(journal, indent=2) + '\n').encode(), owned_recovery)
        expected = dict(before)
        try:
            for name, payload in payloads.items():
                for current, wanted in expected.items():
                    if _read(destination / current) != wanted:
                        raise RuntimeError(f'concurrent media edit preserved: {current}')
                attempted.append(name)
                _atomic_replace(destination / name, payload)
                expected[name] = payload
            _check_source(source_check)
            for name, payload in payloads.items():
                if _read(destination / name) != payload:
                    raise RuntimeError(f'published media changed concurrently: {name}')
        except BaseException as original_error:
            failures = []
            for name in reversed(attempted):
                try:
                    current = _read(destination / name)
                    if current == before[name]:
                        continue
                    if current != payloads[name]:
                        raise RuntimeError(f'concurrent media edit preserved: {name}')
                    if before[name] is None:
                        (destination / name).unlink()
                    else:
                        _atomic_replace(destination / name, before[name])
                    if _read(destination / name) != before[name]:
                        raise RuntimeError(f'original media was not restored: {name}')
                except BaseException as rollback_error:  # noqa: BLE001 -- Finish restoring other files after failure or interruption.
                    failures.append(f'{name}: {rollback_error or type(rollback_error).__name__}')
            if failures:
                raise MediaRecoveryRequired(recovery, 'media rollback incomplete; all original-byte backups and journal retained: '
                                            + '; '.join(failures)) from original_error
            try:
                _discard_recovery(recovery, owned_recovery)
            except BaseException as cleanup_error:  # noqa: BLE001 -- Retain recovery and its lock on cleanup errors or interruption.
                raise MediaRecoveryRequired(recovery, 'Original bundle restored, but recovery cleanup failed: '
                                            + str(cleanup_error)) from original_error
            recovery = None
            raise
        try:
            _discard_recovery(recovery, owned_recovery)
        except BaseException as cleanup_error:
            raise MediaRecoveryRequired(recovery, 'Bundle published and verified, but recovery cleanup failed: '
                                        + str(cleanup_error), published=True) from cleanup_error
        recovery = None
    except MediaRecoveryRequired:
        keep_lock = True
        raise
    except BaseException as setup_error:
        if recovery is not None and not attempted:
            try:
                _discard_recovery(recovery, owned_recovery)
            except BaseException as cleanup_error:  # noqa: BLE001 -- Retain partial setup and its lock on cleanup errors or interruption.
                keep_lock = True
                raise MediaRecoveryRequired(recovery, 'Media setup failed before any asset publication; '
                                            'original assets are untouched, but working-file cleanup failed: '
                                            + str(cleanup_error)) from setup_error
            recovery = None
        raise
    finally:
        if not keep_lock:
            lock.unlink()
    return manifest
