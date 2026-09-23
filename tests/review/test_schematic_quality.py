from pathlib import Path
from shutil import copy2

from pcb_copilot.review.checks import current_checks
from pcb_copilot.review.schematic_quality import check_schematic_sheets


def test_hierarchical_quality_covers_child_sheets(tmp_path):
    source = Path('projects/tms-v3')
    for schematic in source.glob('*.kicad_sch'):
        copy2(schematic, tmp_path / schematic.name)

    result = check_schematic_sheets(tmp_path / 'tms-v3.kicad_sch')

    assert result.passed
    assert '7 sheet(s)' in result.detail
    assert any('controller-and-telemetry' in warning for warning in result.advisories)


def test_missing_child_title_blocks_hierarchical_quality(tmp_path):
    source = Path('projects/tms-v3')
    for schematic in source.glob('*.kicad_sch'):
        copy2(schematic, tmp_path / schematic.name)
    child = tmp_path / 'power-and-protection.kicad_sch'
    child.write_text(child.read_text(encoding='utf-8').replace(
        '(title "TMS V3 — Power")', '(title "")', 1,
    ), encoding='utf-8')

    result = check_schematic_sheets(tmp_path / 'tms-v3.kicad_sch')

    assert not result.passed
    assert 'power-and-protection.kicad_sch' in result.detail


def test_review_registry_uses_hierarchical_quality_check():
    quality = next(check for check in current_checks() if check.check_id == 'schematic_quality')

    assert quality.scope.proves == 'all referenced sheets have title/revision and acceptable density'
