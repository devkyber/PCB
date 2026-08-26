"""Phase 6 — autorouting via Freerouting.

Strategy:
- Unit tests for path detection and stats parsing (no network, no Java).
- @pytest.mark.slow: full pipeline (export DSN → Freerouting → import SES)
  on a small board built with KiCAD official footprints. Skipped if any
  prerequisite (KiCAD bundled Python, Freerouting JAR, library index) is
  missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_claude import state
from kicad_claude.adapters import freerouting, kicad_python
from kicad_claude.indexer import kicad_libs
from kicad_claude.templates.blank import write_blank_project
from kicad_claude.tools import library as lib_tools
from kicad_claude.tools import pcb as pcb_tools
from kicad_claude.tools import routing as routing_tools


# ===== Path detection ====================================================== #


def test_find_kicad_python_returns_existing_path():
    p = kicad_python.find_kicad_python()
    if p is None:
        pytest.skip("KiCAD bundled Python not present on this system")
    assert p.is_file()


def test_find_freerouting_jar_returns_existing_path():
    p = freerouting.find_freerouting_jar()
    if p is None:
        pytest.skip("freerouting.jar not present (not yet downloaded?)")
    assert p.is_file()
    # Sanity: jar files are at least a few MB.
    assert p.stat().st_size > 1_000_000


def test_find_java_present_in_environment():
    j = freerouting.find_java()
    if j is None:
        pytest.skip("`java` not on PATH")
    assert j.is_file()


# ===== Stats parser ======================================================== #


# Real captured output. The previous fixture here was invented ("pass 5
# complete: 87% completed") and matched no Freerouting version, so the parser
# was being validated against a format it would never see.

SAMPLE_LOG_21 = """
2026-08-25 13:19:50.797 INFO   Freerouting v2.1.0 (build-date: 2025-04-12)
2026-08-25 13:19:59.003 INFO   [5963C7] Auto-router pass #1 on board 'a9cc' was completed in 0.23 seconds with the score of 987.51.
2026-08-25 13:19:59.073 INFO   [5963C7] Auto-router pass #2 on board 'f4f9' was completed in 0.02 seconds with the score of 987.51.
2026-08-25 13:19:59.088 INFO   [5963C7] Auto-routing was completed in 0.49 seconds with the score of 987.51.
2026-08-25 13:19:59.194 INFO   [5963C7] Starting optimization on 7 threads...
2026-08-25 13:19:59.196 WARN   [5963C7] Multi-threaded route optimization is broken and it is known to generate clearance violations.
"""

SAMPLE_LOG_23 = """
2026-08-25 13:29:19.217 INFO   [C90315] Auto-routing pass #11 on board '466f' was completed in 0.49 seconds with the score of 983.98 (2 unrouted and 0 violations), using 6.83 CPU seconds.
2026-08-25 13:29:23.377 INFO   [C90315] The router's score (983.98) has not improved by more than 0.5 points in the last 10 passes (2 items still unconnected). Stopping the auto-router.
The following connections could not be routed -- please review your design:
  Net '+3V3' (1 unrouted connection):
    - via  ->  U3-13
  Net 'LC_SIG_N' (1 unrouted connection):
    - R4-1  ->  D2-2
2026-08-25 13:29:24.406 INFO   [C90315] Job finished with state: COMPLETED.
"""


def test_parse_stats_reads_21_log():
    stats = freerouting._parse_stats(SAMPLE_LOG_21)
    assert stats.get("version") == "2.1.0"
    # `passes_done` and `score` take the LAST match (final state).
    assert stats.get("passes_done") == 2
    assert stats.get("score") == 987.51
    # 2.1.x never reports unrouted counts; absence is not a clean route.
    assert stats.get("reported_unrouted") is None
    assert stats.get("optimizer_multithreaded_warning") is True


def test_parse_stats_reads_23_log():
    stats = freerouting._parse_stats(SAMPLE_LOG_23)
    assert stats.get("reported_unrouted") == 2
    assert stats.get("reported_violations") == 0
    assert stats.get("stagnated") is True
    assert stats.get("optimizer_multithreaded_warning") is False
    assert {n["net"] for n in stats["unrouted_nets"]} == {"+3V3", "LC_SIG_N"}


def test_parse_stats_reports_unknown_rather_than_clean():
    """No output must never look like a clean route."""
    stats = freerouting._parse_stats("nothing relevant here")
    assert stats["reported_unrouted"] is None
    assert stats["unrouted_nets"] == []
    assert stats.get("via_count") is None


def test_required_java_major_tracks_the_25_cutover():
    assert freerouting.required_java_major((2, 1, 0)) == 21
    assert freerouting.required_java_major((2, 2, 0)) == 25
    assert freerouting.required_java_major((2, 3, 0)) == 25
    assert freerouting.required_java_major(None) == 21


def test_build_args_omits_modern_flags_on_21():
    """A 2.1.x JAR rejects unknown arguments, so it must get none of them."""
    profile = freerouting.RouteProfile(passes=7, threads=1)
    args = freerouting.build_args((2, 1, 0), profile)
    assert args[:4] == ["-mp", "7", "-mt", "1"]
    assert not any(a.startswith("--") for a in args)


def test_build_args_emits_modern_flags_on_23():
    profile = freerouting.RouteProfile(passes=7, threads=1)
    args = freerouting.build_args((2, 3, 0), profile)
    assert "--gui.enabled=false" in args
    assert "--feature_flags.multi_threading=false" in args
    assert "--router.layers.preferred_direction_horizontal=true,false" in args
    assert "--router.fanout.enabled=true" in args


# ===== Full pipeline (slow) ================================================ #


def _have_prerequisites() -> tuple[bool, str]:
    if kicad_python.find_kicad_python() is None:
        return False, "KiCAD bundled Python not found"
    if freerouting.find_freerouting_jar() is None:
        return False, "freerouting.jar not found"
    if freerouting.find_java() is None:
        return False, "java not on PATH"
    if kicad_libs.load_cache() is None:
        return False, "library index not built"
    return True, ""


@pytest.mark.slow
def test_export_dsn_then_import_ses_pipeline(tmp_path: Path):
    """Build a tiny board, export DSN, run Freerouting, import SES — file grows."""
    ok, why = _have_prerequisites()
    if not ok:
        pytest.skip(why)

    state.clear_active()
    lib_tools._index = kicad_libs.load_cache()

    files = write_blank_project(tmp_path / "rt", "rt")
    state.set_active(tmp_path / "rt", "rt")

    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("t")
    pcb_tools.register(mcp)
    routing_tools.register(mcp)

    def call(name, **kw):
        return mcp._tool_manager.get_tool(name).fn(**kw)

    call("set_board_outline", width_mm=50, height_mm=30)
    call("add_footprint", lib_id="Resistor_SMD:R_0603_1608Metric",
         reference="R1", value="10k", x_mm=20, y_mm=15)
    call("add_footprint", lib_id="Resistor_SMD:R_0603_1608Metric",
         reference="R2", value="1k", x_mm=35, y_mm=15)

    pcb_path = files["pcb"]
    size_before_export = pcb_path.stat().st_size

    # 1) Export DSN
    res = call("export_dsn")
    dsn = Path(res["dsn_path"])
    assert dsn.is_file()
    assert dsn.stat().st_size > 100

    # 2) Run Freerouting (low passes — no nets means it terminates fast anyway)
    route_res = freerouting.route(
        dsn, dsn.with_suffix(".ses"), passes=5, timeout_seconds=60,
    )
    assert route_res["returncode"] == 0
    ses = Path(route_res["ses_path"])
    assert ses.is_file()

    # 3) Import SES — should not error and the PCB should still be parseable.
    import_res = call("import_ses", ses_path=str(ses))
    assert Path(import_res["pcb_path"]).is_file()
    assert pcb_path.stat().st_size >= size_before_export
    state.clear_active()


@pytest.mark.slow
def test_autoroute_pcb_tool_end_to_end(tmp_path: Path):
    """Full single-tool autoroute flow."""
    ok, why = _have_prerequisites()
    if not ok:
        pytest.skip(why)

    state.clear_active()
    lib_tools._index = kicad_libs.load_cache()

    files = write_blank_project(tmp_path / "ar", "ar")
    state.set_active(tmp_path / "ar", "ar")

    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("t")
    pcb_tools.register(mcp)
    routing_tools.register(mcp)

    def call(name, **kw):
        return mcp._tool_manager.get_tool(name).fn(**kw)

    call("set_board_outline", width_mm=50, height_mm=30)
    call("add_footprint", lib_id="Resistor_SMD:R_0603_1608Metric",
         reference="R1", value="10k", x_mm=20, y_mm=15)
    call("add_footprint", lib_id="Resistor_SMD:R_0603_1608Metric",
         reference="R2", value="1k", x_mm=35, y_mm=15)

    res = call("autoroute_pcb", passes=5, timeout_seconds=60)
    assert res["freerouting_returncode"] == 0
    assert Path(res["dsn_path"]).is_file()
    assert Path(res["ses_path"]).is_file()
    assert Path(res["pcb_path"]).is_file()
    state.clear_active()
