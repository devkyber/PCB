"""Candidate routing is isolated, policy-gated, and scored by fresh DRC."""

from __future__ import annotations

import json
import subprocess

import pytest
from kicad_claude.adapters import kicad_python

from pcb_copilot.layout.models import RoutePolicy
from pcb_copilot.layout.route import legacy_route_cli, route_candidate


def test_legacy_discovery_finds_measured_kicad_runtime(kipython):
    assert kicad_python.find_kicad_python() == kipython


def test_human_policy_never_invokes_router(layout_draft, fake_router):
    report = route_candidate(
        layout_draft.project, layout_draft.record, RoutePolicy.HUMAN, 1
    )
    assert fake_router.calls == []
    assert report.selected is None


def test_critical_only_never_broadens_to_all_nets(layout_draft, fake_router):
    report = route_candidate(
        layout_draft.project, layout_draft.record, RoutePolicy.CRITICAL_ONLY, 1
    )
    assert fake_router.calls == []
    assert report.selected is None
    assert any(
        "critical" in item.lower() and "unsupported" in item.lower()
        for item in report.limitations
    )


def test_legacy_wrapper_rejects_accepted_board_without_invoking_router(
    layout_draft, fake_router
):
    with pytest.raises(ValueError, match="published.*draft"):
        legacy_route_cli([str(layout_draft.project.pcb_path)], best_of=False)
    assert fake_router.calls == []


def test_attempts_use_isolated_copies_and_score_unconnected_before_drc(
    layout_draft, fake_router
):
    source = layout_draft.pcb.read_bytes()
    accepted = layout_draft.project.pcb_path.read_bytes()
    report = route_candidate(
        layout_draft.project, layout_draft.record, RoutePolicy.CANDIDATE_ALL, 3
    )
    assert layout_draft.pcb.read_bytes() == source
    assert layout_draft.project.pcb_path.read_bytes() == accepted
    assert len({attempt.pcb_path for attempt in report.attempts}) == 3
    assert all(attempt.pcb_path.read_bytes() != source for attempt in report.attempts)
    assert [(item.unconnected, item.drc_errors) for item in report.attempts] == [
        (3, 4),
        (1, 6),
        (1, 2),
    ]
    assert report.selected == 3
    assert (report.unconnected, report.drc_errors) == (1, 2)


def test_postprocessing_runs_fresh_drc_without_rerouting(layout_draft, fake_router):
    report = route_candidate(
        layout_draft.project, layout_draft.record, RoutePolicy.CANDIDATE_ALL, 1
    )
    commands = report.attempts[0].commands
    assert sum("PCB_COPILOT_ROUTE_RESULT=" in command for command in commands) == 1
    assert any("fix_via_annular.py" in command for command in commands)
    assert any("test-java -version" in command for command in commands)
    assert commands[-1].find(" pcb drc ") >= 0
    assert report.drc_errors == fake_router.scores[0][0]
    assert report.drc_errors != fake_router.initial_drc_errors
    assert any("Freerouting test-2.3.0" in item for item in report.limitations)
    assert any("Java runtime: test-version" in item for item in report.limitations)


def test_failed_attempt_with_unknown_metrics_cannot_be_selected(
    layout_draft, fake_router
):
    fake_router.scores = [(0, 0), (2, 2)]
    fake_router.fail_attempts = {1}
    report = route_candidate(
        layout_draft.project, layout_draft.record, RoutePolicy.CANDIDATE_ALL, 2
    )
    assert (report.attempts[0].unconnected, report.attempts[0].drc_errors) == (-1, -1)
    assert report.selected == 2
    assert (report.unconnected, report.drc_errors) == (2, 2)
    assert any("unknown" in item.lower() for item in report.limitations)


def test_grid_stitching_is_skipped_below_two_pour_layers(layout_draft, fake_router):
    fake_router.pour_layers = ("B.Cu",)
    report = route_candidate(
        layout_draft.project, layout_draft.record, RoutePolicy.CANDIDATE_ALL, 1
    )
    assert not any(
        any(value.endswith("stitch_vias.py") for value in call)
        for call in fake_router.calls
    )
    assert any("grid stitching skipped" in item.lower() for item in report.limitations)
    assert any(
        "fix_via_annular.py" in command for command in report.attempts[0].commands
    )


def test_annular_repair_widens_copper_without_shrinking_drill(
    layout_draft, kipython, repo_root
):
    pcb = layout_draft.pcb
    script = r"""
import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
ds=b.GetDesignSettings()
ds.m_ViasMinAnnularWidth=pcbnew.FromMM(.15)
v=pcbnew.PCB_VIA(b)
v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(9),pcbnew.FromMM(12)))
v.SetDrill(pcbnew.FromMM(.4))
v.SetWidth(pcbnew.FromMM(.6))
b.Add(v)
pcbnew.SaveBoard(sys.argv[1],b,True)
"""
    subprocess.run(
        [str(kipython), "-I", "-c", script, str(pcb)], check=True, timeout=30
    )
    subprocess.run(
        [str(kipython), str(repo_root / "docs/fix_via_annular.py"), str(pcb)],
        check=True,
        timeout=30,
    )
    measure = r"""
import json,pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
v=next(v for v in b.GetTracks() if isinstance(v,pcbnew.PCB_VIA)
       and pcbnew.ToMM(v.GetPosition().x)==9 and pcbnew.ToMM(v.GetPosition().y)==12)
print(json.dumps([pcbnew.ToMM(v.GetFrontWidth()),pcbnew.ToMM(v.GetDrill())]))
"""
    result = subprocess.run(
        [str(kipython), "-I", "-c", measure, str(pcb)],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    diameter, drill = json.loads(result.stdout.strip().splitlines()[-1])
    assert diameter == pytest.approx(0.7)
    assert drill == pytest.approx(0.4)
