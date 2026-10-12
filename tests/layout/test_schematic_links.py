import subprocess
import xml.etree.ElementTree as ET
from copy import deepcopy
from types import SimpleNamespace

import pytest
from kicad_claude.adapters import sch_io

from pcb_copilot.layout import update
from pcb_copilot.layout.render import board_pin_nets, native_board, schematic_inventory
from pcb_copilot.layout.schematic_links import (
    bind_missing_links,
    compare_schematic_links,
    component_paths,
)
from pcb_copilot.review import checks
from pcb_copilot.toolchain import discover_toolchain

SHEET = '11111111-1111-4111-8111-111111111111'
UNIT_A = '22222222-2222-4222-8222-222222222222'
UNIT_B = '33333333-3333-4333-8333-333333333333'
PATH = f'/{SHEET}/{UNIT_A}'


@pytest.mark.parametrize('sheet,units,expected', [
    ('/', UNIT_A, [f'/{UNIT_A}']),
    (f'/{SHEET}/', UNIT_A, [PATH]),
    (f'/{SHEET}/', f'{UNIT_A} {UNIT_B} {UNIT_A}', [PATH, f'/{SHEET}/{UNIT_B}']),
])
def test_native_identity_uses_sheet_path_and_each_unit_without_root_uuid(sheet, units, expected):
    comp = ET.fromstring(f'<comp ref="U1"><sheetpath tstamps="{sheet}"/><tstamps>{units}</tstamps></comp>')
    assert component_paths(comp) == expected


@pytest.mark.parametrize('body', ['', '<tstamps>bad</tstamps>',
    '<sheetpath tstamps="/"/><tstamps>bad</tstamps>',
    f'<sheetpath tstamps="/bad/"/><tstamps>{UNIT_A}</tstamps>'])
def test_missing_or_malformed_native_identity_is_never_guessed(body):
    with pytest.raises(ValueError, match='schematic UUID path'):
        component_paths(ET.fromstring(f'<comp ref="U1">{body}</comp>'))


def inventories():
    parts = {'R1': {'footprint': 'Resistor:R', 'value': '10k', 'lcsc': 'C123',
                    'schematic_paths': [PATH], 'pins': {'1', '2'}}}
    footprints = {'R1': {'lib_id': 'Resistor:R', 'value': '10k', 'lcsc': 'C123',
                         'schematic_path': '', 'pads': [['1', 'PWM'], ['2', 'GND']]}}
    return parts, footprints


def board_file(tmp_path):
    pcb = tmp_path / 'candidate.kicad_pcb'
    pcb.write_text('''(kicad_pcb
      (footprint "Resistor:R" (property "Reference" "R1") (property "Value" "10k")
        (uuid "44444444-4444-4444-8444-444444444444") (at 10 20 90)
        (pad "1" smd rect (at 1 0) (size 1 1) (layers "F.Cu")))
      (footprint "Hole:H" (property "Reference" "H1") (at 1 1))
      (segment (start 10 20) (end 30 20) (width 1) (layer "F.Cu") (net 1))
      (via (at 30 20) (size 1) (drill .5) (layers "F.Cu" "B.Cu") (net 1))
      (zone (net 1) (layer "F.Cu")))''', encoding='utf-8')
    return pcb


def without_paths(tree):
    copy = deepcopy(tree)
    for footprint in sch_io.find_children(copy, 'footprint'):
        for path in sch_io.find_children(footprint, 'path'):
            footprint.remove(path)
    return copy


def test_binding_changes_only_missing_metadata_and_is_idempotent(tmp_path):
    pcb = board_file(tmp_path)
    parts, footprints = inventories()
    footprints['H1'] = {'schematic_path': ''}
    before = sch_io.parse_file(pcb)
    assert bind_missing_links(pcb, parts, footprints) == ['R1']
    after = sch_io.parse_file(pcb)
    assert without_paths(after) == before  # Includes every pad, track, via and zone.
    fps = sch_io.find_children(after, 'footprint')
    assert sch_io.find_child(fps[0], 'path')[1] == PATH
    assert sch_io.find_child(fps[1], 'path') is None
    footprints['R1']['schematic_path'] = PATH
    saved = pcb.read_bytes()
    assert bind_missing_links(pcb, parts, footprints) == []
    assert pcb.read_bytes() == saved


def test_link_binding_preserves_native_escaped_notes_and_coordinate_precision(tmp_path):
    pcb = board_file(tmp_path)
    payload = pcb.read_bytes().replace(b'(at 10 20 90)', b'(at 10.123456789 20 90)')
    payload = payload[:-1] + b' (gr_text "note (one)\\nline \\"two\\" and \\\\path"))'
    payload = payload.replace(b'\n', b'\r\n')
    pcb.write_bytes(payload)
    parts, footprints = inventories()
    bind_missing_links(pcb, parts, footprints)
    inserted = f'\r\n\t\t(path "{PATH}")\r\n\t'.encode()
    assert pcb.read_bytes().replace(inserted, b'') == payload


def test_empty_path_is_replaced_without_duplicate_properties(tmp_path):
    pcb = board_file(tmp_path)
    pcb.write_bytes(pcb.read_bytes().replace(b'(at 10 20 90)', b'(at 10 20 90) (path "")'))
    parts, footprints = inventories()
    bind_missing_links(pcb, parts, footprints)
    fp = sch_io.find_children(sch_io.parse_file(pcb), 'footprint')[0]
    assert len(sch_io.find_children(fp, 'path')) == 1
    assert sch_io.find_child(fp, 'path')[1] == PATH


@pytest.mark.parametrize('fault', ['stale', 'duplicate', 'no_identity', 'value', 'footprint', 'lcsc', 'missing'])
def test_ambiguous_identity_refuses_repair_without_writing(tmp_path, fault):
    pcb = board_file(tmp_path)
    parts, footprints = inventories()
    if fault == 'stale':
        footprints['R1']['schematic_path'] = f'/{UNIT_B}'
    elif fault == 'duplicate':
        footprints['R1']['schematic_path'] = PATH
        footprints['H1'] = {'schematic_path': PATH}
    elif fault == 'no_identity':
        parts['R1']['schematic_paths'] = []
    elif fault == 'missing':
        footprints.clear()
    else:
        footprints['R1'][{'footprint': 'lib_id'}.get(fault, fault)] = 'different'
    before = pcb.read_bytes()
    with pytest.raises(ValueError):
        bind_missing_links(pcb, parts, footprints)
    assert pcb.read_bytes() == before


def test_multiunit_footprint_may_keep_an_existing_valid_unit_link():
    parts, footprints = inventories()
    parts['R1']['schematic_paths'].append(f'/{SHEET}/{UNIT_B}')
    footprints['R1']['schematic_path'] = f'/{SHEET}/{UNIT_B}'
    assert not compare_schematic_links(parts, footprints)


def test_electrically_matching_board_still_fails_parity_without_links(monkeypatch):
    parts, footprints = inventories()
    nets = {'PWM': {('R1', '1')}, 'GND': {('R1', '2')}}
    monkeypatch.setattr(checks, '_toolchain', lambda: None)
    monkeypatch.setattr(checks, 'schematic_inventory', lambda *args: (parts, nets))
    monkeypatch.setattr(checks, 'native_board', lambda *args: {'footprints': footprints})
    project = SimpleNamespace(schematic_path=None, pcb_path=None)
    assert checks.check_parity(project, include_links=False)[0]
    passed, detail = checks.check_parity(project)
    assert not passed and 'missing schematic link' in detail
    footprints['R1']['schematic_path'] = PATH
    assert checks.check_parity(project)[0]


def test_circuit_mismatch_prevents_any_link_inference(monkeypatch):
    def mismatch(context, *, include_links):
        assert include_links is False
        return False, 'different pin net'
    monkeypatch.setattr(update, 'check_parity', mismatch)
    monkeypatch.setattr(update, 'bind_missing_links', lambda *args: pytest.fail('unsafe inference'))
    monkeypatch.setattr(update, 'schematic_inventory', lambda *args: pytest.fail('must stop before inference'))
    assert update._bind_candidate_links(SimpleNamespace(), None) == []


@pytest.mark.parametrize('board_members,expected_omitted', [
    ([('R1', '2')], True),
    ([('R1', '1')], False),  # Placeholder is assigned to the wrong pad.
    ([('R1', '2'), ('J1', '1')], False),  # Must not hide a short to another pin.
])
def test_f8_placeholder_ignored_only_for_exact_native_no_connect(board_members, expected_omitted):
    name = 'unconnected-(R1-Pad2)'
    parts = {'R1': {'no_connects': {'2': name}}}
    footprints = {}
    for ref, pin in board_members:
        footprints.setdefault(ref, {'pads': []})['pads'].append([pin, name])
    assert (name not in board_pin_nets(footprints, parts)) == expected_omitted
    assert name in board_pin_nets(footprints)  # No schematic evidence: no waiver.


def test_exported_no_connects_require_explicit_native_evidence(tmp_path, monkeypatch):
    from pcb_copilot.layout import render

    xml = f'''<export><components><comp ref="U1"><value>IC</value><footprint>Package:IC</footprint>
      <libsource lib="L" part="IC"/><sheetpath tstamps="/"/><tstamps>{UNIT_A}</tstamps>
      </comp></components><libparts><libpart lib="L" part="IC"><pins>
      <pin num="1"/><pin num="2"/><pin num="3"/></pins></libpart></libparts><nets>
      <net name="unconnected-(U1-Pad1)"><node ref="U1" pin="1" pintype="input+no_connect"/></net>
      <net name="unconnected-(U1-Pad2)"><node ref="U1" pin="2" pintype="input"/></net>
      <net name="unconnected-(extra)"><node ref="U1" pin="2" pintype="input+no_connect"/>
      <node ref="U1" pin="3" pintype="input+no_connect"/></net></nets></export>'''
    def export(command, **kwargs):
        from pathlib import Path
        Path(command[command.index('-o') + 1]).write_text(xml)
    monkeypatch.setattr(render.subprocess, 'run', export)
    parts, nets = schematic_inventory(SimpleNamespace(kicad_cli='test'), tmp_path / 'test.kicad_sch')
    assert parts['U1']['no_connects'] == {'1': 'unconnected-(U1-Pad1)'}
    assert nets == {'unconnected-(U1-Pad2)': {('U1', '2')},
                    'unconnected-(extra)': {('U1', '2'), ('U1', '3')}}


def test_native_link_repair_preserves_copper_and_survives_kicad_roundtrip(project_copy, kipython, repo_root):
    tools = discover_toolchain(repo_root)
    pcb = project_copy / 'baro-bmp390.kicad_pcb'
    parts, _ = schematic_inventory(tools, project_copy / 'baro-bmp390.kicad_sch')
    tree = sch_io.parse_file(pcb)
    for fp in sch_io.find_children(tree, 'footprint'):
        for path in sch_io.find_children(fp, 'path'):
            fp.remove(path)
    sch_io.write_file(pcb, tree)
    before = native_board(tools, pcb)
    linked = bind_missing_links(pcb, parts, before['footprints'])
    assert set(linked) == set(parts)
    assert without_paths(sch_io.parse_file(pcb)) == tree
    subprocess.run([str(kipython), '-I', '-c',
        'import pcbnew,sys; b=pcbnew.LoadBoard(sys.argv[1]); pcbnew.SaveBoard(sys.argv[1],b,True)', str(pcb)],
        check=True, capture_output=True, text=True, timeout=30)
    after = native_board(tools, pcb)
    assert after['tracks'] == before['tracks'] > 0
    assert after['zones'] == before['zones'] > 0
    assert not compare_schematic_links(parts, after['footprints'])
    for ref in linked:
        assert after['footprints'][ref]['schematic_path'] == parts[ref]['schematic_paths'][0]
