#!/usr/bin/env python3
"""Widen any via whose annular ring is below the board's own minimum.

Why this exists
---------------
On tms-v3, exactly two vias out of 100 came off the router with a
0.60mm pad on a 0.40mm drill — annular 0.100mm against the board's stated
0.150mm minimum. Every OTHER via on the same nets was correct at 0.80/0.40.
The cause is the DSN/SES round trip pairing a Default-netclass diameter with
a Power-netclass drill on a couple of vias; it is not something the board
author did wrong and not something re-running the router fixes, because the
router is where it comes from.

Two vias is exactly the size of defect that gets waived "for now" and then
ships. A 0.1mm annular ring on a 1.6mm board is a plating reliability
problem, not a cosmetic one: it is the ring the barrel plating has to key
into, and JLCPCB's own process minimum exists for that reason.

The repair is the safe direction. Growing a via's PAD never creates a short
that DRC will not immediately catch on the next run, and never shrinks a
drill below what the fab can do. Shrinking the drill instead would change
the via's current capacity silently, so this deliberately does not.

Run as:  kipython fix_via_annular.py <board.kicad_pcb>
Exit 0 whether or not anything changed; it reports what it did.
"""
import sys

import pcbnew

MM = 1_000_000


def main() -> None:
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    ds = board.GetDesignSettings()

    # The minimum comes FROM THE BOARD. Hardcoding it is how stitch_vias.py
    # ended up wrong in both directions on one board (workflow lesson 41).
    try:
        min_ann = ds.m_ViasMinAnnularWidth / MM
    except AttributeError:
        min_ann = 0.15
    if min_ann <= 0:
        print('  no minimum annular width set on this board — nothing to check')
        return

    fixed = []
    for t in board.GetTracks():
        if not isinstance(t, pcbnew.PCB_VIA):
            continue
        dia, drill = t.GetWidth() / MM, t.GetDrill() / MM
        ann = (dia - drill) / 2
        if ann >= min_ann - 1e-9:
            continue
        want = drill + 2 * min_ann
        t.SetWidth(int(round(want * MM)))
        fixed.append((t.GetNetname(), dia, drill, ann, want))

    if not fixed:
        print(f'  all vias meet the {min_ann:.3f}mm minimum annular width')
        return

    board.Save(path)
    print(f'  widened {len(fixed)} via(s) to meet the '
          f'{min_ann:.3f}mm minimum annular width:')
    for net, dia, drill, ann, want in fixed:
        print(f'    [{net}] dia {dia:.2f} -> {want:.2f} on a {drill:.2f} drill '
              f'(annular {ann:.3f} -> {min_ann:.3f})')


if __name__ == '__main__':
    main()
