"""Review gating and preservation for the external scoped-change demonstration."""

import contextlib
import io
import json

import pymupdf
import pytest

from pcb_copilot.cli import main as cli_main
from pcb_copilot.project import load_project
from pcb_copilot.schematic import native_candidate
from pcb_copilot.schematic.preview import PreviewResult
from pcb_copilot.transaction import input_hashes
from tools import demo_change as change


@pytest.mark.parametrize('selection', ['tests/fixtures/boards/frozen-board', '../external-board'])
def test_cli_rejects_fixtures_and_external_projects_before_creating_output(tmp_path, monkeypatch, capsys, selection):
    repository = tmp_path / 'repo'
    repository.mkdir()
    monkeypatch.setattr(change, '__file__', str(repository / 'tools/demo_change.py'))
    output = tmp_path / 'external-output'
    assert change.main(['--project', selection, '--output', str(output)]) == 2
    assert not output.exists()
    error = capsys.readouterr().err
    assert ('inside this checkout' if selection.startswith('..') else 'frozen fixtures') in error


def test_prepare_rejects_fixture_source_before_creating_any_snapshot(tmp_path):
    repository = tmp_path / 'repo'
    repository.mkdir()
    with pytest.raises(ValueError, match='frozen fixtures'):
        change.prepare(repository, repository / 'tests/fixtures/boards/frozen-board', tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def source_project(repository):
    source = repository / 'examples' / 'gpio-indicator'
    source.mkdir(parents=True)
    (source / 'project.yaml').write_text(
        'schema_version: 1\nname: gpio-indicator\nlifecycle: DRAFT\n'
        'design:\n  schematic: gpio-indicator.kicad_sch\n  pcb: gpio-indicator.kicad_pcb\n'
        '  netmap: netmap.json\nevidence:\n  index: evidence/index.yaml\n'
        'manufacturing:\n  profile: jlcpcb_2layer_default\n', encoding='utf-8',
    )
    (source / 'gpio-indicator.kicad_sch').write_bytes(
        b'(kicad_sch (uuid "keep-uuid") (title_block (title "Demo") (rev "A1 DRAFT"))\r\n'
        b' (wire (pts (xy 1.123456789 2) (xy 3 4))) (no_connect (at 5 6) (uuid "keep-nc")))\r\n'
    )
    (source / 'gpio-indicator.kicad_pcb').write_bytes(b'unchanged owner PCB')
    (source / 'netmap.json').write_text('{"nets": {}}\n', encoding='utf-8')
    (source / 'evidence').mkdir()
    (source / 'evidence/index.yaml').write_text('schema_version: 1\nrecords: []\n', encoding='utf-8')
    return load_project(source)


@pytest.fixture
def checked_run(tmp_path, monkeypatch):
    repository = tmp_path / 'repo'
    project = source_project(repository)
    output = tmp_path / 'external-proof'
    output.mkdir()

    def render(_tools, _schematic, destination):
        destination.mkdir()
        with pymupdf.open() as document:
            document.new_page()
            document.save(destination / 'preview.pdf')
        (destination / 'erc.json').write_text('{"sheets": []}', encoding='utf-8')
        (destination / 'metrics.json').write_text('{"sheets": []}', encoding='utf-8')
        return PreviewResult(destination / 'preview.pdf', destination / 'erc.json',
                             destination / 'metrics.json', ())

    monkeypatch.setattr(native_candidate, 'render_schematic_preview', render)
    monkeypatch.setattr(native_candidate, 'discover_toolchain', lambda _: None)
    monkeypatch.setattr(native_candidate, 'extract', lambda _: {'nets': {}})
    monkeypatch.setattr(native_candidate, 'check_parity', lambda _: (True, 'test boundary'))
    monkeypatch.setattr(native_candidate, 'check_evidence', lambda *_: ())
    monkeypatch.setattr('pcb_copilot.layout.update._bind_candidate_links', lambda *_: [])
    monkeypatch.setattr(change, 'native_inventory', lambda *_: {'parts': {}, 'nets': {}})

    def in_process_command(output, name, arguments, **_kwargs):
        # Use the real public CLI and update guard/transaction implementation;
        # only the external KiCad validation boundary is stubbed in these tests.
        resolved = arguments[:]
        resolved[1] = str(output / arguments[1])
        resolved[resolved.index('--candidate') + 1] = str(output / arguments[arguments.index('--candidate') + 1])
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = cli_main(resolved)
            except SystemExit as exc:
                code = exc.code
        logs = output / 'logs'
        logs.mkdir(exist_ok=True)
        out, err = logs / f'{name}.stdout.txt', logs / f'{name}.stderr.txt'
        out.write_text(stdout.getvalue(), encoding='utf-8')
        err.write_text(stderr.getvalue(), encoding='utf-8')
        return {'name': name, 'command': ['pcb-copilot', *arguments], 'exit_code': code,
                'stdout': out.relative_to(output).as_posix(), 'stderr': err.relative_to(output).as_posix(),
                'error': None}

    monkeypatch.setattr(change.demo, 'run_command', in_process_command)
    return repository, project, output


def test_revision_edit_preserves_every_other_byte_and_electrical_node(tmp_path):
    project = source_project(tmp_path / 'repo')
    original = project.schematic_path.read_bytes()
    result = change.revise_drawing(project.schematic_path, 'DEMO-P1')
    assert project.schematic_path.read_bytes() == original.replace(b'"A1 DRAFT"', b'"DEMO-P1"')
    assert result['before'] == 'A1 DRAFT'
    assert b'1.123456789' in project.schematic_path.read_bytes()
    assert b'keep-nc' in project.schematic_path.read_bytes()


def test_default_proof_stops_after_real_stale_rejection_without_applying(checked_run):
    repository, project, output = checked_run
    before = input_hashes(project)
    result = change.prepare(repository, project.root, output)
    assert result['status'] == 'awaiting-author-visual-review', result
    assert not result['applied'] and result['exit_code'] == 0
    assert result['initial_change']['after'] == 'DEMO-P1'
    assert result['final_change']['after'] == 'DEMO-P2'
    assert b'"DEMO-P2"' in (output / result['candidate']).read_bytes()
    assert [step['exit_code'] for step in result['steps']] == [0, 2, 0]
    assert change.demo.GUARD_MESSAGE in (output / result['steps'][1]['stderr']).read_text(encoding='utf-8')
    assert input_hashes(project) == before
    assert input_hashes(load_project(output / result['snapshot'])) == before
    assert not (output / result['snapshot'] / 'fabrication').exists()


@pytest.mark.parametrize('tamper', ['candidate', 'snapshot', 'render', 'preview', 'source'])
def test_resume_refuses_changed_review_inputs_before_apply(checked_run, tamper):
    repository, project, output = checked_run
    result = change.prepare(repository, project.root, output)
    targets = {
        'candidate': output / result['candidate'],
        'snapshot': output / result['snapshot'] / project.pcb_path.name,
        'render': output / result['review_pdf'],
        'preview': output / result['snapshot'] / '.pcb-copilot/preview/schematic-review.json',
        'source': project.pcb_path,
    }
    if tamper in targets:
        targets[tamper].write_bytes(targets[tamper].read_bytes() + b'\n')
    applied = change.apply_reviewed(output, reviewed_sha256=result['review_sha256'],
                                    reviewer='AUTOMATED TEST ONLY')
    assert applied['exit_code'] == 2 and not applied['applied']
    assert len(applied['steps']) == 3
    if tamper == 'source':
        assert project.pcb_path.read_bytes().endswith(b'\n')  # Never restore a concurrent owner edit.


def test_wrong_review_hash_or_unrecognized_run_preserves_the_review_packet(checked_run):
    repository, project, output = checked_run
    change.prepare(repository, project.root, output)
    original = (output / 'transcript.json').read_bytes(), (output / 'report.md').read_bytes()
    with pytest.raises(ValueError, match='exact SHA-256'):
        change.apply_reviewed(output, reviewed_sha256='wrong', reviewer='AUTOMATED TEST ONLY')
    assert original == ((output / 'transcript.json').read_bytes(), (output / 'report.md').read_bytes())
    (output / 'transcript.json').write_text('{"status": "unrelated"}', encoding='utf-8')
    with pytest.raises(ValueError, match='not awaiting'):
        change.apply_reviewed(output, reviewed_sha256='wrong', reviewer='AUTOMATED TEST ONLY')
    assert (output / 'transcript.json').read_text(encoding='utf-8') == '{"status": "unrelated"}'
    assert (output / 'report.md').read_bytes() == original[1]


def test_reviewed_apply_installs_exact_candidate_only_in_snapshot(checked_run):
    repository, project, output = checked_run
    before = input_hashes(project)
    result = change.prepare(repository, project.root, output)
    result = change.apply_reviewed(output, reviewed_sha256=result['review_sha256'], reviewer='AUTOMATED TEST ONLY')
    assert result['status'] == 'applied-to-disposable-snapshot', result
    assert result['applied'] and result['snapshot_board_unchanged'] and result['source_inputs_unchanged']
    assert result['author_visual_review']['scope'].endswith('not owner sign-off.')
    assert input_hashes(project) == before
    snapshot = load_project(output / result['snapshot'])
    assert snapshot.schematic_path.read_bytes() == (output / result['candidate']).read_bytes()
    assert not (snapshot.root / 'review-signoff.yaml').exists()
    assert not (snapshot.root / 'fabrication').exists()
    assert [step['exit_code'] for step in result['steps']] == [0, 2, 0, 0]
    assert json.loads((output / 'transcript.json').read_text())['applied']


def test_proof_does_not_finish_with_the_original_revision(checked_run):
    repository, project, output = checked_run
    change.revise_drawing(project.schematic_path, 'DEMO-P2')
    result = change.prepare(repository, project.root, output)
    assert result['status'] == 'awaiting-author-visual-review', result
    assert result['final_change']['after'] == 'DEMO-P3'
    applied = change.apply_reviewed(output, reviewed_sha256=result['review_sha256'], reviewer='AUTOMATED TEST ONLY')
    assert applied['applied']
    assert project.schematic_path.name in applied['snapshot_changed_files']


def test_cli_requires_explicit_resume_and_review_identity(tmp_path):
    with pytest.raises(SystemExit) as stopped:
        change.main(['--apply', '--output', str(tmp_path / 'new')])
    assert stopped.value.code == 2
    with pytest.raises(SystemExit):
        change.main(['--resume', str(tmp_path), '--apply', '--reviewed-render-sha256', 'hash'])
