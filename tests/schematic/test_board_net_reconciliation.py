import json
import shutil

import pytest

from pcb_copilot.drafts import create_draft
from pcb_copilot.layout.constraints import _native
from pcb_copilot.models import DraftKind
from pcb_copilot.project import load_project
from pcb_copilot.schematic import parity
from pcb_copilot.schematic.io import load_schematic_intent
from pcb_copilot.schematic.render import render_schematic_draft
from pcb_copilot.toolchain import discover_toolchain


def test_net_renames_follow_exact_pad_membership():
    schematic = {'Power/VBAT_PROT': {('U4', '1'), ('C15', '1')},
                 'GND': {('U4', '2'), ('C15', '2')}}
    board = {'VBAT_PROT': {('U4', '1'), ('C15', '1')},
             'GND': {('U4', '2'), ('C15', '2')}}

    assert parity.derive_net_renames(schematic, board) == {'VBAT_PROT': 'Power/VBAT_PROT'}


def test_net_renames_reject_changed_circuit():
    schematic = {'Power/VBAT_PROT': {('U4', '1'), ('C15', '1')}}
    board = {'VBAT_PROT': {('U4', '1'), ('C15', '2')}}

    with pytest.raises(ValueError, match='different pin membership'):
        parity.derive_net_renames(schematic, board)


def test_board_net_rename_changes_only_net_fields():
    before = b'(segment (net "VBAT_PROT") (start 1 2) (end 3 4))\n(property "Value" "VBAT_PROT")\n'

    after = parity.rewrite_board_net_names(before, {'VBAT_PROT': 'Power/VBAT_PROT'})

    assert after == b'(segment (net "Power/VBAT_PROT") (start 1 2) (end 3 4))\n(property "Value" "VBAT_PROT")\n'


def test_project_net_classes_follow_renamed_nets_without_changing_rules(repo_root):
    source = (repo_root / 'projects/tms-v3/tms-v3.kicad_pro').read_bytes()
    names = {
        'VBAT_PROT': 'Power/VBAT_PROT',
        'IGN_GND': 'Connectors and test/IGN_GND',
        'IGN_BATT+': 'Connectors and test/IGN_BATT+',
    }

    revised = parity.reconcile_project_net_classes(source, names)

    before = json.loads(source)
    after = json.loads(revised)
    added = after['net_settings']['netclass_patterns'][
        len(before['net_settings']['netclass_patterns']):
    ]
    assert added == [
        {'netclass': 'HighCurrent', 'pattern': new}
        for new in names.values()
        if {'netclass': 'HighCurrent', 'pattern': new}
        not in before['net_settings']['netclass_patterns']
    ]
    after['net_settings']['netclass_patterns'] = before['net_settings']['netclass_patterns']
    assert after == before


def test_kicad_board_membership_reads_real_tms_pads(repo_root):
    board = repo_root / 'projects/tms-v3/tms-v3.kicad_pcb'

    groups = parity.read_board_net_groups(board)

    assert len(groups) == 47
    assert groups['Power/VBAT_PROT'] == {('C15', '1'), ('D3', '2'), ('U4', '1')}


@pytest.mark.slow
def test_tms_reconciles_names_without_changing_current_copper(repo_root, tmp_path):
    root = tmp_path / 'tms-v3'
    shutil.copytree(repo_root / 'projects/tms-v3', root,
                    ignore=shutil.ignore_patterns('.pcb-copilot'))
    project = load_project(root)
    current = project.pcb_path.read_bytes()
    qualified = [name for name in parity.read_board_net_groups(project.pcb_path)
                 if '/' in name]
    assert len(qualified) == 26
    legacy_names = {name: name.rsplit('/', 1)[1] for name in qualified}
    project.pcb_path.write_bytes(parity.rewrite_board_net_names(current, legacy_names))
    before = project.pcb_path.read_bytes()
    kipython = discover_toolchain(repo_root).kipython
    before_rules = _native(project.pcb_path, kipython)['nets']
    intent = load_schematic_intent(root / 'schematic-intent.yaml')
    render_schematic_draft(project, intent, create_draft(project, DraftKind.SCHEMATIC))
    draft_root = next((root / '.pcb-copilot/drafts').iterdir())

    candidate, project_settings, names = parity.reconcile_board_net_names(project, draft_root)

    assert len(names) == 26
    assert names['VBAT_PROT'] == 'Power/VBAT_PROT'
    assert parity.candidate_board_parity(project, draft_root) is None
    assert project.pcb_path.read_bytes() == before
    assert candidate == current
    assert project_settings == (draft_root / project.pcb_path.with_suffix('.kicad_pro').name).read_bytes()
    after_rules = _native(draft_root / project.pcb_path.name, kipython)['nets']
    assert all(after_rules[new] == before_rules[old] for old, new in names.items())
    assert candidate.count(b'\n\t(segment\n') == before.count(b'\n\t(segment\n')
    assert candidate.count(b'\n\t(via\n') == before.count(b'\n\t(via\n')
