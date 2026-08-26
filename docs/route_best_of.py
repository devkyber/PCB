#!/usr/bin/env python3
"""Route a board N times and keep the best result.

Freerouting is not deterministic. Identical input gives 5 unconnected on one
run and 8 on the next, because each pass is bounded by wall-clock time rather
than by work done, and 2.3.0's stagnation detector stops on whatever local
minimum it happened to reach. A build that keeps whichever result the last
attempt produced is not repeatable, and the difference between "ships" and
"does not ship" lands on luck.

This runs the shared pipeline (docs/route_and_fill.py -> route_pipeline) from
the SAME unrouted starting board each time, and keeps the board with the
fewest unconnected items. Stops early on a clean route.

Usage:  python3 route_best_of.py <board.kicad_pcb> [attempts] [passes]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> None:
    pcb = Path(sys.argv[1]).resolve()
    attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    passes = sys.argv[3] if len(sys.argv) > 3 else '200'

    pristine = pcb.with_suffix('.unrouted.kicad_pcb')
    shutil.copy(pcb, pristine)          # the placement, before any copper
    best_n, best_board = None, pcb.with_suffix('.best.kicad_pcb')

    for i in range(1, attempts + 1):
        shutil.copy(pristine, pcb)      # always start from the same board
        subprocess.run([sys.executable, str(REPO / 'docs' / 'route_and_fill.py'),
                        str(pcb), passes], capture_output=True, text=True)
        report = pcb.with_suffix('.route-report.json')
        n = json.loads(report.read_text())['unconnected'] if report.is_file() else 10 ** 6
        print(f'  attempt {i}/{attempts}: {n} unconnected')
        if best_n is None or n < best_n:
            best_n = n
            shutil.copy(pcb, best_board)
        if best_n == 0:
            break

    shutil.copy(best_board, pcb)
    best_board.unlink(missing_ok=True)
    pristine.unlink(missing_ok=True)
    print(f'  best of {attempts}: {best_n} unconnected')
    sys.exit(0 if best_n == 0 else 1)


if __name__ == '__main__':
    main()
