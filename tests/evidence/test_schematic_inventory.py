from datetime import date
from types import SimpleNamespace

import pytest
import yaml

from pcb_copilot.evidence.archive import archive_document
from pcb_copilot.evidence.commands import verify_schematic_evidence
from pcb_copilot.evidence.models import EvidenceRole
from pcb_copilot.evidence.schematic_inventory import schematic_parts
from pcb_copilot.review.checks import check_datasheets


def project(tmp_path, symbols):
    root = tmp_path / 'board.kicad_sch'
    root.write_text('(kicad_sch (version 20250114) (generator "test") ' + symbols + ')')
    board = tmp_path / 'board.kicad_pcb'
    board.write_text('(kicad_pcb)')
    index = tmp_path / 'evidence/index.yaml'
    index.parent.mkdir()
    index.write_text(yaml.safe_dump({'schema_version': 1, 'records': []}))
    return SimpleNamespace(root=tmp_path, schematic_path=root, pcb_path=board,
                           evidence_index_path=index)


def symbol(ref, value, mpn='', on_board='yes'):
    return (f'(symbol (on_board {on_board}) (property "Reference" "{ref}") '
            f'(property "Value" "{value}") (property "MPN" "{mpn}"))')


def test_unplaced_ic_is_not_hidden_by_empty_board(tmp_path):
    p = project(tmp_path, symbol('U1', 'LDO', 'EXACT-LDO'))
    passed, detail = check_datasheets(p)
    assert not passed
    assert 'U1 (EXACT-LDO) has no datasheet' in detail


def test_full_audit_includes_passives_but_not_fabricated_probe(tmp_path):
    p = project(tmp_path, symbol('R1', '10k', 'EXACT-R') + symbol('TP1', 'Probe'))
    assert not schematic_parts(p)[0].requires_datasheet
    parts = schematic_parts(p, include_passives=True)
    assert parts[0].requires_datasheet
    assert not parts[1].requires_datasheet
    result = verify_schematic_evidence(p)
    assert result.exit_code == 1
    assert any('EXACT-R' in failure for failure in result.machine_failures)
    assert not any('TP1' in failure for failure in result.machine_failures)


def test_empty_schematic_cannot_claim_coverage(tmp_path):
    p = project(tmp_path, symbol('#PWR01', '+3V3'))
    with pytest.raises(ValueError, match='no physical parts'):
        schematic_parts(p)


def test_old_part_datasheet_at_same_reference_does_not_cover_replacement(tmp_path):
    p = project(tmp_path, symbol('U1', 'New regulator', 'NEW-ORDER'))
    archive_document(p, 'OLD-ORDER', 'https://manufacturer.test/old.pdf',
                     {EvidenceRole.DATASHEET}, b'%PDF-1.7\nold manufacturer sheet',
                     date(2026, 10, 14), component_refs={'U1'})
    result = verify_schematic_evidence(p)
    assert result.exit_code == 1
    assert any('NEW-ORDER' in failure and 'reference-only' in failure
               for failure in result.machine_failures)


def test_exact_selected_order_is_covered_without_reference_alias(tmp_path):
    p = project(tmp_path, symbol('R1', '10k', 'EXACT-ORDER'))
    archive_document(p, 'EXACT-ORDER', 'https://manufacturer.test/exact.pdf',
                     {EvidenceRole.DATASHEET}, b'%PDF-1.7\nexact manufacturer sheet',
                     date(2026, 10, 14))
    assert verify_schematic_evidence(p).exit_code == 0


def test_duplicate_reference_and_nonphysical_parts(tmp_path):
    p = project(tmp_path, symbol('U1', 'LDO') + symbol('U1', 'LDO'))
    with pytest.raises(ValueError, match='duplicate'):
        schematic_parts(p)
    p.schematic_path.write_text('(kicad_sch ' + symbol('U1', 'LDO', on_board='no') +
                                symbol('J1', 'XBee socket', 'XB3') + ')')
    parts = schematic_parts(p)
    assert len(parts) == 1 and parts[0].reference == 'J1'
    assert parts[0].is_module and parts[0].requires_datasheet
