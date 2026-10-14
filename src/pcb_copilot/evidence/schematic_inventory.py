"""Physical schematic parts for research before PCB placement exists."""

from __future__ import annotations

import re

from kicad_claude.adapters import sch_io

from pcb_copilot.evidence.checks import Part
from pcb_copilot.evidence.inventory import MODULE_HINTS
from pcb_copilot.models import Project
from pcb_copilot.schematic.preview import schematic_files


def schematic_parts(project: Project, *, include_passives: bool = False) -> tuple[Part, ...]:
    """Read saved native sheets, including parts absent from an empty PCB.

    The default preserves the shared datasheet exemption policy. Explicit full
    audits include purchased passives and connectors; fabricated probe/mounting
    features still do not have a purchased-component datasheet.
    """
    parts = {}
    for path in schematic_files(project.schematic_path):
        tree = sch_io.parse_file(path)
        for symbol in sch_io.find_children(tree, 'symbol'):
            fields = {str(p[1]): str(p[2]) for p in sch_io.find_children(symbol, 'property')}
            ref = fields.get('Reference', '').strip()
            if not ref or ref.startswith('#'):
                continue
            on_board = sch_io.find_child(symbol, 'on_board')
            if on_board and str(on_board[1]) == 'no':
                continue
            if ref in parts:
                raise ValueError(f'duplicate physical schematic reference: {ref}')
            value = fields.get('Value', '').strip()
            mpn = fields.get('MPN', '').strip() or value
            module = any(hint in (value + ' ' + mpn).lower() for hint in MODULE_HINTS)
            prefix = re.match(r'[A-Za-z]+', ref)
            prefix = prefix.group() if prefix else ''
            fabricated = prefix in {'TP', 'FID', 'H', 'MH', 'LOGO', 'REF'} and not module
            exempt = prefix in {'R', 'C', 'L', 'TP', 'FID', 'H', 'LED', 'J'} and not module
            required = not fabricated and (include_passives or not exempt)
            parts[ref] = Part(ref, mpn, requires_datasheet=required, is_module=module)
    if not parts:
        raise ValueError('schematic contains no physical parts; no component coverage was verified')
    return tuple(parts[ref] for ref in sorted(parts))
