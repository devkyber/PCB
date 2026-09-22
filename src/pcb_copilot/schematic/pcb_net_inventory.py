"""Standalone KiCad-Python helper for exact PCB pad net membership."""

from __future__ import annotations

import json
import sys
from collections import defaultdict

import pcbnew


def main() -> int:
    board = pcbnew.LoadBoard(sys.argv[1])
    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        for pad in footprint.Pads():
            net = str(pad.GetNetname()).lstrip('/')
            if net:
                groups[net].append((reference, str(pad.GetPadName())))
    print(json.dumps({net: sorted(pins) for net, pins in sorted(groups.items())}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
