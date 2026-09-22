"""Preserve each accepted board's component identity and complete pin contract."""

import copy
import json
from collections import Counter

import pytest
from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import kicad_to_mcp_xy, round_mm

from pcb_copilot.schematic.io import load_schematic_intent
from pcb_copilot.schematic.models import validate_component_pins
from pcb_copilot.schematic.preview import schematic_files

BOARDS = ('baro-bmp390', 'imu-icm42688', 'gnss-neom9n', 'tms-v3')


def _assert_accepted_parity(intent, source, baseline):
    sources = source if isinstance(source, tuple) else (source,)
    actual = {
        ed.get_symbol_property(symbol, 'Reference'): (symbol, tree)
        for tree in sources
        for symbol in ed.iter_instance_symbols(tree)
        if not ed.get_symbol_property(symbol, 'Reference').startswith('#PWR')
    }
    assert {component.ref for component in intent.components} == set(actual)

    # Some legacy netmaps include power assertions; physical connectivity is
    # compared consistently, while flags remain in the component/pin inventory.
    physical_nets = {
        ref: pins for ref, pins in baseline['nets'].items()
        if pins and not ref.startswith('#')
    }
    block_sheets = {block.id: block.sheet for block in intent.blocks}
    sheet_titles = {sheet.id: sheet.title for sheet in intent.sheets}

    def net_name(component, connection):
        sheet = block_sheets[component.block]
        if (len(intent.sheets) > 1 and sheet != intent.sheets[0].id
                and connection.style in {'label', 'wire'}):
            return f'{sheet_titles[sheet]}/{connection.net}'
        return connection.net

    intent_nets = {
        component.ref: {pin: net_name(component, connection)
                        for pin, connection in component.pins.items()}
        for component in intent.components
        if component.pins and not component.ref.startswith('#')
    }
    assert intent_nets == physical_nets

    disconnected_positions = Counter()
    for component in intent.components:
        symbol, tree = actual[component.ref]
        assert component.value == ed.get_symbol_property(symbol, 'Value'), component.ref
        assert component.footprint == (ed.get_symbol_property(symbol, 'Footprint') or '~'), component.ref
        assert component.symbol == str(ed.find_child(symbol, 'lib_id')[1]), component.ref
        pins = ed.list_pins_for_symbol(tree, component.ref)
        pin_positions = {
            pin['number']: tuple(round_mm(float(value)) for value in pin['position_mm'])
            for pin in pins
        }
        assert component.pin_inventory == frozenset(pin_positions), component.ref
        validate_component_pins(component, set(pin_positions))
        for disconnected in component.no_connects:
            disconnected_positions[pin_positions[disconnected.pin]] += 1

    # Netmap extraction intentionally omits NCs. Compare the accepted KiCad
    # markers with real pin endpoints using the shared coordinate converter.
    accepted_positions = Counter()
    for tree in sources:
        for marker in ed.find_children(tree, 'no_connect'):
            at = ed.find_child(marker, 'at')
            point = kicad_to_mcp_xy(float(at[1]), float(at[2]), ed.page_height_mm(tree))
            accepted_positions[tuple(round_mm(value) for value in point)] += 1
    assert disconnected_positions == accepted_positions


@pytest.fixture(scope='module')
def accepted_boards():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / 'projects'
    return {
        board: (
            load_schematic_intent(root / board / 'schematic-intent.yaml'),
            tuple(sch_io.parse_file(path) for path in schematic_files(root / board / f'{board}.kicad_sch')),
            json.loads((root / board / 'netmap.json').read_text(encoding='utf-8')),
        )
        for board in BOARDS
    }


@pytest.mark.parametrize('board', BOARDS)
def test_board_intent_preserves_accepted_design(board, accepted_boards):
    _assert_accepted_parity(*accepted_boards[board])


@pytest.mark.parametrize('fault', ('value', 'footprint', 'symbol', 'net', 'inventory', 'no-connect'))
def test_parity_rejects_transcription_faults(fault, accepted_boards):
    intent, source, baseline = accepted_boards['baro-bmp390']
    if fault == 'no-connect':
        source = (copy.deepcopy(source[0]),)
        marker = ed.find_children(source[0], 'no_connect')[0]
        ed.find_child(marker, 'at')[1] += 2.54
    else:
        components = list(intent.components)
        index = next(i for i, component in enumerate(components) if component.pins)
        component = components[index]
        if fault == 'net':
            pins = dict(component.pins)
            pin = next(iter(pins))
            pins[pin] = pins[pin].model_copy(update={'net': 'TRANSCRIPTION_FAULT'})
            update = {'pins': pins}
        elif fault == 'inventory':
            update = {'pin_inventory': frozenset({'999'})}
        else:
            update = {fault: 'TRANSCRIPTION_FAULT'}
        components[index] = component.model_copy(update=update)
        intent = intent.model_copy(update={'components': tuple(components)})
    with pytest.raises(AssertionError):
        _assert_accepted_parity(intent, source, baseline)
