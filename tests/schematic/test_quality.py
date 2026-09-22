import importlib
import sys

import pytest

from pcb_copilot.schematic.quality import analyse_schematic


def test_quality_reads_utf8_independent_of_locale(tmp_path):
    schematic = tmp_path / "unicode.kicad_sch"
    schematic.write_text(
        '(kicad_sch (paper "A4") (title_block (title "압력 센서") (rev "A")))',
        encoding="utf-8",
    )

    metrics = analyse_schematic(schematic)

    assert metrics.title_complete


@pytest.mark.parametrize(
    ("board", "components", "power", "junctions", "minimum_drawn_ratio"),
    [
        ("baro-bmp390", 10, 21, 6, 0.8),
        ("imu-icm42688", 10, 19, 4, 0.75),
        ("gnss-neom9n", 24, 33, 8, 0.7),
        ("tms-v3", 66, 72, 0, 0),
    ],
)
def test_current_schematic_metrics_match_baseline(
    repo_root, board, components, power, junctions, minimum_drawn_ratio,
):
    metrics = analyse_schematic(repo_root / "projects" / board / f"{board}.kicad_sch")

    assert metrics.component_count == components
    assert metrics.power_symbol_count == power
    assert metrics.junction_count == junctions
    if minimum_drawn_ratio:
        assert metrics.drawn_connection_ratio >= minimum_drawn_ratio
    else:
        assert metrics.drawn_connection_ratio == 0


def test_only_tms_fails_current_density_rule(repo_root):
    sys.path.insert(0, str(repo_root / "scripts"))
    checker = importlib.import_module("check_schematic_quality")
    results = {}
    for board in ("baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"):
        schematic = repo_root / "projects" / board / f"{board}.kicad_sch"
        blocking, _advisory, _stats = checker.check(schematic, schematic.parent)
        results[board] = any("documented limit" in finding for finding in blocking)

    assert results == {
        "baro-bmp390": False,
        "imu-icm42688": False,
        "gnss-neom9n": False,
        "tms-v3": True,
    }


def test_legacy_analyse_delegates_to_portable_metrics(repo_root):
    sys.path.insert(0, str(repo_root / "scripts"))
    checker = importlib.import_module("check_schematic_quality")
    schematic = repo_root / "projects/baro-bmp390/baro-bmp390.kicad_sch"

    legacy = checker.analyse(schematic)
    metrics = analyse_schematic(schematic)

    assert legacy["components"] == metrics.component_count
    assert legacy["has_title_block"] == metrics.title_complete
