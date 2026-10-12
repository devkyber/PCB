import json
from pathlib import Path

import pytest

from pcb_copilot.cli import main
from pcb_copilot.project import load_project
from pcb_copilot.schematic import native_candidate as native
from pcb_copilot.schematic.preview import PreviewResult


@pytest.fixture
def fast_checks(monkeypatch):
    """Stub external validation; keep actual byte transactions and guards."""
    def preview(_tools, _schematic, output):
        output.mkdir(parents=True, exist_ok=True)
        (output / 'preview.pdf').write_bytes(b'%PDF fixture')
        (output / 'erc.json').write_text('{"sheets": []}')
        (output / 'metrics.json').write_text('{"sheets": []}')
        return PreviewResult(output / 'preview.pdf', output / 'erc.json', output / 'metrics.json', ())

    monkeypatch.setattr(native, 'discover_toolchain', lambda _: None)
    monkeypatch.setattr(native, 'render_schematic_preview', preview)
    monkeypatch.setattr(native, 'extract', lambda _: {'nets': {'U1': {'1': 'OWNER_NET'}}})
    monkeypatch.setattr(native, 'check_parity', lambda _: (True, 'matched'))
    monkeypatch.setattr(native, 'check_evidence', lambda *_: ())
    from pcb_copilot.layout import update as layout_update
    monkeypatch.setattr(layout_update, '_bind_candidate_links', lambda *_: [])


def make_candidate(project, tmp_path):
    directory = tmp_path / 'owner-candidate'
    directory.mkdir()
    path = directory / project.schematic_path.name
    path.write_bytes(project.schematic_path.read_bytes().replace(
        b'Host supply and I2C', b'Owner drawing note; preserve its UUID and position',
    ))
    return path


def add_child(root, filename):
    # Sufficient native hierarchy for the traversal/transaction tests.
    text = root.read_text(encoding='utf-8').rstrip()
    root.write_text(text[:-1] + f'\n(sheet (property "Sheetfile" "{filename}"))\n)', encoding='utf-8')


def test_native_preview_and_apply_preserve_exact_owner_bytes_and_intent(
    project_copy, tmp_path, fast_checks,
):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    original = project.schematic_path.read_bytes()
    wanted = candidate.read_bytes()
    intent = (project.root / 'schematic-intent.yaml').read_bytes()
    board = project.pcb_path.read_bytes()
    settings = project.pcb_path.with_suffix('.kicad_pro').read_bytes()

    preview = native.update_native_schematic(project, candidate)
    assert not preview['applied'] and preview['exit_code'] == 0
    assert project.schematic_path.read_bytes() == original
    assert Path(preview['preview']).read_bytes().startswith(b'%PDF')
    result = native.update_native_schematic(project, candidate, apply=True)

    assert result['applied'] and result['intent_status'].startswith('historical')
    assert project.schematic_path.read_bytes() == wanted
    assert b'78510354-83a3-4b7b-b00e-67b0e1810dfb' in wanted
    assert (project.root / 'schematic-intent.yaml').read_bytes() == intent
    assert project.pcb_path.read_bytes() == board
    assert project.pcb_path.with_suffix('.kicad_pro').read_bytes() == settings
    assert json.loads(project.netmap_path.read_text()) == {'nets': {'U1': {'1': 'OWNER_NET'}}}
    assert candidate.read_bytes() == wanted


def test_complete_hierarchy_installs_children_without_deleting_unused_sheets(
    project_copy, tmp_path, fast_checks,
):
    project = load_project(project_copy)
    old = project.root / 'old.kicad_sch'
    old.write_text('(kicad_sch (uuid "owner-old"))')
    add_child(project.schematic_path, 'old.kicad_sch')
    candidate = make_candidate(project, tmp_path)
    candidate.write_bytes(candidate.read_bytes().replace(b'old.kicad_sch', b'sub/new.kicad_sch'))
    child = candidate.parent / 'sub/new.kicad_sch'
    child.parent.mkdir()
    payload = b'(kicad_sch (uuid "owner-child") (text "Keep this note"))\n'
    child.write_bytes(payload)

    native.update_native_schematic(project, candidate)
    result = native.update_native_schematic(project, candidate, apply=True)

    assert result['applied']
    assert (project.root / 'sub/new.kicad_sch').read_bytes() == payload
    assert old.read_text() == '(kicad_sch (uuid "owner-old"))'


def test_candidate_cannot_traverse_outside_its_hierarchy(project_copy, tmp_path, fast_checks):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    add_child(candidate, '../outside.kicad_sch')
    with pytest.raises(ValueError, match='escapes'):
        native.update_native_schematic(project, candidate)


def test_unrelated_existing_sheet_is_never_overwritten(project_copy, tmp_path, fast_checks):
    project = load_project(project_copy)
    unrelated = project.root / 'unrelated.kicad_sch'
    unrelated.write_bytes(b'owner file')
    candidate = make_candidate(project, tmp_path)
    add_child(candidate, unrelated.name)
    (candidate.parent / unrelated.name).write_text('(kicad_sch)')
    before = project.schematic_path.read_bytes()

    with pytest.raises(ValueError, match='unrelated file'):
        native.update_native_schematic(project, candidate)
    assert unrelated.read_bytes() == b'owner file'
    assert project.schematic_path.read_bytes() == before


def test_parity_failure_blocks_without_native_cad_writes(project_copy, tmp_path, fast_checks, monkeypatch):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    before = project.schematic_path.read_bytes(), project.pcb_path.read_bytes(), project.netmap_path.read_bytes()
    monkeypatch.setattr(native, 'check_parity', lambda _: (False, 'owner net does not match board'))

    result = native.update_native_schematic(project, candidate)
    assert result['exit_code'] == 1 and not result['applied']
    assert any(item['code'] == 'board-parity' for item in result['findings'])
    with pytest.raises(RuntimeError, match='preview'):
        native.update_native_schematic(project, candidate, apply=True)
    assert before == (project.schematic_path.read_bytes(), project.pcb_path.read_bytes(), project.netmap_path.read_bytes())


@pytest.mark.parametrize('change', ['no_preview', 'candidate', 'current', 'editor'])
def test_apply_requires_current_preview_and_closed_editor(project_copy, tmp_path, fast_checks, change):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    if change != 'no_preview':
        native.update_native_schematic(project, candidate)
    if change == 'candidate':
        candidate.write_bytes(candidate.read_bytes() + b'\n')
    elif change == 'current':
        project.schematic_path.write_bytes(project.schematic_path.read_bytes() + b'\n')
    elif change == 'editor':
        project.schematic_path.with_name('~' + project.schematic_path.name + '.lck').write_text('owner editor')
    before = project.schematic_path.read_bytes()
    with pytest.raises(RuntimeError, match='preview|editor'):
        native.update_native_schematic(project, candidate, apply=True)
    assert project.schematic_path.read_bytes() == before


def test_source_change_during_validation_aborts(project_copy, tmp_path, fast_checks, monkeypatch):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    before = project.schematic_path.read_bytes()
    def change_source(_):
        candidate.write_bytes(candidate.read_bytes() + b'\n')
        return True, 'matched'
    monkeypatch.setattr(native, 'check_parity', change_source)

    with pytest.raises(RuntimeError, match='source changed'):
        native.update_native_schematic(project, candidate)
    assert project.schematic_path.read_bytes() == before


def test_cli_candidate_dispatch_and_reconcile_rejection(project_copy, tmp_path, fast_checks, capsys):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)

    assert main(['update-schematic', str(project.root), '--candidate', str(candidate)]) == 0
    assert json.loads(capsys.readouterr().out)['source_mode'] == 'native'
    with pytest.raises(SystemExit):
        main(['update-schematic', str(project.root), '--candidate', str(candidate), '--reconcile-board-names'])
    assert 'supported only with --intent' in capsys.readouterr().err


def test_paired_board_is_staged_and_bound_with_optional_companions(
    project_copy, tmp_path, fast_checks, monkeypatch,
):
    from pcb_copilot.layout import update

    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    board = tmp_path / 'paired.kicad_pcb'
    board.write_bytes(project.pcb_path.read_bytes() + b'\n')
    def prepare(snapshot, _intent, source, _route, output, *, schematic_change):
        assert schematic_change
        assert snapshot.root != project.root and source != board
        snapshot.pcb_path.write_bytes(source.read_bytes())
        return snapshot.pcb_path, [], {}
    monkeypatch.setattr(update, '_prepare_candidate', prepare)
    native.update_native_schematic(project, candidate, pcb_candidate=board)
    # Adding rules after preview changes the request even if the PCB is unchanged.
    board.with_suffix('.kicad_dru').write_text('(version 1)')
    with pytest.raises(RuntimeError, match='preview'):
        native.update_native_schematic(project, candidate, apply=True, pcb_candidate=board)
    board.with_suffix('.kicad_dru').unlink()
    native.update_native_schematic(project, candidate, pcb_candidate=board)
    result = native.update_native_schematic(project, candidate, apply=True, pcb_candidate=board)
    assert result['applied']
    assert project.pcb_path.read_bytes() == board.read_bytes()


@pytest.mark.parametrize('name', ['paired.txt', 'missing.kicad_pcb'])
def test_invalid_paired_pcb_path_does_not_silently_select_sibling(
    project_copy, tmp_path, fast_checks, name,
):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    (tmp_path / 'paired.txt').write_text('not a board')
    (tmp_path / 'paired.kicad_pcb').write_bytes(project.pcb_path.read_bytes())

    with pytest.raises(ValueError, match='existing .kicad_pcb'):
        native.update_native_schematic(project, candidate, pcb_candidate=tmp_path / name)


def test_failed_hierarchy_preflight_consumes_previous_success(project_copy, tmp_path, fast_checks):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    native.update_native_schematic(project, candidate)
    original = candidate.read_bytes()
    add_child(candidate, '../outside.kicad_sch')
    with pytest.raises(ValueError, match='escapes'):
        native.update_native_schematic(project, candidate)
    candidate.write_bytes(original)

    with pytest.raises(RuntimeError, match='preview'):
        native.update_native_schematic(project, candidate, apply=True)


def test_late_owner_child_created_at_transaction_entry_is_preserved(
    project_copy, tmp_path, fast_checks, monkeypatch,
):
    project = load_project(project_copy)
    candidate = make_candidate(project, tmp_path)
    add_child(candidate, 'new-child.kicad_sch')
    (candidate.parent / 'new-child.kicad_sch').write_text('(kicad_sch (uuid "candidate-child"))')
    native.update_native_schematic(project, candidate)
    destination = project.root / 'new-child.kicad_sch'
    before = (project.schematic_path.read_bytes(), project.netmap_path.read_bytes(), project.pcb_path.read_bytes())
    original_apply = native.apply_files

    def concurrent_owner_file(project, changes, expected, *, expected_targets):
        # This simulates the gap after the final source guard, before the
        # transaction captures originals. A commit-time exists() check is too late.
        assert expected_targets[destination] is None
        destination.write_bytes(b'owner work created after preview guard')
        return original_apply(project, changes, expected, expected_targets=expected_targets)

    monkeypatch.setattr(native, 'apply_files', concurrent_owner_file)
    with pytest.raises(RuntimeError, match='target|concurrent|changed'):
        native.update_native_schematic(project, candidate, apply=True)

    assert destination.read_bytes() == b'owner work created after preview guard'
    assert before == (project.schematic_path.read_bytes(), project.netmap_path.read_bytes(), project.pcb_path.read_bytes())
    assert not list((project.root / '.pcb-copilot').glob('recovery-*'))
    report = json.loads((project.root / '.pcb-copilot/preview/schematic-review.json').read_text())
    assert report['applied'] is False and report['exit_code'] == 1


@pytest.mark.slow
@pytest.mark.parametrize('already_linked', [False, True])
def test_native_candidate_with_real_kicad_preserves_drawing(project_copy, tmp_path, already_linked):
    from kicad_claude.adapters import sch_io
    from sexpdata import loads

    from pcb_copilot.layout.render import native_board, schematic_inventory
    from pcb_copilot.layout.schematic_links import bind_missing_links
    from pcb_copilot.toolchain import discover_toolchain

    project = load_project(project_copy)
    # Cover both a legacy board and a board already linked by F8.
    tools = discover_toolchain(project.root)
    parts, _ = schematic_inventory(tools, project.schematic_path)
    if already_linked:
        bind_missing_links(project.pcb_path, parts, native_board(tools, project.pcb_path)['footprints'])
    candidate = make_candidate(project, tmp_path)
    wanted = candidate.read_bytes()
    pcb = project.pcb_path.read_bytes()
    intent = (project.root / 'schematic-intent.yaml').read_bytes()

    result = native.update_native_schematic(project, candidate)
    assert result['exit_code'] == 0, result['findings']
    assert Path(result['preview']).read_bytes().startswith(b'%PDF')
    result = native.update_native_schematic(project, candidate, apply=True)

    assert result['applied'], result['findings']
    assert project.schematic_path.read_bytes() == wanted
    if already_linked:
        assert project.pcb_path.read_bytes() == pcb
    else:
        saved = sch_io.parse_file(project.pcb_path)
        original = loads(pcb.decode('utf-8'))
        for tree in (saved, original):
            for fp in sch_io.find_children(tree, 'footprint'):
                for path in sch_io.find_children(fp, 'path'):
                    fp.remove(path)
        assert saved == original
        assert any(item['code'] == 'layout.schematic_links_added' for item in result['findings'])
    assert (project.root / 'schematic-intent.yaml').read_bytes() == intent
