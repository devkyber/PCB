import xml.etree.ElementTree as ET

import pytest

from pcb_copilot.evidence.commands import inspect_reference_pair
from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.evidence.references import inspect_eagle_pair, reference_search_plan
from pcb_copilot.project import load_project


def sources(repo_root):
    root = repo_root / 'projects/baro-bmp390/evidence/files'
    return root / 'BMP390_Adafruit_20BMP390.sch', root / 'BMP390_Adafruit_20BMP390.brd'


def test_search_plan_distinguishes_schematic_and_layout_without_claiming_search():
    result = reference_search_plan('BMP390')
    assert result['status'] == 'queries_only_not_searched'
    assert {'manufacturer_schematic', 'manufacturer_layout', 'open_hardware_schematic',
            'open_hardware_layout', 'layout_guidance'} == set(result['queries'])


def test_real_reference_schematic_matches_board(repo_root):
    schematic, board = sources(repo_root)
    result = inspect_eagle_pair(schematic, board)
    assert result['mismatches'] == []
    assert result['compared_pad_count'] > 20
    assert result['board']['elements']['IC1']['package'] == 'BMP388'
    assert result['board']['copper_layers'] == [1, 16]
    assert result['board']['routed_wire_count'] > 0
    assert result['review_required']


def test_changed_board_pad_net_fails_pair_comparison(repo_root, tmp_path):
    schematic, board = sources(repo_root)
    tree = ET.parse(board)
    signals = tree.getroot().find('drawing/board/signals')
    source = next(s for s in signals if s.find('contactref') is not None)
    destination = next(s for s in signals if s is not source)
    contact = source.find('contactref')
    source.remove(contact)
    destination.append(contact)
    changed = tmp_path / 'changed.brd'
    tree.write(changed, encoding='utf-8')
    assert inspect_eagle_pair(schematic, changed)['mismatches']


def test_schematic_cannot_count_as_board(repo_root):
    schematic, _board = sources(repo_root)
    with pytest.raises(ValueError, match='board'):
        inspect_eagle_pair(schematic, schematic)


def test_empty_pair_cannot_claim_success(tmp_path):
    schematic = tmp_path / 'empty.sch'
    board = tmp_path / 'empty.brd'
    schematic.write_text('<eagle><drawing><schematic/></drawing></eagle>')
    board.write_text('<eagle><drawing><board/></drawing></eagle>')
    with pytest.raises(ValueError, match='no connected physical pads'):
        inspect_eagle_pair(schematic, board)


def test_malformed_xml_has_actionable_error(repo_root, tmp_path):
    _schematic, board = sources(repo_root)
    broken = tmp_path / 'broken.sch'
    broken.write_text('<eagle><drawing>')
    with pytest.raises(ValueError, match='invalid Eagle XML'):
        inspect_eagle_pair(broken, board)


def test_empty_pad_mapping_is_rejected(repo_root, tmp_path):
    schematic, board = sources(repo_root)
    tree = ET.parse(schematic)
    for connect in tree.getroot().findall('.//connect'):
        connect.set('pad', '')
    changed = tmp_path / 'empty-pads.sch'
    tree.write(changed, encoding='utf-8')
    with pytest.raises(ValueError, match='empty physical pad mapping'):
        inspect_eagle_pair(changed, board)


def test_indexed_pair_rejects_modified_archive(project_copy):
    project = load_project(project_copy)
    records = load_evidence_index(project.evidence_index_path).records
    schematic = next(r for r in records if r.path.endswith('.sch'))
    board = next(r for r in records if r.path.endswith('.brd'))
    assert inspect_reference_pair(project, schematic.id, board.id)['mismatches'] == []
    with (project.evidence_index_path.parent / board.path).open('ab') as stream:
        stream.write(b'\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        inspect_reference_pair(project, schematic.id, board.id)
