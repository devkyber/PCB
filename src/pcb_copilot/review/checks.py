"""Current-design checks. External tools are discovered only by checks using them."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pcb_copilot import deviations
from pcb_copilot.copper_features import copper_feature_type
from pcb_copilot.evidence.checks import Part, check_evidence
from pcb_copilot.evidence.inventory import MODULE_HINTS, _blocks, _prop, inventory
from pcb_copilot.jlcpcb import check_jlcpcb_review
from pcb_copilot.layout.render import board_pin_nets, native_board, schematic_inventory
from pcb_copilot.layout.schematic_links import compare_schematic_links
from pcb_copilot.models import Project
from pcb_copilot.review.models import CheckResult, CheckScope
from pcb_copilot.review.routing_settings import RoutingSettingsCheck
from pcb_copilot.review.routing_topology import RoutingTopologyCheck
from pcb_copilot.review.schematic_quality import SchematicQualityCheck
from pcb_copilot.review.signoff import SignoffCheck
from pcb_copilot.schematic.netmap import extract
from pcb_copilot.toolchain import discover_toolchain


def _toolchain():
    return discover_toolchain(Path(__file__).resolve().parents[3])


def _run(command, **kwargs):
    return subprocess.run([str(item) for item in command], capture_output=True,
                          text=True, encoding='utf-8', errors='replace',
                          check=False, timeout=180, **kwargs)


def _fresh_report(command, output: Path, fields: tuple[str, ...]) -> dict:
    output.unlink(missing_ok=True)
    result = _run(command)
    if result.returncode or not output.is_file():
        raise RuntimeError(f'KiCad failed to produce a valid report (exit {result.returncode}): '
                           f'{result.stderr or result.stdout}')
    report = json.loads(output.read_text(encoding='utf-8'))
    if not isinstance(report, dict) or any(not isinstance(report.get(key), list) for key in fields):
        raise ValueError('KiCad report is malformed or missing required findings')
    return report


def drc_once(pcb: Path, output: Path) -> tuple[int, int, int]:
    report = _fresh_report(
        [_toolchain().kicad_cli, 'pcb', 'drc', '--format', 'json', '--refill-zones',
         '-o', output, pcb], output, ('violations', 'unconnected_items'),
    )
    violations = report['violations']
    if any(not isinstance(item, dict) or item.get('severity') not in {'error', 'warning', 'ignore'}
           for item in violations):
        raise ValueError('DRC violation has no recognized severity')
    errors = sum(item['severity'] == 'error' for item in violations)
    return errors, len(violations) - errors, len(report['unconnected_items'])


def check_drc(project: Project) -> tuple[bool, str]:
    runs = [drc_once(project.pcb_path, project.root / 'drc-report.json') for _ in range(2)]
    errors, warnings, unconnected = (max(run[i] for run in runs) for i in range(3))
    detail = f'{errors} error(s), {warnings} warning(s), {unconnected} unconnected; two refilled runs'
    if runs[0] != runs[1]:
        detail += f'; unstable results: {runs}'
    return errors == 0 and unconnected == 0, detail


def check_erc(project: Project) -> tuple[bool, str]:
    output = project.root / 'erc-report.json'
    report = _fresh_report(
        [_toolchain().kicad_cli, 'sch', 'erc', '--format', 'json', '-o', output,
         project.schematic_path], output, ('sheets',),
    )
    violations = []
    for sheet in report['sheets']:
        if not isinstance(sheet, dict) or not isinstance(sheet.get('violations'), list):
            raise ValueError('malformed ERC sheet')
        violations.extend(sheet['violations'])
    real = [item for item in violations if not (
        item.get('type') == 'pin_to_pin' and item.get('severity') == 'warning'
        and re.search(r'\bunspecified\b', item.get('description', ''), re.I))]
    return not real, f'{len(real)} violation(s), {len(violations)-len(real)} unspecified-pin warnings waived'


def check_netmap(project: Project) -> tuple[bool, str]:
    recorded = json.loads(project.netmap_path.read_text(encoding='utf-8'))['nets']
    recorded = {ref: pins for ref, pins in recorded.items() if not ref.startswith('#')}
    current = extract(project.schematic_path)['nets']
    differing = sorted(ref for ref in set(recorded) | set(current) if recorded.get(ref) != current.get(ref))
    return not differing, ('netmap matches the current schematic' if not differing else
                           f'netmap is stale for: {", ".join(differing)}')


def check_parity(project: Project, *, include_links: bool = True) -> tuple[bool, str]:
    toolchain = _toolchain()
    parts, schematic = schematic_inventory(toolchain, project.schematic_path)
    footprints = native_board(toolchain, project.pcb_path)['footprints']
    board = board_pin_nets(footprints, parts)
    differences = [f'{name}: schematic {sorted(schematic.get(name, set()))}; PCB {sorted(board.get(name, set()))}'
                   for name in sorted(set(schematic) | set(board)) if schematic.get(name) != board.get(name)]
    differences.extend(compare_physical_parts(parts, footprints))
    if include_links:
        differences.extend(compare_schematic_links(parts, footprints))
    detail = 'exact schematic/PCB pin-net parity' + (' and schematic links' if include_links else '')
    return not differences, detail if not differences else '\n'.join(differences)


def compare_physical_parts(parts, footprints) -> list[str]:
    differences = [f'{ref}: schematic part missing from board' for ref in sorted(set(parts) - set(footprints))]
    differences.extend(f'{ref}: board part missing from schematic'
                       for ref in sorted(set(footprints) - set(parts))
                       if not re.fullmatch(r'(FID|H|MH|LOGO|REF)\d+', ref))
    for ref in sorted(set(parts) & set(footprints)):
        expected, actual = parts[ref], footprints[ref]
        if expected['footprint'] != actual['lib_id']:
            differences.append(f'{ref}: schematic/PCB footprint identity differs')
        if expected['value'] != actual['value']:
            differences.append(f'{ref}: schematic/PCB component value differs')
        if expected.get('lcsc') and expected['lcsc'] != actual.get('lcsc'):
            differences.append(f'{ref}: schematic/PCB LCSC sourcing identity differs')
    return differences


def check_placement(project: Project) -> tuple[bool, str]:
    from pcb_copilot.review import placement

    text = project.pcb_path.read_text(encoding='utf-8')
    functions = [placement.check_placeholders, placement.check_board_dimensions,
                 placement.check_traces_exist, placement.check_edge_clearance,
                 placement.check_pads_inside_board, placement.check_courtyard_overlap,
                 placement.check_module_socket_pinouts]
    results = [fn(text) for fn in functions]
    results.append(placement.check_connector_class(str(project.pcb_path), project.schematic_path))
    failures = [detail for state, detail in results if state == 'FAIL']
    return not failures, '\n'.join(failures) if failures else 'implemented placement checks pass'


def check_design_rules(project: Project) -> tuple[bool, str]:
    python = _toolchain().kipython
    if python is None:
        return False, 'KiCad Python with pcbnew is unavailable'
    result = _run([python, Path(__file__).with_name('design_rules_native.py'), project.pcb_path])
    return result.returncode == 0 and 'RESULT:' in result.stdout, (result.stdout or result.stderr).strip()


def _parts(project: Project, *, datasheets=False):
    text = project.pcb_path.read_text(encoding='utf-8')
    copper = {_prop(block, 'Reference') for block in _blocks(text)
              if copper_feature_type(block)}
    items = inventory(text)
    for ref, value, _pads, _lcsc, key in items:
        if ref in copper:
            continue  # Fabricated copper has no purchased-component datasheet.
        module = any(hint in value.lower() for hint in MODULE_HINTS)
        prefix = re.match(r'[A-Za-z]+', ref)
        exempt = prefix and prefix.group() in {'R', 'C', 'L', 'TP', 'FID', 'H', 'LED', 'J'} and not module
        if (datasheets and not exempt) or (not datasheets and key):
            yield Part(ref, value, requires_datasheet=datasheets,
                       requires_reference=not datasheets, is_module=module)


def check_datasheets(project: Project) -> tuple[bool, str]:
    from pcb_copilot.evidence.schematic_inventory import schematic_parts

    native_parts = schematic_parts(project)
    findings = check_evidence(project, (*native_parts, *_parts(project, datasheets=True)))
    relevant = [item for item in findings if item.code.startswith(('archive.', 'index.'))
                or item.code in {'part.missing_datasheet', 'part.missing_module_document'}]
    return not relevant, '\n'.join(dict.fromkeys(item.message for item in relevant)) or (
        f'required datasheet bytes verified; {len(native_parts)} physical schematic parts inspected '
        '(shared passive exemptions apply)')


def check_research(project: Project) -> tuple[bool, str]:
    problems = []
    path = project.root / 'REQUIREMENTS.md'
    text = path.read_text(encoding='utf-8') if path.is_file() else ''
    for section in ('Purpose', 'Electrical', 'Mechanical', 'Interfaces', 'Environment', 'Success criteria'):
        heading = re.search(r'^(#+).*' + re.escape(section) + r'.*$', text, re.I | re.M)
        body = ''
        if heading:
            body = text[heading.end():]
            following = re.search(r'^#{1,%d}\s' % len(heading.group(1)), body, re.M)
            if following:
                body = body[:following.start()]
        stripped = re.sub(r'\s+', ' ', re.sub(r'^\s*[-*|>#]+\s*', '', body, flags=re.M)).strip()
        if len(stripped) < 40 or re.search(r'\b(TBD|TODO|FILL ?ME)\b|<[^>\n]{2,120}>', body, re.I):
            problems.append(f'requirement section missing, empty or unfinished: {section}')
    problems.extend(item.message for item in check_evidence(project, tuple(_parts(project))))
    _, malformed = deviations.parse(project.root)
    problems.extend(malformed)
    return not problems, '\n'.join(dict.fromkeys(problems)) or 'requirements, cited basis and archived evidence verified'


@dataclass(frozen=True)
class MachineCheck:
    check_id: str
    function: object
    scope: CheckScope

    def run(self, project: Project) -> CheckResult:
        passed, detail = self.function(project)
        return CheckResult(self.check_id, passed, detail, self.scope)


def current_checks() -> tuple:
    from pcb_copilot.assembly import check_assembly
    entries = (
        ('research', check_research, 'requirements, cited basis and source integrity', 'engineering validity of those choices', False),
        ('datasheets', check_datasheets, 'required datasheets are archived and verified', 'interpretation of electrical limits', False),
        ('erc', check_erc, 'fresh KiCad electrical-rule findings', 'circuit fitness or safe operation', True),
        ('schematic_ownership', check_netmap, 'netmap matches the current schematic', 'circuit correctness', True),
        ('netlist_parity', check_parity, 'exact schematic/PCB pin-net agreement and forward-annotation links', 'which circuit is correct', True),
        ('placement', check_placement, 'implemented placement geometry checks', 'assembly or enclosure fit', False),
        ('design_rules', check_design_rules, 'geometric rules 1.2, 2.2, 5.1 and 6.1', 'all house rules or source applicability', True),
        ('drc', check_drc, 'two fresh zone-refilled DRC runs and routing completeness', 'RF, thermal or functional behavior', True),
        ('jlcpcb_dfm', check_jlcpcb_review, 'independent dated JLCPCB geometry and declared stackup checks',
         'assembly eligibility, current capacity or supplier order acceptance', True),
        ('assembly_contracts', check_assembly, 'exact-part rotation rules, local model files and wire-pad label/net association',
         'supplier preview approval, mechanical fit or model shape correctness', False),
    )
    return tuple(MachineCheck(name, fn, CheckScope(proves, limit, name != 'drc', external))
                 for name, fn, proves, limit, external in entries) + (
                     RoutingSettingsCheck(), RoutingTopologyCheck(), SchematicQualityCheck(), SignoffCheck(),
                 )
