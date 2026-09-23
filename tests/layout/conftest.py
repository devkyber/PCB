from __future__ import annotations

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
    "characterized_pcb_layout_helpers", REPO_ROOT / "src/pcb_copilot/layout/geometry.py"
)
VALIDATOR = _load_module(
    "characterized_validate_pcb", REPO_ROOT / "src/pcb_copilot/review/placement.py"
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
        if any(value.endswith("stitch_vias_native.py") for value in command):
            assert pcb is not None
            pcb.write_bytes(pcb.read_bytes() + b"\nstitch")
            return SimpleNamespace(returncode=0, stdout="stitched\n", stderr="")
        if any(value.endswith("fix_via_annular_native.py") for value in command):
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
