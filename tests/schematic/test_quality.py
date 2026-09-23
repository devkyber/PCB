
import pytest

from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.schematic.quality import analyse_schematic


def test_quality_reads_utf8_independent_of_locale(tmp_path):
    schematic = tmp_path / "unicode.kicad_sch"
    schematic.write_text(
        '(kicad_sch (paper "A4") (title_block (title "Ã¬â€¢â€¢Ã«Â Â¥ Ã¬â€žÂ¼Ã¬â€žÅ“") (rev "A")))',
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


def test_tms_hierarchy_preserves_components_and_stays_within_page_capacity(repo_root):
    root = repo_root / "projects/tms-v3/tms-v3.kicad_sch"
    sheets = schematic_files(root)
    metrics = [analyse_schematic(path) for path in sheets]

    assert len(sheets) == 7
    assert metrics[0].sheet_count == 7
    assert sum(item.component_count for item in metrics) == 66
    assert sum(item.power_symbol_count for item in metrics) == 72
    assert sum(item.junction_count for item in metrics) == 19
    assert all(item.title_complete for item in metrics)
    assert all(item.component_count <= item.page_capacity for item in metrics)
    # The controller and external-connector sheets remain label-heavy; the
    # hierarchy is an improvement, not a claim of fully human-level drawing.
    assert sum(item.junction_count == 0 for item in metrics[1:]) == 2
