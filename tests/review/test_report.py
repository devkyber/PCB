"""Portable report integrity and no-clobber publication, with native tools stubbed."""

import base64
import hashlib
import json
from pathlib import Path

import pymupdf
import pytest

from pcb_copilot.cli import main
from pcb_copilot.project import load_project
from pcb_copilot.review import report as handover
from pcb_copilot.review.fingerprint import pcb_digest, schematic_digest
from pcb_copilot.review.models import (
    CheckResult,
    CheckScope,
    Finding,
    FindingKind,
    ReviewReport,
)
from pcb_copilot.transaction import input_hashes


@pytest.fixture
def native_boundaries(monkeypatch):
    def review(project):
        scope = CheckScope('Synthetic check boundary', 'Actual engineering approval', True, False)
        return ReviewReport(project.manifest.name, schematic_digest(project.schematic_path),
                            pcb_digest(project.pcb_path),
                            (CheckResult('signoff', False, 'unsigned test fixture', scope, FindingKind.HUMAN_DECISION),),
                            (Finding('signoff', FindingKind.HUMAN_DECISION, 'unsigned test fixture', True),), True)

    def capture(project, work):
        with pymupdf.open() as pdf:
            page = pdf.new_page()
            page.insert_text((40, 40), 'Synthetic native export boundary')
            payload, png = pdf.tobytes(), page.get_pixmap().tobytes('png')
        files = {'schematic.pdf': payload}
        images = []
        for name, category in [('schematic-001.png', 'schematic'), ('assembly.png', 'assembly'),
                               ('top-copper.png', 'copper'), ('bottom-copper.png', 'copper')]:
            files[name] = png
            images.append({'id': Path(name).stem, 'title': name, 'kind': category,
                           'orientation': 'Test export',
                           'data_uri': 'data:image/png;base64,' + base64.b64encode(png).decode()})
        return files, images, {'kicad_version': 'test boundary'}

    monkeypatch.setattr(handover, 'review_project', review)
    monkeypatch.setattr(handover, 'capture_native', capture)
    return capture


def test_blocked_review_still_creates_complete_inspectable_packet(project_copy, tmp_path, native_boundaries):
    project = load_project(project_copy)
    before = input_hashes(project)
    output = tmp_path / 'handover'
    result = handover.create_report(project, output)
    assert result['exit_code'] == 1 and result['review_blocking']
    assert result['schematic_pages'] == 1 and result['native_views'] == 4
    assert input_hashes(project) == before
    assert '<strong>Blocked</strong>' in (output / 'index.html').read_text(encoding='utf-8')
    verified = handover.verify_report(output, project)
    assert verified['integrity_valid'] and verified['current_source_matches']
    assert verified['exit_code'] == 0 and verified['verified_outputs'] == 8


def test_verification_needs_no_native_tools_and_separates_stale_sources(
    project_copy, tmp_path, native_boundaries, monkeypatch,
):
    project = load_project(project_copy)
    output = tmp_path / 'handover'
    handover.create_report(project, output)
    monkeypatch.setattr(handover, 'discover_toolchain', lambda *a: pytest.fail('verification invoked native tools'))
    assert handover.verify_report(output)['current_source_matches'] is None
    project.schematic_path.write_bytes(project.schematic_path.read_bytes() + b'\n')
    result = handover.verify_report(output, project)
    assert result['integrity_valid'] and result['current_source_matches'] is False and result['exit_code'] == 1


@pytest.mark.parametrize('fault', ['changed-image', 'missing-file', 'extra-file', 'duplicate-key', 'escape'])
def test_verification_rejects_incomplete_or_tampered_packets(project_copy, tmp_path, native_boundaries, fault):
    output = tmp_path / 'handover'
    handover.create_report(load_project(project_copy), output)
    path = output / 'manifest.json'
    if fault == 'changed-image':
        (output / 'assembly.png').write_bytes(b'tampered')
    elif fault == 'missing-file':
        (output / 'schematic.pdf').unlink()
    elif fault == 'extra-file':
        (output / 'unlisted.txt').write_bytes(b'owner file')
    elif fault == 'duplicate-key':
        path.write_bytes(path.read_bytes().replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'))
    else:
        manifest = json.loads(path.read_bytes())
        manifest['outputs']['../owner.txt'] = manifest['outputs'].pop('assembly.png')
        path.write_bytes(json.dumps(manifest).encode())
    with pytest.raises(ValueError):
        handover.verify_report(output)


def test_existing_and_in_project_outputs_fail_before_review(project_copy, tmp_path, monkeypatch):
    project = load_project(project_copy)
    output = tmp_path / 'owner'
    output.mkdir()
    note = output / 'keep.txt'
    note.write_bytes(b'owner')
    monkeypatch.setattr(handover, 'review_project', lambda *a: pytest.fail('invalid output reached review'))
    with pytest.raises(FileExistsError):
        handover.create_report(project, output)
    with pytest.raises(ValueError, match='outside the source project'):
        handover.create_report(project, project.root / 'output/handover')
    assert note.read_bytes() == b'owner'


def test_source_edit_during_capture_refuses_publication(project_copy, tmp_path, native_boundaries, monkeypatch):
    project = load_project(project_copy)
    output = tmp_path / 'handover'

    def edited(snapshot, work):
        result = native_boundaries(snapshot, work)
        (project.root / 'DEVIATIONS.md').write_bytes(b'new owner decision')
        return result

    monkeypatch.setattr(handover, 'capture_native', edited)
    with pytest.raises(RuntimeError, match='inputs changed'):
        handover.create_report(project, output)
    assert not output.exists()
    assert (project.root / 'DEVIATIONS.md').read_bytes() == b'new owner decision'


def test_publication_source_failure_removes_only_unchanged_new_files(tmp_path):
    destination = tmp_path / 'new-output'
    calls = []

    def fail_after():
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError('source changed')

    with pytest.raises(RuntimeError, match='source changed'):
        handover._publish(destination, {'index.html': b'new', 'manifest.json': b'last'}, fail_after)
    assert not destination.exists()


def test_concurrent_owner_file_survives_failed_publication(tmp_path):
    destination = tmp_path / 'new-output'
    calls = []

    def owner_edit():
        calls.append(True)
        if len(calls) == 2:
            (destination / 'owner.txt').write_bytes(b'keep')

    with pytest.raises(RuntimeError, match='retained at'):
        handover._publish(destination, {'index.html': b'new', 'manifest.json': b'last'}, owner_edit)
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == {'owner.txt': b'keep'}


def test_cli_reports_blocker_and_verify_statuses(project_copy, tmp_path, native_boundaries, capsys):
    output = tmp_path / 'handover'
    assert main(['report', str(project_copy), '--output', str(output)]) == 1
    assert json.loads(capsys.readouterr().out)['review_blocking']
    assert main(['verify-report', str(output), '--project', str(project_copy)]) == 0
    assert json.loads(capsys.readouterr().out)['current_source_matches']


def test_report_path_alias_never_writes_to_owner_folder(project_copy, tmp_path):
    owner = tmp_path / 'owner'
    owner.mkdir()
    note = owner / 'keep.txt'
    note.write_bytes(b'owner')
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(owner, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'symlinks unavailable: {exc}')
    with pytest.raises(ValueError, match='symlink'):
        handover.create_report(load_project(project_copy), alias / 'handover')
    assert list(owner.iterdir()) == [note]


@pytest.mark.parametrize('fault', ['cached-review', 'cached-image'])
def test_individually_hashed_html_must_match_the_recorded_review_and_native_images(
    project_copy, tmp_path, native_boundaries, fault,
):
    output = tmp_path / 'handover'
    handover.create_report(load_project(project_copy), output)
    path = output / 'index.html'
    html = path.read_text(encoding='utf-8')
    if fault == 'cached-review':
        html = html.replace('"source_inputs_unchanged": true', '"source_inputs_unchanged": false')
    else:
        html = html.replace('data:image/png;base64,', 'data:image/jpeg;base64,', 1)
    payload = html.encode()
    path.write_bytes(payload)
    manifest_path = output / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    manifest['outputs']['index.html'] = {'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
    manifest_path.write_bytes(json.dumps(manifest).encode())
    with pytest.raises(ValueError, match='HTML'):
        handover.verify_report(output)
