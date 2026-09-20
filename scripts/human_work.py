#!/usr/bin/env python3
"""Everything waiting on a person, gathered from where it already lives.

Why this is GENERATED and never hand-written
--------------------------------------------
This workspace already deleted one hand-maintained status file. `BLOCKERS.md`
sat next to the generated `STATUS.md`, said different things, and was wrong on
the day it was removed — because a list a human updates by hand drifts from
the board the moment anyone forgets, and the forgetting is silent. Writing a
second one by hand would repeat that exactly.

So nothing here is authored. Every line is read back out of a file that is
already the authority for it:

  * unchecked `- [ ]` items in each board's SIGNOFF.md
  * `[OWNER]` markers in REQUIREMENTS.md and DESIGN_BASIS.md
  * currently-failing gates, by CALLING run_gates — never by re-reading a
    stored report, which is how audit_workflow.py twice drifted into
    disagreeing with the gate it was supposed to mirror

Delete this file and nothing is lost. Delete a SIGNOFF.md and the work is.

Ordering is by consequence, not by board: a wrong connector on a firing
circuit outranks a missing height limit on a breakout, and a list that buries
the first under the second is a list nobody triages from.

Usage:  python3 human_work.py [--write]
        --write refreshes HUMAN_WORK.md at the repo root.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / 'scripts'
sys.path.insert(0, str(SCRIPTS))

# Words that mark an item as safety-bearing. Deliberately narrow: inflating
# this list would put everything in the top bucket and destroy the ordering.
SAFETY = re.compile(
    r'(?i)\b(ignit|e-?match|igniter|pyro|firing|relay|battery|xt60|current '
    r'path|contact rating|nichrome|bridgewire|mains|high voltage|safety)\b')
FAB = re.compile(
    r'(?i)\b(lcsc|stock|sourceab|assembl|footprint|pinout|pin order|bom|'
    r'extended|fabricat|connector|datasheet)\b')


def _boards() -> list:
    out = []
    for d in sorted((REPO / 'projects').iterdir()):
        if d.is_dir() and next(d.glob('*.kicad_pcb'), None):
            out.append(d)
    return out


def _signoff(board: Path) -> list:
    f = board / 'SIGNOFF.md'
    if not f.is_file():
        return []
    items, lines = [], f.read_text().splitlines()
    for i, l in enumerate(lines):
        if re.match(r'\s{4,}', l):          # an indented example, not an item
            continue
        if re.match(r'\s*-\s*\[ \]', l):
            text = re.sub(r'^\s*-\s*\[ \]\s*', '', l).strip()
            # Pull in the continuation lines so the reason survives.
            for nxt in lines[i + 1:i + 3]:
                if re.match(r'\s{6,}\S', nxt) and not re.match(r'\s*-\s*\[', nxt):
                    text += ' ' + nxt.strip()
            items.append(('sign-off', text))
    return items


def _owner(board: Path) -> list:
    out = []
    for name in ('REQUIREMENTS.md', 'DESIGN_BASIS.md'):
        f = board / name
        if not f.is_file():
            continue
        for line in f.read_text().splitlines():
            if '[OWNER]' not in line:
                continue
            t = re.sub(r'^[\s\-*|>#]+', '', line).strip()
            if t.startswith('>') or len(t) < 20:
                continue
            out.append((f'decision ({name.split(".")[0].lower()})', t))
    return out


def _gates(board: Path) -> list:
    import run_gates                                          # noqa: PLC0415
    pcb = next(board.glob('*.kicad_pcb'), None)
    if pcb is None:
        return []
    out = []
    for name, fn, kind in run_gates.GATES:
        try:
            ok, detail = fn(pcb)
        except Exception as exc:                              # noqa: BLE001
            ok, detail = False, f'gate crashed: {exc}'
        if not ok and kind != 'HUMAN':      # HUMAN gates are the sign-off list
            out.append(('failing gate', f'{name} — {detail.splitlines()[0]}'))
    return out


def _rank(text: str) -> int:
    if SAFETY.search(text):
        return 0
    if FAB.search(text):
        return 1
    return 2


BUCKET = ['SAFETY — decide before this board is built or fired',
          'FABRICATION — decide before ordering',
          'REVIEW — decide before sign-off']


def _boilerplate(data: dict) -> set:
    """Checklist lines that are identical on most boards.

    The stock SIGNOFF template explains "Connectors are the real connector"
    with the example *a part labelled "XT60" that is a 2.54mm header*. Ranked
    on its full text, that illustration put a SAFETY flag on baro, imu and
    gnss — none of which has an XT60, or any current path worth the word.
    A register that cries safety on three boards out of four is one nobody
    triages from, so a line that appears on most boards is ranked on its own
    title and not on the example it happens to quote.
    """
    counts: dict = {}
    for rows in data.values():
        for _kind, text in rows:
            counts[text] = counts.get(text, 0) + 1
    threshold = max(2, len(data) // 2 + 1)
    return {t for t, n in counts.items() if n >= threshold}


def _title(text: str) -> str:
    m = re.match(r'\*\*(.+?)\*\*', text)
    return m.group(1) if m else text


def collect() -> dict:
    data = {}
    for b in _boards():
        data[b.name] = _signoff(b) + _owner(b) + _gates(b)
    generic = _boilerplate(data)
    for name, rows in data.items():
        data[name] = sorted(
            rows, key=lambda r: (_rank(_title(r[1]) if r[1] in generic else r[1]),
                                 r[0]))
    data['_generic'] = generic          # render() needs the same judgement
    return data


def render(data: dict) -> str:
    generic = data.pop('_generic', set())

    def rank(text):
        return _rank(_title(text) if text in generic else text)

    total = sum(len(v) for v in data.values())
    out = ['# Human Work Register', '',
           f'**{total} open item(s) across {len(data)} board(s).**', '',
           'Generated by `scripts/human_work.py`. Do not edit — every line is read',
           'from the file that owns it (`SIGNOFF.md`, `REQUIREMENTS.md`,',
           '`DESIGN_BASIS.md`) or from a live `run_gates.py` call. Edit those.',
           '']
    for rank_i, heading in enumerate(BUCKET):
        chunk = [(b, k, t) for b, rows in data.items()
                 for k, t in rows if rank(t) == rank_i]
        if not chunk:
            continue
        out += [f'## {heading}', '']
        for board in sorted({c[0] for c in chunk}):
            out.append(f'### {board}')
            for _b, kind, text in [c for c in chunk if c[0] == board]:
                out.append(f'- **[{kind}]** {text}')
            out.append('')
    return '\n'.join(out).rstrip() + '\n'


def main() -> int:
    data = collect()
    text = render(data)
    if '--write' in sys.argv:
        (REPO / 'HUMAN_WORK.md').write_text(text)
        print(f'wrote HUMAN_WORK.md — {sum(len(v) for v in data.values())} item(s)')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
