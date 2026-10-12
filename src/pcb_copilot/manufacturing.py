"""Checked native fabrication and assembly exports."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
import zipfile
from pathlib import Path

import yaml
from kicad_claude.adapters import sch_io

from pcb_copilot.models import Project
from pcb_copilot.toolchain import discover_toolchain


def _run(command):
    run = subprocess.run([str(item) for item in command], capture_output=True,
                         text=True, encoding='utf-8', errors='replace', timeout=180, check=False)
    if run.returncode:
        raise RuntimeError(f'export failed: {run.stderr or run.stdout}')
    return run.stdout.strip()


def _property(node, name):
    for prop in sch_io.find_children(node, 'property'):
        if len(prop) >= 3 and str(prop[1]) == name:
            return str(prop[2])
    return ''


def footprint_geometry_digest(footprint) -> str:
    """Bind an export-only centroid correction to embedded body geometry."""
    shapes = []
    for node in footprint:
        if not isinstance(node, list) or not str(node[0]).startswith('fp_'):
            continue
        layer = sch_io.find_child(node, 'layer') or []
        if len(layer) < 2 or str(layer[1]) not in {'F.Fab', 'B.Fab'}:
            continue
        coordinates = {key: (sch_io.find_child(node, key) or [])[1:]
                       for key in ('start', 'end', 'center', 'mid', 'pts')
                       if sch_io.find_child(node, key)}
        if coordinates:
            shapes.append([str(node[0]), coordinates])
    if not shapes:
        raise ValueError('centroid correction requires embedded fabrication geometry')
    entries = sorted(json.dumps(item, sort_keys=True, default=str) for item in shapes)
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest()


def _assembly_plan(project: Project, footprints: dict) -> dict:
    path = project.root / 'jlcpcb-assembly.yaml'
    if not path.exists():
        return {'manual_fit': {}, 'centroid_offsets': {}}
    plan = yaml.safe_load(path.read_text(encoding='utf-8'))
    if (not isinstance(plan, dict) or plan.get('schema_version') not in {1, 2}
            or set(plan) - {'schema_version', 'manual_fit', 'centroid_offsets',
                           'rotation_offsets', 'model_contracts', 'supplier_review'}):
        raise ValueError('invalid jlcpcb-assembly.yaml schema')
    for field in ('manual_fit', 'centroid_offsets', 'rotation_offsets', 'model_contracts'):
        plan.setdefault(field, {})
        if not isinstance(plan[field], dict):
            raise ValueError(f'{field} must be a mapping')  # noqa: TRY004 -- invalid external configuration
    for ref, item in plan['manual_fit'].items():
        if (not isinstance(item, dict) or set(item) != {'footprint', 'reason'}
                or not isinstance(item['reason'], str) or not item['reason'].strip()
                or ref not in footprints or item['footprint'] != str(footprints[ref][1])):
            raise ValueError(f'invalid or stale manual-fit definition: {ref}')
    for name, item in plan['centroid_offsets'].items():
        if (not isinstance(item, dict)
                or set(item) != {'x_mm', 'y_mm', 'geometry_sha256', 'reason'}
                or not isinstance(item['reason'], str) or not item['reason'].strip()):
            raise ValueError(f'invalid centroid correction: {name}')
        for key in ('x_mm', 'y_mm'):
            if isinstance(item[key], bool) or not isinstance(item[key], (int, float)) or not math.isfinite(item[key]):
                raise ValueError(f'invalid centroid offset {key}: {name}')
        matching = [fp for fp in footprints.values() if str(fp[1]) == name]
        if not matching:
            raise ValueError(f'centroid correction has no matching footprint: {name}')
        if any(footprint_geometry_digest(fp) != item['geometry_sha256'] for fp in matching):
            raise ValueError(f'centroid correction geometry changed: {name}')
    from pcb_copilot.assembly import lcsc, rotation_rule
    for field in ('rotation_offsets', 'model_contracts'):
        stale = set(plan[field]) - {lcsc(fp) for fp in footprints.values()}
        if stale:
            raise ValueError(f'{field} contains parts absent from PCB: {sorted(stale)}')
    for fp in footprints.values():
        rotation_rule(project, fp, plan)
    return plan


def _natural_ref(ref: str):
    return tuple(int(part) if part.isdigit() else part for part in re.split(r'(\d+)', ref))


def write_bom(pcb: Path, output: Path, *, excluded_refs=()) -> set[str]:
    groups = {}
    seen = set()
    identities = {}
    for footprint in sch_io.find_children(sch_io.parse_file(pcb), 'footprint'):
        reference = _property(footprint, 'Reference')
        attributes = sch_io.find_child(footprint, 'attr') or []
        excluded = {'exclude_from_bom', 'dnp'} & {str(value) for value in attributes[1:]}
        if not reference or excluded or reference in excluded_refs:
            continue
        # Test points, fiducials and mounting holes are board features.
        prefix = re.match(r'[A-Za-z]+', reference)
        if prefix and prefix.group() in {'TP', 'FID', 'H', 'MH', 'LOGO', 'REF'}:
            continue
        if reference in seen:
            raise ValueError(f'duplicate BOM reference: {reference}')
        seen.add(reference)
        lcsc = next((_property(footprint, key).strip() for key in
                     ('LCSC Part', 'LCSC', 'LCSC Part #', 'JLCPCB', 'JLCPCB Part')
                     if _property(footprint, key).strip()), '')
        value, name, mpn = _property(footprint, 'Value'), str(footprint[1]), _property(footprint, 'MPN').strip()
        if lcsc:
            if not re.fullmatch(r'C\d+', lcsc):
                raise ValueError(f'invalid LCSC part number for {reference}: {lcsc}')
            identity = (name, mpn)
            if lcsc in identities and identities[lcsc] != identity:
                raise ValueError(f'conflicting footprint/MPN for {lcsc}')
            identities[lcsc] = identity
        key = (name, lcsc, mpn, '' if lcsc else value)
        group = groups.setdefault(key, {'refs': [], 'values': set()})
        group['refs'].append(reference)
        group['values'].add(value)
    if not groups:
        raise ValueError('board has no orderable BOM parts')
    with output.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Quantity', 'MPN'])
        for (footprint, lcsc, mpn, _), group in sorted(groups.items()):
            refs = sorted(group['refs'], key=_natural_ref)
            values = group['values']
            if len(values) > 1 and not mpn:
                raise ValueError(f'conflicting values without an exact MPN: {refs}')
            comment = next(iter(values)) if len(values) == 1 else mpn
            # JLCPCB's importer accepts at most 200 designators per row.
            for start in range(0, len(refs), 200):
                batch = refs[start:start + 200]
                writer.writerow([comment, ','.join(batch), footprint, lcsc, len(batch), mpn])
    return seen


def export_manufacturing(project: Project, output: Path) -> dict:
    from pcb_copilot.assembly import audit_assembly, corrected_position, supplier_review
    if project.manifest.manufacturing.profile not in {'jlcpcb', 'jlcpcb_2layer_default'}:
        raise ValueError(f'unsupported manufacturing profile: {project.manifest.manufacturing.profile}')
    board = sch_io.parse_file(project.pcb_path)
    footprint_nodes = sch_io.find_children(board, 'footprint')
    footprints = {_property(fp, 'Reference'): fp for fp in footprint_nodes}
    if len(footprints) != len(footprint_nodes):
        raise ValueError('duplicate footprint references on PCB')
    plan = _assembly_plan(project, footprints)
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
          '--no-protel-ext', '--subtract-soldermask', '--check-zones',
          '--output', str(gerbers) + '/', project.pcb_path])
    for layer in layers:
        path = gerbers / f'{project.pcb_path.stem}-{layer.replace(".", "_")}.gbr'
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f'missing Gerber layer: {layer}')
    _run([cli, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
          '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal',
          '--excellon-oval-format', 'alternate', '--excellon-separate-th',
          '--output', str(drills) + '/', project.pcb_path])
    if not any(path.stat().st_size for path in drills.glob('*.drl')):
        raise RuntimeError('drill export produced no Excellon file')
    pad_types = {str(pad[2]) for fp in footprint_nodes for pad in sch_io.find_children(fp, 'pad')}
    for kind, required in (('PTH', 'thru_hole' in pad_types or bool(sch_io.find_children(board, 'via'))),
                           ('NPTH', 'np_thru_hole' in pad_types)):
        drill = drills / f'{project.pcb_path.stem}-{kind}.drl'
        if required and (not drill.is_file() or not re.search(r'^X[-\d.]+Y[-\d.]+', drill.read_text(), re.MULTILINE)):
            raise RuntimeError(f'missing or empty {kind} drill data')
    positions = output / 'positions.csv'
    _run([cli, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
          '--side', 'both', '--exclude-dnp', '-o', positions, project.pcb_path])
    if not positions.is_file():
        raise RuntimeError('position export produced no file')
    with positions.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not {'Ref', 'PosX', 'PosY', 'Side', 'Rot'} <= rows[0].keys():
        raise RuntimeError('position export is empty or malformed')
    bom_refs = write_bom(project.pcb_path, output / 'bom.csv', excluded_refs=plan['manual_fit'])
    positioned = set()
    corrections = []
    rotations = []
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
            offset = plan['centroid_offsets'].get(str(footprints[row['Ref']][1]))
            native_angle = coordinates[2]
            x, y, angle, rule = corrected_position(
                project, footprints[row['Ref']], plan, *coordinates, row['Side'].lower())
            if offset:
                corrections.append({'reference': row['Ref'], 'offset': offset})
            rotations.append({'reference': row['Ref'], 'native_angle': native_angle,
                              'jlcpcb_angle': angle, 'offset_degrees': rule['degrees'] if rule else None,
                              'basis': rule['basis'] if rule else 'missing'})
            writer.writerow([row['Ref'], f'{x:.6f}', f'{y:.6f}', row['Side'].capitalize(), f'{angle:.6f}'])
    if positioned != bom_refs:
        raise RuntimeError(f'BOM/CPL mismatch; parts without positions: {sorted(bom_refs - positioned)}')
    with (output / 'bom.csv').open(encoding='utf-8', newline='') as stream:
        bom = list(csv.DictReader(stream))
    archive = output / 'gerbers.zip'
    upload_files = sorted(gerbers.glob('*.gbr')) + sorted(drills.glob('*.drl'))
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in upload_files:
            zipped.write(path, path.name)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() or set(zipped.namelist()) != {p.name for p in upload_files}:
            raise RuntimeError('Gerber/drill ZIP validation failed')
    audit = audit_assembly(project, footprints, bom_refs, plan)
    supplier = supplier_review(project, output, plan)
    (output / 'assembly-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    with (output / 'rotation-audit.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rotations[0]))
        writer.writeheader()
        writer.writerows(rotations)
    # Assembly drawings and 3D review are separate from fabrication Gerber uploads.
    for side in ('F', 'B'):
        drawing = output / f'assembly-{side}.svg'
        _run([cli, 'pcb', 'export', 'svg', '--page-size-mode', '2', '--mode-single',
              '--sketch-pads-on-fab-layers', '--crossout-DNP-footprints-on-fab-layers',
              '--layers', f'{side}.Fab,{side}.Silkscreen,Edge.Cuts',
              '--output', drawing, project.pcb_path])
        if not drawing.is_file():
            raise RuntimeError(f'missing {side} assembly drawing')
    model_logs = {}
    if audit['passed']:
        model_logs['step'] = _run([cli, 'pcb', 'export', 'step', '--subst-models', '--no-dnp',
                                  '--output', output / 'assembly.step', project.pcb_path])
        model_logs['render'] = _run([cli, 'pcb', 'render', '--width', '1400', '--height', '1600',
                                    '--side', 'top', '--background', 'opaque', '--quality', 'basic',
                                    '--output', output / 'assembly-top.png', project.pcb_path])
        for name in ('assembly.step', 'assembly-top.png'):
            if not (output / name).is_file() or not (output / name).stat().st_size:
                raise RuntimeError(f'missing assembly model output: {name}')
    else:
        model_logs['skipped'] = 'Unresolved local assembly checks; do not imply a complete 3D assembly.'
    (output / 'model-export.json').write_text(json.dumps(model_logs, indent=2) + '\n', encoding='utf-8')
    assembly = {'components': len(bom_refs), 'bom_rows': len(bom),
                'manual_fit': plan['manual_fit'], 'centroid_corrections': corrections,
                'rotation_corrections': rotations, 'local_checks_passed': audit['passed'],
                'supplier_review': supplier,
                'passed': audit['passed'] and supplier['passed'],
                'unsourced': [r['Designator'] for r in bom if not r['LCSC Part #']],
                'supplier_rotation_verified': supplier['passed'], 'supplier_stock_verified': False}
    (output / 'assembly.json').write_text(json.dumps(assembly, indent=2) + '\n', encoding='utf-8')
    (output / 'ASSEMBLY.md').write_text(
        '# JLCPCB upload files\n\n'
        'Upload gerbers.zip in the PCB/Gerber slot, bom.csv in the BOM slot, '
        'and cpl.csv in the CPL slot. The ZIP contains both Gerbers and Excellon drills.\n\n'
        f'{len(bom_refs)} components; {len(bom)} grouped BOM rows. '
        'BOM and CPL designators match exactly. Quantities are per board.\n\n'
        'Positions use the native KiCad coordinate origin, shared with the Gerber export.\n'
        'Negative Y coordinates are intentional. Exact-part vendor angle corrections are applied '
        'after centroid calculation using the native angle. See rotation-audit.csv for every part.\n'
        'Rule evidence and unresolved orientation are recorded in assembly-audit.json; derived '
        'corrections require a fresh supplier preview. Local 3D models do not upload with Gerbers '
        'and cannot repair missing models in JLCPCB’s independent library.\n'
        'Explicit centroid corrections and manually fitted parts are recorded in assembly.json. '
        'assembly-F.svg and assembly-B.svg are assembly drawings, not Gerber upload files.\n\n'
        'Check pin 1, polarity, body alignment, bottom-side orientation, matched MPN/package, '
        'stock and through-hole assembly eligibility in JLCPCB before ordering. '
        'Export checks do not establish supplier acceptance or fabrication approval.\n', encoding='utf-8')
    return {'kicad': version, 'manufacturing_profile': 'jlcpcb', 'assembly': assembly}
