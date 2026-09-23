import csv

import pytest

from pcb_copilot.manufacturing import export_manufacturing, write_bom
from pcb_copilot.project import load_project


def test_two_layer_profile_rejects_inner_copper(project_copy, tmp_path):
    project = load_project(project_copy)
    text = project.pcb_path.read_text(encoding='utf-8')
    text = text.replace('(layers', '(layers (2 "In1.Cu" signal)', 1)
    project.pcb_path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match='exactly two copper'):
        export_manufacturing(project, tmp_path / 'output')


def test_bom_excludes_dnp_and_board_features_and_preserves_lcsc(tmp_path):
    pcb = tmp_path / 'test.kicad_pcb'
    pcb.write_text('''(kicad_pcb
      (footprint "R:R" (property "Reference" "R1") (property "Value" "10k") (property "LCSC Part #" "C123"))
      (footprint "R:R" (property "Reference" "R2") (property "Value" "10k") (attr smd dnp))
      (footprint "Mount:H" (property "Reference" "H1")))''')
    output = tmp_path / 'bom.csv'
    write_bom(pcb, output)
    with output.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]['Designator'] == 'R1'
    assert rows[0]['LCSC Part #'] == 'C123'


@pytest.mark.slow
def test_native_manufacturing_has_complete_layers_and_drill_files(project_copy, tmp_path):
    output = tmp_path / 'manufacturing-test-only'
    export_manufacturing(load_project(project_copy), output)
    assert all((output / 'gerbers' / f'baro-bmp390-{layer}.gbr').stat().st_size
               for layer in ('F_Cu', 'B_Cu', 'F_Mask', 'B_Mask', 'Edge_Cuts'))
    assert list((output / 'drill').glob('*.drl'))
    with (output / 'bom.csv').open(newline='') as stream:
        refs = {ref for row in csv.DictReader(stream) for ref in row['Designator'].split(',')}
    with (output / 'cpl.csv').open(newline='') as stream:
        positions = list(csv.DictReader(stream))
    assert positions
    assert {row['Designator'] for row in positions} <= refs
