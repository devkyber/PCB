#!/usr/bin/env python3
"""Derive `netmap.json` from the schematic itself, for boards a human owns.

Why this file exists
--------------------
`netmap.json` is the ONE schematic->PCB connectivity contract in this
workspace (CLAUDE.md rule 12). Until now it was always *declared* by
`gen_<board>_sch.py`: the generator recorded every `pin_label()` call and
wrote the file out at the end. That works only while a script is the thing
that draws the schematic.

The moment a human draws the sheet in Eeschema, the generator is no longer
the author of the connectivity — the `.kicad_sch` is. So the contract has to
be *extracted* from the schematic rather than declared alongside it, or the
PCB gets built from a netlist describing a schematic that no longer exists.

It reuses `check_netlist_parity.schematic_nets()` deliberately. That function
already asks KiCad itself (`kicad-cli sch export netlist`) rather than
parsing the `.kicad_sch` by hand, already normalises the sheet path, already
drops `unconnected-(...)` pseudo-nets, and already skips `#PWR`/`#FLG`
pseudo-refs that carry no footprint. A second implementation of that logic
is recurring defect class #5 ("the second parser"), and this workspace has
paid for it four times.

What happens to parity
----------------------
Once the netmap is derived from the schematic, `check_netlist_parity.py`
stops comparing two independent derivations and becomes a *transcription*
check: does the board match the schematic the human drew? That is weaker by
construction, and it is still the right check — it is exactly the
netlist-import verification every EDA flow runs, and it still catches the
failure that shipped the five dead test points (a PCB generator that
silently drops assignments). It also newly catches a part ADDED in Eeschema
that the PCB generator does not place, which would otherwise be silent.

On `no_connect`
---------------
Emitted empty, on purpose. KiCad's no-connect flags are positional markers
with no pin binding, so deriving them means matching coordinates to pin
positions — and the field feeds nothing: `NO_CONNECT` is assigned and never
read in all four `gen_*_pcb.py`. ERC is what governs unconnected pins.

Usage:
    python3 extract_netmap.py <board.kicad_sch>     # writes netmap.json beside it
    python3 extract_netmap.py <board.kicad_sch> --print
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_netlist_parity as parity  # noqa: E402


def extract(sch: Path) -> dict:
    """Return the netmap dict for `sch`, in the shape gen_*_pcb.py reads."""
    by_net = parity.schematic_nets(sch)          # {net: {(ref, pin), ...}}
    nets: dict[str, dict[str, str]] = {}
    for net, pins in by_net.items():
        for ref, pin in pins:
            nets.setdefault(ref, {})[pin] = net
    # Deterministic ordering: the file is tracked in git and a diff of it is
    # a diff of the board's netlist, so it must not churn between runs.
    nets = {ref: dict(sorted(p.items())) for ref, p in sorted(nets.items())}
    return {
        'source': f'extract_netmap.py (derived from {sch.name})',
        'nets': nets,
        'no_connect': {},
    }


def write(sch: Path) -> tuple[Path, int]:
    """Write netmap.json beside `sch`. Returns (path, pin-assignment count)."""
    data = extract(sch)
    out = sch.parent / 'netmap.json'
    out.write_text(json.dumps(data, indent=2) + '\n')
    return out, sum(len(p) for p in data['nets'].values())


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith('-')]
    if len(args) != 1:
        print(__doc__.strip().splitlines()[-3].strip(), file=sys.stderr)
        return 2
    sch = Path(args[0]).resolve()
    if not sch.is_file():
        print(f'no such schematic: {sch}', file=sys.stderr)
        return 2
    if '--print' in argv:
        print(json.dumps(extract(sch), indent=2))
        return 0
    out, n = write(sch)
    print(f'{out.name}: {n} pin-net assignments derived from {sch.name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
