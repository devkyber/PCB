#!/usr/bin/env python3
"""Create one routed candidate from a published PCB Copilot layout draft.

Compatibility spelling: ``route_and_fill.py <draft-board.kicad_pcb> [passes]``.
The input draft is never overwritten; the candidate and fresh DRC remain under
that draft's ``routing/run-*/attempt-001`` directory for human review.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))


def main() -> None:
    from pcb_copilot.layout.route import legacy_route_cli

    try:
        status = legacy_route_cli(sys.argv[1:], best_of=False)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"route_and_fill.py: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(status)


if __name__ == "__main__":
    main()
