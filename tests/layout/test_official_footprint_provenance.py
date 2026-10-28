import hashlib
import json
import os
from datetime import date

import pytest

from pcb_copilot.evidence.archive import archive_document
from pcb_copilot.evidence.index import load_evidence_index, save_evidence_index
from pcb_copilot.evidence.models import EvidenceRole, TrustTier
from pcb_copilot.layout.footprints import resolve_footprint, verify_pin_pad_map
from pcb_copilot.layout.official_footprint_provenance import OFFICIAL_COPY_DESCRIPTION
from pcb_copilot.project import load_project


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_setup(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'project.yaml').write_text(
        'schema_version: 1\nname: test\nlifecycle: DRAFT\n'
        'design:\n  schematic: test.kicad_sch\n  pcb: test.kicad_pcb\n  netmap: netmap.json\n'
        'evidence:\n  index: evidence/index.yaml\nmanufacturing:\n  profile: test\n', encoding='utf-8')
    (root / 'test.kicad_sch').write_text(
        '(kicad_sch (symbol (lib_id "Official:Part") (unit 1) (property "Reference" "U1") '
        '(property "Footprint" "Official:Part") (property "MPN" "EXACT-PART")))', encoding='utf-8')
    (root / 'fp-lib-table').write_text(
        '(fp_lib_table (lib (name "Official") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/Official.pretty") (options "") '
        f'(descr "{OFFICIAL_COPY_DESCRIPTION}")))', encoding='utf-8')
    project = load_project(root)
    local = root / 'libs/Official.pretty/Part.kicad_mod'
    upstream = root / 'libs/upstream/Part.kicad_mod'
    model = root / 'libs/models/Part.step'
    source_model = root / 'libs/upstream/models/Part.step'
    for path in (local, upstream, model, source_model):
        path.parent.mkdir(parents=True, exist_ok=True)
    original_uri = '${KICAD10_3DMODEL_DIR}/Test.3dshapes/Part.step'
    local_uri = '${KIPRJMOD}/libs/models/Part.step'
    text = ('(footprint "Part" (layer "F.Cu") '
            '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")) '
            '(fp_rect (start -1 -1) (end 1 1) (layer "F.CrtYd")) '
            f'(model "{original_uri}" (offset (xyz 0 0 0))))')
    upstream.write_bytes(text.encode())
    local.write_bytes(text.replace(original_uri, local_uri).encode())
    model.write_bytes(b'ISO-10303-21;\nexact archived source model\nEND-ISO-10303-21;')
    source_model.write_bytes(model.read_bytes())
    source = archive_document(project, 'EXACT-PART', 'https://manufacturer.test/drawing.pdf',
                              {'footprint_drawing'}, b'%PDF-1.7\nexact-part manufacturer drawing',
                              date(2026, 10, 29))
    record = {
        'symbol': 'Official:Part', 'source_symbol': 'Device:Part',
        'source_symbol_library_sha256': 'a' * 64,
        'footprint': 'Official:Part', 'source_footprint': 'Test:Part',
        'upstream_path': 'libs/upstream/Part.kicad_mod', 'upstream_sha256': digest(upstream),
        'upstream_url': 'https://gitlab.com/kicad/libraries/kicad-footprints/-/blob/master/Test.pretty/Part.kicad_mod',
        'local_path': 'libs/Official.pretty/Part.kicad_mod', 'local_sha256': digest(local),
        'changes': ['Only model URI rewritten to project-local exact model bytes'],
        'mpn': 'EXACT-PART', 'pad_functions': {'1': 'signal'},
        'models': [{'source': '/installed/KiCad/models/Part.step',
                    'path': 'libs/models/Part.step', 'sha256': digest(model),
                    'upstream_path': 'libs/upstream/models/Part.step',
                    'upstream_sha256': digest(model), 'upstream_uri': original_uri, 'local_uri': local_uri}],
        'manufacturer_evidence_ids': [source.id], 'manufacturer_locations': ['Manufacturer drawing p1'],
        'physical_fit_qualified': False,
    }
    data = {'schema_version': 1, 'distribution': 'Installed official KiCad 10.0.6 libraries',
            'upstream_version': '10.0.6', 'author_review': 'Test author; no human signoff',
            'source': 'https://gitlab.com/kicad/libraries', 'records': [record]}
    manifest = root / 'libs/PROVENANCE.json'
    manifest.write_text(json.dumps(data), encoding='utf-8')
    return project, local, upstream, model, manifest, data


def test_exact_official_copy_and_model_uri_replacement_have_scoped_provenance(tmp_path):
    project, local, _, _, _, _ = receipt_setup(tmp_path)
    before = local.read_bytes()
    candidate = resolve_footprint(project, 'U1', 'Official:Part')
    assert candidate.fidelity == 'real'
    assert candidate.evidence_id.startswith('sha256:')
    assert 'physical fit unqualified' in candidate.source
    assert verify_pin_pad_map(candidate, {'1'}) == []
    assert local.read_bytes() == before


@pytest.mark.parametrize('fault', [
    'missing_receipt', 'malformed_json', 'duplicate_json_key', 'unknown_field', 'unknown_record_field',
    'wrong_version', 'missing_version', 'nonofficial_origin', 'local_hash', 'upstream_hash',
    'local_geometry', 'local_courtyard', 'local_model_transform', 'source_changed', 'model_changed',
    'upstream_model_hash', 'model_uri', 'missing_model', 'wrong_pad', 'missing_mpn', 'wrong_mpn',
    'missing_native_mpn', 'manufacturer_evidence', 'physical_qualification', 'duplicate_record',
    'source_escape', 'model_escape', 'upstream_model_escape', 'local_escape', 'model_uri_injection',
    'evidence_changed', 'wrong_evidence_identity', 'wrong_evidence_role', 'untrusted_evidence',
    'same_file_model_source', 'upstream_model_changed',
])
def test_stale_malformed_or_unbound_official_receipts_block(tmp_path, fault):
    project, local, upstream, model, manifest, data = receipt_setup(tmp_path)
    record = data['records'][0]
    if fault == 'missing_receipt':
        manifest.unlink()
    elif fault == 'malformed_json':
        manifest.write_text('{bad JSON', encoding='utf-8')
    elif fault == 'duplicate_json_key':
        manifest.write_text(manifest.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
    else:
        if fault == 'unknown_field': data['unreviewed_extension'] = True
        if fault == 'unknown_record_field': record['permit_courtyard_changes'] = True
        if fault == 'wrong_version': data['schema_version'] = True
        if fault == 'missing_version': data['upstream_version'] = ''
        if fault == 'nonofficial_origin': record['upstream_url'] = record['upstream_url'].replace('gitlab.com', 'attacker.test')
        if fault == 'local_hash': record['local_sha256'] = '0' * 64
        if fault == 'upstream_hash': record['upstream_sha256'] = '0' * 64
        if fault in {'local_geometry', 'local_courtyard', 'local_model_transform'}:
            before, after = {'local_geometry': ('(size 1 1)', '(size 2 2)'),
                             'local_courtyard': ('(end 1 1)', '(end 2 2)'),
                             'local_model_transform': ('(xyz 0 0 0)', '(xyz 1 0 0)')}[fault]
            local.write_bytes(local.read_bytes().replace(before.encode(), after.encode()))
            record['local_sha256'] = digest(local)  # Updated receipt cannot authorize a geometry edit.
        if fault == 'source_changed': upstream.write_bytes(upstream.read_bytes() + b'\n')
        if fault == 'model_changed': model.write_bytes(model.read_bytes() + b'changed')
        if fault == 'upstream_model_hash': record['models'][0]['upstream_sha256'] = '0' * 64
        if fault == 'model_uri': record['models'][0]['upstream_uri'] = 'other-model.step'
        if fault == 'missing_model': record['models'] = []
        if fault == 'wrong_pad': record['pad_functions'] = {'2': 'signal'}
        if fault == 'missing_mpn': record['mpn'] = ''
        if fault == 'wrong_mpn': record['mpn'] = 'OTHER-PART'
        if fault == 'missing_native_mpn': project.schematic_path.write_bytes(project.schematic_path.read_bytes().replace(b'(property "MPN" "EXACT-PART")', b''))
        if fault == 'manufacturer_evidence': record['manufacturer_evidence_ids'] = []
        if fault == 'physical_qualification': record['physical_fit_qualified'] = True
        if fault == 'duplicate_record': data['records'].append(dict(record))
        if fault == 'source_escape': record['upstream_path'] = '../Part.kicad_mod'
        if fault == 'model_escape': record['models'][0]['path'] = '../Part.step'
        if fault == 'upstream_model_escape': record['models'][0]['upstream_path'] = '../Part.step'
        if fault == 'same_file_model_source': record['models'][0]['upstream_path'] = record['models'][0]['path']
        if fault == 'upstream_model_changed':
            (project.root / record['models'][0]['upstream_path']).write_bytes(b'changed original model')
        if fault == 'local_escape': record['local_path'] = '../Part.kicad_mod'
        if fault == 'model_uri_injection':
            record['models'][0]['path'] = 'libs/models/Part.step" (pad "2" smd rect)'
            record['models'][0]['local_uri'] = '${KIPRJMOD}/' + record['models'][0]['path']
        if fault in {'evidence_changed', 'wrong_evidence_identity', 'wrong_evidence_role', 'untrusted_evidence'}:
            index = load_evidence_index(project.evidence_index_path)
            if fault == 'evidence_changed':
                (project.evidence_index_path.parent / index.records[0].path).write_bytes(b'changed source')
            else:
                update = {'wrong_evidence_identity': {'part_numbers': frozenset({'OTHER-PART'})},
                          'wrong_evidence_role': {'roles': frozenset({EvidenceRole.CAD_LIBRARY})},
                          'untrusted_evidence': {'trust_tier': TrustTier.SUPPLIER}}[fault]
                updated = index.records[0].model_copy(update=update)
                save_evidence_index(index.model_copy(update={'records': (updated,)}), project.evidence_index_path)
        manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        resolve_footprint(project, 'U1', 'Official:Part')


def test_fabricated_mounting_feature_exemption_cannot_cover_a_purchased_part(tmp_path):
    project, local, upstream, _, manifest, data = receipt_setup(tmp_path)
    record = data['records'][0]
    text = '(footprint "Part" (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask")))'
    local.write_bytes(text.encode())
    upstream.write_bytes(text.encode())
    record.update(local_sha256=digest(local), upstream_sha256=digest(upstream), models=[],
                  fabricated_only=True, mpn='', manufacturer_evidence_ids=[], pad_functions={})
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='mounting features'):
        resolve_footprint(project, 'U1', 'Official:Part')
    project.schematic_path.write_bytes(project.schematic_path.read_bytes().replace(b'"U1"', b'"H1"'))
    candidate = resolve_footprint(project, 'H1', 'Official:Part')
    assert candidate.fidelity == 'real' and candidate.evidence_id is None


@pytest.mark.parametrize('target', ['upstream', 'model', 'manifest'])
def test_archive_and_receipt_symlinks_cannot_escape_project(tmp_path, target):
    project, _, upstream, model, manifest, _ = receipt_setup(tmp_path)
    path = {'upstream': upstream, 'model': model, 'manifest': manifest}[target]
    outside = tmp_path / path.name
    outside.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip('symlink creation is unavailable on this host')
    with pytest.raises(ValueError, match='escapes'):
        resolve_footprint(project, 'U1', 'Official:Part')


@pytest.mark.parametrize('link_kind', ['symlink', 'hardlink'])
def test_independent_model_archive_cannot_alias_the_local_model(tmp_path, link_kind):
    project, _, _, model, _, data = receipt_setup(tmp_path)
    source = project.root / data['records'][0]['models'][0]['upstream_path']
    source.unlink()
    try:
        if link_kind == 'symlink':
            source.symlink_to(model)
        else:
            os.link(model, source)
    except OSError:
        pytest.skip(f'{link_kind} creation is unavailable on this host')
    with pytest.raises(ValueError, match='must be distinct'):
        resolve_footprint(project, 'U1', 'Official:Part')


def multiunit_symbol(unit, *, mpn='EXACT-PART', footprint='Official:Part', library='Official:Part'):
    unit_node = f'(unit {unit})' if unit is not None else ''
    return (f'(symbol (lib_id "{library}") {unit_node} (property "Reference" "U1") '
            f'(property "Footprint" "{footprint}") (property "MPN" "{mpn}"))')


def test_consistent_distinct_units_resolve_as_one_physical_part(tmp_path):
    project, _, _, _, _, _ = receipt_setup(tmp_path)
    project.schematic_path.write_text(
        '(kicad_sch ' + multiunit_symbol(1) + multiunit_symbol(2) + ')', encoding='utf-8')
    assert resolve_footprint(project, 'U1', 'Official:Part').fidelity == 'real'


@pytest.mark.parametrize('fault', ['mpn', 'footprint', 'library', 'duplicate_unit',
                                  'missing_unit', 'zero_unit', 'negative_unit', 'fractional_unit'])
def test_conflicting_or_duplicated_multiunit_parts_block(tmp_path, fault):
    project, _, _, _, _, _ = receipt_setup(tmp_path)
    unit = {'duplicate_unit': 1, 'missing_unit': None, 'zero_unit': 0,
            'negative_unit': -1, 'fractional_unit': 1.5}.get(fault, 2)
    other = multiunit_symbol(unit, mpn='OTHER-PART' if fault == 'mpn' else 'EXACT-PART',
                             footprint='Other:Part' if fault == 'footprint' else 'Official:Part',
                             library='Other:Symbol' if fault == 'library' else 'Official:Part')
    project.schematic_path.write_text('(kicad_sch ' + multiunit_symbol(1) + other + ')', encoding='utf-8')
    with pytest.raises(ValueError):
        resolve_footprint(project, 'U1', 'Official:Part')
