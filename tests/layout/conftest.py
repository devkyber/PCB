from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pcb_copilot.toolchain import discover_toolchain

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PCB_HELPERS = _load_module("characterized_pcb_layout_helpers", REPO_ROOT / "docs/pcb_layout_helpers.py")
VALIDATOR = _load_module("characterized_validate_pcb", REPO_ROOT / "docs/validate_pcb.py")


@pytest.fixture
def header_mod(repo_root: Path) -> Path:
    return repo_root / "tests/fixtures/kicad/PinHeader_1x04_P2.54mm_Vertical.kicad_mod"


@pytest.fixture
def pcb_helpers():
    return PCB_HELPERS


@pytest.fixture
def validator():
    return VALIDATOR


@pytest.fixture
def coordinate_helpers(repo_root: Path) -> dict[str, object]:
    """Load only pure coordinate definitions; importing the generator rewrites its board."""
    path = repo_root / "projects/tms-v3/gen_tms_v3_pcb.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {"ORIGIN_X", "ORIGIN_Y", "BOARD_W", "BOARD_H", "PAGE_H", "KICAD_Y0"}
    functions = {"design_to_mcp", "design_to_kicad", "kicad_to_design"}
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id in names for target in targets):
                selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in functions:
            selected.append(node)
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - deliberately execute only selected pure AST definitions
        compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace
    )
    return namespace


def capture_layout_metrics(pcb: Path) -> dict[str, object]:
    """Capture a read-only, deterministic summary through KiCad's pcbnew API."""
    toolchain = discover_toolchain(REPO_ROOT)
    if toolchain.kipython is None:
        raise RuntimeError("KiCad Python with pcbnew is required for layout characterization")
    script = r'''
import json
import pcbnew
import sys

board = pcbnew.LoadBoard(sys.argv[1])
footprints = sorted(board.GetFootprints(), key=lambda fp: fp.GetReference())
tracks = list(board.GetTracks())
print(json.dumps({
    "refs": [fp.GetReference() for fp in footprints],
    "footprints": {fp.GetReference(): fp.GetFPIDAsString() for fp in footprints},
    "pad_counts": {fp.GetReference(): fp.GetPadCount() for fp in footprints},
    "net_count": max(0, board.GetNetCount() - 1),
    "track_count": sum(item.GetClass() == "PCB_TRACK" for item in tracks),
    "via_count": sum(item.GetClass() == "PCB_VIA" for item in tracks),
    "zone_layers": sorted({zone.GetLayerName() for zone in board.Zones()}),
}, sort_keys=True))
'''
    result = subprocess.run(
        [str(toolchain.kipython), "-I", "-c", script, str(pcb.resolve())],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    metrics = json.loads(result.stdout)
    text = pcb.read_text(encoding="utf-8")
    xs, ys = VALIDATOR.get_board_bounds(text)
    metrics["board_bounds_mm"] = {
        "x_min": min(xs),
        "y_min": min(ys),
        "x_max": max(xs),
        "y_max": max(ys),
    }

    checks = {
        "placeholder_footprints": VALIDATOR.check_placeholders(text),
        "fiducials": VALIDATOR.check_fiducials(text),
        "board_dimensions": VALIDATOR.check_board_dimensions(text),
        "silkscreen": VALIDATOR.check_silkscreen(text),
        "trace_routing": VALIDATOR.check_traces_exist(text),
        "edge_clearance_origins": VALIDATOR.check_edge_clearance(text),
        "pads_inside_board": VALIDATOR.check_pads_inside_board(text),
        "courtyard_collisions": VALIDATOR.check_courtyard_overlap(text),
        "module_socket_pinouts": VALIDATOR.check_module_socket_pinouts(text),
        "symbol_footprint_parity": VALIDATOR.check_symbol_footprint_parity(str(pcb)),
        "connector_class": VALIDATOR.check_connector_class(str(pcb)),
        "drc_report": VALIDATOR.check_drc_freshness(str(pcb)),
    }
    metrics["validator_statuses"] = {name: result[0] for name, result in checks.items()}

    reports = sorted(pcb.parent.glob("*drc*.json"))
    if reports:
        report = reports[-1]
        document = json.loads(report.read_text(encoding="utf-8"))
        violations = document.get("violations", [])
        unconnected = document.get("unconnected_items", [])
        parity = document.get("schematic_parity", [])
        metrics["known_drc_result"] = {
            "provenance": "historical_saved_report_not_freshly_run",
            "report": report.name,
            "result": "FAIL" if violations or unconnected or parity else "PASS",
            "violation_count": len(violations),
            "unconnected_count": len(unconnected),
            "schematic_parity_count": len(parity),
        }
    else:
        metrics["known_drc_result"] = {
            "provenance": "no_saved_report",
            "result": "UNKNOWN",
        }
    return metrics


@pytest.fixture
def capture_layout_metrics_fn():
    return capture_layout_metrics
