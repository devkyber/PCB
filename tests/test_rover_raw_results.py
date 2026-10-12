"""Raw simulation evidence stays exact and failed packing keeps previous results."""
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'projects/rover-pdb/simulation/raw_results.py'
spec = importlib.util.spec_from_file_location('rover_raw_results', MODULE)
raw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw)


@pytest.fixture
def cases(tmp_path):
    staging = tmp_path / 'staging'
    staging.mkdir()
    payloads = {'case.cir': b'Title\r\n.end\r\n', 'case.csv': b'time,v\n0,1\n',
                'case.log': b'raw ngspice log\r\n'}
    for name, data in payloads.items():
        (staging / name).write_bytes(data)
    report = {'case_count': 1, 'cases': [{'name': 'case', 'deck_sha256': raw.sha(payloads['case.cir'])}]}
    (staging / 'results.json').write_text(json.dumps(report))
    return staging, payloads


def test_exact_round_trip_without_extraction(cases, tmp_path):
    staging, payloads = cases
    raw.pack_raw_cases(staging, staging / 'results.json', staging / raw.ARCHIVE)
    destination = tmp_path / 'results'
    raw.publish_results(staging, destination)
    store = raw.RawCaseStore(destination)
    for name, expected in payloads.items():
        stem, suffix = name.rsplit('.', 1)
        assert store.read(stem, '.' + suffix) == expected
    assert sorted(path.name for path in destination.iterdir()) == ['raw-cases.zip', 'results.json']


def test_failed_verification_preserves_raw_files_and_previous_archive(cases, monkeypatch):
    staging, payloads = cases
    destination = staging / raw.ARCHIVE
    destination.write_bytes(b'previous archive')

    def fail(*args, **kwargs):
        raise ValueError('verification failure')

    monkeypatch.setattr(raw, 'verify_archive', fail)
    with pytest.raises(ValueError, match='verification failure'):
        raw.pack_raw_cases(staging, staging / 'results.json', destination)
    assert destination.read_bytes() == b'previous archive'
    assert {name: (staging / name).read_bytes() for name in payloads} == payloads


def test_missing_case_file_never_replaces_previous_archive(cases):
    staging, _ = cases
    destination = staging / raw.ARCHIVE
    destination.write_bytes(b'previous archive')
    (staging / 'case.log').unlink()
    with pytest.raises(FileNotFoundError):
        raw.pack_raw_cases(staging, staging / 'results.json', destination)
    assert destination.read_bytes() == b'previous archive'


def test_modified_archive_member_is_rejected(cases):
    staging, _ = cases
    destination = staging / raw.ARCHIVE
    raw.pack_raw_cases(staging, staging / 'results.json', destination)
    with zipfile.ZipFile(destination) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members['case.csv'] = b'changed waveform'
    with zipfile.ZipFile(destination, 'w') as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    with pytest.raises(ValueError, match='Raw member hash differs'):
        raw.verify_archive(destination, (staging / 'results.json').read_bytes())


def test_failed_pair_publication_restores_previous_bytes(cases, tmp_path, monkeypatch):
    staging, _ = cases
    raw.pack_raw_cases(staging, staging / 'results.json', staging / raw.ARCHIVE)
    destination = tmp_path / 'results'
    destination.mkdir()
    (destination / raw.ARCHIVE).write_bytes(b'previous archive')
    (destination / 'results.json').write_bytes(b'previous report')
    original = raw._replace

    def fail_report(path, data):
        if path.name == 'results.json':
            raise OSError('publication failed')
        original(path, data)

    monkeypatch.setattr(raw, '_replace', fail_report)
    with pytest.raises(OSError, match='publication failed'):
        raw.publish_results(staging, destination)
    assert (destination / raw.ARCHIVE).read_bytes() == b'previous archive'
    assert (destination / 'results.json').read_bytes() == b'previous report'


def test_wrong_report_and_wrong_deck_fail(cases):
    staging, _ = cases
    report_path = staging / 'results.json'
    raw.pack_raw_cases(staging, report_path, staging / raw.ARCHIVE)
    with pytest.raises(ValueError, match='different results report'):
        raw.verify_archive(staging / raw.ARCHIVE, report_path.read_bytes() + b' ')
    (staging / 'case.cir').write_bytes(b'modified circuit')
    with pytest.raises(ValueError, match='Deck differs'):
        raw.pack_raw_cases(staging, report_path, staging / raw.ARCHIVE)
