"""Rendered labels must grow away from real pin stubs, not over their pins."""

import subprocess

import pymupdf
import pytest
from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.templates.blank import write_blank_schematic
from kicad_claude.utils.kicad_paths import find_symbol_lib_dirs

from pcb_copilot.schematic.render import LabelPlacer, SymbolPlacer, _LabelEditor
from pcb_copilot.toolchain import discover_toolchain


@pytest.fixture(scope='module')
def direction_preview(tmp_path_factory):
    root = tmp_path_factory.mktemp('label-direction')
    schematic = root / 'directions.kicad_sch'
    write_blank_schematic(schematic)
    tree = sch_io.parse_file(schematic)
    definition = ed.fetch_symbol_def(
        find_symbol_lib_dirs()[0] / 'Connector_Generic.kicad_sym',
        'Conn_02x02_Odd_Even',
    )
    ed.add_symbol(tree, qualified_lib_id='Connector_Generic:Conn_02x02_Odd_Even',
                  reference='J8', value='Direction fixture', x_mm=127, y_mm=127,
                  rotation=0, sym_def_node=definition, project_name='directions',
                  footprint='Connector_PinHeader_2.54mm:PinHeader_2x02_P2.54mm_Vertical')
    symbols = SymbolPlacer(ed, tree)
    symbols.register('J8')
    editor = _LabelEditor()
    labels = LabelPlacer(editor, tree, symbols=symbols)
    anchors = {}
    for pin, name, hierarchical in [
        ('1', 'HIER_LEFT', True), ('2', 'HIER_RIGHT', True),
        ('3', 'LOCAL_LEFT', False), ('4', 'LOCAL_RIGHT', False),
    ]:
        editor.hierarchical = hierarchical
        labels.place('J8', pin, name, *symbols._origin('J8'))
        anchors[name] = labels._segments[-1][1]
    sch_io.write_file(schematic, tree)
    cli = discover_toolchain(root).kicad_cli
    pdf = root / 'directions.pdf'
    subprocess.run([str(cli), 'sch', 'export', 'pdf', '--output', str(pdf),
                    str(schematic)], check=True, capture_output=True, text=True)
    document = pymupdf.open(pdf)
    page = document[0]
    page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(root / 'directions.png')
    rectangles = {name: page.search_for(name) for name in anchors}
    # The A4 blank schematic's physical width gives the PDF coordinate scale.
    scale = page.rect.width / symbols._page_size()[0]
    document.close()
    return schematic, anchors, rectangles, scale


@pytest.mark.slow
@pytest.mark.parametrize('name', ['HIER_LEFT', 'HIER_RIGHT', 'LOCAL_LEFT', 'LOCAL_RIGHT'])
def test_label_pdf_text_extends_outward_from_pin_stub(direction_preview, name):
    _schematic, anchors, rectangles, scale = direction_preview
    assert len(rectangles[name]) == 1
    rect = rectangles[name][0]
    anchor_x = anchors[name][0] * scale
    if name.endswith('LEFT'):
        assert rect.x1 <= anchor_x + 0.5, f'{name} extends back across its pin stub: {rect}'
    else:
        assert rect.x0 >= anchor_x - 0.5, f'{name} extends back across its pin stub: {rect}'


@pytest.mark.slow
def test_label_direction_preserves_real_pin_connectivity(direction_preview):
    from pcb_copilot.schematic.netmap import extract

    schematic, _anchors, _rectangles, _scale = direction_preview
    assert extract(schematic)['nets'] == {'J8': {
        '1': 'HIER_LEFT', '2': 'HIER_RIGHT',
        '3': 'LOCAL_LEFT', '4': 'LOCAL_RIGHT',
    }}
