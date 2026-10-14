import hashlib
from datetime import date

import pytest
import yaml

from pcb_copilot.evidence.archive import archive_document
from pcb_copilot.evidence.index import load_evidence_index, save_evidence_index
from pcb_copilot.evidence.models import EvidenceRole, TrustTier
from pcb_copilot.layout.footprint_provenance import DRAWING_DERIVED_DESCRIPTION
from pcb_copilot.layout.footprints import resolve_footprint, verify_pin_pad_map
from pcb_copilot.project import load_project


def setup_receipt(project_copy):
    p = load_project(project_copy)
    library = project_copy / 'libs/drawing.pretty'
    library.mkdir()
    path = library / 'Part.kicad_mod'
    path.write_text('(footprint "Part" (pad "1" smd rect (at 0 0) '
                    '(size 1 1) (layers "F.Cu")))')
    source = archive_document(p, 'EXACT-PART', 'https://manufacturer.test/drawing.pdf',
                              {EvidenceRole.FOOTPRINT_DRAWING}, b'%PDF-1.7\nmanufacturer drawing',
                              date(2026, 10, 14))
    manifest = project_copy / 'libs/footprint-provenance.yaml'
    record = {'path': 'libs/drawing.pretty/Part.kicad_mod',
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'part_numbers': ['EXACT-PART'], 'evidence_ids': [source.id],
              'pad_functions': {'1': 'signal'}, 'author': 'Test author',
              'reviewed_on': '2026-10-14', 'derived_from': 'Manufacturer p1',
              'limitations': 'Physical fit remains unqualified', 'owner_signoff': False}
    manifest.write_text(yaml.safe_dump({'schema_version': 1, 'records': [record]}))
    (project_copy / 'fp-lib-table').write_text(
        '(fp_lib_table (version 7) (lib (name "drawing") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/drawing.pretty") (options "") '
        f'(descr "{DRAWING_DERIVED_DESCRIPTION}")))')
    return p, path, manifest, record, p.evidence_index_path.parent / source.path


def test_source_bound_author_drawing_resolves_without_claiming_physical_fit(project_copy):
    p, _, _, _, _ = setup_receipt(project_copy)
    candidate = resolve_footprint(p, 'U1', 'drawing:Part')
    assert candidate.fidelity == 'real'
    assert candidate.evidence_id is not None
    assert 'physical fit unqualified' in candidate.source
    assert verify_pin_pad_map(candidate, {'1'}) == []


@pytest.mark.parametrize('fault', ['missing_receipt', 'footprint_changed', 'source_changed',
                                  'wrong_part', 'missing_pad', 'owner_signoff', 'duplicate',
                                  'untrusted_source', 'wrong_source_role', 'invalid_date'])
def test_unbound_or_false_provenance_is_rejected(project_copy, fault):
    p, path, manifest, record, source_path = setup_receipt(project_copy)
    if fault == 'missing_receipt':
        manifest.unlink()
    elif fault == 'footprint_changed':
        path.write_text(path.read_text() + '\n')
    elif fault == 'source_changed':
        source_path.write_bytes(b'%PDF-1.7\ntampered')
    elif fault in {'untrusted_source', 'wrong_source_role'}:
        index = load_evidence_index(p.evidence_index_path)
        updates = ({'trust_tier': TrustTier.SUPPLIER} if fault == 'untrusted_source'
                   else {'roles': {EvidenceRole.INTEGRATION_MANUAL}})
        records = tuple(r.model_copy(update=updates) if r.id == record['evidence_ids'][0]
                        else r for r in index.records)
        save_evidence_index(index.model_copy(update={'records': records}), p.evidence_index_path)
    else:
        if fault == 'wrong_part': record['part_numbers'] = ['OTHER-PART']
        if fault == 'missing_pad': record['pad_functions'] = {}
        if fault == 'owner_signoff': record['owner_signoff'] = True
        if fault == 'invalid_date': record['reviewed_on'] = 'undated'
        records = [record, record] if fault == 'duplicate' else [record]
        manifest.write_text(yaml.safe_dump({'schema_version': 1, 'records': records}))
    with pytest.raises(ValueError):
        resolve_footprint(p, 'U1', 'drawing:Part')
