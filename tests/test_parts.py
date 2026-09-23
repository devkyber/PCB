import json

import pytest
from kicad_claude.adapters import sch_io

from pcb_copilot.parts import import_part, lookup_part
from pcb_copilot.project import load_project
from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.evidence.models import EvidenceRole, TrustTier


def downloaded(_url):
    return json.dumps({'success': True, 'result': {
        'lcsc': {'number': 'C123'}, 'dataStr': {'head': {'c_para': {
            'Supplier Part': 'C123', 'Manufacturer Part': 'EXACT-PART',
            'Manufacturer': 'Fixture', 'package': 'SOT-23',
        }}},
    }}).encode()


def conversion(_cad, lcsc, libs):
    libs.mkdir(exist_ok=True)
    name = 'lcsc_' + lcsc
    symbol = libs / (name + '.kicad_sym')
    symbol.write_text('(kicad_symbol_lib (version 20231120) (generator test) (symbol "PART"))')
    directory = libs / (name + '.pretty')
    directory.mkdir()
    footprint = directory / 'PACKAGE.kicad_mod'
    footprint.write_text('(footprint "PACKAGE" (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))')
    return {'symbol_path': symbol, 'footprint_path': footprint,
            'symbol_name': 'PART', 'footprint_name': 'PACKAGE', 'pin_count': 1, 'warnings': []}


def test_lookup_requires_exact_supplier_identity():
    metadata, _, _ = lookup_part('c123', downloader=downloaded)
    assert metadata['manufacturer_part'] == 'EXACT-PART'
    with pytest.raises(ValueError, match='match'):
        lookup_part('C124', downloader=downloaded)
    with pytest.raises(ValueError, match='C-number'):
        lookup_part('../C123', downloader=downloaded)


@pytest.mark.parametrize('suffix', ['.pretty', '.3dshapes'])
def test_import_preserves_existing_assets_without_symbol(project_copy, tree_hash, suffix):
    project = load_project(project_copy)
    directory = project.root / 'libs' / ('lcsc_C123' + suffix)
    directory.mkdir()
    (directory / 'existing').write_bytes(b'original user asset')
    before = tree_hash(project.root)
    with pytest.raises(ValueError, match='preserved'):
        import_part(project, 'C123', 'EXACT-PART', downloader=downloaded, converter=conversion)
    assert tree_hash(project.root) == before


@pytest.mark.parametrize('board_lcsc', ['', 'C124'])
def test_stale_board_sourcing_identity_blocks_physical_parity(board_lcsc):
    from pcb_copilot.review.checks import compare_physical_parts
    parts = {'R1': {'value': '10k', 'footprint': 'R:R', 'lcsc': 'C123'}}
    board = {'R1': {'value': '10k', 'lib_id': 'R:R', 'lcsc': board_lcsc}}
    assert compare_physical_parts(parts, board) == ['R1: schematic/PCB LCSC sourcing identity differs']


def test_import_registers_assets_and_exact_provenance_without_changing_cad(project_copy):
    project = load_project(project_copy)
    protected = {path: path.read_bytes() for path in project.root.rglob('*')
                 if path.is_file() and ('libs' in path.parts or path.suffix in {'.kicad_pcb', '.kicad_sch'})}
    result = import_part(project, 'C123', 'EXACT-PART', downloader=downloaded, converter=conversion)
    assert result['symbol'] == 'lcsc_C123:PART'
    assert result['footprint'] == 'lcsc_C123:PACKAGE'
    for path, payload in protected.items():
        assert path.read_bytes() == payload
    for name in ('fp-lib-table', 'sym-lib-table'):
        table = sch_io.parse_file(project.root / name)
        assert any(sch_io.find_child(item, 'name')[1] == 'lcsc_C123'
                   for item in sch_io.find_children(table, 'lib'))
    record = next(item for item in load_evidence_index(project.evidence_index_path).records
                  if item.id == result['evidence_id'])
    assert record.roles == {EvidenceRole.CAD_LIBRARY}
    assert record.trust_tier == TrustTier.SUPPLIER
    assert (project.evidence_index_path.parent / record.path).read_bytes() == downloaded('')


def test_mismatch_and_failed_conversion_leave_project_unchanged(project_copy, tree_hash):
    project = load_project(project_copy)
    before = tree_hash(project.root)
    with pytest.raises(ValueError, match='identity mismatch'):
        import_part(project, 'C123', 'WRONG', downloader=downloaded, converter=conversion)
    assert tree_hash(project.root) == before

    def failed(cad, lcsc, libs):
        conversion(cad, lcsc, libs)
        raise RuntimeError('conversion failed')

    with pytest.raises(RuntimeError, match='conversion failed'):
        import_part(project, 'C123', 'EXACT-PART', downloader=downloaded, converter=failed)
    assert tree_hash(project.root) == before


def test_project_symbol_registration_and_lcsc_survive_schematic_generation(project_copy):
    import shutil

    from kicad_claude.adapters import sch_editor
    from pcb_copilot.drafts import create_draft
    from pcb_copilot.models import DraftKind
    from pcb_copilot.parts import _register
    from pcb_copilot.schematic.io import load_schematic_intent
    from pcb_copilot.schematic.render import render_schematic_draft

    project = load_project(project_copy)
    shutil.copy2(project.root / 'libs/jlcpcb.kicad_sym',
                 project.root / 'libs/lcsc_C5124834.kicad_sym')
    _register(project.root, 'lcsc_C5124834', symbols=True)
    intent = load_schematic_intent(project.root / 'schematic-intent.yaml')
    components = tuple(component.model_copy(update={
        'symbol': component.symbol.replace('jlcpcb:', 'lcsc_C5124834:'), 'lcsc': 'C5124834',
    }) if component.ref == 'U1' else component for component in intent.components)
    intent = intent.model_copy(update={'components': components})
    schematic = render_schematic_draft(project, intent, create_draft(project, DraftKind.SCHEMATIC))
    instance = sch_editor.find_symbol_by_reference(sch_io.parse_file(schematic), 'U1')
    assert sch_editor.get_symbol_property(instance, 'LCSC Part') == 'C5124834'
