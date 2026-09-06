#!/usr/bin/env python3
"""Schematic and PCB must describe the SAME circuit. Nothing checked that.

Why this file exists
--------------------
Connectivity was declared TWICE on three of four boards in this workspace:

  * `gen_<board>_sch.py`  ->  `pin_label(ref, pin, net)` calls
  * `gen_<board>_pcb.py`  ->  its own `NET_MAP = {(ref, pad): net}` dict

Two hand-maintained copies of one fact, and no check compared them. tms-v3
found this the hard way and fixed it by writing `netmap.json` from the
schematic generator for the PCB generator to read. Its own source says:

    "It used to re-derive the map by running regexes over THIS FILE's source
     text ... That is how J7/J8 kept a stale map."

That fix was never propagated to the other three boards — recurring defect
class #6 in docs/ARCHITECTURE.md, "the fix that did not propagate".

What it shipped
---------------
Five dead test points. `gnss-neom9n` TP1/TP2 and `imu-icm42688` TP1/TP2/TP3
are wired in the schematic and carry NO NET in the PCB, because the PCB
generator's call

    place_std('TP1', '+3V3', 'TestPoint', ...)
                     ^^^^^^ this is the VALUE field, not a net assignment

places the footprint and assigns nothing. On the fabricated board those pads
are electrically dead: you solder a probe to TP2 expecting GND and read
nothing. `baro-bmp390`'s TP1 is correctly netted, which is what proves this
is an omission rather than a design choice.

Every existing gate passed all three boards. DRC cannot see it: a pad with no
net has no ratsnest, so it is not "unconnected" — it is simply absent from
the netlist. ERC cannot see it either; the schematic is correct.

Why this is not a "netless pad" check
-------------------------------------
The obvious implementation — flag every pad with no net — was measured
against the real boards first and is WRONG. Netless pads are overwhelmingly
legitimate: 3 fiducials and 2-4 mounting holes per board, connector mounting
pads, and above all the deliberately unconnected pins of real ICs and module
sockets. tms-v3 alone has 42 such pads across J7/J8/J9 (unused Teensy and
XBee pins, each carrying an explicit no-connect in the schematic) plus 14
NC pins across U2/U3. A prefix-based heuristic would report ~56 false
positives on that board and would be switched off within a week.

The exact test is parity, and parity subsumes the netless-pad case: a pad is
a defect when THE SCHEMATIC GIVES IT A NET AND THE PCB DOES NOT. A pad that
neither side nets is a no-connect, and ERC already governs those.

Authority
---------
This check states only that the two views AGREE. It is deliberately silent
on which one is right. When it fails, read the named pins and decide — never
"fix" one side to match the other without knowing which one holds the intent.

Usage:  kipython check_netlist_parity.py <board.kicad_pcb>
Exit 0 when the schematic and the PCB describe the same circuit.
"""
from __future__ import annotations

import collections
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parent.parent
KICAD_CLI = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')

# Nets KiCad invents for a pin that is connected to nothing. They exist only
# in the schematic netlist and have no PCB counterpart by construction.
PSEUDO_NET = re.compile(r'^unconnected-\(')


def _norm(net: str) -> str:
    """One normalisation, applied identically to both sides.

    Only the leading sheet-path slash is stripped. Deeper path components are
    KEPT: a hierarchical design names a net `/Power/VBUS` on both sides, so
    stripping to the basename would merge two genuinely different nets that
    happen to share a local label — the exact bug this gate exists to catch.
    """
    return net.lstrip('/')


def schematic_nets(sch: Path) -> dict:
    """ref/pin -> net, as KiCad itself computes it from the schematic."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / 'netlist.net'
        r = subprocess.run(
            [str(KICAD_CLI), 'sch', 'export', 'netlist', '-o', str(out), str(sch)],
            capture_output=True, text=True)
        if not out.is_file():
            raise RuntimeError(
                f'kicad-cli produced no netlist (exit {r.returncode}): '
                + (r.stderr or r.stdout).strip()[:200])
        text = out.read_text()

    nets: dict = collections.defaultdict(set)
    for m in re.finditer(r'\(net\b(.*?)\n\t\t\)', text, re.S):
        body = m.group(1)
        nm = re.search(r'\(name "([^"]+)"\)', body)
        if not nm:
            continue
        name = _norm(nm.group(1))
        if PSEUDO_NET.match(name):
            continue
        for ref, pin in re.findall(r'\(ref "([^"]+)"\)\s*\n?\s*\(pin "([^"]+)"\)', body):
            # `#PWR01`, `#FLG02` — power symbols and PWR_FLAGs. Schematic-only
            # by definition: they carry no footprint, so no PCB pad can match.
            if ref.startswith('#'):
                continue
            nets[name].add((ref, pin))
    return dict(nets)


def pcb_nets(pcb: Path) -> dict:
    """ref/pad -> net, as KiCad itself resolves it from the board.

    Read through pcbnew rather than by parsing the file, deliberately. These
    boards are written with a non-canonical `(net "NAME")` form carrying no
    numeric id and no net table (see ARCHITECTURE.md). KiCad accepts it, but a
    text parser and KiCad could disagree — and what KiCad believes is what
    gets fabricated.
    """
    import pcbnew                                          # noqa: PLC0415
    board = pcbnew.LoadBoard(str(pcb))
    nets: dict = collections.defaultdict(set)
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            name = str(pad.GetNetname())
            if name:
                nets[_norm(name)].add((ref, str(pad.GetPadName())))
    return dict(nets)


def compare(sch: dict, pcb: dict) -> list:
    """Return a list of human-readable problems, most structural first."""
    problems = []
    sk, pk = set(sch), set(pcb)

    for n in sorted(sk - pk):
        problems.append(f'net "{n}" exists in the SCHEMATIC but not the PCB '
                        f'— pins {sorted(sch[n])}')
    for n in sorted(pk - sk):
        problems.append(f'net "{n}" exists in the PCB but not the SCHEMATIC '
                        f'— pads {sorted(pcb[n])}')

    for n in sorted(sk & pk):
        only_sch = sorted(sch[n] - pcb[n])
        only_pcb = sorted(pcb[n] - sch[n])
        if not only_sch and not only_pcb:
            continue
        bits = [f'net "{n}" differs:']
        if only_sch:
            bits.append('  wired in the schematic, NOT on the board: '
                        + ', '.join(f'{r}.{p}' for r, p in only_sch))
        if only_pcb:
            bits.append('  on the board, NOT in the schematic: '
                        + ', '.join(f'{r}.{p}' for r, p in only_pcb))
        problems.append('\n'.join(bits))
    return problems


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pcb = Path(sys.argv[1]).resolve()
    sch = pcb.with_suffix('.kicad_sch')
    if not pcb.is_file():
        print(f'RESULT: FAIL — no board file at {pcb}')
        return 1
    if not sch.is_file():
        print(f'RESULT: FAIL — no schematic beside the board ({sch.name})')
        return 1

    try:
        s = schematic_nets(sch)
        p = pcb_nets(pcb)
    except Exception as exc:                                # noqa: BLE001
        print(f'RESULT: FAIL — parity could not be established: {exc}')
        return 1

    problems = compare(s, p)

    # The escape hatch, scoped. `<ref>.<pin> | parity | <reason>` waives that
    # one designator. Parsed by docs/deviations.py — the ONE parser.
    if problems:
        from deviations import parse                        # noqa: PLC0415
        waivers, _ = parse(pcb.parent)
        waived_refs = {r for r, _p, s_, _w in waivers if s_ == 'parity'}
        if waived_refs:
            kept, excused = [], []
            for prob in problems:
                refs = set(re.findall(r'\b([A-Za-z]+[0-9]+)\.', prob))
                (excused if refs and refs <= waived_refs else kept).append(prob)
            problems = kept
            for prob in excused:
                print('  [waived] ' + prob.splitlines()[0])

    print(f'schematic: {len(s)} net(s)   board: {len(p)} net(s)')
    for prob in problems:
        for i, line in enumerate(prob.splitlines()):
            print(('  MISMATCH: ' if i == 0 else '            ') + line)

    if problems:
        print(f'\nRESULT: FAIL — {len(problems)} net(s) differ between the '
              'schematic and the board')
        print('        Decide which side holds the intent before changing either.')
        return 1
    print('\nRESULT: PASS — schematic and board describe the same circuit')
    return 0


if __name__ == '__main__':
    sys.exit(main())
