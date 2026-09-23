#!/usr/bin/env python3
"""Check a routed board against docs/DESIGN_RULES.md, using real pad geometry.

Why this exists
---------------
CLAUDE.md calls docs/DESIGN_RULES.md MANDATORY. Nothing checked it. DRC
does not: DRC answers "can JLCPCB build this?", not "is this a good
layout?". So a board can pass DRC with zero violations while breaking the
single rule the document calls "the #1 beginner mistake".

That is what TMS V3 did. Components were placed on a tidy arithmetic grid
(x = 22/30/38, y = 25/28/31 ...) that looks orderly and has no relationship
to which pin each part serves. Decoupling caps sat 8mm from the IC they
decouple, the 7.68MHz crystal sat 10mm from its oscillator pins, and the
regulator's stability caps sat 12mm from the regulator. Every one of those
is a numbered rule in the document, and the board still reported clean.

Rules checked here (section numbers refer to docs/DESIGN_RULES.md):

  2.2  decoupling cap within 2mm pad-to-pad of the power pin it serves
  2.4  bulk (>=1uF) caps allowed further out, but still on the same rail
  5.1  crystal within 5mm of its IC's oscillator pins
  5.1  crystal load caps within 3mm of the crystal pins
  6.1  regulator input/output caps within 5mm of the regulator pin
  1.2  heat sources (regulator, relay) >=15mm from precision ADC inputs

Run:  kipython check_design_rules.py <board.kicad_pcb>
Exit 0 if every rule passes, 1 otherwise.
"""
import math
import re
import sys
from collections import defaultdict

import pcbnew

# The rules this script can actually decide from board geometry, and the
# size of the document it is named after. Kept next to each other on
# purpose: the gap between them is the honest limit of the check.
EXECUTABLE_RULES = ('1.2', '2.2', '5.1', '6.1')
DOC_RULE_COUNT = 42

MM = 1_000_000
POWER_RE = re.compile(r'^(\+|VDD|VCC|AVDD|DVDD|VREF|VA|VD|\d+V)', re.I)


def val_to_farads(v: str) -> float:
    m = re.match(r'([\d.]+)\s*([munp]?)F?$', v.strip(), re.I)
    if not m:
        return 0.0
    return float(m.group(1)) * {'': 1, 'm': 1e-3, 'u': 1e-6, 'n': 1e-9, 'p': 1e-12}[m.group(2).lower()]


def main() -> None:
    board = pcbnew.LoadBoard(sys.argv[1])
    pads = []
    meta = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        meta[ref] = fp.GetValue()
        for pad in fp.Pads():
            net = pad.GetNetname()
            p = pad.GetPosition()
            bb = pad.GetBoundingBox()
            pads.append((ref, str(pad.GetPadName()), net, p.x / MM, p.y / MM,
                         (bb.GetLeft() / MM, bb.GetTop() / MM,
                          bb.GetRight() / MM, bb.GetBottom() / MM)))

    by_ref = defaultdict(list)
    by_net = defaultdict(list)
    for rec in pads:
        by_ref[rec[0]].append(rec)
        by_net[rec[2]].append(rec)

    def dist(a, b):
        """Edge-to-edge gap between two pads, in mm — which is what
        docs/DESIGN_RULES.md means by "2mm pad-to-pad". Measuring centre to
        centre instead reports a correctly-placed 0603 beside an SSOP pin
        as a violation, because it charges the design for half of each pad.
        0.0 means the copper touches or overlaps."""
        ax0, ay0, ax1, ay1 = a[5]
        bx0, by0, bx1, by1 = b[5]
        gx = max(0.0, max(bx0 - ax1, ax0 - bx1))
        gy = max(0.0, max(by0 - ay1, ay0 - by1))
        return math.hypot(gx, gy)

    def is_ic(ref):
        return ref[0] == 'U'

    fails, notes = [], []

    # --- 2.2  decoupling proximity ------------------------------------
    # Pin-centric, not cap-centric. The rule is "every power pin has a
    # bypass cap within 2mm", so the question to ask of each IC power pin
    # is "where is your NEAREST cap". Asking it cap-first instead reports
    # a bulk reservoir cap sitting legitimately far away as a violation.
    for ref, pd in by_ref.items():
        if not is_ic(ref):
            continue
        if '780' in (meta.get(ref, '') + ref):
            continue      # linear regulators are governed by rule 6.1, not 2.2:
                          # a TO-263's output cap spec is 5mm, not 2mm
        for pin in pd:
            if not POWER_RE.match(pin[2] or ''):
                continue
            best = None
            for cand in by_net[pin[2]]:
                if not cand[0].startswith('C'):
                    continue
                f = val_to_farads(meta.get(cand[0], ''))
                if not (0 < f <= 1e-6):        # bulk caps exempt (rule 2.4)
                    continue
                d = dist(pin, cand)
                if best is None or d < best[0]:
                    best = (d, cand[0])
            if best is None:
                fails.append(('2.2 every power pin needs a bypass cap',
                              f'{ref}.{pin[1]} [{pin[2]}]: no <=1uF cap on this net'))
                continue
            d, cref = best
            line = f'{ref}.{pin[1]} [{pin[2]}] -> nearest {cref} ({meta[cref]}): {d:.2f}mm'
            (notes if d <= 2.0 else fails).append(
                ('2.2 decoupling <=2mm', line + ('' if d <= 2.0 else '  EXCEEDS 2mm')))

    # --- 5.1  crystal proximity ----------------------------------------
    for ref, pd in by_ref.items():
        if not ref.startswith('Y'):
            continue
        best = None
        for p in pd:
            for cand in by_net[p[2]]:
                if is_ic(cand[0]):
                    d = dist(p, cand)
                    if best is None or d < best[0]:
                        best = (d, cand[0], cand[1])
        if best:
            d, ic, pin = best
            line = f'{ref} -> {ic}.{pin}: {d:.2f}mm'
            (notes if d <= 5.0 else fails).append(
                ('5.1 crystal <=5mm from IC', line + ('' if d <= 5.0 else '  EXCEEDS 5mm')))
        # load caps within 3mm
        for cref, cpd in by_ref.items():
            if not cref.startswith('C'):
                continue
            f = val_to_farads(meta.get(cref, ''))
            if not (0 < f <= 100e-12):
                continue
            dmin = min(dist(a, b) for a in cpd for b in pd)
            line = f'{cref} ({meta[cref]}) -> {ref}: {dmin:.2f}mm'
            (notes if dmin <= 3.0 else fails).append(
                ('5.1 load cap <=3mm from crystal', line + ('' if dmin <= 3.0 else '  EXCEEDS 3mm')))

    # --- 6.1  regulator stability caps ---------------------------------
    # Same pin-centric framing: each regulator power pin needs A cap within
    # 5mm, not "every cap on the rail must be within 5mm of the regulator".
    for ref, pd in by_ref.items():
        if not (ref.startswith('U') and '780' in (meta.get(ref, '') + ref)):
            continue
        for pin in pd:
            if not POWER_RE.match(pin[2] or ''):
                continue
            caps = [c for c in by_net[pin[2]] if c[0].startswith('C')]
            if not caps:
                fails.append(('6.1 regulator pin needs a cap',
                              f'{ref}.{pin[1]} [{pin[2]}]: no cap on this rail'))
                continue
            d, cref = min((dist(pin, c), c[0]) for c in caps)
            line = f'{ref}.{pin[1]} [{pin[2]}] -> nearest {cref} ({meta[cref]}): {d:.2f}mm'
            (notes if d <= 5.0 else fails).append(
                ('6.1 regulator cap <=5mm', line + ('' if d <= 5.0 else '  EXCEEDS 5mm')))

    # --- 1.2  heat sources away from precision analog -------------------
    hot = [r for r in by_ref if r.startswith('K') or ('780' in meta.get(r, ''))]
    analog_nets = [n for n in by_net if re.search(r'AIN|VREF|LC_|EXC', n or '', re.I)]
    for h in hot:
        worst = None
        for n in analog_nets:
            for cand in by_net[n]:
                if cand[0] == h:
                    continue
                d = min(dist(cand, p) for p in by_ref[h])
                if worst is None or d < worst[0]:
                    worst = (d, cand[0], n)
        if worst:
            d, ref2, n = worst
            line = f'{h} ({meta.get(h,"")}) -> {ref2} [{n}]: {d:.1f}mm'
            (notes if d >= 15.0 else fails).append(
                ('1.2 heat source >=15mm from analog', line + ('' if d >= 15.0 else '  TOO CLOSE (<15mm)')))

    # Declared deviations. A rule you cannot meet is an engineering
    # decision, and engineering decisions get written down with a reason —
    # they do not get quietly dropped from the report. DEVIATIONS.md lines
    # look like:   U2.3 | 2.2 decoupling | reason...
    # Anything not listed there is a hard violation.
    from pathlib import Path as _P
    _here = _P(__file__).resolve().parents[2]
    if str(_here) not in sys.path:
        sys.path.insert(0, str(_here))
    from pcb_copilot.deviations import rule_waiver          # the ONE parser

    # This block used to carry its own reading of DEVIATIONS.md: whole file,
    # no "## Declared" containment. Two parsers for one file is the same
    # defect as two build paths for one board, and this copy was the looser
    # of the two — the scaffolded template's own example line
    # `U2.3 | 2.2 | VREF_N ...` would have waived a real rule-2.2 violation
    # on U2 pin 3 of any board started by copying the template directory.
    proj = _P(sys.argv[1]).parent
    waived, still = [], []
    for rule, line in fails:
        key = line.split()[0].strip()
        short = rule.split()[0]
        why = rule_waiver(proj, key, short)
        if why:
            waived.append((rule, line, why))
        else:
            still.append((rule, line))
    fails = still

    print(f'=== docs/DESIGN_RULES.md geometric checks: {sys.argv[1].split("/")[-1]} ===')
    if waived:
        print(f'\n{len(waived)} DECLARED DEVIATION(S) (DEVIATIONS.md):')
        for rule, line, why in waived:
            print(f'  [{rule}]  {line}')
            print(f'      reason: {why}')
    if fails:
        print(f'\n{len(fails)} VIOLATION(S):')
        for rule, line in fails:
            print(f'  [{rule}]  {line}')
    passed = defaultdict(int)
    for rule, _ in notes:
        passed[rule] += 1
    if passed:
        print('\npassing:')
        for rule, n in sorted(passed.items()):
            print(f'  [{rule}]  {n} ok')
    # Say what this actually covers. The gate is named after the whole of
    # docs/DESIGN_RULES.md, which has 42 numbered subsections; FOUR of them
    # are geometric enough to check from a .kicad_pcb. A gate whose name
    # promises a document and whose code delivers a tenth of it teaches
    # people to read "0 violations" as "the rules are met". They are not
    # met, they are un-contradicted — and the rest of the document is the
    # human review in Phase 5, not something this script has looked at.
    print(f'\nRESULT: {len(fails)} violation(s), {len(notes)} check(s) passed')
    print(f'SCOPE: geometric rules {", ".join(EXECUTABLE_RULES)} only '
          f'({len(EXECUTABLE_RULES)} of {DOC_RULE_COUNT} numbered subsections in '
          'docs/DESIGN_RULES.md). The remainder are not machine-checkable from '
          'the board file and are covered by the Phase 5 human review.')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
