#!/usr/bin/env python3
"""Courtyard-aware placement helpers — fixes the "coordinates chosen before
real parts existed don't transfer once real parts land" defect class.

Root cause (found across TMS V3, IMU, and barometer boards): placement
scripts picked (x, y) coordinates by eye, before the real footprint's
courtyard size was known. A relay that turns out 20.5mm long, or a header
with a 60mm pin span, or a connector 3x bigger than guessed, collides with
whatever was placed next to it under the old assumption.

This module makes courtyard size a first-class, checked-at-generation-time
fact instead of something DRC discovers minutes later:

  - get_courtyard_bbox(fp_def_node)   -> real (width_mm, height_mm) from
    the fetched footprint's own F.CrtYd geometry, before you ever choose
    a coordinate for it.
  - PlacementTracker                   -> call .place(ref, fp_def_node, x,
    y, rot) for every component as you place it; it raises immediately on
    a courtyard collision, with the two overlapping refs and the overlap
    amount, instead of surfacing as one of 40 DRC violations after the
    whole board is built.
  - shelf_pack()                       -> optional: given a list of
    (ref, fp_def_node) in placement order and a zone rectangle, computes
    non-overlapping coordinates automatically using real courtyard sizes,
    for when you don't need to hand-place every component.

Usage pattern (see gen_tms_v3_pcb.py / gen_imu_pcb.py for the manual-place
style, or the shelf_pack() example at the bottom for automatic):

    from pcb_layout_helpers import PlacementTracker

    tracker = PlacementTracker()

    def place_real(ref, value, fp_filename, x, y, rot=0):
        fp_def = _fetch_cached(REAL_FP_DIR / f'{fp_filename}.kicad_mod')
        tracker.place(ref, fp_def, x, y, rot)   # raises on collision
        node = pe.add_footprint(tree, ..., x_mm=..., y_mm=..., fp_def_node=fp_def)
        return _set_pad_nets(node, ref)
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Courtyard bounding box extraction
# --------------------------------------------------------------------------- #

def _extract_crtyd_block(text: str) -> str | None:
    """Isolate the F.CrtYd (or B.CrtYd) portion of a raw .kicad_mod file."""
    return text  # geometry elements are matched by proximity to the layer tag below


def _iter_top_level_elements(text: str, tag: str):
    """Yield the full balanced-paren text of every `(tag ...)` element in
    text, scoped correctly (no leakage across sibling elements) — a loose
    `.*?` regex between a coordinate and a later `(layer ...)` tag will
    happily skip past an element's own close-paren and match a DIFFERENT
    element's layer tag several siblings down. This bit the first version
    of this parser: it silently mismatched a silkscreen fp_line with the
    courtyard fp_rect three elements later. Depth-counting avoids that
    class of bug entirely by only ever looking inside one element at a time.
    """
    pat = f'({tag}'
    start = 0
    while True:
        idx = text.find(pat, start)
        if idx == -1:
            return
        depth = 0
        i = idx
        while i < len(text):
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
                if depth == 0:
                    yield text[idx:i + 1]
                    start = i + 1
                    break
            i += 1
        else:
            return


def get_courtyard_bbox_from_text(mod_text: str) -> tuple[float, float] | None:
    """Parse a raw .kicad_mod file's text and return (width_mm, height_mm)
    of its F.CrtYd (falls back to B.CrtYd) bounding box in the footprint's
    own local coordinate frame (before placement rotation/offset).

    Returns None if no courtyard layer is present (some minimal footprints
    omit it — treat as "unknown, use a conservative default").
    """
    xs: list[float] = []
    ys: list[float] = []
    crtyd_layer_re = re.compile(r'\(layer\s+"[FB]\.CrtYd"\)')

    for tag in ('fp_line', 'fp_rect'):
        for block in _iter_top_level_elements(mod_text, tag):
            if not crtyd_layer_re.search(block):
                continue
            m = re.search(
                r'\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)',
                block,
            )
            if m:
                x1, y1, x2, y2 = map(float, m.groups())
                xs.extend([x1, x2])
                ys.extend([y1, y2])

    for block in _iter_top_level_elements(mod_text, 'fp_circle'):
        if not crtyd_layer_re.search(block):
            continue
        m = re.search(
            r'\(center\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)',
            block,
        )
        if m:
            cx, cy, ex, ey = map(float, m.groups())
            r = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
            xs.extend([cx - r, cx + r])
            ys.extend([cy - r, cy + r])

    for block in _iter_top_level_elements(mod_text, 'fp_poly'):
        if not crtyd_layer_re.search(block):
            continue
        for pm in re.finditer(r'\(xy\s+([-\d.]+)\s+([-\d.]+)\)', block):
            xs.append(float(pm.group(1)))
            ys.append(float(pm.group(2)))

    if not xs:
        return None
    return (max(xs) - min(xs), max(ys) - min(ys))


def get_courtyard_bbox(fp_def_node) -> tuple[float, float] | None:
    """Same as get_courtyard_bbox_from_text but takes a parsed sexpdata
    footprint node (as returned by pcb_editor.fetch_footprint_def)."""
    import sexpdata
    text = sexpdata.dumps(fp_def_node)
    return get_courtyard_bbox_from_text(text)


def get_courtyard_bbox_from_file(mod_path) -> tuple[float, float] | None:
    from pathlib import Path
    return get_courtyard_bbox_from_text(Path(mod_path).read_text())




# --------------------------------------------------------------------------- #
# Offset-aware extents (courtyard UNION pads)
# --------------------------------------------------------------------------- #
#
# Two defects in the original courtyard-only, size-only model, both of which
# shipped on TMS V3 and neither of which this module could have caught:
#
#   1. Size-only (w, h) implicitly assumes the bbox is CENTRED on the
#      footprint anchor. It usually is for SMD passives and ICs, and it is
#      never true for a 1xN pin header, whose anchor is PIN 1. A 1x24
#      header reported as "2.5 x 60mm centred on (x, y)" is really
#      "2.5 x 60mm starting at (x, y) and running 60mm in +Y". TMS V3's
#      J7/J8 ran 16mm off the board edge because of exactly this.
#
#   2. Courtyard-only geometry is not a safe proxy for how much room a part
#      needs. EasyEDA-converted footprints regularly ship a courtyard
#      SMALLER than their own land pattern — TMS V3's ADS1256 SSOP-28 does
#      — so four decoupling caps were placed inside the IC's pads and
#      shorted +5V to +3V3. Pads must be unioned in.
#
# get_extents_from_text() returns (min_x, min_y, max_x, max_y) in the
# footprint's local frame, over courtyard AND pads, so both are fixed.

def _pad_local_extents(mod_text: str) -> list[tuple[float, float, float, float]]:
    """Per-pad local-frame bounding boxes, rotation-aware."""
    boxes = []
    for block in _iter_top_level_elements(mod_text, 'pad'):
        m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)', block)
        s = re.search(r'\(size\s+([-\d.]+)\s+([-\d.]+)\)', block)
        if not (m and s):
            continue
        px, py = float(m.group(1)), float(m.group(2))
        prot = float(m.group(3)) if m.group(3) else 0.0
        sw, sh = float(s.group(1)), float(s.group(2))
        if abs(prot % 180.0) < 0.01:
            hw, hh = sw / 2.0, sh / 2.0
        elif abs(prot % 180.0 - 90.0) < 0.01:
            hw, hh = sh / 2.0, sw / 2.0
        else:
            hw = hh = max(sw, sh) / 2.0   # conservative for off-axis pads
        boxes.append((px - hw, py - hh, px + hw, py + hh))
    return boxes


def _courtyard_local_extents(mod_text: str) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    crtyd_layer_re = re.compile(r'\(layer\s+"[FB]\.CrtYd"\)')
    for tag in ('fp_line', 'fp_rect'):
        for block in _iter_top_level_elements(mod_text, tag):
            if not crtyd_layer_re.search(block):
                continue
            m = re.search(r'\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)', block)
            if m:
                x1, y1, x2, y2 = map(float, m.groups())
                xs.extend([x1, x2]); ys.extend([y1, y2])
    for block in _iter_top_level_elements(mod_text, 'fp_circle'):
        if not crtyd_layer_re.search(block):
            continue
        m = re.search(r'\(center\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)', block)
        if m:
            cx, cy, ex, ey = map(float, m.groups())
            r = math.hypot(ex - cx, ey - cy)
            xs.extend([cx - r, cx + r]); ys.extend([cy - r, cy + r])
    for block in _iter_top_level_elements(mod_text, 'fp_poly'):
        if not crtyd_layer_re.search(block):
            continue
        for pm in re.finditer(r'\(xy\s+([-\d.]+)\s+([-\d.]+)\)', block):
            xs.append(float(pm.group(1))); ys.append(float(pm.group(2)))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def get_extents_from_text(mod_text: str) -> tuple[float, float, float, float] | None:
    """(min_x, min_y, max_x, max_y) in the footprint's LOCAL frame, over the
    union of courtyard geometry and every pad. Local frame means relative to
    the footprint anchor, so a 1xN header correctly reports min_y ~= -1.6 and
    max_y ~= +58, rather than a symmetric box around pin 1."""
    boxes = _pad_local_extents(mod_text)
    crt = _courtyard_local_extents(mod_text)
    if crt is not None:
        boxes.append(crt)
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def local_pad_positions(mod_text: str) -> dict[str, tuple[float, float]]:
    """{pad_name: (x, y)} in the footprint's LOCAL frame.

    This is what makes pin-relative placement possible. Placing a
    decoupling cap "near U2" on an arithmetic grid is not the rule —
    pcb-design-rules.md 2.2 asks for 2mm from the POWER PIN, and an
    SSOP-28's power pins are 10mm apart, so "near the part" and "near the
    pin" are different places. Grid placement is how TMS V3 ended up with
    every bypass cap 3-10mm from the pin it was bypassing while passing
    DRC."""
    out: dict[str, tuple[float, float]] = {}
    for block in _iter_top_level_elements(mod_text, 'pad'):
        n = re.search(r'\(pad\s+"([^"]*)"', block)
        m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)', block)
        if n and m:
            out[n.group(1)] = (float(m.group(1)), float(m.group(2)))
    return out


def get_extents(fp_def_node) -> tuple[float, float, float, float] | None:
    import sexpdata
    return get_extents_from_text(sexpdata.dumps(fp_def_node))


def get_extents_from_file(mod_path) -> tuple[float, float, float, float] | None:
    from pathlib import Path
    return get_extents_from_text(Path(mod_path).read_text())


def _rotate_local(px: float, py: float, deg: float) -> tuple[float, float]:
    """KiCad footprint-local -> board delta (Y down, angle CCW on screen)."""
    a = math.radians(deg)
    return (px * math.cos(a) + py * math.sin(a),
            -px * math.sin(a) + py * math.cos(a))


def board_aabb(extents: tuple[float, float, float, float],
               x_mm: float, y_mm: float, rot_deg: float = 0.0
               ) -> tuple[float, float, float, float]:
    """Place a local extents box at (x_mm, y_mm) with rot_deg and return its
    axis-aligned board-frame bounds. Exact for any angle (AABB over the four
    rotated corners)."""
    x0, y0, x1, y1 = extents
    corners = [_rotate_local(cx, cy, rot_deg)
               for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    return (x_mm + min(c[0] for c in corners), y_mm + min(c[1] for c in corners),
            x_mm + max(c[0] for c in corners), y_mm + max(c[1] for c in corners))


# --------------------------------------------------------------------------- #
# Rotation-aware AABB + collision tracking
# --------------------------------------------------------------------------- #

@dataclass
class _Placed:
    ref: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


def _rotated_half_extents(w: float, h: float, rot_deg: float) -> tuple[float, float]:
    """DEPRECATED — kept so older generator scripts keep importing cleanly.

    Half-width/half-height of the AABB of a w x h rectangle rotated by
    rot_deg, ASSUMING the rectangle is centred on the anchor. That
    assumption is false for any 1xN header (anchor = pin 1) and is what let
    TMS V3's J7/J8 run off the board edge. Use board_aabb() with
    get_extents() instead."""
    r = math.radians(rot_deg % 180)
    hw = abs(w / 2 * math.cos(r)) + abs(h / 2 * math.sin(r))
    hh = abs(w / 2 * math.sin(r)) + abs(h / 2 * math.cos(r))
    return hw, hh


class CourtyardCollisionError(RuntimeError):
    def __init__(self, ref_a, ref_b, overlap_x, overlap_y):
        self.ref_a, self.ref_b = ref_a, ref_b
        self.overlap_x, self.overlap_y = overlap_x, overlap_y
        super().__init__(
            f"Placement collision: {ref_a} overlaps {ref_b} by "
            f"{overlap_x:.2f}mm x {overlap_y:.2f}mm. One of these needs a "
            f"different (x, y) — this is exactly the 'placeholder "
            f"coordinates don't transfer to real footprints' failure mode; "
            f"fix it now, at generation time, not after DRC."
        )


class OffBoardError(RuntimeError):
    def __init__(self, ref, aabb, board, over):
        super().__init__(
            f"{ref} extends OUTSIDE the board outline by {over:.2f}mm. "
            f"Part occupies x[{aabb[0]:.2f},{aabb[2]:.2f}] y[{aabb[1]:.2f},{aabb[3]:.2f}]; "
            f"board is x[{board[0]:.2f},{board[2]:.2f}] y[{board[1]:.2f},{board[3]:.2f}]. "
            f"If this is a 1xN header, remember its anchor is PIN 1, not its "
            f"centre — the part runs (n-1)*pitch away from the coordinate you gave."
        )


class PlacementTracker:
    """Call .place() for every component as you place it. Raises immediately
    if the new component's real extents overlap a previously-placed one, or
    fall outside the board outline — before you have written 50 more lines
    assuming the board is fine.

    Extents are the UNION of courtyard geometry and every pad, expressed as
    an offset box relative to the footprint anchor. Both of those matter:

      - pads, because EasyEDA-converted footprints ship courtyards smaller
        than their own land pattern (TMS V3's ADS1256 does), so a
        courtyard-only check will happily place a decoupling cap on top of
        an IC's pins;
      - offset (rather than a centred w x h), because a 1xN header anchors
        on pin 1 and extends one way only.

    board_mm: (width, height) or (x0, y0, x1, y1). When given, every
    placement is bounds-checked and OffBoardError is raised on overhang.

    margin_mm: minimum clearance kept between parts (default matches the
    JLCPCB ~0.5mm assembly clearance guidance in pcb-design-rules.md 1.2).
    """

    def __init__(self, margin_mm: float = 0.5,
                 default_size_mm: tuple[float, float] = (3.0, 3.0),
                 board_mm: tuple[float, ...] | None = None,
                 edge_margin_mm: float = 0.3,
                 survey: bool = False):
        self.margin_mm = margin_mm
        self.default_size_mm = default_size_mm
        self.edge_margin_mm = edge_margin_mm
        # survey=True downgrades both hard errors to collected warnings, so a
        # single run reports EVERY placement problem instead of stopping at the
        # first. Intended for the fix-up loop; leave it False for real builds.
        self.survey = survey
        self.board: tuple[float, float, float, float] | None = None
        if board_mm is not None:
            if len(board_mm) == 2:
                self.board = (0.0, 0.0, float(board_mm[0]), float(board_mm[1]))
            elif len(board_mm) == 4:
                self.board = tuple(float(v) for v in board_mm)  # type: ignore[assignment]
            else:
                raise ValueError("board_mm must be (w, h) or (x0, y0, x1, y1)")
        self._placed: list[_Placed] = []
        self.warnings: list[str] = []

    def place(self, ref: str, fp_def_node, x_mm: float, y_mm: float, rot_deg: float = 0,
              raise_on_collision: bool = True) -> tuple[float, float, float, float]:
        """Register a placement. Returns the board-frame AABB actually
        occupied, so callers can log or lay out against it."""
        extents = None
        if fp_def_node is not None:
            try:
                extents = (get_extents_from_text(fp_def_node)
                           if isinstance(fp_def_node, str) else get_extents(fp_def_node))
            except Exception as exc:      # noqa: BLE001 - fall back, never crash placement
                self.warnings.append(f"{ref}: extent extraction failed ({exc}); using default box.")
        if extents is None:
            w, h = self.default_size_mm
            extents = (-w / 2, -h / 2, w / 2, h / 2)
            self.warnings.append(
                f"{ref}: no courtyard or pad geometry found — using conservative "
                f"default {self.default_size_mm[0]}x{self.default_size_mm[1]}mm centred "
                f"on the anchor. Verify this footprint before trusting the layout."
            )

        aabb = board_aabb(extents, x_mm, y_mm, rot_deg)

        if self.board is not None:
            bx0, by0, bx1, by1 = self.board
            m = self.edge_margin_mm
            over = max(bx0 + m - aabb[0], by0 + m - aabb[1],
                       aabb[2] - (bx1 - m), aabb[3] - (by1 - m))
            if over > 0:
                err = OffBoardError(ref, aabb, self.board, over)
                if self.survey:
                    self.warnings.append(f"OFF-BOARD {ref}: {over:.2f}mm past the edge")
                else:
                    raise err

        h = self.margin_mm / 2
        grown = (aabb[0] - h, aabb[1] - h, aabb[2] + h, aabb[3] + h)
        new = _Placed(ref, *grown)
        for existing in self._placed:
            ox = min(new.bounds[2], existing.bounds[2]) - max(new.bounds[0], existing.bounds[0])
            oy = min(new.bounds[3], existing.bounds[3]) - max(new.bounds[1], existing.bounds[1])
            if ox > 0 and oy > 0:
                if raise_on_collision and not self.survey:
                    raise CourtyardCollisionError(ref, existing.ref, ox, oy)
                self.warnings.append(f"COLLIDE  {ref} overlaps {existing.ref} by {ox:.2f}x{oy:.2f}mm")
        self._placed.append(new)
        return aabb

    def occupied(self) -> list[tuple[str, tuple[float, float, float, float]]]:
        """(ref, board-frame AABB) for every part placed so far, margin included."""
        return [(pl.ref, pl.bounds) for pl in self._placed]

    def hits(self, x_mm: float, y_mm: float, radius_mm: float = 0.0) -> str | None:
        """Ref of the first placed part a circle at (x, y) touches, else None.

        Use this for anything generated onto the board AFTER placement —
        stitching vias, keepouts, silkscreen. The alternative, a hand-written
        list of "places not to put a via", is a second copy of the placement
        coordinates that silently goes stale the moment a part moves. That is
        what happened on TMS V3: the stitching keepout list still named the
        mounting holes' old positions after the board was resized, so vias
        landed inside pads and drilled through other holes."""
        for pl in self._placed:
            x0, y0, x1, y1 = pl.bounds
            if (x0 - radius_mm <= x_mm <= x1 + radius_mm
                    and y0 - radius_mm <= y_mm <= y1 + radius_mm):
                return pl.ref
        return None

    def report(self) -> str:
        lines = [f"{len(self._placed)} components tracked."]
        if self.board:
            lines.append(f"Board outline: x[{self.board[0]:.1f},{self.board[2]:.1f}] "
                         f"y[{self.board[1]:.1f},{self.board[3]:.1f}] "
                         f"(edge margin {self.edge_margin_mm}mm, enforced)")
        else:
            lines.append("NO board outline given — off-board overhang was NOT checked. "
                         "Pass board_mm=(w, h) to enable it.")
        if self.warnings:
            lines.append(f"{len(self.warnings)} warning(s):")
            lines.extend(f"  - {w}" for w in self.warnings)
        else:
            lines.append("No collisions, no off-board parts, no missing-geometry fallbacks.")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Optional: automatic shelf packing (for when hand-placement isn't needed)
# --------------------------------------------------------------------------- #

def shelf_pack(items: list[tuple[str, object]], zone_x: float, zone_y: float,
               zone_w: float, zone_h: float, margin_mm: float = 1.0,
               row_gap_mm: float = 1.0) -> dict[str, tuple[float, float]]:
    """Lay out `items` (list of (ref, fp_def_node)) left-to-right, wrapping
    to a new row when the zone width is exceeded, using each item's REAL
    courtyard size. Returns {ref: (x_mm, y_mm)} — center coordinates,
    already collision-free by construction.

    This is the "don't hand-guess coordinates at all" option: fetch every
    footprint first, then call this once instead of picking (x, y) by eye.
    Good for a zone of same-ish-sized passives (decoupling caps, series
    resistors); for a board's overall floor plan, hand-placement by zone
    (per pcb-design-rules.md §1.1) plus PlacementTracker for verification
    is usually more appropriate.
    """
    positions: dict[str, tuple[float, float]] = {}
    cursor_x = zone_x + margin_mm
    cursor_y = zone_y + margin_mm
    row_height = 0.0

    for ref, fp_def_node in items:
        bbox = get_courtyard_bbox(fp_def_node) or (3.0, 3.0)
        w, h = bbox
        if cursor_x + w > zone_x + zone_w and cursor_x > zone_x + margin_mm:
            cursor_x = zone_x + margin_mm
            cursor_y += row_height + row_gap_mm
            row_height = 0.0
        positions[ref] = (cursor_x + w / 2, cursor_y + h / 2)
        cursor_x += w + margin_mm
        row_height = max(row_height, h)

    total_h = cursor_y + row_height - zone_y
    if total_h > zone_h:
        import sys
        print(f"WARNING: shelf_pack needed {total_h:.1f}mm of height, "
              f"zone only has {zone_h:.1f}mm — components will overflow "
              f"the intended zone. Widen the zone or split into two.",
              file=sys.stderr)

    return positions


if __name__ == '__main__':
    # Quick self-test against a couple of real fetched footprints, if run
    # directly with a project path argument.
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python3 pcb_layout_helpers.py <path-to-.pretty-dir>")
        sys.exit(1)

    pretty_dir = Path(sys.argv[1])
    print(f"Courtyard sizes in {pretty_dir}:\n")
    for mod_file in sorted(pretty_dir.glob("*.kicad_mod")):
        bbox = get_courtyard_bbox_from_file(mod_file)
        if bbox:
            print(f"  {mod_file.stem:50s} {bbox[0]:6.2f} x {bbox[1]:6.2f} mm")
        else:
            print(f"  {mod_file.stem:50s} NO COURTYARD FOUND")
