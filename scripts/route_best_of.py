#!/usr/bin/env python3
"""Create and score isolated routing candidates from a published layout draft.

Compatibility spelling:
``route_best_of.py <draft-board.kicad_pcb> [attempts] [passes]``.
Selection minimizes fresh DRC unconnected items, then DRC errors. It does not
overwrite the draft or imply acceptance/fabrication approval.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))


def main() -> None:
    from pcb_copilot.layout.route import legacy_route_cli

    try:
        status = legacy_route_cli(sys.argv[1:], best_of=True)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"route_best_of.py: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(status)


if __name__ == "__main__":
    main()
