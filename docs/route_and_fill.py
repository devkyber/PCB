#!/usr/bin/env python3
"""Autoroute a board, bond its ground pour, and verify the result with DRC.

This is a thin CLI over `kicad_claude.adapters.route_pipeline.route_board`.
It used to be a second, divergent routing implementation that disagreed with
the MCP tool; both now share one path, so a fix made here is a fix everywhere.

The three things this exists to get right, all of which produced misleading
DRC results while fixing TMS V3:

1. `kicad-cli pcb drc` does not fill zones. On a board with a ground pour, an
   unfilled DRC reports every GND pad as unconnected, so zones must be filled
   between routing and DRC.

2. Autorouting fragments the pours it routes through. The islands left behind
   are floating copper unless a via reaches them, and Freerouting will never
   place that via — it treats the pour as an obstacle, not as a net it owns.

3. A `.ses` file on disk is not a routed board. The exit status here reflects
   DRC, not the router's opinion of itself.

Freerouting 2.1.x is additionally afflicted by an upstream-broken
multi-threaded optimizer that `-mt 1` does NOT disable (verified against
tms-v3: the log still reports "Starting optimization on 7 threads", with or
without the flag, and with FREEROUTING__ROUTER__MAX_THREADS=1 set). The fix is
a 2.2+ JAR on Java 25, which the adapter selects automatically when present.

Usage:
    route_and_fill.py <board.kicad_pcb> [passes]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'tools' / 'kicad-claude-mcp' / 'src'))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)

    from kicad_claude.adapters import route_pipeline

    pcb = Path(sys.argv[1]).resolve()
    passes = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    result = route_pipeline.route_board(pcb, passes=passes, timeout_seconds=900.0)

    fr = result['freerouting']
    print(f"  router     : Freerouting {fr['jar_version']}")
    print(f"  passes     : {fr['stats'].get('passes_done')} "
          f"(score {fr['stats'].get('score')})")
    if fr['stats'].get('optimizer_multithreaded_warning'):
        print("  WARNING    : broken multi-threaded optimizer ran "
              "(upgrade to a 2.2+ JAR on Java 25)")
    bond = result.get('ground_bond') or {}
    if bond:
        print(f"  bonding    : +{bond.get('added_via_count', 0)} vias "
              f"({len(bond.get('stitch_vias', []))} island stitches, "
              f"{len(bond.get('escapes', []))} pad escapes)")
    print(f"  unconnected: {result['unconnected_after_route']} after routing "
          f"-> {result['unconnected']} after bonding")
    print(f"  DRC        : {result['drc']['errors']} errors, "
          f"{result['drc']['warnings']} warnings")

    for item in result['remaining_signal_items']:
        print(f"  SIGNAL  {','.join(item['nets'])}: {item['descriptions'][0]}")
    for item in result['remaining_pour_items']:
        print(f"  POUR    {','.join(item['nets'])}: {item['descriptions'][0]}")
    for miss in (bond.get('unescapable') or []):
        print(f"  MANUAL  {miss['ref']}.{miss['pad']} at {miss.get('pad_mm')}: "
              f"{miss['reason']}")

    report = pcb.with_suffix('.route-report.json')
    report.write_text(json.dumps(result, indent=2))
    print(f"  report     : {report}")

    print("  GATE       : " + ("PASS" if result['passed'] else "FAIL"))
    sys.exit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
