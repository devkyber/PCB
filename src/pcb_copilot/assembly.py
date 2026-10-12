"""Assembly contracts: vendor zero angles, physical pad labels and local models.

These checks are separate from electrical DRC and from supplier preview approval.
Never infer a vendor's pin 1 from a red marker or from a KiCad 3D transform.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path

from kicad_claude.adapters import sch_io as s
from kicad_claude.utils.kicad_paths import find_footprint_lib_dirs


def prop(node, name):
    return next((str(p[2]) for p in s.find_children(node, 'property') if str(p[1]) == name), '')


def lcsc(node):
    return next((prop(node, name).strip() for name in ('LCSC Part', 'LCSC', 'LCSC Part #',
                'JLCPCB', 'JLCPCB Part') if prop(node, name).strip()), '')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pad_geometry_digest(fp):
    """Local pad numbering/shape/angle/body, invariant to board position and UUIDs.

    KiCad stores pad XY in footprint coordinates but pad angles in board coordinates.
    Net names must not enter a reusable package's zero-angle contract.
    """
    from pcb_copilot.manufacturing import footprint_geometry_digest

    at = s.find_child(fp, 'at') or []
    angle = float(at[3]) if len(at) > 3 else 0
    pads = []
    for pad in s.find_children(fp, 'pad'):
        xy = s.find_child(pad, 'at') or ['at', 0, 0]
        pa = float(xy[3]) if len(xy) > 3 else 0
        item = {'identity': [str(v) for v in pad[1:4]],
                'at': [round(float(xy[1]), 6), round(float(xy[2]), 6), round((pa-angle) % 360, 6)]}
        for key in ('size', 'drill', 'layers', 'roundrect_rratio', 'chamfer_ratio', 'chamfer',
                    'rect_delta', 'options', 'primitives'):
            child = s.find_child(pad, key)
            if child:
                item[key] = child[1:]
        pads.append(json.dumps(item, sort_keys=True, default=str))
    payload = {'pads': sorted(pads), 'body': footprint_geometry_digest(fp)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def evidence_file(project, relative, expected):
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise ValueError('assembly evidence path and SHA256 are required')  # noqa: TRY004 -- external configuration
    path = (project.root / relative).resolve()
    if not path.is_relative_to(project.root.resolve() / 'evidence'):
        raise ValueError('assembly evidence must be inside project evidence/')
    if not path.is_file() or digest(path) != expected:
        raise ValueError(f'assembly evidence missing or changed: {relative}')
    return path


def rotation_rule(project, fp, plan):
    part = lcsc(fp)
    rule = plan.get('rotation_offsets', {}).get(part)
    if rule is None:
        return None
    required = {'mpn', 'footprint', 'side', 'pad_geometry_sha256', 'degrees', 'basis',
                'evidence', 'evidence_sha256', 'reason'}
    if not isinstance(rule, dict) or set(rule) != required:
        raise ValueError(f'invalid rotation rule: {part}')
    side = 'top' if str((s.find_child(fp, 'layer') or ['', ''])[1]) == 'F.Cu' else 'bottom'
    if (rule['mpn'] != prop(fp, 'MPN').strip() or rule['footprint'] != str(fp[1])
            or rule['side'] != side or rule['pad_geometry_sha256'] != pad_geometry_digest(fp)):
        raise ValueError(f'{prop(fp, "Reference")}: rotation rule identity/side/pad geometry changed ({part})')
    degrees = rule['degrees']
    if isinstance(degrees, bool) or not isinstance(degrees, (int, float)) or not math.isfinite(degrees):
        raise ValueError(f'invalid rotation degrees: {part}')
    if rule['basis'] not in {'observed', 'derived_from_preview', 'unverified'} or not rule['reason']:
        raise ValueError(f'invalid rotation evidence basis: {part}')
    evidence_file(project, rule['evidence'], rule['evidence_sha256'])
    return rule


def corrected_position(project, fp, plan, x, y, native_angle, side):
    """Centroid rotates with native footprint; vendor angle changes placement only."""
    from pcb_copilot.layout.geometry import _rotate_local

    offset = plan['centroid_offsets'].get(str(fp[1]))
    if offset:
        if side != 'top':
            raise ValueError(f'bottom-side centroid correction needs separate verification: {prop(fp, "Reference")}')
        dx, dy = _rotate_local(offset['x_mm'], offset['y_mm'], native_angle)
        x, y = x + dx, y - dy  # Native position CSV uses Y-up.
    rule = rotation_rule(project, fp, plan)
    angle = (native_angle + (rule['degrees'] if rule else 0)) % 360
    return x, y, angle, rule


def polarity_labels(footprints):
    """Verify every surface wire pad's nearest silk label against its actual net.

    Deliberately scoped to WirePads; this is not OCR or a general schematic check.
    """
    rows, issues = [], []
    for fp in footprints.values():
        if ':WirePads_' not in str(fp[1]):
            continue
        ref = prop(fp, 'Reference')
        pads = [p for p in s.find_children(fp, 'pad') if str(p[1])]
        labels = []
        for text in s.find_children(fp, 'fp_text'):
            layer = s.find_child(text, 'layer') or []
            if len(layer) > 1 and str(layer[1]) in {'F.SilkS', 'F.Silkscreen', 'B.SilkS', 'B.Silkscreen'}:
                raw = str(text[2])
                if raw in {'+', '-', 'GND'} or re.fullmatch(r'\+\d+(?:\.\d+)?V', raw) or raw.startswith('${SHORT_NET_NAME('):
                    labels.append(text)
        seen = set()
        for text in labels:
            xy = (s.find_child(text, 'at') or [])[1:3]
            pad = min(pads, key=lambda p: math.dist(xy, (s.find_child(p, 'at') or [])[1:3]))
            number = str(pad[1])
            netnode = s.find_child(pad, 'net') or []
            net = str(netnode[-1]) if len(netnode) > 1 else ''
            short_net = net.rsplit('/', 1)[-1]
            # KiCad 10 stores net names inline; older KiCad needs board-net resolution.
            raw = str(text[2])
            variable = re.fullmatch(r'\$\{SHORT_NET_NAME\(([^)]+)\)\}', raw)
            shown = short_net if variable else raw
            valid = bool(net) and number not in seen
            if variable:
                valid &= variable[1] == number
            elif raw in {'GND', '-'}:
                valid &= bool(re.fullmatch(r'(?:[ADP]?GND)(?:_\d+)?', short_net))
            elif raw == '+':
                valid &= bool(re.fullmatch(r'\+\d+(?:\.\d+)?V|VBAT|BAT_SWITCHED', short_net))
            else:
                valid &= raw == short_net
            seen.add(number)
            rows.append({'reference': ref, 'pad': number, 'net': net, 'text': raw,
                         'shown': shown, 'passed': valid})
            if not valid:
                issues.append(f'{ref}.{number}: silk {raw!r} conflicts with {net!r} or label association')
        if seen != {str(p[1]) for p in pads}:
            issues.append(f'{ref}: missing polarity label for one or more wire pads')
    return rows, issues


def resolve_model(project, name):
    expanded = name.replace('${KIPRJMOD}', str(project.root))
    for variable in re.findall(r'\$\{([^}]+)\}', expanded):
        if variable in os.environ:
            expanded = expanded.replace('${' + variable + '}', os.environ[variable])
        elif re.fullmatch(r'KICAD\d+_3DMODEL_DIR', variable):
            suffix = expanded.split('${' + variable + '}', 1)[1].lstrip('/\\')
            for library in find_footprint_lib_dirs():
                candidate = library.parent / '3dmodels' / suffix
                if candidate.is_file():
                    return candidate.resolve()
            raise ValueError(f'cannot resolve {variable}: {name}')
        else:
            raise ValueError(f'unresolved model variable {variable}')
    path = Path(expanded)
    return (path if path.is_absolute() else project.root / path).resolve()


def model_inventory(project, footprints, refs, plan):
    rows, issues = [], []
    for ref in sorted(refs):
        fp = footprints[ref]
        models = s.find_children(fp, 'model')
        enabled = [m for m in models if 'hide' not in [str(v) for v in m[2:] if not isinstance(v, list)]]
        if not enabled:
            issues.append(f'{ref}: missing enabled local 3D model')
        contract = plan.get('model_contracts', {}).get(lcsc(fp))
        matched = False
        for model in enabled:
            row = {'reference': ref, 'path': str(model[1]), 'passed': False}
            try:
                path = resolve_model(project, str(model[1]))
                if not path.is_file() or path.stat().st_size < 32:
                    raise ValueError('model file missing or empty')
                transforms = {}
                for key in ('scale', 'offset', 'rotate'):
                    transform = s.find_child(model, key)
                    xyz = s.find_child(transform, 'xyz') if transform else None
                    values = [float(v) for v in xyz[1:]] if xyz else ([1, 1, 1] if key == 'scale' else [0, 0, 0])
                    if len(values) != 3 or not all(math.isfinite(v) for v in values) or (key == 'scale' and min(values) <= 0):
                        raise ValueError('invalid model transform')
                    transforms[key] = values
                row.update(sha256=digest(path), transforms=transforms)
                if path.suffix.lower() == '.wrl':
                    substitute = next((path.with_suffix(ext) for ext in ('.step', '.stp', '.igs', '.iges')
                                       if path.with_suffix(ext).is_file()), None)
                    if substitute is not None:
                        row['step_substitute'] = {'path': str(model[1]).rsplit('.', 1)[0] + substitute.suffix,
                                                  'sha256': digest(substitute)}
                if contract:
                    if (contract.get('path') != str(model[1]) or contract.get('sha256') != row['sha256']
                            or any(contract.get(key) != value for key, value in transforms.items())
                            or contract.get('mpn') != prop(fp, 'MPN') or contract.get('footprint') != str(fp[1])):
                        raise ValueError('model identity/content/transform differs from dimensional contract')
                    matched = True
                    row['fidelity'] = contract['fidelity']
                else:
                    row['fidelity'] = 'library model; dimensional accuracy not certified by file check'
                row['passed'] = True
            except (OSError, ValueError) as exc:
                row['error'] = str(exc)
                issues.append(f'{ref}: {exc}')
            rows.append(row)
        if contract and not matched:
            issues.append(f'{ref}: required model contract is not satisfied')
    return rows, issues


def audit_assembly(project, footprints, refs, plan):
    rotations, issues = [], []
    for ref in sorted(refs):
        rule = rotation_rule(project, footprints[ref], plan)
        if rule is None:
            issues.append(f'{ref}: missing exact-part rotation rule')
        rotations.append({'reference': ref, 'lcsc': lcsc(footprints[ref]), 'rule': rule})
    labels, label_issues = polarity_labels(footprints)
    models, model_issues = model_inventory(project, footprints, refs, plan)
    issues.extend(label_issues + model_issues)
    return {'passed': not issues, 'issues': issues, 'rotation_rules': rotations,
            'polarity_labels': labels, 'models': models,
            'scope': 'Rule identity, local model files/transforms and wire-pad label/net association; '
                     'not supplier orientation approval, component fit, model shape correctness or circuit safety.'}


def supplier_review(project, output, plan):
    """Require a named review of the actual upload, tied to board/BOM/CPL bytes."""
    review = plan.get('supplier_review')
    if not review:
        return {'passed': False, 'detail': 'JLCPCB placement review has not been recorded for this upload.'}
    try:
        if set(review) != {'reviewer', 'reviewed_on', 'pcb_sha256', 'bom_sha256', 'cpl_sha256',
                           'evidence', 'evidence_sha256'}:
            raise ValueError('invalid supplier review record')
        if not isinstance(review['reviewer'], str) or not review['reviewer'].strip():
            raise ValueError('supplier reviewer is missing')
        if date.fromisoformat(str(review['reviewed_on'])) > datetime.now(UTC).astimezone().date():
            raise ValueError('supplier review date is in the future')
        for key, path in (('pcb_sha256', project.pcb_path), ('bom_sha256', output / 'bom.csv'),
                          ('cpl_sha256', output / 'cpl.csv')):
            if review[key] != digest(path):
                raise ValueError(f'supplier review is stale: {key}')
        evidence_file(project, review['evidence'], review['evidence_sha256'])
    except (ValueError, TypeError, OSError) as exc:
        return {'passed': False, 'detail': str(exc)}
    return {'passed': True, 'detail': 'Named supplier preview review matches current PCB/BOM/CPL and evidence.',
            'reviewer': review['reviewer'], 'reviewed_on': str(review['reviewed_on'])}


def check_assembly(project):
    import tempfile

    from pcb_copilot.manufacturing import _assembly_plan, write_bom

    try:
        footprints = {prop(fp, 'Reference'): fp for fp in s.find_children(s.parse_file(project.pcb_path), 'footprint')}
        plan = _assembly_plan(project, footprints)
        with tempfile.TemporaryDirectory(prefix='assembly-audit-') as directory:
            refs = write_bom(project.pcb_path, Path(directory) / 'bom.csv', excluded_refs=plan['manual_fit'])
        report = audit_assembly(project, footprints, refs, plan)
        return report['passed'], '\n'.join(report['issues']) or f'{len(refs)} assembly components: rule, local model and wire-label checks pass'
    except (ValueError, OSError) as exc:
        return False, str(exc)
