"""Sheet-path normalization must never conceal changed electrical groups."""

import copy

import pytest

from pcb_copilot.schematic.models import SchematicIntent


@pytest.fixture
def intent():
    pin_nets = {
        'R1': {'1': 'VBAT_PROT', '2': 'GND'},
        'R2': {'1': 'VBAT_PROT', '2': 'GND'},
        'R3': {'1': 'SENSE/HI', '2': 'GND'},
        'R4': {'1': 'HI', '2': 'GND'},
        '#FLG01': {'1': 'GND'},
    }
    return SchematicIntent.model_validate({
        'schema_version': 1, 'title': 'Netlist comparison', 'revision': 'T1',
        'sheets': [{'id': 'main', 'title': 'Main'}],
        'blocks': [{'id': 'power', 'title': 'Power', 'sheet': 'main', 'flow_order': 0}],
        'components': [
            {'ref': ref, 'value': 'FIXTURE', 'symbol': 'Device:R', 'footprint': '~',
             'block': 'power', 'evidence_part_number': 'FIXTURE',
             'pin_map_evidence_id': None, 'pin_map_review_note': 'Comparison fixture only.',
             'pins': {pin: {'net': net, 'style': 'label'} for pin, net in pins.items()}}
            for ref, pins in pin_nets.items()
        ],
    })


@pytest.fixture
def expected():
    return {
        'R1': {'1': 'VBAT_PROT', '2': 'GND'},
        'R2': {'1': 'VBAT_PROT', '2': 'GND'},
        'R3': {'1': 'SENSE/HI', '2': 'GND'},
        'R4': {'1': 'HI', '2': 'GND'},
    }


@pytest.mark.parametrize('prefix', ('', 'Electronics power and protection/', '/Top/Power/'))
def test_complete_groups_allow_sheet_prefixes(intent, expected, prefix):
    from pcb_copilot.schematic.netlist import normalize_intent_netmap

    extracted = {
        ref: {pin: net if net == 'GND' else prefix + net for pin, net in pins.items()}
        for ref, pins in expected.items()
    }
    before = copy.deepcopy(extracted)
    assert normalize_intent_netmap(intent, extracted) == expected
    assert extracted == before


def test_pseudo_references_are_excluded_on_both_sides(intent, expected):
    from pcb_copilot.schematic.netlist import normalize_intent_netmap

    extracted = {**expected, '#PWR01': {'1': 'GND'}, '#FLG01': {'1': 'GND'}}
    assert normalize_intent_netmap(intent, extracted) == expected


@pytest.mark.parametrize('fault', (
    'split', 'short', 'missing-pin', 'extra-pin', 'missing-component',
    'extra-component', 'renamed', 'false-suffix', 'slash-truncated', 'swapped-groups',
))
def test_changed_groups_or_names_are_rejected(intent, expected, fault):
    from pcb_copilot.schematic.netlist import normalize_intent_netmap

    extracted = copy.deepcopy(expected)
    if fault == 'split':
        extracted['R1']['1'] = 'SheetA/VBAT_PROT'
        extracted['R2']['1'] = 'SheetB/VBAT_PROT'
    elif fault == 'short':
        extracted['R1']['1'] = extracted['R2']['1'] = 'GND'
    elif fault == 'missing-pin':
        del extracted['R1']['1']
    elif fault == 'extra-pin':
        extracted['R1']['3'] = 'GND'
    elif fault == 'missing-component':
        del extracted['R1']
    elif fault == 'extra-component':
        extracted['R99'] = {'1': 'GND'}
    elif fault == 'renamed':
        extracted['R1']['1'] = extracted['R2']['1'] = 'WRONG'
    elif fault == 'false-suffix':
        extracted['R1']['1'] = extracted['R2']['1'] = 'prefixVBAT_PROT'
    elif fault == 'slash-truncated':
        extracted['R3']['1'] = 'Sheet/HI'
    elif fault == 'swapped-groups':
        extracted['R3']['1'], extracted['R4']['1'] = 'HI', 'SENSE/HI'
    with pytest.raises(ValueError):
        normalize_intent_netmap(intent, extracted)
