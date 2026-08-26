#!/usr/bin/env python3
"""Gate the RESEARCH half of the workflow — everything before schematic.

Why this exists
---------------
The workspace gated the back half (ERC, placement, design rules, DRC,
sign-off) and left the front half entirely in prose. Audit, 2026-08-25:

  Phase 1  requirements       no artifact on any board, no gate
  Step 2.2 reference designs  ZERO stored on 4 boards; no such folder existed
  Step 2.3 "HARD GATE"        labelled a hard gate in TWO docs; nothing ran
  Step 2.4 LCSC sourcing      44 of 53 TMS V3 parts had no LCSC number
  design rationale            no artifact; "why" lived only in chat scrollback

Reference designs are the highest-value input to a board and were the least
enforced thing in the repo. PCB design, like code, is mostly learning how
credible predecessors solved the same circuit and then justifying every
departure. A departure nobody wrote down is indistinguishable from an
oversight — that is the entire failure mode.

How this stays USABLE
---------------------
Every finding here has an escape hatch: one line in the board's
DEVIATIONS.md naming the part and the reason clears it. The gate does not
demand you find a reference that does not exist; it demands you say so. So
it blocks CLAIMING DONE, never designing. Nothing here stops a build — the
`research` pipeline stage is advisory and reports without halting.

Usage:  check_research.py <board.kicad_pcb> [--json]
Exit 0 when every BLOCK-severity check passes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'docs'))

PASSIVE = ('R', 'C', 'L', 'TP', 'FID', 'H', 'LED', 'D', 'SW', 'F', 'JP')
MODULE_HINTS = ('teensy', 'xbee', 'arduino', 'esp', 'raspberry', 'pico',
                'feather', 'nucleo', 'module', 'socket')
REQUIRED_SECTIONS = ['Purpose', 'Electrical', 'Mechanical', 'Interfaces',
                     'Environment', 'Success criteria']
# `<[a-z ]+>` missed every multi-word placeholder in our own template
# ("<X x Y mm>", "<What the board does, in one paragraph...>") — so a
# freshly scaffolded, entirely unfilled spec passed 4 of 6 sections.
PLACEHOLDER = re.compile(r'\b(TBD|TODO|FILL ?ME)\b|<[^>\n]{2,120}>', re.I)


def _blocks(text: str):
    i = 0
    while True:
        i = text.find('(footprint "', i)
        if i < 0:
            return
        depth, j = 0, i
        while j < len(text):
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield text[i:j + 1]
        i = j


def _prop(block: str, name: str) -> str:
    """Read a footprint property, in EITHER of KiCad's two spellings.

    Modern footprints carry `(property "Reference" "J9")`. Footprints that
    came from an older library — or that a tool wrote in the legacy form —
    carry `(fp_text reference "J9")` instead. This only understood the
    first, and the consequence was not a missing field but a MISSING PART:
    tms-v3's XBee socket J9 uses the legacy form, so `inventory()` never
    returned it at all. It was invisible to the sourcing gate (which
    therefore reported "every part sourced" while J9 had no part number),
    invisible to key-part detection, and invisible to the reference-design
    gate. A part the gates cannot see is worse than a part they fail on.
    """
    m = re.search(r'\(property\s+"%s"\s+"([^"]*)"' % re.escape(name), block)
    if m:
        return m.group(1)
    legacy = {'Reference': 'reference', 'Value': 'value'}.get(name)
    if legacy:
        m = re.search(r'\(fp_text\s+%s\s+"([^"]*)"' % legacy, block)
        if m:
            return m.group(1)
    return ''


def _lcsc(block: str) -> str:
    for key in ('LCSC', 'LCSC Part #', 'LCSC Part', 'JLCPCB', 'JLCPCB Part'):
        v = _prop(block, key)
        if v.strip():
            return v.strip()
    m = re.search(r'"(C\d{4,})"', block)
    return m.group(1) if m else ''


def inventory(pcb_text: str):
    """-> [(ref, value, pads, lcsc, is_key)]

    A KEY part is one whose circuit you are supposed to have learned from
    somebody: an IC of >=8 pins, or any plug-in module socket. A 3-pin LDO
    or a 2-pin passive is not worth a reference hunt, and demanding one is
    how a gate gets ignored."""
    out = []
    for blk in _blocks(pcb_text):
        ref = _prop(blk, 'Reference')
        if not ref:
            continue
        val = _prop(blk, 'Value')
        pads = blk.count('(pad "')
        base = (re.match(r'[A-Za-z]+', ref) or re.match(r'.*', ref)).group(0)
        is_module = any(h in val.lower() for h in MODULE_HINTS)
        is_passive = base in PASSIVE and not is_module
        is_key = is_module or (not is_passive and pads >= 8)
        out.append((ref, val, pads, _lcsc(blk), is_key))
    return out


def _waived(proj: Path, ref: str, scope: str) -> bool:
    """Is `ref` excused from `scope`? Delegates to the ONE parser.

    This function used to carry its own reading of DEVIATIONS.md and to
    ignore the scope field entirely, matching on the designator alone. That
    let a narrow waiver of one numbered decoupling rule on one pin
    (`U1.5 | 2.2 | Pad 5 is SDO...`) silently excuse that part from needing
    an archived reference design AND from needing a design-basis row —
    three unrelated gates reading one line and each taking it as blanket
    permission. See docs/deviations.py for the full account.
    """
    from deviations import waived
    return waived(proj, ref, scope)


def _deviation_problems(proj: Path) -> list:
    """Reasons this board's DEVIATIONS.md waives less than it appears to.

    Surfaced in gate output rather than swallowed: a file whose waivers
    silently do nothing is the same hazard as a waiver that does too much.
    """
    from deviations import parse
    return parse(proj)[1]


# ---------------------------------------------------------------- checks

def check_requirements(proj: Path, inv) -> tuple[bool, str]:
    f = proj / 'REQUIREMENTS.md'
    if not f.is_file():
        return False, ('no REQUIREMENTS.md — Phase 1 produced no artifact. '
                       'Scaffold: python3 docs/run_gates.py --init ' + str(proj))
    txt = f.read_text()
    missing = [s for s in REQUIRED_SECTIONS
               if not re.search(r'^#+.*' + re.escape(s), txt, re.I | re.M)]
    unfilled = [s for s in REQUIRED_SECTIONS if s not in missing
                and PLACEHOLDER.search(_section(txt, s))]
    # A heading with nothing under it is not a captured requirement. This
    # check tested only for <angle-bracket> placeholders, so DELETING a
    # section's body passed while leaving the template text failed — the
    # opposite of the intent. Emptying the entire Electrical section of
    # baro-bmp390 still reported "6 sections present and filled".
    # MIN_BODY is deliberately low: it is a floor against blank, not an
    # attempt to judge whether a requirement is any good.
    MIN_BODY = 40
    empty = [s for s in REQUIRED_SECTIONS if s not in missing and s not in unfilled
             and len(_strip_md(_section(txt, s))) < MIN_BODY]
    if missing or unfilled or empty:
        bits = []
        if missing:
            bits.append('missing section(s): ' + ', '.join(missing))
        if unfilled:
            bits.append('still placeholder: ' + ', '.join(unfilled))
        if empty:
            bits.append('heading present but empty: ' + ', '.join(empty))
        return False, '; '.join(bits)
    return True, f'{len(REQUIRED_SECTIONS)} sections present and filled'


def _strip_md(s: str) -> str:
    """Body text with markdown scaffolding removed, for emptiness tests."""
    s = re.sub(r'^\s*[-*|>#]+\s*', '', s, flags=re.M)
    return re.sub(r'\s+', ' ', s).strip()


def _section(txt: str, name: str) -> str:
    m = re.search(r'^(#+).*' + re.escape(name) + r'.*$', txt, re.I | re.M)
    if not m:
        return ''
    depth = len(m.group(1))
    rest = txt[m.end():]
    nxt = re.search(r'^#{1,%d}\s' % depth, rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def check_references(proj: Path, inv) -> tuple[bool, str]:
    from collect_references import read_index
    idx = proj / 'reference-designs' / 'INDEX.md'
    rows = read_index(idx)
    covered = ' '.join(' '.join(p) for p, _, _ in rows).lower()
    key = [(r, v) for r, v, _, _, k in inv if k]
    if not key:
        return True, 'no key parts on this board'
    missing, waived = [], []
    for ref, val in key:
        hit = ref.lower() in covered or (len(val) > 3 and
              re.sub(r'[^a-z0-9]', '', val.lower())[:8] in
              re.sub(r'[^a-z0-9]', '', covered))
        if hit:
            continue
        (waived if _waived(proj, ref, 'reference') else missing).append(f'{ref} ({val})')
    n_files = len(list((proj / 'reference-designs').glob('*'))) - 1 if idx.is_file() else 0
    head = (f'{len(key)} key part(s); {len(rows)} archived reference(s), '
            f'{max(n_files, 0)} file(s) on disk')
    if waived:
        head += f'; {len(waived)} waived in DEVIATIONS.md'
    if missing:
        return False, (head + '\nNO REFERENCE: ' + ', '.join(sorted(missing)) +
                       '\nSearch seeds:  python3 docs/collect_references.py suggest <PART>'
                       '\nArchive it:    python3 docs/collect_references.py add ' +
                       str(proj) + ' <PART> <URL>'
                       '\nOr record in DEVIATIONS.md why no reference exists for it.')
    return True, head + '; every key part has an archived reference'


def check_archive_integrity(proj: Path, inv) -> tuple[bool, str]:
    """Every archived document is real, and every archived document is sourced.

    This walked INDEX.md rows only, which made it a check on the rows a
    person chose to write rather than on the archive. A datasheet sitting
    in datasheets/ with no INDEX row was invisible: baro-bmp390's BMP390
    PDF satisfied the datasheet gate by filename and had no recorded
    origin at all, so "which revision, from where?" — the first question
    of any datasheet dispute — had no answer on disk.

    Un-sourced is not a lesser problem than un-archived. A document whose
    provenance nobody wrote down cannot be re-fetched, re-verified, or
    checked for a newer revision, and that is the whole reason the archive
    exists rather than a browser tab.
    """
    from collect_references import read_index, sniff
    bad, total = [], 0
    for sub in ('reference-designs', 'datasheets'):
        d = proj / sub
        listed = set()
        for parts, fname, url in read_index(d / 'INDEX.md'):
            listed.add(fname)
            total += 1
            fmt = sniff(d / fname)
            if fmt == 'empty':
                bad.append(f'{fname}: missing/empty')
            elif fmt == 'html':
                bad.append(f'{fname}: HTML error or login page, not a document')
            elif not url:
                bad.append(f'{fname}: no source URL recorded')
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.name == 'INDEX.md' or f.name.startswith('.'):
                continue
            if f.name in listed:
                continue
            total += 1
            bad.append(f'{f.name}: on disk but not in {sub}/INDEX.md '
                       f'(no source URL, no provenance)')
    if not total:
        return True, 'nothing archived yet'
    if bad:
        return False, (f'{total} archived; {len(bad)} bad\n' +
                       '\n'.join('  ' + b for b in bad[:8]))
    return True, f'{total} archived document(s) present, real format, sourced'


def check_design_basis(proj: Path, inv) -> tuple[bool, str]:
    """A basis ROW is only real if it names a source and reaches a verdict.

    First version just asked "does the file mention U1?" — and passed on the
    scaffolded template, whose example row literally reads `<U1>`. A check
    that a blank template satisfies is worse than no check: it certifies the
    thing it was written to catch."""
    f = proj / 'DESIGN_BASIS.md'
    key = [(r, v) for r, v, _, _, k in inv if k]
    if not key:
        return True, 'no key parts on this board'
    if not f.is_file():
        return False, ('no DESIGN_BASIS.md — every key part\'s circuit should '
                       'name what it was learned from (Step 2.3 comparison).')
    real = []
    for line in f.read_text().splitlines():
        if not line.strip().startswith('|') or PLACEHOLDER.search(line):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 7 or set(cells[0]) <= set('-: '):
            continue
        if not cells[5] or not re.match(r'(?i)match|deviate', cells[6]):
            continue                       # no source, or no verdict reached
        real.append(cells)
    # A row's Ref cell may name several parts ("J7, J8") or a specific pin
    # ("U3.13"). Matching the whole cell verbatim counted neither as
    # covering J7 nor U3, so a file with a correct, sourced row for every
    # key part still reported them all missing. Split the cell into
    # designators and drop any pin suffix — the row documents the PART.
    cited = set()
    for c in real:
        for tok in re.split(r'[,/\s]+', c[0]):
            m = re.match(r'([A-Za-z]+[0-9]+)(?:\.[A-Za-z0-9]+)?$', tok.strip('`*'))
            if m:
                cited.add(m.group(1).lower())
    missing = [f'{r} ({v})' for r, v in key
               if r.lower() not in cited and not _waived(proj, r, 'basis')]
    if missing:
        return False, (f'{len(key)} key part(s), {len(real)} complete basis row(s); '
                       'no sourced+decided row for: ' + ', '.join(sorted(missing)[:8]) +
                       '\nA row counts only with a Source and a verdict of '
                       'Match or Deviate: <reason>.')
    return True, f'{len(key)} key part(s), {len(real)} sourced basis row(s)'


def check_deviations(proj: Path, inv) -> tuple[bool, str]:
    """The escape hatch itself must work, and must be visibly scoped.

    Every gate here honours DEVIATIONS.md, so a malformed one is not a
    cosmetic problem: it is either a waiver that quietly does nothing (the
    author believes a rule is excused; it is not) or — before scoping — a
    waiver that quietly did far too much. Both failure modes are silent by
    construction, which is exactly the kind of thing this repo has learned
    to put a check on rather than a paragraph.
    """
    f = proj / 'DEVIATIONS.md'
    if not f.is_file():
        return True, 'no DEVIATIONS.md — nothing waived'
    from deviations import parse, GATE_SCOPES
    ws, problems = parse(proj)
    if problems:
        return False, ('DEVIATIONS.md waives less than it appears to:\n' +
                       '\n'.join('  ' + x.split(': ', 1)[-1] for x in problems) +
                       '\n  Scope must be a rule number (e.g. 2.2) or one of '
                       + ', '.join(sorted(GATE_SCOPES)) + '.')
    by = {}
    for _r, _p, s, _w in ws:
        by[s] = by.get(s, 0) + 1
    detail = ', '.join(f'{n}x {s}' for s, n in sorted(by.items())) or 'none'
    return True, f'{len(ws)} declared waiver(s): {detail}'


def check_sourcing(proj: Path, inv) -> tuple[bool, str]:
    need = [(r, v) for r, v, _, _, _ in inv
            if not (re.match(r'[A-Za-z]+', r) or re.match(r'.*', r)).group(0) in ('TP', 'FID', 'H')]
    have = [(r, v) for r, v, _, l, _ in inv if l]
    pct = (100 * len(have) // len(need)) if need else 100
    reg = []
    for tbl, want in (('sym-lib-table', 'jlcpcb'), ('fp-lib-table', 'jlcpcb')):
        p = proj / tbl
        if not p.is_file() or want not in p.read_text():
            reg.append(tbl)
    bits = [f'LCSC part numbers on {len(have)}/{len(need)} sourceable parts ({pct}%)']
    if reg:
        bits.append('jlcpcb library NOT registered in: ' + ', '.join(reg))
    ok = pct >= 80 and not reg
    if not ok:
        bits.append('Source with: mcp kicad-jlcpcb lcsc_search / fetch_part_library; '
                    'an unsourced part cannot be assembled by JLCPCB.')
    return ok, '\n'.join(bits)


# BLOCK  = must pass (or be waived in DEVIATIONS.md) before "ready"
# ADVISE = reported, never changes the exit code. Used where the right
#          answer genuinely varies by board, so the gate stays credible.
CHECKS = [
    ('Phase 1   requirements captured', check_requirements,      'BLOCK'),
    ('Step 2.2  reference designs archived', check_references,   'BLOCK'),
    ('Step 2.2  archive integrity', check_archive_integrity,     'BLOCK'),
    # BLOCK, not ADVISE, from 2026-08-26. Every design choice must be
    # documented against the datasheet and reference design actually
    # collected on disk, so an undocumented key part is an unfinished board,
    # not a note for later.
    #
    # Safe to design against because of the two-speed split: the pipeline's
    # `research` stage is advisory and never halts a build; this only bites
    # at the `gates` stage, where "done" is decided. Escape hatch unchanged
    # — one line in DEVIATIONS.md naming the part.
    ('Step 2.3  design basis cited', check_design_basis,         'BLOCK'),
    ('Escape hatch  DEVIATIONS.md well-formed', check_deviations, 'BLOCK'),
    ('Step 2.4  LCSC sourcing', check_sourcing,                  'ADVISE'),
]


def run(pcb: Path):
    inv = inventory(pcb.read_text())
    proj = pcb.parent
    out = []
    for name, fn, sev in CHECKS:
        try:
            ok, detail = fn(proj, inv)
        except Exception as exc:                            # noqa: BLE001
            ok, detail = False, f'check crashed: {exc}'
        out.append({'name': name, 'ok': ok, 'severity': sev, 'detail': detail})
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pcb = Path(sys.argv[1]).resolve()
    res = run(pcb)
    if '--json' in sys.argv:
        print(json.dumps(res, indent=2))
    else:
        print(f'=== research gates: {pcb.name} ===')
        for r in res:
            mark = 'PASS' if r['ok'] else ('FAIL' if r['severity'] == 'BLOCK' else 'WARN')
            print(f'  [{mark}] {r["name"]}')
            for ln in r['detail'].splitlines():
                print(f'         {ln}')
    hard = [r for r in res if not r['ok'] and r['severity'] == 'BLOCK']
    soft = [r for r in res if not r['ok'] and r['severity'] == 'ADVISE']
    if '--json' not in sys.argv:
        # A trailing human line after the JSON body made json.loads() fail,
        # and run_gates reported "research check did not run" — a machine
        # format with prose appended is not a machine format.
        print(f'\nRESULT: {len(hard)} blocking, {len(soft)} advisory')
    return 1 if hard else 0


if __name__ == '__main__':
    sys.exit(main())
