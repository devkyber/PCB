#!/usr/bin/env python3
"""Add ground stitching vias to an ALREADY-ROUTED board, via pcbnew.

Why this runs after routing, not during placement:

    A stitching via placed before routing is an obstacle the router then
    has to weave around. On TMS V3, generating an 8mm via grid at
    placement time took unrouted connections from 1 to 8; at 12mm it was
    still 4. The vias were competing with the very traces they exist to
    support. Stitching is filler for the copper nobody used — so it can
    only be computed once you know what nobody used.

    The placement-time version also had to guess at obstacles from
    footprint extents alone, because the traces did not exist yet. Here
    the real pads, tracks and vias are all on the board and pcbnew can be
    asked directly.

Run as:  kipython stitch_vias.py <board.kicad_pcb> [pitch_mm] [edge_mm]
"""
import sys

import pcbnew

MM = 1_000_000


def main() -> None:
    path = sys.argv[1]
    pitch = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
    edge_gap = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
    drill, dia = 0.3, 0.6

    board = pcbnew.LoadBoard(path)

    # Clearance is READ FROM THE BOARD, never assumed. It was hardcoded at
    # 0.4mm, which is wrong in both directions and was observed failing both
    # ways on the same board:
    #
    #   too small — KiCad's Fiducial_1mm_Mask3mm carries a 1.1mm local pad
    #               clearance, so a 0.4mm assumption dropped a GND via
    #               1.025mm from FID1: clearance error + solder-mask bridge.
    #   too large — this board's default netclass clearance is 0.127mm, so
    #               inflating U1's neighbouring pads by 0.4mm sealed off the
    #               only escape route from U1.3 and the ground-pad pass
    #               silently placed nothing, leaving that pad on a 1.24mm^2
    #               floating fragment of top pour.
    #
    # The second failure is the dangerous one: it produces no error, just a
    # via that never got placed and a pad that is not grounded.
    try:
        clearance = board.GetDesignSettings().m_NetSettings \
                         .GetDefaultNetclass().GetClearance() / MM
    except Exception:
        clearance = board.GetDesignSettings().m_MinClearance / MM
    print(f'  board default clearance {clearance:.3f}mm '
          f'(per-pad overrides read individually)')

    # A stitching via ties two pours together. If only ONE copper layer
    # carries a pour, there is nothing on the other end and every via the
    # grid pass places is dangling copper: 90 vias produced 112
    # via_dangling violations on this board after the top pour was removed.
    #
    # So the grid pass is topology-dependent, and refuses rather than
    # producing plausible-looking garbage. The ground-PAD pass below still
    # applies — connecting an IC's ground pad down to the single plane is
    # meaningful with one pour or two.
    zone_layers = {z.GetLayer() for z in board.Zones()
                   if z.GetNetname() == 'GND' and not z.GetIsRuleArea()}
    grid_ok = len(zone_layers) >= 2
    if not grid_ok:
        print(f'  grid pass SKIPPED: GND pours on {len(zone_layers)} layer(s); '
              f'stitching needs two. Ground-pad escapes still run.')
    gnd = board.GetNetsByName().get('GND') if hasattr(board.GetNetsByName(), 'get') else None
    if gnd is None:
        for name, net in board.GetNetsByName().items():
            if str(name) == 'GND':
                gnd = net
                break
    if gnd is None:
        print('  no GND net — nothing to stitch')
        return
    gnd_code = gnd.GetNetCode()

    edge = board.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = edge.GetLeft(), edge.GetTop(), edge.GetRight(), edge.GetBottom()

    # Every existing copper item, as an inflated bounding box.
    # Two obstacle sets, because a GND via has different rights to the two.
    #
    #   boxes      - every copper item. Used for the grid pass, which is
    #                filler and should stay out of everyone's way.
    #   foreign    - only copper on OTHER nets. Used for the ground-pad pass,
    #                because a ground via is allowed to touch ground copper:
    #                that is the entire point of it. Treating the IC's own
    #                GND pad as an obstacle is what stopped rule 3.3's "a
    #                single via right at the IC's ground pads" from ever
    #                being satisfied, and left six ADC ground pads sitting
    #                on floating islands of top pour.
    reach = int((dia / 2 + clearance) * MM)

    def _pad_reach(pad):
        """Inflation for THIS pad, from the pad's own clearance rule.

        `clearance` above is a constant, and a constant is wrong the moment
        a footprint overrides it. KiCad's Fiducial_1mm_Mask3mm carries a
        ~1mm local pad clearance precisely so that no copper creeps near
        the optical target — five times the 0.2mm netclass rule this board
        otherwise uses. The grid pass, inflating by a flat 0.4mm, dropped a
        GND via 1.025mm from FID1 and produced a clearance error plus a
        solder-mask bridge on an otherwise clean board.

        Reading the rule off the pad makes the pass correct on any board
        instead of on boards that happen to use default clearances.
        """
        c = clearance
        try:
            own = pad.GetOwnClearance(pad.GetLayer())
            if own:
                c = max(c, own / MM)
        except Exception:
            try:
                loc = pad.GetLocalClearance()
                if loc:
                    c = max(c, float(loc) / MM)
            except Exception:
                pass
        return int((dia / 2 + c) * MM)

    boxes, foreign = [], []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            b = pad.GetBoundingBox()
            b.Inflate(_pad_reach(pad))
            boxes.append(b)
            if pad.GetNetCode() != gnd_code:
                foreign.append(b)
    for tr in board.GetTracks():
        b = tr.GetBoundingBox()
        b.Inflate(reach)
        boxes.append(b)
        if tr.GetNetCode() != gnd_code:
            foreign.append(b)
        # Vias are drill holes, and two holes need spacing regardless of net
        # — a GND via may share copper with GND copper but may not share a
        # drill with another via. Missing this produced a hole_to_hole
        # violation between two stitching vias.
        if isinstance(tr, pcbnew.PCB_VIA):
            foreign.append(b)

    step = int(pitch * MM)
    margin = int((edge_gap + dia / 2) * MM)
    added = 0
    y = y0 + margin
    while grid_ok and y <= y1 - margin:
        x = x0 + margin
        while x <= x1 - margin:
            pt = pcbnew.VECTOR2I(int(x), int(y))
            if not any(b.Contains(pt) for b in boxes):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pt)
                via.SetDrill(int(drill * MM))
                via.SetWidth(int(dia * MM))
                via.SetNetCode(gnd_code)
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                board.Add(via)
                nb = via.GetBoundingBox()
                nb.Inflate(reach)
                boxes.append(nb)
                foreign.append(nb)
                added += 1
            x += step
        y += step

    # Second pass: give every SMD ground pad its own via down to the
    # bottom pour.
    #
    # On a 2-layer board the top pour is chopped into islands by the routed
    # traces. An island carrying an IC's GND pad but no via is not ground —
    # it is a floating patch of copper, and DRC correctly reports the pad as
    # unconnected. The grid pass above cannot help, because it deliberately
    # keeps clear of pads, and the islands that matter are exactly the tight
    # spaces between a fine-pitch IC's pins.
    #
    # It is also just good analog practice: a return path that has to travel
    # around a trace before it finds a via is a loop, and loop area is what
    # couples noise into a 24-bit ADC.
    pad_vias = 0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gnd_code:
                continue
            if pad.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD,
                                          pcbnew.PAD_ATTRIB_CONN):
                continue
            pc = pad.GetPosition()
            psz = max(pad.GetSize().x, pad.GetSize().y)
            placed = False
            r = psz / 2 + (dia / 2) * MM        # may abut its own GND pad
            while r < psz / 2 + 3.0 * MM and not placed:
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                               (-1, -1), (1, -1), (-1, 1), (1, 1)):
                    pt = pcbnew.VECTOR2I(int(pc.x + dx * r), int(pc.y + dy * r))
                    if not (x0 + margin <= pt.x <= x1 - margin
                            and y0 + margin <= pt.y <= y1 - margin):
                        continue
                    if any(b.Contains(pt) for b in foreign):
                        continue
                    # The via being clear is not enough: the copper BETWEEN
                    # the pad and the via has to be clear too, or the stub
                    # that joins them shorts whatever it crosses. Drawing
                    # the stub without this check produced 3 clearance
                    # violations, 2 shorts and a crossing pair on an earlier
                    # attempt. Sample the segment and reject the whole
                    # position if any sample lands in foreign copper.
                    steps = 12
                    blocked = False
                    for k in range(1, steps):
                        sx = int(pc.x + (pt.x - pc.x) * k / steps)
                        sy = int(pc.y + (pt.y - pc.y) * k / steps)
                        sp = pcbnew.VECTOR2I(sx, sy)
                        if any(b.Contains(sp) for b in foreign):
                            blocked = True
                            break
                    if blocked:
                        continue

                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(pt)
                    via.SetDrill(int(drill * MM))
                    via.SetWidth(int(dia * MM))
                    via.SetNetCode(gnd_code)
                    via.SetViaType(pcbnew.VIATYPE_THROUGH)
                    board.Add(via)

                    # Stub from pad to via, on the pad's own layer. Rule 3.3
                    # asks for "a single via right at the IC's ground pads";
                    # between 0.65mm-pitch pins there is no room for the via
                    # itself, so the via goes just outside the package and a
                    # short trace reaches it — which is what a person drawing
                    # this by hand does. Safe now because the path above was
                    # checked, not assumed.
                    stub = pcbnew.PCB_TRACK(board)
                    stub.SetStart(pc)
                    stub.SetEnd(pt)
                    stub.SetWidth(int(0.25 * MM))
                    stub.SetLayer(pad.GetLayer())
                    stub.SetNetCode(gnd_code)
                    board.Add(stub)
                    sb = stub.GetBoundingBox()
                    sb.Inflate(reach)
                    boxes.append(sb)
                    nb = via.GetBoundingBox()
                    nb.Inflate(reach)
                    boxes.append(nb)
                    foreign.append(nb)
                    pad_vias += 1
                    placed = True
                    break
                r += 0.15 * MM

    board.Save(path)
    print(f'  {added} grid + {pad_vias} ground-pad stitching vias added post-route '
          f'(pitch {pitch}mm, {edge_gap}mm edge gap)')


if __name__ == '__main__':
    main()
