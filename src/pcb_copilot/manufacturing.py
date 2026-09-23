"""Checked native fabrication and assembly exports."""

from __future__ import annotations

import csv
import math
import re
import subprocess
from pathlib import Path

from kicad_claude.adapters import sch_io

from pcb_copilot.models import Project
from pcb_copilot.toolchain import discover_toolchain


def _run(command):
    run = subprocess.run([str(item) for item in command], capture_output=True,
                         text=True, encoding='utf-8', errors='replace', timeout=180)
    if run.returncode:
        raise RuntimeError(f'export failed: {run.stderr or run.stdout}')
    return run.stdout.strip()


def _property(node, name):
    for prop in sch_io.find_children(node, 'property'):
        if len(prop) >= 3 and str(prop[1]) == name:
            return str(prop[2])
    return ''


def write_bom(pcb: Path, output: Path) -> set[str]:
    groups = {}
    for footprint in sch_io.find_children(sch_io.parse_file(pcb), 'footprint'):
        reference = _property(footprint, 'Reference')
        attributes = sch_io.find_child(footprint, 'attr') or []
        excluded = {'exclude_from_bom', 'dnp'} & {str(value) for value in attributes[1:]}
        if not reference or excluded:
            continue
        # Test points, fiducials and mounting holes are board features.
        prefix = re.match(r'[A-Za-z]+', reference)
        if prefix and prefix.group() in {'TP', 'FID', 'H', 'MH', 'LOGO', 'REF'}:
            continue
        lcsc = next((_property(footprint, key).strip() for key in
                     ('LCSC Part', 'LCSC', 'LCSC Part #', 'JLCPCB', 'JLCPCB Part')
                     if _property(footprint, key).strip()), '')
        key = (_property(footprint, 'Value'), str(footprint[1]), lcsc)
        groups.setdefault(key, []).append(reference)
    if not groups:
        raise ValueError('board has no orderable BOM parts')
    with output.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (value, footprint, lcsc), refs in sorted(groups.items()):
            writer.writerow([value, ','.join(sorted(refs)), footprint, lcsc])
    return {reference for refs in groups.values() for reference in refs}


def export_manufacturing(project: Project, output: Path) -> dict:
    if project.manifest.manufacturing.profile not in {'jlcpcb', 'jlcpcb_2layer_default'}:
        raise ValueError(f'unsupported manufacturing profile: {project.manifest.manufacturing.profile}')
    board = sch_io.parse_file(project.pcb_path)
    copper = [str(layer[1]) for layer in (sch_io.find_child(board, 'layers') or [])[1:]
              if len(layer) > 1 and str(layer[1]).endswith('.Cu')]
    if set(copper) != {'F.Cu', 'B.Cu'}:
        raise ValueError(f'manufacturing profile requires exactly two copper layers: {copper}')
    toolchain = discover_toolchain(Path(__file__).resolve().parents[2])
    cli = toolchain.kicad_cli
    version = _run([cli, '--version'])
    output.mkdir()
    gerbers = output / 'gerbers'
    drills = output / 'drill'
    gerbers.mkdir()
    drills.mkdir()
    layers = ('F.Cu', 'B.Cu', 'F.Mask', 'B.Mask', 'F.Paste', 'B.Paste',
              'F.Silkscreen', 'B.Silkscreen', 'Edge.Cuts')
    _run([cli, 'pcb', 'export', 'gerbers', '--layers', ','.join(layers),
          '--no-protel-ext', '--check-zones', '--output', str(gerbers) + '/', project.pcb_path])
    for layer in layers:
        path = gerbers / f'{project.pcb_path.stem}-{layer.replace(".", "_")}.gbr'
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f'missing Gerber layer: {layer}')
    _run([cli, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
          '--excellon-separate-th', '--output', str(drills) + '/', project.pcb_path])
    if not any(path.stat().st_size for path in drills.glob('*.drl')):
        raise RuntimeError('drill export produced no Excellon file')
    positions = output / 'positions.csv'
    _run([cli, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
          '--side', 'both', '--exclude-dnp', '-o', positions, project.pcb_path])
    if not positions.is_file():
        raise RuntimeError('position export produced no file')
    with positions.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not {'Ref', 'PosX', 'PosY', 'Side', 'Rot'} <= rows[0].keys():
        raise RuntimeError('position export is empty or malformed')
    bom_refs = write_bom(project.pcb_path, output / 'bom.csv')
    positioned = set()
    with (output / 'cpl.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for row in rows:
            if row['Ref'] not in bom_refs:
                continue
            coordinates = [float(row[key]) for key in ('PosX', 'PosY', 'Rot')]
            if (not all(math.isfinite(value) for value in coordinates)
                    or row['Side'].lower() not in {'top', 'bottom'} or row['Ref'] in positioned):
                raise RuntimeError(f'invalid placement row: {row["Ref"]}')
            positioned.add(row['Ref'])
            writer.writerow([row['Ref'], coordinates[0], coordinates[1],
                             row['Side'].capitalize(), coordinates[2]])
    (output / 'ASSEMBLY.md').write_text(
        'Positions use the native KiCad coordinate origin, shared with the Gerber export.\n'
        'Review component rotation, bottom-side orientation and any blank LCSC fields\n'
        'in the assembler preview before placing an order.\n', encoding='utf-8')
    return {'kicad': version, 'manufacturing_profile': 'jlcpcb'}
