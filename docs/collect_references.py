#!/usr/bin/env python3
"""Download and archive reference designs, datasheets and vendor sources.

Why this exists
---------------
`pcb-design-workflow.md` Step 2.2 ("Collect Reference Designs") is the
richest section in the whole workflow: a three-tier vendor table, trust
ordering, format notes. Step 2.3 labels itself "HARD GATE — Do Not Skip"
and `.claude/rules/pcb-schematic.md` repeats that it is "a hard gate, not
optional."

Audited 2026-08-25: across FOUR boards there were ZERO stored reference
designs. No `reference-designs/` directory existed anywhere in the repo.
`fetch_reference_doc.py` — written specifically to fetch this material
correctly — was invoked by NOTHING; it appeared only in prose.

That is Failure Mode Zero again, one tier below where we last looked. The
back half of the pipeline got gates; the research half stayed prose. So the
most valuable step in PCB design ("learn how credible predecessors solved
this exact circuit, then justify every departure") was the single least
enforced step in the workspace.

The split this tool assumes
---------------------------
SEARCHING the web is Claude's job (WebSearch/WebFetch see the live index;
a script cannot). ARCHIVING is this tool's job, because archiving is where
the evidence gets lost:

  * a link that was read once and never saved cannot be re-checked
  * a dead link reported as "unavailable" hides whether anyone tried
  * WebFetch's summariser silently drops the pin-level ground truth that
    is the entire reason to read a reference design

So: Claude searches, this tool verifies + downloads + records provenance.
Nothing counts as a reference until it is a FILE ON DISK with a live-
verified source URL next to it.

Usage
-----
  collect_references.py suggest <PARTNO>
        Print canonical candidate URLs for a part across the Tier-1/2/3
        vendor sources, so the search starts from the trust ordering in
        workflow Step 2.2 instead of from a blank Google query.

  collect_references.py add <project> <PARTNO> <URL> [--kind ref|datasheet]
                            [--note "..."]
        Verify the URL is alive, download it, sanity-check the payload
        (an HTML error page saved as .pdf is the classic silent failure),
        file it under reference-designs/ or datasheets/, and append a
        provenance row to that folder's INDEX.md.

  collect_references.py verify <project>
        Re-check every archived file: present on disk, non-empty, real
        format, source URL still recorded. Offline-safe (does not re-hit
        the network unless --online is given).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Canonical per-vendor entry points, ordered by the trust tiers in
# pcb-design-workflow.md Step 2.2. These are SEARCH SEEDS, not guaranteed
# links — `add` verifies whatever URL is actually chosen.
SUGGEST = [
    ('Tier 1  mfr', 'TI',        'https://www.ti.com/product/{p}  -> Design & development -> Evaluation boards / Reference designs'),
    ('Tier 1  mfr', 'Analog',    'https://www.analog.com/en/products/{p}.html  -> Reference Circuits (CN-xxxx)'),
    ('Tier 1  mfr', 'ST',        'https://www.st.com/en/product/{p}  -> Tools & Software -> Evaluation boards'),
    ('Tier 1  mfr', 'NXP',       'https://www.nxp.com/search?keyword={p}  -> EVK schematic'),
    ('Tier 1  mfr', 'Microchip', 'https://www.microchip.com/en-us/product/{p}  -> Documentation'),
    ('Tier 1  mfr', 'Bosch',     'https://www.bosch-sensortec.com/  -> product -> shuttle board / app note'),
    ('Tier 1  mfr', 'u-blox',    'https://www.u-blox.com/  -> product -> Hardware Integration Manual'),
    ('Tier 1  mfr', 'TDK/Inven', 'https://invensense.tdk.com/  -> product -> EV board user guide'),
    ('Tier 2  open', 'Adafruit', 'https://github.com/adafruit/  search "{p}"  -> *.sch / *.brd (Eagle, EXACT values)'),
    ('Tier 2  open', 'SparkFun', 'https://github.com/sparkfun/  search "{p}"  -> Eagle/KiCad source'),
    ('Tier 2  open', 'Seeed',    'https://github.com/Seeed-Studio/  search "{p}"'),
    ('Tier 2  open', 'GitHub',   'https://github.com/search?q={p}+kicad_sch&type=code'),
    ('Tier 3  teach', "Phil's Lab", 'https://www.youtube.com/@PhilsLab  search "{p}" — layout rationale; many videos ship the KiCad project'),
    ('Tier 3  teach', 'Altium Academy', 'https://resources.altium.com/  search "{p}" — design rationale + rule-of-thumb sourcing'),
    ('Tier 3  teach', 'App notes', 'search: "{p}" application note filetype:pdf layout guidelines'),
]

KIND_DIR = {'ref': 'reference-designs', 'datasheet': 'datasheets'}

INDEX_HEADER = """# Reference / document archive

Provenance record. `docs/collect_references.py verify` and
`docs/check_research.py` read the `->` rows; the rest is for humans.

Format:  PART[, PART...]  ->  filename  # source-url | fetched YYYY-MM-DD | note

A reference that is not a file on this disk with a live-verified URL beside
it does not count. See pcb-design-workflow.md Step 2.2.

"""


def _sh(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def verify_url(url: str) -> tuple[bool, str]:
    """HEAD, then fall back to a ranged GET (many vendor CDNs 403 a HEAD)."""
    r = _sh(['curl', '-sSIL', '-o', '/dev/null', '-w', '%{http_code}',
             '--max-time', '25', url])
    code = (r.stdout or '').strip()[-3:]
    if code.startswith('2'):
        return True, code
    r = _sh(['curl', '-sSL', '-r', '0-1024', '-o', '/dev/null',
             '-w', '%{http_code}', '--max-time', '25', url])
    code2 = (r.stdout or '').strip()[-3:]
    return code2.startswith('2') or code2 == '206', code2 or code or '000'


def sniff(path: Path) -> str:
    """What did we ACTUALLY download? A vendor login wall saved as .pdf is
    the classic silent failure — the gate then sees a file and passes."""
    if not path.is_file() or path.stat().st_size == 0:
        return 'empty'
    head = path.read_bytes()[:2048]
    if head[:4] == b'%PDF':
        return 'pdf'
    if head[:2] == b'PK':
        return 'zip'
    low = head.lower()
    if b'<html' in low or b'<!doctype html' in low:
        return 'html'
    if b'<?xml' in low and b'eagle' in low:
        return 'eagle'
    if b'kicad_sch' in low or b'kicad_pcb' in low:
        return 'kicad'
    if b'<?xml' in low:
        return 'xml'
    return 'binary'


def cmd_suggest(part: str) -> int:
    print(f'=== reference-design search seeds for {part} ===')
    print('Trust order is Step 2.2. Work Tier 1 first; do not stop at Tier 3.\n')
    tier = None
    for t, name, tmpl in SUGGEST:
        if t != tier:
            print(f'{t}')
            tier = t
        print(f'   {name:<16} {tmpl.format(p=part)}')
    print('\nFor anything you need an EXACT value or pin from, download with:')
    print(f'   python3 docs/collect_references.py add <project> {part} <URL>')
    print('then parse it with docs/fetch_reference_doc.py (Eagle .sch -> real')
    print('pin-level nets; PDF -> rendered pages). WebFetch SUMMARISES and will')
    print('lose exactly the detail you came for.')
    return 0


def cmd_add(proj: Path, part: str, url: str, kind: str, note: str) -> int:
    out_dir = proj / KIND_DIR[kind]
    out_dir.mkdir(parents=True, exist_ok=True)

    alive, code = verify_url(url)
    if not alive:
        print(f'[DEAD] HTTP {code}  {url}')
        print('Report it as "verified dead, HTTP %s" — never as "couldn\'t fetch".' % code)
        return 1

    stem = re.sub(r'[^A-Za-z0-9._-]', '_', f'{part}_{Path(url).name or "doc"}')[:90]
    if '.' not in stem[-6:]:
        stem += '.pdf'
    dest = out_dir / stem
    r = _sh(['curl', '-sSL', '--max-time', '120', '-o', str(dest), url])
    if r.returncode != 0:
        print(f'[FAIL] download failed: {r.stderr.strip()[:200]}')
        return 1

    fmt = sniff(dest)
    if fmt in ('empty', 'html'):
        dest.unlink(missing_ok=True)
        print(f'[REJECT] URL returned {fmt}, not a document — this is a login '
              f'wall or an error page, not a reference. Not archived.')
        return 1

    # Name the file after what it ACTUALLY is. The '.pdf' default above is a
    # guess made before the bytes arrive, and it archived a KiCad schematic
    # as `ICM-42688.kicad_sch.pdf` — a filename that contradicts its own
    # contents. That is the exact mismatch `check_datasheets.py` now rejects,
    # and there is no reason to create it here and detect it there.
    EXT = {'pdf': '.pdf', 'zip': '.zip', 'eagle': '.sch',
           'kicad': '.kicad_sch', 'xml': '.xml'}
    want = EXT.get(fmt)
    if want and dest.suffix != want:
        fixed = dest.with_name(re.sub(r'\.(pdf|zip|xml)$', '', dest.name) + want)
        if fixed != dest:
            dest.rename(fixed)
            dest = fixed

    idx = out_dir / 'INDEX.md'
    if not idx.is_file():
        idx.write_text(INDEX_HEADER)
    kb = dest.stat().st_size // 1024
    line = (f'{part}  ->  {dest.name}  # {url} | fetched {date.today()} | '
            f'{fmt} {kb}KB{" | " + note if note else ""}\n')
    with idx.open('a') as fh:
        fh.write(line)
    print(f'[OK] {fmt} {kb}KB -> {dest.relative_to(REPO)}')
    print(f'     provenance recorded in {idx.relative_to(REPO)}')
    return 0


def read_index(idx: Path) -> list[tuple[list[str], str, str]]:
    """-> [(parts, filename, source_url)]"""
    rows = []
    if not idx.is_file():
        return rows
    for line in idx.read_text().splitlines():
        if '->' not in line or line.lstrip().startswith('#'):
            continue
        keys, rest = line.split('->', 1)
        fname, _, meta = rest.partition('#')
        fname = fname.strip()
        # A row's target must look like a real filename. The header of this
        # very file documents the `->` format in prose, and a naive reader
        # parsed those sentences as archive rows.
        # A row's target must look like a real filename. The header of this
        # very file documents the `->` format in prose, and a naive reader
        # parsed those sentences as archive rows.
        #
        # The first version of this test asked for a '.' within the last 6
        # characters, which silently rejected `ICM-42688.kicad_sch` — a
        # 10-character extension — so a correctly archived reference read as
        # "not archived" and the gate demanded a file that was already there.
        # A too-clever filter is its own kind of false negative.
        if not re.fullmatch(r'[A-Za-z0-9][\w.+-]*\.[A-Za-z0-9_]{1,12}', fname or ''):
            continue
        m = re.search(r'https?://\S+', meta)
        rows.append(([k.strip() for k in keys.split(',') if k.strip()],
                     fname, m.group(0).rstrip('|,') if m else ''))
    return rows


def cmd_verify(proj: Path, online: bool) -> int:
    bad = 0
    for kind, sub in KIND_DIR.items():
        d = proj / sub
        rows = read_index(d / 'INDEX.md')
        if not rows:
            print(f'  {sub}/: no INDEX.md rows')
            continue
        print(f'  {sub}/: {len(rows)} archived')
        for parts, fname, url in rows:
            f = d / fname
            fmt = sniff(f)
            probs = []
            if fmt == 'empty':
                probs.append('file missing or empty')
            elif fmt == 'html':
                probs.append('file is HTML (error/login page), not a document')
            if not url:
                probs.append('no source URL recorded')
            elif online:
                alive, code = verify_url(url)
                if not alive:
                    probs.append(f'source URL dead (HTTP {code})')
            if probs:
                bad += 1
                print(f'    [BAD]  {fname}: {"; ".join(probs)}')
    print('  all archived documents verified' if not bad
          else f'  {bad} archived document(s) failed verification')
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('suggest'); s.add_argument('part')
    a = sub.add_parser('add')
    a.add_argument('project'); a.add_argument('part'); a.add_argument('url')
    a.add_argument('--kind', choices=list(KIND_DIR), default='ref')
    a.add_argument('--note', default='')
    v = sub.add_parser('verify')
    v.add_argument('project'); v.add_argument('--online', action='store_true')
    n = ap.parse_args()

    if n.cmd == 'suggest':
        return cmd_suggest(n.part)
    proj = Path(n.project).resolve()
    if proj.is_file():
        proj = proj.parent
    if not proj.is_dir():
        print(f'no such project: {proj}')
        return 2
    if n.cmd == 'add':
        return cmd_add(proj, n.part, n.url, n.kind, n.note)
    return cmd_verify(proj, n.online)


if __name__ == '__main__':
    sys.exit(main())
