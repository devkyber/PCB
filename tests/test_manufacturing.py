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


def test_bom_consolidates_one_supplier_part_with_different_connector_labels(tmp_path):
    pcb = tmp_path / 'test.kicad_pcb'
    pcb.write_text('''(kicad_pcb
      (footprint "J:J" (property "Reference" "J10") (property "Value" "Motor")
        (property "MPN" "CONNECTOR") (property "LCSC" "C123"))
      (footprint "J:J" (property "Reference" "J2") (property "Value" "Data")
        (property "MPN" "CONNECTOR") (property "LCSC" "C123")))''')
    output = tmp_path / 'bom.csv'
    assert write_bom(pcb, output) == {'J2', 'J10'}
    with output.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]['Designator'] == 'J2,J10'
    assert rows[0]['Quantity'] == '2'
    assert rows[0]['Comment'] == rows[0]['MPN'] == 'CONNECTOR'


def test_conflicting_supplier_identity_is_not_silently_grouped(tmp_path):
    pcb = tmp_path / 'test.kicad_pcb'
    pcb.write_text('''(kicad_pcb
      (footprint "R:R" (property "Reference" "R1") (property "MPN" "10K") (property "LCSC" "C123"))
      (footprint "R:R" (property "Reference" "R2") (property "MPN" "20K") (property "LCSC" "C123")))''')
    with pytest.raises(ValueError, match='conflicting'):
        write_bom(pcb, tmp_path / 'bom.csv')


def test_centroid_correction_is_invalidated_by_changed_embedded_geometry(project_copy):
    import yaml
    from kicad_claude.adapters import sch_io

    from pcb_copilot.manufacturing import (
        _assembly_plan,
        _property,
        footprint_geometry_digest,
    )

    project = load_project(project_copy)
    board = sch_io.parse_file(project.pcb_path)
    footprints = {_property(fp, 'Reference'): fp for fp in sch_io.find_children(board, 'footprint')}
    fp = next(fp for ref, fp in footprints.items() if ref.startswith('C'))
    config = {'schema_version': 1, 'centroid_offsets': {str(fp[1]): {
        'x_mm': 0, 'y_mm': 0, 'reason': 'test body center',
        'geometry_sha256': footprint_geometry_digest(fp),
    }}}
    (project.root / 'jlcpcb-assembly.yaml').write_text(yaml.safe_dump(config))
    _assembly_plan(project, footprints)
    for shape in sch_io.find_children(fp, 'fp_line') + sch_io.find_children(fp, 'fp_rect'):
        if str((sch_io.find_child(shape, 'layer') or ['', ''])[1]) == 'F.Fab':
            sch_io.find_child(shape, 'start')[1] += 1
            break
    else:
        pytest.fail('fixture has no fabrication line or rectangle')
    with pytest.raises(ValueError, match='geometry changed'):
        _assembly_plan(project, footprints)


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
    assert {row['Designator'] for row in positions} == refs
    assert all(0 <= float(row['Rotation']) < 360 for row in positions)
    import zipfile
    with zipfile.ZipFile(output / 'gerbers.zip') as archive:
        assert archive.testzip() is None
        assert any(name.endswith('.drl') for name in archive.namelist())
        assert sum(name.endswith('.gbr') for name in archive.namelist()) == 9
