#!/usr/bin/env python3
"""The single parser for DEVIATIONS.md — the escape hatch every gate honours.

Why this file exists
--------------------
Four false-waiver bugs shipped here before 2026-08-26, each one a different
way of reading this file too loosely: a part VALUE matched inside the title;
a rule number `U2.3` read as a designator; a reason paragraph mentioning
`U2's pads`; and the scaffolded template's own `Example:` line. Each was
fixed in place, in `check_research.py`, while `check_design_rules.py` kept
its own looser copy of the same parsing. Two parsers for one file is the
same defect as two build paths for one board.

The fifth bug was not a parsing bug at all, and it is the reason this module
exists. A DEVIATIONS.md line is:

    <ref>.<pin>  |  <scope>  |  <reason>

and the SCOPE field says what is being excused. On baro-bmp390 the line

    U1.5 | 2.2 | Pad 5 is SDO, not a supply pin ...

is a narrow, correct waiver of ONE numbered decoupling rule on ONE pin. But
`_waived()` threw the scope away and matched on the designator alone, and
three unrelated gates consulted it. The effect: that line silently excused
U1 — the board's only IC — from needing an archived reference design AND
from needing a design-basis row. Deleting every reference file and every
basis row still produced "every key part has an archived reference".

An escape hatch must be no wider than the thing it excuses. So scope is
matched, never ignored:

  * a numeric scope (`2.2`, `6.1`) waives THAT numbered design rule, on that
    pin, and nothing else;
  * `reference` waives the archived-reference requirement for that part;
  * `basis` waives the DESIGN_BASIS.md row for that part;
  * `datasheet` waives the datasheet-on-file requirement for that part.

Containment is mandatory, not opt-in
------------------------------------
Only lines under a `## Declared` heading declare anything. When that heading
is absent the old code fell back to parsing the WHOLE FILE — silently
restoring the exact behaviour that caused four of the five bugs. Two of five
projects were in that state and nothing said so. A missing heading now
waives nothing and reports why.
"""
from __future__ import annotations

import re
from pathlib import Path

# Scopes that are not design-rule numbers. Anything else must look like a
# rule number ("2.2"), or the line is not a waiver at all.
GATE_SCOPES = {'reference', 'basis', 'datasheet'}
_RULE_RE = re.compile(r'\d+(?:\.\d+)*$')
_REF_RE = re.compile(r'([A-Za-z]+[0-9]+)(?:\.([A-Za-z0-9]+))?$')
DECLARED_RE = re.compile(r'^#{2,}\s*Declared\s*$', re.M)


def parse(proj: Path):
    """Return (waivers, problems).

    waivers: list of (ref, pin, scope, reason) with ref/scope lowercased.
    problems: human-readable reasons this file waives less than it looks like.
    """
    f = Path(proj) / 'DEVIATIONS.md'
    if not f.is_file():
        return [], [f'no DEVIATIONS.md in {proj}']
    body = f.read_text()
    m = DECLARED_RE.search(body)
    if not m:
        return [], [
            f'{f}: no "## Declared" heading — nothing in this file waives '
            'anything. Put real waivers under a line reading exactly '
            '"## Declared"; text above it is documentation, not a waiver.']
    out, problems = [], []
    for raw in body[m.end():].splitlines():
        line = raw.strip()
        if line.startswith(('#', '>')) or line.count('|') < 2:
            continue
        if '~~' in line:
            # A struck-out row is a WITHDRAWN waiver. Stripping '~' as if it
            # were decoration re-activated one on tms-v3 the moment this
            # parser was written — a withdrawn deviation must never quietly
            # come back to life because of markdown syntax.
            continue
        cells = [c.strip() for c in line.split('|')]
        rm = _REF_RE.fullmatch(cells[0].strip('`* '))
        if not rm:
            continue                      # placeholders, prose, struck-out rows
        scope = cells[1].strip('`*~ ').lower()
        # The scope cell may read "2.2 decoupling"; take the leading token.
        head = scope.split()[0] if scope.split() else ''
        if head in GATE_SCOPES:
            scope = head
        elif _RULE_RE.fullmatch(head):
            scope = head
        else:
            problems.append(
                f'{f}: line for {rm.group(1)} has scope "{cells[1].strip()}" — '
                f'not a rule number and not one of {sorted(GATE_SCOPES)}; '
                'it waives nothing.')
            continue
        out.append((rm.group(1).lower(), (rm.group(2) or '').lower(),
                    scope, cells[2].strip()))
    return out, problems


def waived(proj: Path, ref: str, scope: str) -> bool:
    """Is `ref` excused from `scope`? Scope must match — see module docstring."""
    ws, _ = parse(proj)
    ref = ref.lower()
    scope = scope.lower()
    return any(r == ref and s == scope for r, _p, s, _why in ws)


def rule_waiver(proj: Path, key: str, rule: str):
    """Reason a specific `<ref>.<pin>` is excused from numbered `rule`, else None.

    Used by check_design_rules.py, which was carrying its own whole-file
    parser with no `## Declared` containment — so the template's example
    line `U2.3 | 2.2 | VREF_N ...` would have waived a real rule-2.2
    violation on U2 pin 3 of any board scaffolded by copying the template.
    """
    km = _REF_RE.fullmatch(key.strip())
    if not km:
        return None
    ref, pin = km.group(1).lower(), (km.group(2) or '').lower()
    for r, p, s, why in parse(proj)[0]:
        if r == ref and p == pin and s == rule.strip():
            return why
    return None
