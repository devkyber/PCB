"""Lossless, source-bound storage for completed passive simulation cases."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

ARCHIVE = 'raw-cases.zip'
MANIFEST = '_manifest.json'
SUFFIXES = ('.cir', '.log', '.csv')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def case_names(report):
    names = [case['name'] for case in report['cases']]
    if len(names) != report['case_count'] or len(set(names)) != len(names):
        raise ValueError('Case names/count disagree')
    if any(not re.fullmatch(r'[A-Za-z0-9_+-][A-Za-z0-9_.+-]*', name) for name in names):
        raise ValueError('Unsafe case name')
    return {name + suffix for name in names for suffix in SUFFIXES}


def verify_archive(archive_path, report_bytes, loose_dir=None):
    """Read every member: check CRC, provenance, deck hashes and optional raw bytes."""
    report = json.loads(report_bytes)
    expected = case_names(report)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != expected | {MANIFEST}:
            raise ValueError('Raw archive members do not match the completed cases')
        manifest = json.loads(archive.read(MANIFEST))
        if manifest['results_sha256'] != sha(report_bytes) or set(manifest['files']) != expected:
            raise ValueError('Raw archive is bound to a different results report')
        for name in sorted(expected):
            data = archive.read(name)
            if sha(data) != manifest['files'][name]:
                raise ValueError(f'Raw member hash differs: {name}')
            if loose_dir is not None and data != (Path(loose_dir) / name).read_bytes():
                raise ValueError(f'Raw member differs from loose source: {name}')
        for case in report['cases']:
            if manifest['files'][case['name'] + '.cir'] != case['deck_sha256']:
                raise ValueError(f"Deck differs from verified simulation: {case['name']}")
    return manifest


def pack_raw_cases(raw_dir, report_path, destination):
    """Publish a complete verified archive; never delete the loose inputs."""
    raw_dir, report_path, destination = map(Path, (raw_dir, report_path, destination))
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    payloads = {name: (raw_dir / name).read_bytes() for name in sorted(case_names(report))}
    manifest = {'schema': 1, 'results_sha256': sha(report_bytes),
                'files': {name: sha(data) for name, data in payloads.items()}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.zip', delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in payloads.items():
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2) + '\n')
        verify_archive(temporary_path, report_bytes, raw_dir)
        if report_path.read_bytes() != report_bytes:
            raise RuntimeError('Results report changed while packing raw cases')
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return manifest


class RawCaseStore:
    """Read validated packed cases without creating an extraction directory."""
    def __init__(self, results_dir):
        self.directory = Path(results_dir)
        self.report_bytes = (self.directory / 'results.json').read_bytes()
        self.manifest = verify_archive(self.directory / ARCHIVE, self.report_bytes)

    def read(self, name, suffix='.csv'):
        member = name + suffix
        if suffix not in SUFFIXES or member not in self.manifest['files']:
            raise ValueError(f'Unknown raw case member: {member}')
        if (self.directory / member).exists():
            raise ValueError(f'Both packed and loose data exist for {member}; reconcile before plotting')
        if (self.directory / 'results.json').read_bytes() != self.report_bytes:
            raise RuntimeError('Results changed while reading cases')
        with zipfile.ZipFile(self.directory / ARCHIVE) as archive:
            data = archive.read(member)
        if sha(data) != self.manifest['files'][member]:
            raise RuntimeError(f'Packed case changed while reading: {member}')
        return data


def _replace(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        temp_path = Path(temporary.name)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def publish_results(staging, destination):
    """Only completed batches replace the previous archive/report pair."""
    staging, destination = Path(staging), Path(destination)
    report_bytes = (staging / 'results.json').read_bytes()
    verify_archive(staging / ARCHIVE, report_bytes)
    destination.mkdir(parents=True, exist_ok=True)
    outputs = {destination / ARCHIVE: (staging / ARCHIVE).read_bytes(),
               destination / 'results.json': report_bytes}
    previous = {path: path.read_bytes() if path.exists() else None for path in outputs}
    changed = []
    try:
        for path, data in outputs.items():
            _replace(path, data)
            changed.append(path)
        verify_archive(destination / ARCHIVE, (destination / 'results.json').read_bytes())
    except Exception:
        for path in reversed(changed):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                _replace(path, previous[path])
        raise
