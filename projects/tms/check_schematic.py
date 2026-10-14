"""TMS A2 independent wiring contract, authored from device pin tables.

Run with the workspace Python: .venv/bin/python PATH/check_schematic.py.
This checks every physical pin and every intentional NC, including unplaced
components. It does not qualify analog performance, physical fit or release.
Source locations and limitations are in docs/design/ELECTRICAL_VERIFICATION_A2.md.
"""
from pathlib import Path
from collections import defaultdict
import hashlib, json, re, sys

from kicad_claude.adapters import sch_io as io, sch_editor as ed
from pcb_copilot.schematic.netmap import extract
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.layout.footprints import resolve_footprint
from pcb_copilot.project import load_project

ROOT = Path(__file__).resolve().parent
expected = {}


def node(name, *pins):
    for value in pins:
        ref, pin = value.split('.')
        assert (ref, pin) not in expected, (ref, pin)
        expected[ref, pin] = name


def pair(ref, a, b):
    node(a, ref + '.1')
    node(b, ref + '.2')


# Each node below is an engineering specification, not copied from an export.
node('GND', 'J1.1', 'U2.1', 'U3.2', 'U1.GNDL', 'U1.GNDR', 'U1.GNDA',
     'J2.2', 'J2.5', 'D20.3', 'U4.4', 'U5.2', 'U5.3', 'U5.17',
     'U6.4', 'U10.2', 'J3.3', 'D41.3', 'U7.3', 'U7.4', 'U7.5', 'U8.10', 'U9.7', 'Q1.2')
node('BAT_RAW', 'J1.2', 'D1.2')
node('VBAT', 'D1.1', 'U2.3', 'TP1.1', 'J3.1')
node('EN', 'U2.5')
pair('R1', 'VBAT', 'EN'); pair('R2', 'EN', 'GND')
node('SW', 'U2.2'); node('CB', 'U2.6'); pair('C3', 'CB', 'SW')
pair('L1', 'SW', '+5V'); pair('R5', '+5V', 'FB_TOP')
pair('R3', 'FB_TOP', 'FB'); pair('R4', 'FB', 'GND'); node('FB', 'U2.4')
node('+5V', 'U3.1', 'U3.3', 'JP1.1', 'K1.1', 'D60.1', 'TP2.1')
pair('FB1', '+5V', '+5VA'); pair('D2', 'VBAT', 'GND')
node('+3V3_RF', 'U3.5', 'U8.1', 'U9.14')
node('+3V3', 'U1.3V3L', 'U1.3V3R', 'TP3.1', 'U5.14', 'U5.15', 'U5.16',
     'U7.13', 'U9.1', 'U9.8')
node('+5VA', 'J2.1', 'U4.8', 'U5.1', 'U6.7', 'U7.12', 'U10.5')
node('TEENSY_VIN', 'JP1.2', 'U1.VIN')
for net, refs in {
    'VBAT': 'C1 C2 C11 C12', '+5V': 'C4 C5 C7 C13 C14 C15 C16 C17 C18 C19 C29',
    '+5VA': 'C6 C21 C23 C27 C31 C41 C43', '+3V3': 'C24 C28 C42 C53',
    '+3V3_RF': 'C8 C50 C51 C52 C54', 'TEENSY_VIN': 'C10',
}.items():
    for ref in refs.split(): pair(ref, net, 'GND')
for gpio, ref in [(4, '10'), (5, '11'), (6, '12')]:
    node('LED_' + ref, f'U1.D{gpio}')
    pair('R' + ref, 'LED_' + ref, 'LED_A_' + ref)
    pair('D' + ref, 'GND', 'LED_A_' + ref)
# Bridge: TI OPA2388 D8 and ADS1256 DB28 pin tables.
for sign, channel, inp, out, inv, adc in [('P', '0', '3', '1', '2', '6'),
                                        ('N', '1', '5', '7', '6', '7')]:
    suffix = '20' if sign == 'P' else '21'
    clamp = 'D21' if sign == 'P' else 'D22'
    node('LC_RAW_' + sign, 'J2.' + ('3' if sign == 'P' else '4'),
         'D20.' + ('1' if sign == 'P' else '2'))
    pair('R' + suffix, 'LC_RAW_' + sign, 'LC_FILT_' + sign)
    node('LC_FILT_' + sign, 'U4.' + inp, clamp + '.3')
    pair(clamp, 'GND', '+5VA')
    node('LC_BUF_' + sign, 'U4.' + out, 'U4.' + inv)
    pair('R' + ('22' if sign == 'P' else '23'), 'LC_BUF_' + sign, 'LC_ADC_' + sign)
    node('LC_ADC_' + sign, 'U5.' + adc)
pair('C20', 'LC_FILT_P', 'LC_FILT_N'); pair('C22', 'LC_ADC_P', 'LC_ADC_N')
pair('R30', '+5VA', 'VREF_DIV'); pair('R31', 'VREF_DIV', 'GND')
pair('R32', 'VREF_DIV', 'VREF_FILT'); pair('C30', 'VREF_FILT', 'GND')
node('VREF_FILT', 'U6.3'); node('LC_VREF', 'U6.2', 'U6.6', 'U5.4', 'TP5.1')
for ref in ['C32', 'C33', 'C34']: pair(ref, 'LC_VREF', 'GND')
node('XTAL1', 'U5.19', 'Y1.1'); node('XTAL2', 'U5.18', 'Y1.2')
pair('C25', 'XTAL1', 'GND'); pair('C26', 'XTAL2', 'GND')
# ADC buses: series damping belongs to each source endpoint on the PCB.
for adc, mcu, ref, signal in [('24', '13', 'R24', 'LC_SCK'),
                             ('23', '11', 'R25', 'LC_MOSI'),
                             ('22', '12', 'R26', 'LC_MISO')]:
    node(signal + '_ADC', 'U5.' + adc)
    pair(ref, signal + '_ADC', signal); node(signal, 'U1.D' + mcu)
node('LC_CS_N', 'U5.20', 'U1.D10'); pair('R27', '+3V3', 'LC_CS_N')
node('LC_DRDY_N', 'U5.21', 'U1.D9', 'TP4.1')
# ADS1220 PW16: CLK3, DGND4, AVSS5 stay grounded. AIN0 is pin11.
node('P_RAW', 'J3.2', 'D41.1'); pair('R40', 'P_RAW', 'P_DIV')
pair('R41', 'P_DIV', 'GND'); pair('C40', 'P_DIV', 'GND')
pair('D40', 'GND', '+5VA'); node('P_DIV', 'D40.3', 'U10.3', 'TP6.1')
node('P_BUFFER', 'U10.1', 'U10.4'); pair('R46', 'P_BUFFER', 'P_ADC')
node('P_ADC', 'U7.11'); pair('C44', 'P_ADC', 'GND')
for adc, mcu, ref, signal in [('1', '27', 'R42', 'P_SCK'),
                             ('16', '26', 'R43', 'P_MOSI'),
                             ('15', '1', 'R44', 'P_MISO')]:
    node(signal + '_ADC', 'U7.' + adc)
    pair(ref, signal + '_ADC', signal); node(signal, 'U1.D' + mcu)
node('P_CS_N', 'U7.2', 'U1.D0'); pair('R45', '+3V3', 'P_CS_N')
node('P_DRDY_N', 'U7.14', 'U1.D2', 'TP7.1')
# PJRC Serial3 supports TX14, RX15, CTS19; attachRts(18) is supported.
# Digi names refer to the DCE: DIN/RTS are inputs; DOUT/CTS are outputs.
for gpio, a, b, module, pull, signal in [
    ('14', '2', '13', '3', 'R52', 'XB_TX'),
    ('15', '4', '11', '2', 'R55', 'XB_RX'),
    ('18', '3', '12', '16', 'R53', 'XB_RTS_N'),
    ('19', '5', '10', '12', 'R54', 'XB_CTS_N'),
]:
    node(signal, 'U1.D' + gpio, 'U9.' + a)
    node(signal + '_RF', 'U9.' + b, 'U8.' + module)
    pair(pull, '+3V3', signal)
pair('R50', '+3V3_RF', 'RF_RESET_N'); node('RF_RESET_N', 'U8.5', 'TP8.1')
pair('R51', 'RF_SLEEP_RQ', 'GND'); node('RF_SLEEP_RQ', 'U8.9', 'TP9.1')
# Relay: Hongfa type1 bottom-view numbering; current path has separate return.
node('FIRE_CMD', 'U1.D3'); pair('R60', 'FIRE_CMD', 'GATE')
node('GATE', 'Q1.1'); pair('R61', 'GATE', 'GND')
node('COIL_LOW', 'Q1.3', 'K1.6', 'D60.2', 'TP10.1')
node('IGN_BAT', 'J4.2', 'J5.1'); node('ARM_RETURN', 'J5.2', 'K1.2')
node('IGN_OUT', 'K1.3', 'J6.2'); node('IGN_GND', 'J4.1', 'J6.1')
nc = {
    'U1': {f'D{i}' for i in [7, 8, 16, 17, *range(20, 26), *range(28, 42)]},
    'U3': {'4'}, 'U5': {'5', *map(str, range(8, 14)), *map(str, range(25, 29))},
    'U6': {'1', '5', '8'}, 'U7': set(map(str, range(6, 11))),
    'U8': set('4 6 7 8 11 13 14 15 17 18 19 20'.split()),
    'U9': {'6', '9'}, 'D41': {'2'},
}
expected_nc = {(r, p) for r, pins in nc.items() for p in pins}


def verify(root=ROOT):
    actual = extract(root / 'tms.kicad_sch')['nets']
    actual_pins = {}; actual_nc = set(); sources = {}; annotation_failures = []; polarity_failures = []
    top = io.parse_file(root / 'tms.kicad_sch')
    root_id = io.find_child(top, 'uuid')[1]
    paths = {'tms.kicad_sch': '/' + root_id}
    for sheet in io.find_children(top, 'sheet'):
        fields = {p[1]: p[2] for p in io.find_children(sheet, 'property')}
        paths[fields['Sheetfile']] = '/' + root_id + '/' + io.find_child(sheet, 'uuid')[1]
    for file in schematic_files(root / 'tms.kicad_sch'):
        sources[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        t = io.parse_file(file); height = ed.page_height_mm(t)
        points = {tuple(io.find_child(n, 'at')[1:3]) for n in io.find_children(t, 'no_connect')}
        for n in io.find_children(t, 'symbol'):
            fields = {p[1]: p[2] for p in io.find_children(n, 'property')}; ref = fields['Reference']
            instances = io.find_child(n, 'instances')
            entries = [entry for project in io.find_children(instances, 'project')
                       for entry in io.find_children(project, 'path')] if instances else []
            if not entries or any(entry[1] != paths[file.name] or
                                  io.find_child(entry, 'reference')[1] != ref for entry in entries):
                annotation_failures.append({'reference': ref, 'sheet': file.name})
            if ref.startswith('#'): continue
            assert ref not in actual_pins, f'Duplicate reference {ref}'
            pins = ed.list_pins_for_symbol(t, ref); actual_pins[ref] = {p['number'] for p in pins}
            if ref in {'J1', 'J4', 'J6'}:
                candidate = resolve_footprint(load_project(root), ref, fields['Footprint'])
                footprint = io.parse_file(candidate.path)
                pads = {str(pad[1]): io.find_child(pad, 'at')[1:3]
                        for pad in io.find_children(footprint, 'pad') if str(pad[1])}
                labels = {str(n[2]): io.find_child(n, 'at')[1:3]
                          for n in io.find_children(footprint, 'fp_text') if n[2] in {'+', '-'}}
                names = {p['name']: p['number'] for p in pins}
                for sign in ['+', '-']:
                    if sign not in labels or sign not in names:
                        polarity_failures.append({'reference': ref, 'missing_polarity': sign})
                        continue
                    x, y = labels[sign]
                    nearest = min(pads, key=lambda p: (pads[p][0]-x)**2 + (pads[p][1]-y)**2)
                    if names[sign] != nearest:
                        polarity_failures.append({'reference': ref, 'sign': sign,
                                                  'symbol_pin': names[sign], 'footprint_pad': nearest})
            for p in pins:
                x, y = ed.get_pin_position(t, ref, p['number'])
                if (round(x, 4), round(height-y, 4)) in points: actual_nc.add((ref, p['number']))
    all_actual = {(r, p) for r, pins in actual_pins.items() for p in pins}
    failures = []
    if annotation_failures: failures.append({'incorrect_instance_metadata': annotation_failures})
    if polarity_failures: failures.append({'connector_polarity_mismatch': polarity_failures})
    if all_actual != set(expected) | expected_nc:
        failures.append({'uncovered_or_missing_pins': sorted(all_actual ^ (set(expected) | expected_nc))})
    if actual_nc != expected_nc: failures.append({'NC_difference': sorted(actual_nc ^ expected_nc)})
    groups = defaultdict(set)
    for ref, pins in actual.items():
        for pin, net in pins.items(): groups[net].add((ref, pin))
    intended = defaultdict(set)
    for rp, net in expected.items(): intended[net].add(rp)
    actual_groups = {frozenset(v) for v in groups.values()}
    intended_groups = {frozenset(v) for v in intended.values()}
    if actual_groups != intended_groups:
        failures.append({'unexpected_connections': [sorted(g) for g in actual_groups-intended_groups],
                         'missing_connections': [sorted(g) for g in intended_groups-actual_groups]})
    return {'scope': 'All physical pin membership and explicit NCs; not performance/fit/release',
            'parts': len(actual_pins), 'pins': len(all_actual), 'NCs': len(actual_nc),
            'expected_nodes': len(intended), 'failures': failures, 'source_sha256': sources,
            'author_check': 'Codex', 'owner_signoff': False}


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, indent=2))
    sys.exit(bool(result['failures']))
