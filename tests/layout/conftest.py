from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from pcb_copilot.toolchain import ToolchainDiscoveryError, discover_toolchain

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PCB_HELPERS = _load_module(
    "characterized_pcb_layout_helpers", REPO_ROOT / "scripts/pcb_layout_helpers.py"
)
VALIDATOR = _load_module(
    "characterized_validate_pcb", REPO_ROOT / "scripts/validate_pcb.py"
)


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
            if any(
                isinstance(target, ast.Name) and target.id in names
                for target in targets
            ):
                selected.append(node)
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in functions
        ):
            selected.append(node)
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - deliberately execute only selected pure AST definitions
        compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return namespace


def _kipython_or_skip() -> Path:
    try:
        toolchain = discover_toolchain(REPO_ROOT)
    except ToolchainDiscoveryError as exc:
        pytest.skip(f"KiCad integration unavailable: {exc}")
    if toolchain.kipython is None:
        pytest.skip(
            "KiCad integration unavailable: no Python runtime can import pcbnew"
        )
    return toolchain.kipython


@pytest.fixture(scope="session")
def kipython() -> Path:
    return _kipython_or_skip()


def capture_layout_metrics(pcb: Path) -> dict[str, object]:
    """Capture a read-only, deterministic summary through KiCad's pcbnew API."""
    kipython = _kipython_or_skip()
    script = r"""
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
"""
    result = subprocess.run(
        [str(kipython), "-I", "-c", script, str(pcb.resolve())],
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
    }
    metrics["validator_statuses"] = {name: result[0] for name, result in checks.items()}

    reports = sorted(pcb.parent.glob("*drc*.json"))
    if reports:
        # Match validate_pcb's report choice, while keeping its mtime-sensitive
        # freshness verdict out of this checkout-stable historical snapshot.
        report = max(reports, key=lambda path: path.stat().st_mtime)
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


@pytest.fixture
def sensor_layout_draft(project_copy, repo_root, kipython):
    from pcb_copilot.drafts import create_draft
    from pcb_copilot.layout.io import load_layout_intent
    from pcb_copilot.models import DraftKind
    from pcb_copilot.project import load_project

    project = load_project(project_copy)
    return SimpleNamespace(
        project=project,
        intent=load_layout_intent(
            repo_root / "tests/fixtures/layout/sensor-layout.yaml"
        ),
        record=create_draft(project, DraftKind.LAYOUT),
    )


@pytest.fixture
def layout_draft(sensor_layout_draft):
    """A published layout draft suitable for candidate-only routing tests."""
    from pcb_copilot.drafts import publish_draft

    fixture = sensor_layout_draft
    publish_draft(fixture.record, lambda root: None)
    fixture.pcb = fixture.record.root / fixture.project.pcb_path.relative_to(
        fixture.project.root
    )
    return fixture


@dataclass
class _FakeRouter:
    """Subprocess-shaped offline router used at the RouteBackend boundary."""

    calls: list[list[str]] = field(default_factory=list)
    scores: list[tuple[int, int]] = field(
        default_factory=lambda: [(4, 3), (6, 1), (2, 1)]
    )
    pour_layers: tuple[str, ...] = ("F.Cu", "B.Cu")
    initial_drc_errors: int = 99
    fail_attempts: set[int] = field(default_factory=set)

    def __call__(self, command, **kwargs):
        command = [str(value) for value in command]
        self.calls.append(command)
        pcb = next(
            (
                Path(value)
                for value in reversed(command)
                if value.endswith(".kicad_pcb")
            ),
            None,
        )
        if any("PCB_COPILOT_ROUTE_RESULT=" in value for value in command):
            assert pcb is not None
            index = int(pcb.parent.name.rsplit("-", 1)[1]) - 1
            if index + 1 in self.fail_attempts:
                raise RuntimeError("simulated router failure")
            pcb.write_bytes(pcb.read_bytes() + f"\nroute-{index + 1}".encode())
            result = {
                "unconnected": self.scores[index][1],
                "drc": {"errors": self.initial_drc_errors},
                "steps": ["export_dsn", "freerouting", "import_ses", "fill_zones"],
                "freerouting": {
                    "jar_version": "test-2.3.0",
                    "java": "test-java",
                    "args": ["-jar", "test-router.jar"],
                },
                "_router_details": {
                    "jar_version": "test-2.3.0",
                    "java": "test-java",
                    "jar": "test-router.jar",
                    "args": ["-de", "test.dsn", "-do", "test.ses"],
                },
                "_command_trace": [
                    {
                        "operation": "pipeline.export_dsn",
                        "argv": ["kipython", "export_dsn"],
                        "cwd": None,
                    },
                    {
                        "operation": "pipeline.inspect_keepouts",
                        "argv": ["kipython", "inspect_keepouts"],
                        "cwd": None,
                    },
                    {
                        "operation": "pipeline.freerouting",
                        "argv": ["java", "freerouting"],
                        "cwd": None,
                    },
                    {
                        "operation": "pipeline.import_ses",
                        "argv": ["kipython", "import_ses"],
                        "cwd": None,
                    },
                    {
                        "operation": "pipeline.fill_zones",
                        "argv": ["kipython", "fill_zones"],
                        "cwd": None,
                    },
                    {
                        "operation": "pipeline.drc.1",
                        "argv": ["kicad-cli", "drc_before_bond"],
                        "cwd": None,
                    },
                    {
                        "operation": "pipeline.bond_ground",
                        "argv": ["kipython", "bond_ground"],
                        "cwd": None,
                    },
                    {
                        "operation": "pipeline.drc.2",
                        "argv": ["kicad-cli", "drc_after_bond"],
                        "cwd": None,
                    },
                ],
            }
            return SimpleNamespace(
                returncode=0,
                stdout="PCB_COPILOT_ROUTE_RESULT=" + json.dumps(result) + "\n",
                stderr="",
            )
        if any("PCB_COPILOT_POUR_LAYERS=" in value for value in command):
            return SimpleNamespace(
                returncode=0,
                stdout="PCB_COPILOT_POUR_LAYERS=" + json.dumps(self.pour_layers) + "\n",
                stderr="",
            )
        if any(value.endswith("stitch_vias.py") for value in command):
            assert pcb is not None
            pcb.write_bytes(pcb.read_bytes() + b"\nstitch")
            return SimpleNamespace(returncode=0, stdout="stitched\n", stderr="")
        if any(value.endswith("fix_via_annular.py") for value in command):
            assert pcb is not None
            pcb.write_bytes(pcb.read_bytes() + b"\nannular")
            return SimpleNamespace(returncode=0, stdout="fixed\n", stderr="")
        if "drc" in command:
            assert pcb is not None
            index = int(pcb.parent.name.rsplit("-", 1)[1]) - 1
            output = Path(command[command.index("-o") + 1])
            errors, unconnected = self.scores[index]
            output.write_text(
                json.dumps(
                    {
                        "violations": [
                            {"severity": "error", "type": "clearance"}
                            for _ in range(errors)
                        ],
                        "unconnected_items": [{} for _ in range(unconnected)],
                    }
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "--version" in command or "-version" in command:
            return SimpleNamespace(returncode=0, stdout="test-version\n", stderr="")
        raise AssertionError(f"unexpected routing command: {command}")


@pytest.fixture
def fake_router(monkeypatch, repo_root):
    from pcb_copilot.layout import route
    from pcb_copilot.toolchain import ToolchainPaths

    fake = _FakeRouter()
    backend = route.RouteBackend(
        runner=fake,
        repo_root=repo_root,
        toolchain=ToolchainPaths(
            kicad_cli=Path("kicad-cli"),
            kipython=Path("kipython"),
            freerouting_jars=(Path("test-router.jar"),),
        ),
    )
    monkeypatch.setattr(route, "_backend_factory", lambda _project: backend)
    return fake
