#!/usr/bin/env python3
"""Produce a complete, JLCPCB-ready fabrication package for a board.

Why this is not just `kicad-cli export gerbers`
-----------------------------------------------
Two things bite at the ordering step and neither is obvious until the
upload is rejected:

1. **The BOM must carry LCSC part numbers, and `kicad-cli sch export bom`
   reads the SCHEMATIC.** Part numbers in this workspace are stamped onto
   PCB FOOTPRINTS, so the schematic BOM comes out with an empty LCSC
   column — a file that looks complete and orders nothing. This builds the
   BOM from the .kicad_pcb, which is the artifact that actually gets
   fabricated and the one the numbers are on.

2. **JLCPCB wants its own column names and its own CPL layout.** "Comment /
   Designator / Footprint / LCSC Part #" for the BOM, and
   "Designator / Mid X / Mid Y / Layer / Rotation" for the CPL, with Y
   positive-up relative to the board origin. kicad-cli's native CSV uses
   neither.

Parts with no LCSC number are written to the BOM with an empty part column
and listed separately at the end, rather than being dropped: a connector
you intend to hand-solder should appear in the BOM you keep, and be absent
only from the assembly order.

Usage:  python3 docs/export_fab.py <board.kicad_pcb>
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

KICAD_CLI = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')

# Reference prefixes that are board features, not orderable parts.
NON_PARTS = ('TP', 'FID', 'H', 'MH', 'LOGO', 'REF')


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
    m = re.search(r'\(property\s+"%s"\s+"([^"]*)"' % re.escape(name), block)
    if m:
        return m.group(1)
    legacy = {'Reference': 'reference', 'Value': 'value'}.get(name)
    if legacy:
        m = re.search(r'\(fp_text\s+%s\s+"([^"]*)"' % legacy, block)
        if m:
            return m.group(1)
    return ''


def board_bbox(text: str):
    """(min_x, min_y, max_x, max_y) of the Edge_Cuts outline, in KiCad mm."""
    xs, ys = [], []
    for m in re.finditer(r'\(gr_(?:line|rect)\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)'
                         r'\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)'
                         r'(?:(?!\(gr_).)*?\(layer\s+"Edge\.Cuts"\)', text, re.S):
        xs += [float(m.group(1)), float(m.group(3))]
        ys += [float(m.group(2)), float(m.group(4))]
    for m in re.finditer(r'\(gr_arc[\s\S]{0,400}?\(layer\s+"Edge\.Cuts"\)', text):
        for mm in re.finditer(r'\((?:start|mid|end)\s+([-\d.]+)\s+([-\d.]+)\)', m.group(0)):
            xs.append(float(mm.group(1)))
            ys.append(float(mm.group(2)))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def main() -> None:
    pcb = Path(sys.argv[1]).resolve()
    proj, name = pcb.parent, pcb.stem
    out = proj / 'fabrication'
    out.mkdir(exist_ok=True)
    text = pcb.read_text()

    print(f'=== fabrication package: {name} ===')

    for args, label in (
        (['pcb', 'export', 'gerbers', '--output', str(out), str(pcb)], 'gerbers'),
        (['pcb', 'export', 'drill', '--output', str(out) + '/',
          '--format', 'excellon', '--excellon-separate-th', str(pcb)], 'drill'),
    ):
        r = subprocess.run([str(KICAD_CLI)] + args, capture_output=True, text=True)
        print(f'  [{"ok" if r.returncode == 0 else "FAIL"}] {label}')

    # ---- BOM, built from the BOARD so the LCSC numbers are present -------
    groups: dict[tuple, list[str]] = {}
    for b in _blocks(text):
        ref = _prop(b, 'Reference')
        if not ref:
            continue
        base = re.match(r'[A-Za-z]+', ref)
        if base and base.group(0) in NON_PARTS:
            continue
        lib = re.search(r'\(footprint\s+"([^"]+)"', b)
        key = (_prop(b, 'Value'),
               (lib.group(1) if lib else '').split(':')[-1],
               _prop(b, 'LCSC Part') or _prop(b, 'LCSC'))
        groups.setdefault(key, []).append(ref)

    bom = out / f'{name}-bom.csv'
    unsourced = []
    with bom.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (val, fp, lcsc), refs in sorted(groups.items(), key=lambda k: k[0][0]):
            refs = sorted(refs, key=lambda r: (re.sub(r'\d', '', r),
                                               int(re.sub(r'\D', '', r) or 0)))
            w.writerow([val, ','.join(refs), fp, lcsc])
            if not lcsc:
                unsourced.append(f'{val} ({",".join(refs)})')
    print(f'  [ok] BOM   -> {bom.name}  ({len(groups)} line(s))')

    # ---- CPL -------------------------------------------------------------
    tmp = out / '_pos.csv'
    r = subprocess.run([str(KICAD_CLI), 'pcb', 'export', 'pos', '--output', str(tmp),
                        '--format', 'csv', '--units', 'mm', '--side', 'both',
                        str(pcb)], capture_output=True, text=True)
    cpl = out / f'{name}-cpl.csv'
    if r.returncode == 0 and tmp.is_file():
        with tmp.open() as fi, cpl.open('w', newline='') as fo:
            rd, w = csv.DictReader(fi), csv.writer(fo)
            w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
            # Re-origin to the board's BOTTOM-LEFT corner.
            #
            # kicad-cli emits positions against the page/aux origin, which
            # for these boards produced Mid Y around -188 — a CPL that
            # uploads without complaint and places every part off the panel.
            # JLCPCB expects X right and Y UP, measured from the board's own
            # bottom-left corner. kicad-cli already negates Y (its export is
            # Y-up), so only the offset has to be removed.
            bb = board_bbox(text)
            off_x = bb[0] if bb else 0.0
            off_y = -bb[3] if bb else 0.0      # bottom edge = max KiCad y
            n = 0
            for row in rd:
                ref = row.get('Ref', '')
                base = re.match(r'[A-Za-z]+', ref)
                if base and base.group(0) in NON_PARTS:
                    continue
                w.writerow([ref,
                            f"{float(row['PosX']) - off_x:.4f}",
                            f"{float(row['PosY']) - off_y:.4f}",
                            row.get('Side', '').capitalize(),
                            f"{float(row['Rot']):.2f}"])
                n += 1
        tmp.unlink()
        print(f'  [ok] CPL   -> {cpl.name}  ({n} placement(s))')

    if unsourced:
        print(f'\n  {len(unsourced)} BOM line(s) with NO LCSC number — these are '
              f'yours to fit by hand, and JLCPCB will not assemble them:')
        for u in unsourced:
            print(f'    - {u}')
    print(f'\nOutput: {out}')
    print('NOTE: this packages whatever is on disk. It does NOT check the '
          'gates — run `python3 docs/pipeline.py <project> --check` first.')


if __name__ == '__main__':
    main()
