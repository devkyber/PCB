"""A broken outline can be repaired without losing the owner's copper baseline."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from pcb_copilot.layout import update
from pcb_copilot.layout.render import native_board
from pcb_copilot.project import load_project


@pytest.mark.parametrize('outline_state', ['open', 'missing'])
def test_native_repair_baseline_retains_inventory_and_strict_candidate_rejects(
    project_copy, kipython, outline_state,
):
    pcb = project_copy / 'baro-bmp390.kicad_pcb'
    tools = SimpleNamespace(kipython=kipython)
    original = native_board(tools, pcb)
    subprocess.run(
        [str(kipython), '-I', '-c', '''import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
edges=[d for d in b.GetDrawings() if d.GetLayer()==pcbnew.Edge_Cuts]
for edge in edges:
    b.RemoveNative(edge)
if sys.argv[2]=='open':
    edge=pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(0),pcbnew.FromMM(0)))
    edge.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(20),pcbnew.FromMM(0)))
    edge.SetWidth(pcbnew.FromMM(.05))
    b.Add(edge)
pcbnew.SaveBoard(sys.argv[1],b,True)
''', str(pcb), outline_state],
        check=True, capture_output=True, text=True, timeout=30,
    )
    saved = pcb.read_bytes()
    baseline = native_board(tools, pcb, require_outline=False)
    assert baseline['bounds'] is None and baseline['rectangular'] is None
    assert baseline['outline_error'] == 'Cannot obtain native board outline'
    for key in ('footprints', 'tracks', 'zones', 'rule_areas'):
        assert baseline[key] == original[key]
    assert baseline['tracks'] > 0 and baseline['zones'] > 0
    with pytest.raises(ValueError, match='Cannot obtain native board outline'):
        native_board(tools, pcb)
    assert pcb.read_bytes() == saved


def test_optional_outline_never_allows_malformed_cad_or_writes(tmp_path, kipython):
    pcb = tmp_path / 'broken.kicad_pcb'
    pcb.write_text('this is not a KiCad board')
    tools = SimpleNamespace(kipython=kipython)
    with pytest.raises(ValueError, match='native PCB operation failed'):
        native_board(tools, pcb, require_outline=False)
    output = tmp_path / 'should-not-exist.kicad_pcb'
    with pytest.raises(ValueError, match='read-only'):
        native_board(tools, pcb, require_outline=False, output=output)
    assert not output.exists()


def test_optional_outline_keeps_duplicate_reference_rejection(project_copy, kipython):
    pcb = project_copy / 'baro-bmp390.kicad_pcb'
    subprocess.run(
        [str(kipython), '-I', '-c', '''import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
fps=list(b.GetFootprints())
fps[1].SetReference(fps[0].GetReference())
pcbnew.SaveBoard(sys.argv[1],b,True)
''', str(pcb)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    with pytest.raises(ValueError, match='Duplicate footprint reference'):
        native_board(SimpleNamespace(kipython=kipython), pcb, require_outline=False)


@pytest.mark.parametrize('after_tracks', [0, 12])
def test_repair_update_relaxes_only_baseline_and_preserves_copper_loss_gate(
    project_copy, tmp_path, monkeypatch, after_tracks,
):
    project = load_project(project_copy)
    candidate = tmp_path / 'candidate.kicad_pcb'
    candidate.write_bytes(project.pcb_path.read_bytes())
    (project.root / 'layout-intent.yaml').unlink(missing_ok=True)
    calls = []
    before = {'footprints': {'U1': {}}, 'tracks': 10, 'zones': 1,
              'bounds': None, 'rectangular': None,
              'outline_error': 'Cannot obtain native board outline'}

    def inspect_native(_toolchain, pcb, *, require_outline=True, allow_duplicate_references=False):
        calls.append(require_outline)
        if len(calls) == 1:
            return before
        return {'footprints': {'U1': {}}, 'tracks': after_tracks, 'zones': 1}

    monkeypatch.setattr(update, 'discover_toolchain', lambda _: SimpleNamespace(kipython=Path('python')))
    monkeypatch.setattr(update, 'native_board', inspect_native)
    monkeypatch.setattr(update.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    monkeypatch.setattr(update, 'check_parity', lambda _: (True, 'parity'))
    monkeypatch.setattr(update, 'check_placement', lambda _: (True, 'placement'))
    monkeypatch.setattr(update, 'drc_once', lambda *args: (0, 0, 0))
    monkeypatch.setattr(update, '_bind_candidate_links', lambda *args: [])
    monkeypatch.setattr(update, 'inspect_routing', lambda *args: {'findings': [], 'counts': {}})
    monkeypatch.setattr(update, 'render_layout_preview', lambda *args: [])
    monkeypatch.setattr(update, 'check_evidence', lambda *args: [])
    result = update.update_layout(project, candidate=candidate)
    assert calls == [False, True]
    assert result['comparison']['before'] == before
    assert any(f['code'] == 'layout.baseline_outline' and f['severity'] == 'review'
               for f in result['findings'])
    assert any(f['code'] == 'layout.copper_loss' and f['severity'] == 'block'
               for f in result['findings']) == (after_tracks == 0)
    assert result['exit_code'] == int(after_tracks == 0)


def test_duplicate_reference_baseline_keeps_every_uuid_and_candidate_stays_strict(project_copy, kipython):
    pcb = project_copy / 'baro-bmp390.kicad_pcb'
    tools = SimpleNamespace(kipython=kipython)
    original = native_board(tools, pcb)
    subprocess.run([str(kipython), '-I', '-c', '''import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1]); fps=list(b.GetFootprints())
fps[1].SetReference(fps[0].GetReference()); pcbnew.SaveBoard(sys.argv[1],b,True)
''', str(pcb)], check=True, capture_output=True, timeout=30)
    saved = pcb.read_bytes()
    baseline = native_board(tools, pcb, allow_duplicate_references=True)
    assert baseline['duplicate_references']
    assert len(baseline['footprints']) == len(original['footprints'])
    assert {p['uuid'] for p in baseline['footprints'].values()} == {
        p['uuid'] for p in original['footprints'].values()}
    assert not update.nonregression_findings(baseline, original, unconnected=0)
    removed = dict(original, footprints=dict(list(original['footprints'].items())[1:]))
    assert any(f['code'] == 'layout.removed_parts' for f in
               update.nonregression_findings(baseline, removed, unconnected=0))
    with pytest.raises(ValueError, match='Duplicate footprint reference'):
        native_board(tools, pcb)
    assert pcb.read_bytes() == saved
