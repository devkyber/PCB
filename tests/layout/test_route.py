"""Candidate routing is isolated, policy-gated, and scored by fresh DRC."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace

import pytest
from kicad_claude.adapters import kicad_python

from pcb_copilot.layout.models import RoutePolicy
from pcb_copilot.layout.route import (
    _ROUTE_CHILD,
    RouteAttempt,
    RouteReport,
    legacy_route_cli,
    route_candidate,
)
from pcb_copilot.state import canonical_design_hash


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


def test_candidate_rejects_caller_forged_base_hash(layout_draft, fake_router):
    accepted = layout_draft.project.pcb_path
    accepted.write_bytes(accepted.read_bytes() + b"\n(stale accepted board)\n")
    forged = replace(layout_draft.record, base_pcb_hash=canonical_design_hash(accepted))
    with pytest.raises(ValueError, match="persisted"):
        route_candidate(layout_draft.project, forged, RoutePolicy.CANDIDATE_ALL, 1)
    assert fake_router.calls == []


def test_candidate_uses_persisted_schematic_base_hash(layout_draft, fake_router):
    schematic = layout_draft.project.schematic_path
    schematic.write_bytes(schematic.read_bytes() + b"\n(stale accepted schematic)\n")
    with pytest.raises(ValueError, match="accepted design changed"):
        route_candidate(
            layout_draft.project,
            layout_draft.record,
            RoutePolicy.CANDIDATE_ALL,
            1,
        )
    assert fake_router.calls == []


def test_candidate_rejects_forged_noncanonical_draft_root(
    layout_draft, fake_router, tmp_path
):
    forged_root = tmp_path / layout_draft.record.id
    shutil.copytree(layout_draft.record.root, forged_root)
    forged = replace(layout_draft.record, root=forged_root)
    with pytest.raises(ValueError, match="canonical"):
        route_candidate(layout_draft.project, forged, RoutePolicy.CANDIDATE_ALL, 1)
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


def test_shared_pipeline_subprocess_trace_is_complete_and_ordered(
    layout_draft, fake_router
):
    report = route_candidate(
        layout_draft.project, layout_draft.record, RoutePolicy.CANDIDATE_ALL, 1
    )
    commands = report.attempts[0].commands
    expected = [
        "pipeline.export_dsn",
        "pipeline.inspect_keepouts",
        "pipeline.freerouting",
        "pipeline.import_ses",
        "pipeline.fill_zones",
        "pipeline.drc.1",
        "pipeline.bond_ground",
        "pipeline.drc.2",
    ]
    operations = [
        command.split(":", 1)[0]
        for command in commands
        if command.startswith("pipeline.")
    ]
    assert operations == expected


def test_route_child_traces_each_nested_subprocess_boundary(tmp_path):
    package = tmp_path / "fake" / "kicad_claude" / "adapters"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from . import dsn_keepouts, route_pipeline\n", encoding="utf-8"
    )
    (package / "dsn_keepouts.py").write_text(
        """import subprocess,sys
def collect(*args, **kwargs):
    subprocess.run([sys.executable, '-c', 'pass', 'inspect_keepouts'], check=True)
    return []
""",
        encoding="utf-8",
    )
    (package / "route_pipeline.py").write_text(
        """import subprocess,sys
from . import dsn_keepouts
def invoke(name):
    subprocess.run([sys.executable, '-c', 'pass', name], check=True)
class KiPython:
    def export_dsn(self, *args, **kwargs): invoke('export_dsn')
    def import_ses(self, *args, **kwargs): invoke('import_ses')
    def fill_zones(self, *args, **kwargs): invoke('fill_zones')
    def bond_ground(self, *args, **kwargs): invoke('bond_ground')
class Freerouting:
    def route(self, *args, **kwargs):
        invoke('freerouting')
        return {'jar_version': 'test', 'java': sys.executable,
                'jar': 'test.jar', 'args': ['-de', 'test.dsn']}
class KicadCli:
    def run_drc(self, *args, **kwargs): invoke('drc')
kicad_python, freerouting, kicad_cli = KiPython(), Freerouting(), KicadCli()
def route_board(path, **kwargs):
    kicad_python.export_dsn()
    dsn_keepouts.collect()
    freerouting.route()
    kicad_python.import_ses()
    kicad_python.fill_zones()
    if path.name.startswith('fail'):
        raise RuntimeError('simulated pipeline failure')
    kicad_cli.run_drc()
    kicad_python.bond_ground()
    kicad_cli.run_drc()
    return {'pcb_path': str(path)}
""",
        encoding="utf-8",
    )
    pcb = tmp_path / "candidate.kicad_pcb"
    pcb.write_text("fixture", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            _ROUTE_CHILD,
            str(tmp_path / "fake"),
            str(pcb),
            "1",
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    document = json.loads(
        next(
            line.removeprefix("PCB_COPILOT_ROUTE_RESULT=")
            for line in result.stdout.splitlines()
            if line.startswith("PCB_COPILOT_ROUTE_RESULT=")
        )
    )
    assert [entry["operation"] for entry in document["_command_trace"]] == [
        "pipeline.export_dsn",
        "pipeline.inspect_keepouts",
        "pipeline.freerouting",
        "pipeline.import_ses",
        "pipeline.fill_zones",
        "pipeline.drc.1",
        "pipeline.bond_ground",
        "pipeline.drc.2",
    ]
    assert all(entry["argv"] and "cwd" in entry for entry in document["_command_trace"])

    failed_pcb = tmp_path / "fail-candidate.kicad_pcb"
    failed_pcb.write_text("fixture", encoding="utf-8")
    failed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            _ROUTE_CHILD,
            str(tmp_path / "fake"),
            str(failed_pcb),
            "1",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert failed.returncode == 0
    failed_document = json.loads(
        next(
            line.removeprefix("PCB_COPILOT_ROUTE_RESULT=")
            for line in failed.stdout.splitlines()
            if line.startswith("PCB_COPILOT_ROUTE_RESULT=")
        )
    )
    assert "simulated pipeline failure" in failed_document["_pipeline_error"]
    assert [entry["operation"] for entry in failed_document["_command_trace"]] == [
        "pipeline.export_dsn",
        "pipeline.inspect_keepouts",
        "pipeline.freerouting",
        "pipeline.import_ses",
        "pipeline.fill_zones",
    ]


def test_legacy_wrapper_presents_unknown_instead_of_negative_metrics(
    layout_draft, monkeypatch, capsys
):
    from pcb_copilot.layout import route

    unknown = RouteReport(
        attempts=(RouteAttempt(1, layout_draft.pcb, -1, -1, ()),),
        selected=None,
        drc_errors=-1,
        unconnected=-1,
        limitations=("measurement unavailable",),
    )
    monkeypatch.setattr(route, "RouteBackend", lambda **_kwargs: object())
    monkeypatch.setattr(route, "_route_candidate", lambda *_args: unknown)
    assert legacy_route_cli([str(layout_draft.pcb)], best_of=False) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["drc_errors"] == "unknown"
    assert output["unconnected"] == "unknown"
    assert output["attempts"][0]["drc_errors"] == "unknown"
    assert output["attempts"][0]["unconnected"] == "unknown"


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
        [str(kipython), str(repo_root / "scripts/fix_via_annular.py"), str(pcb)],
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
