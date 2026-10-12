"""Dated JLCPCB geometry baseline checked independently of weaker project rules."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from kicad_claude.adapters import sch_io

from pcb_copilot.toolchain import discover_toolchain

PROFILE = 'jlcpcb-2layer-1oz-green-2026-10-05'
SOURCE = 'https://jlcpcb.com/capabilities/pcb-capabilities'


def check_jlcpcb(project) -> dict:
    """Run on isolated CAD; never alter the owner's rules, exclusions or copper."""
    template = Path(__file__).resolve().parents[2] / 'templates/jlcpcb-2layer-1oz'
    baseline = json.loads((template / 'jlcpcb-2layer-1oz.kicad_pro').read_text())
    rules = (template / 'jlcpcb-2layer-1oz.kicad_dru').read_bytes()
    board = sch_io.parse_file(project.pcb_path)
    setup = sch_io.find_child(board, 'setup') or []
    stack = sch_io.find_child(setup, 'stackup') or []
    layers = {n[1]: n for n in sch_io.find_children(stack, 'layer')}
    problems = []
    copper = [n[1] for n in (sch_io.find_child(board, 'layers') or [])[1:]
              if isinstance(n, list) and str(n[1]).endswith('.Cu')]
    if set(copper) != {'F.Cu', 'B.Cu'}:
        problems.append('This baseline supports exactly two copper layers.')
    for name in ('F.Cu', 'B.Cu'):
        thickness = sch_io.find_child(layers.get(name, []), 'thickness')
        if not thickness or abs(float(thickness[1]) - .035) > .000001:
            problems.append(f'{name}: explicitly declare 0.035 mm / 1 oz copper, or qualify another profile.')
    for name in ('F.Mask', 'B.Mask'):
        color = sch_io.find_child(layers.get(name, []), 'color')
        if not color or str(color[1]).lower() != 'green':
            problems.append(f'{name}: this profile requires declared green solder mask.')
    mask_web = sch_io.find_child(setup, 'solder_mask_min_width')
    if not mask_web or float(mask_web[1]) < .1:
        problems.append('Set solder-mask minimum web width to at least 0.10 mm.')
    with tempfile.TemporaryDirectory(prefix='pcb-jlcpcb-') as directory:
        pcb = Path(directory) / project.pcb_path.name
        shutil.copy2(project.pcb_path, pcb)
        # Resolve project footprint IDs in the disposable check just as in
        # normal DRC. Copy only footprint sources; 3D models are not required.
        source_root = getattr(project, 'root', project.pcb_path.parent)
        table = source_root / 'fp-lib-table'
        if table.is_file():
            shutil.copy2(table, pcb.parent / table.name)
        for folder in ('footprints', 'libs'):
            for source in (source_root / folder).rglob('*.kicad_mod'):
                target = pcb.parent / source.relative_to(source_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        settings_path = project.pcb_path.with_suffix('.kicad_pro')
        settings = json.loads(settings_path.read_text()) if settings_path.is_file() else {}
        design = settings.setdefault('board', {}).setdefault('design_settings', {})
        current_rules = design.setdefault('rules', {})
        for key, value in baseline['board']['design_settings']['rules'].items():
            if key.startswith('min_') or key == 'solder_mask_to_copper_clearance':
                current_rules[key] = max(current_rules.get(key, 0), value)
        design['drc_exclusions'] = []
        severities = design.setdefault('rule_severities', {})
        for key in baseline['board']['design_settings']['rule_severities']:
            severities[key] = 'error'
        for key in ('clearance', 'track_width', 'copper_edge_clearance', 'drill_out_of_range',
                    'annular_width', 'hole_clearance', 'hole_to_hole', 'assertion_failure',
                    'solder_mask_bridge', 'silk_edge_clearance', 'silk_over_copper',
                    'silk_overlap', 'text_height', 'text_thickness', 'via_diameter',
                    'shorting_items', 'unconnected_items', 'invalid_outline'):
            severities[key] = 'error'
        pcb.with_suffix('.kicad_pro').write_text(json.dumps(settings), encoding='utf-8')
        # Independent baseline: arbitrary project custom exceptions cannot weaken it.
        # The normal project DRC separately checks the project's own custom rules.
        pcb.with_suffix('.kicad_dru').write_bytes(rules)
        output = pcb.with_name('jlcpcb-drc.json')
        cli = discover_toolchain(Path(__file__).resolve().parents[2]).kicad_cli
        run = subprocess.run([str(cli), 'pcb', 'drc', '--format', 'json', '--refill-zones',
                              '-o', str(output), str(pcb)], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=180, check=False)
        if run.returncode or not output.is_file():
            raise RuntimeError(f'JLCPCB DRC failed: {run.stderr or run.stdout}')
        result = json.loads(output.read_text(encoding='utf-8'))
        if not all(isinstance(result.get(k), list) for k in ('violations', 'unconnected_items')):
            raise ValueError('Malformed JLCPCB DRC result')
        violations = result['violations']
        if any(not isinstance(v, dict) or v.get('severity') not in {'error', 'warning'}
               for v in violations):
            raise ValueError('Malformed JLCPCB violation severity')
        errors = [v for v in violations if v.get('severity') == 'error']
    return {'profile': PROFILE, 'source': SOURCE,
            'baseline_sha256': hashlib.sha256(json.dumps(baseline, sort_keys=True).encode() + rules).hexdigest(),
            'passed': not problems and not errors and not result['unconnected_items'],
            'configuration_findings': problems, 'errors': errors,
            'warnings': [v for v in violations if v.get('severity') == 'warning'],
            'unconnected_items': result['unconnected_items'],
            'scope': 'Native geometry, declared two-layer / 1 oz / green-mask profile. '
                     'Does not establish current capacity, physical fit, assembler acceptance or order settings.'}


def check_jlcpcb_review(project):
    if project.manifest.manufacturing.profile not in {'jlcpcb', 'jlcpcb_2layer_default'}:
        return True, 'JLCPCB baseline not applicable to the selected manufacturer profile.'
    result = check_jlcpcb(project)
    (project.root / 'jlcpcb-dfm.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    details = result['configuration_findings'] + [v['description'] for v in result['errors'][:8]]
    return result['passed'], (f"{PROFILE}: {len(result['errors'])} error(s), "
                            f"{len(result['unconnected_items'])} unconnected. " + '; '.join(details))
