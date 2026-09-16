"""Inspect reference CAD without confusing downloaded files with reviewed designs."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


def reference_search_plan(part: str) -> dict:
    part = part.strip()
    if not part:
        raise ValueError('part number must not be blank')
    return {
        'part': part, 'status': 'queries_only_not_searched',
        'queries': {
            'manufacturer_schematic': f'"{part}" manufacturer evaluation board schematic reference design',
            'manufacturer_layout': f'"{part}" manufacturer evaluation board PCB layout CAD Gerber',
            'open_hardware_schematic': f'"{part}" schematic site:github.com (adafruit OR sparkfun OR Seeed-Studio)',
            'open_hardware_layout': f'"{part}" (brd OR kicad_pcb) site:github.com',
            'layout_guidance': f'"{part}" datasheet hardware integration layout guidelines',
        },
        'record_for_each_search': ['query', 'date', 'source URL', 'source owner',
                                   'exact variant/revision', 'outcome including rejection or access failure'],
        'completion': [
            'Search schematic and PCB layout separately; record unavailable results honestly.',
            'Archive native CAD and manufacturer documents with source identity and hashes.',
            'Inspect schematic and copper/layout views, then compare applicability with datasheet and requirements.',
            'Validate matching CAD pairs where supported; record differences and limits of every check.',
        ],
    }


def _root(path: Path, kind: str):
    try:
        root = ET.parse(path).getroot().find(f'drawing/{kind}')
    except ET.ParseError as exc:
        raise ValueError(f'{path.name}: invalid Eagle XML: {exc}') from exc
    if root is None:
        raise ValueError(f'{path.name} is not an Eagle {kind}')
    return root


def _identity(path: Path) -> dict:
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def _assign(mapping, key, net):
    if key in mapping and mapping[key] != net:
        raise ValueError(f'{key} assigned to two nets: {mapping[key]} / {net}')
    mapping[key] = net


def inspect_eagle_pair(schematic: Path, board: Path) -> dict:
    """Compare physical pad membership using the schematic's gate-to-pad map.

    Placement/routing metadata is descriptive; this does not run DRC, solve
    polygon pours, prove routed completion, or validate electrical suitability.
    """
    sch = _root(schematic, 'schematic')
    pcb = _root(board, 'board')
    devices = {}
    for library in sch.findall('libraries/library'):
        for deviceset in library.findall('devicesets/deviceset'):
            for device in deviceset.findall('devices/device'):
                devices[(library.get('name'), deviceset.get('name'), device.get('name'))] = device
    parts = {p.get('name'): p for p in sch.findall('parts/part')}
    expected = {}
    packages = {}
    for ref, part in parts.items():
        key = (part.get('library'), part.get('deviceset'), part.get('device'))
        if key not in devices:
            raise ValueError(f'missing device definition for {ref}')
        device = devices[key]
        if device.get('package'):
            packages[ref] = device.get('package')
    for net in sch.findall('sheets/sheet/nets/net'):
        for pin in net.findall('segment/pinref'):
            ref = pin.get('part')
            part = parts[ref]
            device = devices[(part.get('library'), part.get('deviceset'), part.get('device'))]
            if not device.get('package'):
                continue  # Power/net symbols have no physical pads.
            connects = [c for c in device.findall('connects/connect')
                        if c.get('gate') == pin.get('gate') and c.get('pin') == pin.get('pin')]
            if not connects:
                raise ValueError(f'no physical pad mapping for {ref}.{pin.get("pin")}')
            for connect in connects:
                pads = connect.get('pad', '').split()
                if not pads:
                    raise ValueError(f'empty physical pad mapping for {ref}.{pin.get("pin")}')
                for pad in pads:
                    _assign(expected, (ref, pad), net.get('name'))
    if not expected:
        raise ValueError('schematic has no connected physical pads to compare')
    actual = {}
    signals = pcb.findall('signals/signal')
    for signal in signals:
        for contact in signal.findall('contactref'):
            _assign(actual, (contact.get('element'), contact.get('pad')), signal.get('name'))
    elements = {e.get('name'): dict(e.attrib) for e in pcb.findall('elements/element')}
    mismatches = [
        {'element': ref, 'pad': pad, 'schematic_net': expected.get((ref, pad)),
         'board_net': actual.get((ref, pad))}
        for ref, pad in sorted(expected.keys() | actual.keys())
        if expected.get((ref, pad)) != actual.get((ref, pad))
    ]
    for ref, package in packages.items():
        if ref not in elements or elements[ref].get('package') != package:
            mismatches.append({'element': ref, 'schematic_package': package,
                               'board_package': elements.get(ref, {}).get('package')})
        elif parts[ref].get('value') and parts[ref].get('value') != elements[ref].get('value', ''):
            mismatches.append({'element': ref, 'schematic_value': parts[ref].get('value', ''),
                               'board_value': elements[ref].get('value', '')})
    layers = sorted({int(item.get('layer')) for signal in signals
                     for item in [*signal.findall('wire'), *signal.findall('polygon')]
                     if 1 <= int(item.get('layer')) <= 16})
    return {
        'schematic_source': _identity(schematic), 'board_source': _identity(board),
        'compared_pad_count': len(expected), 'mismatches': mismatches,
        'board': {
            'elements': elements, 'copper_layers': layers,
            'routed_wire_count': sum(len(s.findall('wire')) for s in signals),
            'via_count': sum(len(s.findall('via')) for s in signals),
            'polygons': [{'net': s.get('name'), **p.attrib}
                         for s in signals for p in s.findall('polygon')],
            'design_rules': {p.get('name'): p.get('value')
                             for p in pcb.findall('designrules/param')},
        },
        'review_required': [
            'Confirm exact device variant, source revision and license; filenames are not proof.',
            'Inherited/default schematic values are not compared; only explicit part values are checked.',
            'Compare supply, interfaces, passive values and protection with the device datasheet and our requirements.',
            'Inspect actual copper views: decoupling, return paths, pours, routing, keepouts and mechanical constraints.',
            'Pad membership is not routing completion, DRC, stackup validation, or electrical approval.',
            'Record adopted choices and justified differences in DESIGN_BASIS.md before using this reference.',
        ],
    }
