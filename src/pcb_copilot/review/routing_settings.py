"""Read-only routing editability audit, not a trace-current or DRC calculator.

Existing wide supply routes are evidence for reviewing saved router defaults,
not permission to impose their width on every branch of the same net.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from fnmatch import fnmatchcase

from kicad_claude.adapters.sch_io import find_child, find_children, head_of, parse_file

from pcb_copilot.models import Project
from pcb_copilot.review.models import CheckResult, CheckScope

SCOPE = CheckScope(
    proves='stored native routing widths/locks and project routing-setting coverage',
    does_not_prove='ampacity, thermal margin, branch currents, effective custom rules or router UI selection',
    deterministic=True,
    requires_external_tool=False,
)

# Name heuristics select candidates only; they never infer current requirements.
_SUPPLY = re.compile(
    r'^(?:\+?\d+(?:[.]\d+)?V\d*|V(?:BAT|MOTOR|IN|OUT|CC|DD|SYS|BUS|SUPPLY)'
    r'(?:_.*)?|BAT(?:TERY)?_(?:SWITCHED|FUSED))$', re.IGNORECASE,
)


def _width(value) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) and value > 0 else 0.0
    return 0.0


def _locked(item: list) -> bool:
    field = find_child(item, 'locked')
    if field is not None:
        return len(field) == 1 or str(field[1]) == 'yes'
    return any(str(atom) == 'locked' for atom in item[1:] if not isinstance(atom, list))


def _assigned_classes(settings: dict, classes: dict, net: str) -> set[str]:
    """Inspect stored assignments, without claiming KiCad's rule resolution."""
    found = {
        item['netclass'] for item in settings.get('netclass_patterns', []) or []
        if isinstance(item, dict) and isinstance(item.get('pattern'), str)
        and fnmatchcase(net, item['pattern']) and item.get('netclass') in classes
    }
    direct = settings.get('netclass_assignments') or {}
    if isinstance(direct, dict):
        assigned = direct.get(net, [])
        if isinstance(assigned, str):
            assigned = [assigned]
        if isinstance(assigned, list):
            found.update(name for name in assigned if isinstance(name, str) and name in classes)
    # Older project files store exact net names inside each class.
    found.update(name for name, item in classes.items() if net in (item.get('nets') or []))
    return found - {'Default'}


class RoutingSettingsCheck:
    check_id = 'routing_settings'
    scope = SCOPE

    def run(self, project: Project) -> CheckResult:
        board = parse_file(project.pcb_path)
        if head_of(board) != 'kicad_pcb':
            raise ValueError('routing audit requires a native kicad_pcb document')
        # KiCad 9 uses numbered nets; KiCad 10 stores names directly on items.
        names = {item[1]: str(item[2]) for item in find_children(board, 'net') if len(item) >= 3}
        routes = [item for item in board[1:] if head_of(item) in {'segment', 'arc', 'via'}]
        counts = {kind: sum(head_of(item) == kind for item in routes)
                  for kind in ('segment', 'arc', 'via')}
        locked = sum(_locked(item) for item in routes)
        detail = (f"Native routing: {counts['segment']} segments, {counts['arc']} arcs, "
                  f"{counts['via']} vias; {locked} locked item(s).")
        advisories = []
        if locked:
            advisories.append(
                f'{locked} native routing item(s) are locked. Intentional locks are valid; '
                'inspect the KiCad selection filter and lock state before editing. '
                'No items were unlocked.'
            )
        widths = defaultdict(set)
        for item in routes:
            if head_of(item) == 'via':
                continue
            field, net = find_child(item, 'width'), find_child(item, 'net')
            if field and len(field) > 1 and net and len(net) > 1:
                width = _width(field[1])
                name = names.get(net[1], net[1] if isinstance(net[1], str) else '')
                if width and name:
                    widths[name].add(width)

        path = project.pcb_path.with_suffix('.kicad_pro')
        if not path.is_file():
            advisories.append('Companion .kicad_pro is missing; saved routing presets and net classes could not be audited.')
            return CheckResult(self.check_id, True, detail, self.scope, advisories=tuple(advisories))
        document = json.loads(path.read_text(encoding='utf-8'))
        settings = document.get('net_settings') or {}
        classes = {item['name']: item for item in settings.get('classes', [])
                   if isinstance(item, dict) and isinstance(item.get('name'), str)}
        default = _width(classes.get('Default', {}).get('track_width'))
        presets = document.get('board', {}).get('design_settings', {}).get('track_widths', [])
        presets = {_width(value) for value in presets} - {0.0}
        detail += f' Default width: {default:g} mm; {len(presets)} positive width preset(s).'
        if not default:
            advisories.append('No positive Default track width is recorded; inspect the project routing defaults in KiCad.')

        for net, values in sorted(widths.items()):
            # Only substantially wider, supply-named routes prompt this convenience
            # warning. These thresholds are noise filters, not electrical minima.
            widest = max(values)
            if not _SUPPLY.fullmatch(net.rsplit('/', 1)[-1]) or widest < max(0.5, 2 * default):
                continue
            assigned = _assigned_classes(settings, classes, net)
            declared = {_width(classes[name].get('track_width')) for name in assigned} - {0.0}
            has_wide_class = any(width >= widest - 1e-6 for width in declared)
            label = f'{net}: existing tracks span {min(values):g}–{widest:g} mm'
            if not has_wide_class:
                advisories.append(
                    f'{label}, but no stored non-Default class assignment provides a '
                    f'{widest:g} mm routing width. Review the intended main-route default; '
                    'smaller low-current branches on this net can be legitimate. '
                    'This does not impose a net-wide minimum or assess ampacity.'
                )
            if not has_wide_class and not any(abs(width - widest) < 1e-6 for width in presets):
                advisories.append(
                    f'{net}: existing {widest:g} mm route width is absent from the saved '
                    'width presets and assigned class widths; consider a matching preset '
                    'for future manual routing. Custom rules and connected-track mode '
                    'may still determine the actual router width.'
                )
        return CheckResult(self.check_id, True, detail, self.scope, advisories=tuple(advisories))
