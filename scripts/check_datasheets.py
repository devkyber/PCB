#!/usr/bin/env python3
"""Verify every non-passive part on a board has a datasheet on file.

Why this exists
---------------
`docs/WORKFLOW.md` Step 2.1 has always said "download the datasheet
for every IC, save to projects/<board>/datasheets/". On TMS V3 that folder
was EMPTY at the point the board was considered ready for review — nine
ICs, a relay and a crystal, no datasheets — and nothing anywhere noticed.

The step was prose. Prose is not a gate. Worse, the one part whose pinout
WAS checked against its datasheet (the HF46F relay) had its PDF fetched to
a temp path, read, and thrown away, so even the work that was done left no
evidence behind and could not be re-checked by anyone else.

Two failure modes, one cause: nothing in the pipeline could tell the
difference between "verified" and "not verified", because verification
produced no artifact.

What counts as covered
----------------------
Passives (R/C/L), LEDs, test points, fiducials, mounting holes and generic
pin headers are exempt — their behaviour is fully described by the value
and the land pattern. Everything else — ICs, discrete semiconductors,
relays, crystals, and any plug-in MODULE socket — needs a file.

Module sockets are the important case. They are the parts most likely to
be represented by a generic header footprint, which means the netlist is
whatever the schematic author decided, and the only way to check it is the
vendor's pinout card. See workflow Step 2.3b.

Why the payload is sniffed (added 2026-08-25)
---------------------------------------------
This check counted `*.pdf` filenames and nothing else. Fault injection:
replacing baro-bmp390's BMP390 datasheet with a 60-byte HTML login wall,
still named `.pdf`, left this gate reporting "every part accounted for"
and exiting 0.

The datasheet is the one document every electrical decision is checked
against. A gate that cannot tell a datasheet from a vendor sign-in page
certifies exactly the thing it exists to prevent — the same silent failure
`collect_references.py` already sniffs for on reference designs. There is
no reason the bible got a weaker check than the commentary.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'scripts'))
from pcb_copilot.evidence.checks import Part, check_evidence  # noqa: E402
from pcb_copilot.project import load_project  # noqa: E402
from collect_references import sniff          # noqa: E402  (payload verification)

EXEMPT_PREFIXES = ('R', 'C', 'L', 'TP', 'FID', 'H', 'LED')
MODULE_HINTS = ('teensy', 'xbee', 'arduino', 'esp', 'raspberry', 'pico',
                'feather', 'nucleo', 'module', 'socket')


def _footprint_blocks(text: str):
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
    return m.group(1) if m else ''


def parts_needing_datasheets(pcb_text: str) -> list[tuple[str, str]]:
    out = []
    for blk in _footprint_blocks(pcb_text):
        ref, val = _prop(blk, 'Reference'), _prop(blk, 'Value')
        if not ref:
            continue
        base = re.match(r'[A-Za-z]+', ref)
        base = base.group(0) if base else ref
        is_module = any(h in val.lower() for h in MODULE_HINTS)
        if base in EXEMPT_PREFIXES and not is_module:
            continue
        if base == 'J' and not is_module:
            continue      # plain field connectors/headers
        out.append((ref, val))
    return out


def _norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _load_index(ds_dir: Path) -> dict[str, str]:
    """datasheets/INDEX.md maps parts to files for cases a filename cannot
    encode — e.g. the Teensy 4.1 pinout card is 'card11a_rev4_web.pdf'.
    Lines look like:  `J7, J8, TEENSY  ->  card11a_rev4_web.pdf  # PJRC rev4`
    It doubles as the provenance record: where each document came from."""
    idx = {}
    f = ds_dir / 'INDEX.md'
    if not f.is_file():
        return idx
    for line in f.read_text().splitlines():
        line = line.split('#')[0].strip()
        if '->' not in line:
            continue
        keys, fname = line.split('->', 1)
        for k in keys.split(','):
            if k.strip():
                idx[_norm(k)] = fname.strip()
    return idx


def _matches(value: str, ref: str, files: list[str], index: dict[str, str]) -> str:
    """-> the filename that documents this part, or '' if none does."""
    if _norm(ref) in index or _norm(value) in index:
        target = _norm(index.get(_norm(ref)) or index.get(_norm(value)))
        return next((f for f in files if target == _norm(f)), '')
    v = _norm(value)
    if len(v) < 4:
        return ''
    for f in files:
        fn = _norm(f.rsplit('.', 1)[0])
        # longest common substring of >= 5 chars counts as a match, so
        # "ADS1256IDBR" finds "ADS1256_ti.pdf" and vice versa
        for n in range(len(v), 4, -1):
            if any(v[i:i + n] in fn for i in range(len(v) - n + 1)):
                return f
    return ''


def check(pcb_path: Path) -> tuple[bool, str]:
    text = pcb_path.read_text(encoding='utf-8')
    ds_dir = pcb_path.parent / 'datasheets'
    files = [p.name for p in ds_dir.glob('*.pdf')] if ds_dir.is_dir() else []
    index = _load_index(ds_dir)
    needed = parts_needing_datasheets(text)

    project = load_project(pcb_path.parent)
    if project.evidence_index_path.is_file():
        parts = [
            Part(
                reference=ref,
                part_number=value,
                requires_datasheet=True,
                is_module=any(hint in value.lower() for hint in MODULE_HINTS),
            )
            for ref, value in needed
        ]
        findings = check_evidence(project, parts)
        relevant = [
            finding
            for finding in findings
            if finding.code.startswith('archive.')
            or finding.code in {'index.invalid', 'index.missing',
                                'part.missing_datasheet',
                                'part.missing_module_document'}
        ]
        lines = [f'{len(needed)} part(s) require a datasheet; unified evidence index']
        lines.extend(f'{finding.code}: {finding.message}' for finding in relevant)
        if not relevant:
            lines.append('every part accounted for in verified evidence')
        return not relevant, '\n'.join(lines)

    missing, fake = [], []
    from deviations import waived as _waived
    proj = ds_dir.parent
    waived_parts = []
    for ref, val in needed:
        hit = _matches(val, ref, files, index)
        if not hit:
            # Some parts genuinely have no obtainable datasheet — a generic
            # header, a discontinued cell. That is an engineering decision
            # and gets the same escape hatch as everything else, scoped to
            # the datasheet gate alone:  <REF> | datasheet | <reason>
            if _waived(proj, ref, 'datasheet'):
                waived_parts.append(f'{ref} ({val or "no value"})')
            else:
                missing.append(f'{ref} ({val or "no value"})')
            continue
        # A filename is a claim. Sniff what the bytes actually are: a login
        # wall or an error page saved as .pdf passes any check that counts
        # names, and every downstream "verified against the datasheet"
        # then rests on a document nobody can read.
        fmt = sniff(ds_dir / hit)
        if fmt != 'pdf':
            fake.append(f'{ref}: {hit} is {fmt}, not a PDF')

    lines = [f'{len(needed)} part(s) require a datasheet; '
             f'{len(files)} PDF(s) in {ds_dir.name}/']
    if waived_parts:
        lines.append('waived in DEVIATIONS.md: ' + ', '.join(sorted(waived_parts)))
    if fake:
        lines.append('NOT A DATASHEET: ' + '; '.join(sorted(fake)))
        lines.append('The file exists but its bytes are not a PDF — typically a '
                     'vendor login wall or a 404 page saved with a .pdf name. '
                     'Re-fetch with scripts/collect_references.py add '
                     '<project> <PART> <URL> --kind datasheet, which verifies '
                     'the payload before it lands on disk.')
    if missing:
        lines.append('MISSING: ' + ', '.join(sorted(missing)))
        lines.append('Fetch each into datasheets/ before schematic sign-off '
                     '(workflow Step 2.1), or map it in datasheets/INDEX.md if the '
                     'filename cannot carry the part name. A module socket with no '
                     'datasheet on file means its pin map was invented (Step 2.3b).')
        return False, '\n'.join(lines)
    if fake:
        return False, '\n'.join(lines)
    lines.append('every part accounted for, every file a real PDF')
    return True, '\n'.join(lines)


if __name__ == '__main__':
    ok, msg = check(Path(sys.argv[1]))
    print(msg)
    sys.exit(0 if ok else 1)
