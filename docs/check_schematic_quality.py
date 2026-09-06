#!/usr/bin/env python3
"""The schematic is the least-gated artifact in a workspace built on gates.

Why this file exists
--------------------
Seven gates existed before this one — datasheets, placement, design-rules,
research, ERC, DRC, sign-off — and exactly one of them looked at the
schematic: ERC, which checks connectivity and is blind to everything a human
reads. So two rules this repo states in writing were broken by every board in
it, for as long as the boards had existed, with nothing to notice.

Rule 1, from .claude/rules/pcb-schematic.md, verbatim:

    "Page size is a design decision. ~25 components is about the limit for
     A4 ... past that, split into hierarchical sheets rather than shrinking
     spacing."

tms-v3 carries 66 components on one A3 sheet. Zero of the four boards has a
single hierarchical sheet. `sch_editor.py` has had `add_sheet_node`,
`add_hierarchical_label` and `add_sheet_pin` the whole time, called by
nothing — recurring defect class #3, "the orphaned tool", sitting next to the
rule that needed it.

Rule 2, from CLAUDE.md: put your name and rev on the board. Not one schematic
has a `title_block` at all. TITLE / AUTHOR / REVISION exist only as textvars
in the `.kicad_pro`, so every sheet renders with Title, Date and Rev blank.

What is counted, and why it is not everything
---------------------------------------------
COMPONENTS, not symbols. Power symbols and PWR_FLAGs are excluded, and that
decision was made by measuring the real boards rather than by reading the
rule literally:

    board          symbols   power   components
    baro-bmp390        31      21       10
    imu-icm42688       29      19       10
    gnss-neom9n        57      33       24
    tms-v3            138      72       66

Counting all symbols would fail baro-bmp390 at 31-on-A4 — a board whose sheet
is 60% empty white space. A gate that fires on a sheet you can see is not
crowded is a gate that gets switched off, and this repo's own history is that
an ignored check is worse than an absent one. Density is about components.

The drawn-connection ratio is ADVISORY, deliberately
----------------------------------------------------
All four boards have ZERO junctions: every pin terminates in a 3.81mm stub
and a label, and nothing is drawn connecting any two components. That is the
real reason the sheets cannot be read. It is reported here as a number and
NOT enforced, because the fix is an architectural change to the generators
that has not landed yet. Gating it today would only mean four boards failing
a gate nobody can currently pass.

Usage:  python3 check_schematic_quality.py <board.kicad_pcb | board.kicad_sch>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Components per sheet. A4 anchors the documented "~25"; the rest scale with
# sheet area (each step up the A series doubles it).
PAGE_CAPACITY = {
    'A5': 12, 'A4': 25, 'A3': 50, 'A2': 100, 'A1': 200, 'A0': 400,
    'USLetter': 25, 'USLegal': 32, 'USLedger': 50,
}
DEFAULT_CAPACITY = 25


def _instances(text: str) -> str:
    """The symbol-instance region — everything after the `lib_symbols` block.

    Definitions inside `lib_symbols` also carry `(lib_id ...)`-shaped content;
    counting those would inflate every board by the size of its library.

    The end of that block is found by counting parentheses, not by looking for
    a `\n\t)\n` delimiter. The delimiter version returned the WHOLE FILE for
    gnss-neom9n, whose library nests differently, and the check then reported
    "0 components" for a 24-component board — a silent pass, which is the one
    failure mode a gate must never have.
    """
    i = text.find('(lib_symbols')
    if i < 0:
        return text
    depth, in_str = 0, False
    for j in range(i, len(text)):
        c = text[j]
        if c == '"' and text[j - 1] != '\\':
            in_str = not in_str
        elif not in_str:
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return text[j + 1:]
    return text[i:]


def analyse(sch: Path) -> dict:
    t = sch.read_text()
    inst = _instances(t)
    ids = re.findall(r'\(lib_id "([^"]+)"\)', inst)
    paper_m = re.search(r'\(paper "([^"]+)"', t)
    paper = paper_m.group(1) if paper_m else 'A4'

    tb = re.search(r'\(title_block\b(.*?)\n\t\)', t, re.S)
    tb_body = tb.group(1) if tb else ''
    title = re.search(r'\(title "([^"]*)"', tb_body)
    rev = re.search(r'\(rev "([^"]*)"', tb_body)

    return {
        'paper': paper,
        'capacity': PAGE_CAPACITY.get(paper, DEFAULT_CAPACITY),
        'components': len([i for i in ids if not i.startswith('power:')]),
        'power': len([i for i in ids if i.startswith('power:')]),
        # `(sheet (at ...)` is a hierarchical sheet; `(sheet_instances` is not.
        'sheets': len(re.findall(r'\(sheet\s*\n\s*\(at ', t)),
        'junctions': len(re.findall(r'\(junction\s', t)),
        'labels': len(re.findall(r'\(label\s', t)),
        'has_title_block': bool(tb),
        'title': title.group(1) if title else '',
        'rev': rev.group(1) if rev else '',
    }


def check(sch: Path, proj: Path) -> tuple[list, list, dict]:
    """Return (blocking, advisory, stats)."""
    st = analyse(sch)
    from deviations import waived                            # the ONE parser
    block, advise = [], []

    if st['components'] > st['capacity'] and st['sheets'] == 0:
        if not waived(proj, 'SHEET1', 'density'):
            block.append(
                f"{st['components']} components on one {st['paper']} sheet "
                f"(~{st['capacity']} is the documented limit) with 0 hierarchical "
                f"sheets.\n.claude/rules/pcb-schematic.md: \"past that, split into "
                f"hierarchical sheets rather than shrinking spacing.\"\n"
                f"sch_editor.py already provides add_sheet_node / "
                f"add_hierarchical_label / add_sheet_pin.")

    if not st['has_title_block'] or not st['title'].strip():
        if not waived(proj, 'SHEET1', 'titleblock'):
            block.append(
                'no title block — the sheet renders with Title, Date and Rev '
                'blank. A printed schematic with no revision on it cannot be '
                'matched to the board it describes.'
                + ('' if st['has_title_block'] else
                   ' (no `title_block` node at all; TITLE/REVISION exist only '
                   'as .kicad_pro textvars, which do not render.)'))
    elif not st['rev'].strip():
        block.append('title block has a title but no rev.')

    if st['components'] >= 5 and st['junctions'] == 0:
        advise.append(
            f"0 junctions across {st['components']} components: every pin "
            f"terminates in a stub and a label, so nothing on this sheet is "
            f"drawn as connected to anything. {st['labels']} labels carry the "
            f"whole netlist. This is why the sheet is hard to read; it is "
            f"advisory until the generators draw local nets as wires.")
    return block, advise, st


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    p = Path(sys.argv[1]).resolve()
    sch = p if p.suffix == '.kicad_sch' else p.with_suffix('.kicad_sch')
    if not sch.is_file():
        print(f'RESULT: FAIL — no schematic at {sch}')
        return 1

    block, advise, st = check(sch, sch.parent)
    print(f"{sch.name}: {st['components']} components + {st['power']} power "
          f"symbols on {st['paper']} (capacity ~{st['capacity']}), "
          f"{st['sheets']} hierarchical sheet(s), {st['junctions']} junction(s)")
    for b in block:
        for i, line in enumerate(b.splitlines()):
            print(('  FAIL:   ' if i == 0 else '          ') + line)
    for a in advise:
        for i, line in enumerate(a.splitlines()):
            print(('  advise: ' if i == 0 else '          ') + line)

    if block:
        print(f'\nRESULT: FAIL — {len(block)} schematic quality problem(s)')
        return 1
    print(f'\nRESULT: PASS'
          + (f' — {len(advise)} advisory' if advise else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
