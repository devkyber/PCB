#!/usr/bin/env python3
"""Schematic label-placement helpers — fixes the "net label sits exactly on
top of the pin name / power-symbol value text" defect class.

Root cause (found on IMU, and structural to every board this workspace
generates): `pin_label()` in every `gen_*_sch.py` places a net label at the
pin's *exact* connection coordinate — deliberately, per docs/DESIGN_RULES.md
§15.7 ("wire every net to the symbol's real pin coordinate, never a guessed
(x,y)"), because a label placed *near* a pin but not exactly on it can look
connected in a screenshot while ERC sees it as dangling. That rule is
correct and must not be relaxed.

But KiCad *also* auto-draws the symbol's own pin name at that same point,
and for power symbols the symbol's own value text lands there too — so
every pin gets two or three overlapping text strings stacked on the same
coordinate. ERC doesn't care (it only checks connectivity, not text
layout), so this is invisible until a human looks at the schematic.

The fix used here — standard KiCad schematic-drawing practice, not
specific to this codebase — is a short **stub wire**: draw a wire segment
from the pin's exact connection point outward (away from the symbol body,
in the pin's real exit direction) by a fixed standoff distance, then place
the label at the *far end* of that stub. The label is still on copper
electrically identical to the pin (ERC-clean, same net, same connectivity
guarantee as before) — it has just been moved to a point in space that
isn't already occupied by the pin's own name text.

Usage (replaces the old `pin_label()` pattern in a `gen_*_sch.py`):

    from schematic_layout_helpers import LabelPlacer

    labels = LabelPlacer(ed, tree)

    def pin_label(ref, pin_number, net_name, symbol_x, symbol_y):
        return labels.place(ref, pin_number, net_name, symbol_x, symbol_y)

`symbol_x, symbol_y` is the same (x, y) you already pass to
`place()`/`place_real()` for that symbol — the placement origin, not a pin
position. It's needed to determine which side of the body a pin is on
(see `pin_exit_orientation` below); pin `angle` metadata is not reliable
for this because real EasyEDA-fetched symbols and native KiCad library
symbols have been observed using the *opposite* angle sign convention for
the same visual direction (confirmed empirically: IMU's real ICM-42688-P
symbol vs. the standard `Conn_01x06` header, same numeric angle, opposite
actual exit side) — comparing pin position against the symbol's own
placement origin sidesteps the whole question and is robust to either
convention.

Power symbols (GND, +3V3, ...) still need a `pin_label()` call — tested
empirically: omitting it produces an ERC `pin_not_connected` error on the
power symbol's own pin, even though same-named power pins join into one
net sheet-wide regardless of any local wire/label. (Same-name net-joining
and "this specific pin has something touching it" are two separate ERC
checks.) The stub-based placement here still fixes the original bug —
the label no longer lands on top of the symbol's own auto-drawn value
text, which is what produced the doubled "GNONND" text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

GRID_MM = 1.27  # KiCad default schematic grid (50 mil)
_STAGGER_STEPS = 4  # distinct stub lengths cycled across a pin column
DEFAULT_STUB_MM = 2.54  # one grid step at the default 1.27mm schematic grid

# KiCad draws a pin's own name text starting AT the pin's connection point
# and extending outward (away from the body) — the same anchor and
# direction our stub-placed label uses. A fixed short stub only clears
# short names ("GND", "VDD"); long real-part pin names ("AP_SDA/AP_SDIO/
# AP_SDI", 22 chars) render far wider than any fixed small stub, so the
# label re-overlaps the pin name's tail end regardless. Estimate the pin
# name's rendered width from its character count and make the stub at
# least that long plus a margin — verified against KiCad's default
# 1.27mm stroke font by rendering imu-icm42688 to SVG and comparing.
CHAR_WIDTH_MM = 1.1  # ~stroke-font character advance at 1.27mm font size
NAME_CLEARANCE_MARGIN_MM = 1.27  # one grid step of breathing room past the name

_DIR_VECTOR = {
    "right": (1.0, 0.0),
    "left": (-1.0, 0.0),
    "up": (0.0, 1.0),
    "down": (0.0, -1.0),
}


# ---------------------------------------------------------------------------
# Power rails: symbols, not text labels
# ---------------------------------------------------------------------------
# The single biggest readability defect in a script-generated schematic is
# that power/ground connections are emitted as *text labels*, because
# "same name == same net" is how netlist entry works. Measured on tms-v3:
# 172 text labels on one sheet, 78 of them (45%) just "GND"/"+5V"/"+3V3",
# including 38 separate "GND" strings. No human-drawn schematic does this
# — every reference schematic uses the *graphical* power symbol (the
# ground bars, the up-arrow rail) which reads as a shape at a glance and
# carries no free-floating text to collide with anything.
#
# Electrically the two are identical: KiCad's `power:*` symbols expose a
# single power-input/output pin whose name joins globally by name, exactly
# like a label. So this is a pure rendering upgrade with no connectivity
# risk — and it deletes ~45% of the sheet's text.
#
# Names below are the actual contents of KiCad 10's `power.kicad_sym`.
POWER_LIB_SYMBOLS = {
    "+10V", "+12C", "+12L", "+12LF", "+12P", "+12V", "+12VA", "+15V", "+1V0",
    "+1V1", "+1V2", "+1V35", "+1V5", "+1V8", "+24V", "+28V", "+2V5", "+2V8",
    "+3.3V", "+3.3VA", "+3.3VADC", "+3.3VDAC", "+3.3VP", "+36V", "+3V0",
    "+3V3", "+3V8", "+48V", "+4V", "+5C", "+5F", "+5P", "+5V", "+5VA", "+5VD",
    "+5VL", "+5VP", "+6V", "+7.5V", "+8V", "+9V", "+9VA", "+BATT", "+VDC",
    "+VSW", "-10V", "-12V", "-12VA", "-15V", "-24V", "-2V5", "-36V", "-3V3",
    "-48V", "-5V", "-5VA", "-6V", "-8V", "-9V", "-9VA", "-BATT", "-VDC",
    "-VSW", "AC", "Earth", "Earth_Clean", "Earth_Protective", "GND", "GND1",
    "GND2", "GND3", "GNDA", "GNDD", "GNDPWR", "GNDREF", "GNDS", "HT", "LINE",
    "NEUT", "PRI_HI", "PRI_LO", "PRI_MID", "PWR_FLAG", "VAA", "VAC", "VBUS",
    "VCC", "VCCQ", "VCOM", "VD", "VDC", "VDD", "VDDA", "VDDF", "VEE", "VMEM",
    "VPP", "VS", "VSS", "VSSA", "Vdrive",
}

# A power symbol's net name comes from its PIN NAME, not from its Value
# field — so substituting a differently-spelled library symbol for a net
# (e.g. drawing `VBAT` with the `+BATT` symbol because it's "the same
# rail") does not decorate the net, it RENAMES it. That silently desyncs
# the schematic from an already-generated .kicad_pcb, and neither ERC nor
# a visual check would show it. Hence: exact match only, no aliasing, no
# normalization. A net that isn't spelled exactly like a library symbol
# stays a text label, which is always correct if less pretty.
#
# This also happens to be the right call semantically for intermediate
# rails: `+5V_FILT` and `VBAT_PROT` are real nodes *between* two stages,
# not global rails, and drawing them as power symbols would wrongly imply
# they're the same net as their unfiltered source.

# Ground-style rails (drawn pointing down) vs supply-style (pointing up).
# Informational only — power symbols are always placed unrotated, which
# is what schematic convention wants; see LabelPlacer.POWER_ROTATION.
def is_ground_rail(lib_symbol_name: str) -> bool:
    n = lib_symbol_name.upper()
    return n.startswith("GND") or n.startswith("EARTH") or n in {"VSS", "VSSA", "NEUT"}


def resolve_power_symbol(net_name: str) -> str | None:
    """Map a net name onto a `power:` library symbol, or None if the net
    should stay a text label. Exact match only — see the note above on
    why aliasing renames nets rather than decorating them."""
    return net_name if net_name in POWER_LIB_SYMBOLS else None


class StubCrossingError(RuntimeError):
    """Two different nets' stub wires geometrically cross/touch.

    KiCad wires connect wherever they physically overlap, regardless of
    intended net — a short stub for a nearby part (a decoupling cap right
    next to its IC, say) can land its endpoint exactly on a *different*
    pin's longer stub if the two happen to cross in space. This is not
    cosmetic: it silently bridges two different nets into one, and
    neither ERC nor a visual check catches it reliably (confirmed on
    baro-bmp390 — a single such crossing merged the entire schematic,
    GND included, into one "+3V3" net, with only one oblique ERC hint
    `pin_to_pin` pointing at two unrelated power-flag pins). Raised
    immediately, with both conflicting (ref, pin, net) triples, so the
    fix (move the component, or pass an explicit shorter/differently-
    directed stub_mm) happens at generation time — the same principle as
    pcb_copilot.layout.geometry's PlacementTracker for PCB courtyards.
    """


def _segments_touch(a1, b1, a2, b2) -> bool:
    """True if two axis-aligned segments share any point (endpoint,
    T-junction, or collinear overlap). Assumes each segment is purely
    horizontal or vertical, which is guaranteed for stub wires (see
    _DIR_VECTOR) — general-case segment intersection isn't needed."""

    def on_segment(p, a, b):
        cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if abs(cross) > 1e-6:
            return False
        dot = (p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])
        if dot < -1e-6:
            return False
        length_sq = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
        return dot <= length_sq + 1e-6

    return any(on_segment(p, a1, b1) for p in (a2, b2)) or any(
        on_segment(p, a2, b2) for p in (a1, b1)
    )


def _snap_to_grid(v: float, grid_mm: float = 1.27) -> float:
    return round(round(v / grid_mm) * grid_mm, 3)


def snap_mcp_y_to_kicad_grid(y_mcp: float, page_h: float,
                             grid_mm: float = GRID_MM) -> float:
    """Snap an MCP-space Y so that the KiCad-space Y it maps to is on grid.

    `y_kicad = page_h - y_mcp`, and page_h is not a grid multiple on any
    ISO sheet, so snapping y_mcp directly leaves y_kicad off-grid. Always
    round-trip through the flip.
    """
    y_k = page_h - y_mcp
    return round(page_h - (round(y_k / grid_mm) * grid_mm), 3)


def pin_exit_orientation(pin_x: float, pin_y: float, symbol_x: float, symbol_y: float) -> str:
    """Which way a pin points away from its symbol's body, as one of the
    four `add_label` orientation strings.

    Compares the pin's position against the symbol's own placement origin
    (the (x, y) passed to `place()`/`place_real()`) rather than the pin's
    library `angle` field — see module docstring for why. Picks whichever
    axis has the larger offset — correct for a 2-pin passive or a 2/4-
    sided IC, but WRONG for a multi-pin single-column header (Conn_01xNN):
    those have a small, ~constant dx (the column's offset from the body)
    and a dy that grows with pin count (2.54mm per pin), so past ~5 pins
    dy exceeds dx and this picks 'up'/'down' — sending every pin's stub
    running lengthwise along the header, straight into its neighbors'
    stubs (confirmed: J3, a 6-pin header, self-crossed on pins 5/6).
    Single-pin callers (passives, power symbols) have no better signal
    than this, so it's kept as the fallback — but prefer
    `pin_exit_orientation_for_symbol` below when multiple pins are known.
    """
    dx = pin_x - symbol_x
    dy = pin_y - symbol_y
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "up" if dy >= 0 else "down"


def pin_exit_orientation_for_symbol(pin_x, pin_y, symbol_x, symbol_y, all_pin_positions) -> str:
    """Like `pin_exit_orientation`, but for a symbol with 3+ pins, looks
    at how many *other* pins share this pin's X (or Y) coordinate to find
    which axis it's stacked along locally, rather than the whole symbol's
    overall bounding-box spread.

    A whole-symbol spread comparison (an earlier version of this
    function) breaks on any multi-edge package: a wide-but-short 24-pin
    module with two 12-pin columns (one on each side) has a wider X
    spread (edge-to-edge) than its Y spread (12 pins' worth of pitch) —
    so "pick the larger spread axis" picks X, and sends every pin's stub
    running vertically (parallel to its own column) instead of
    horizontally (out of the package) — confirmed on gnss-neom9n's U2. A
    plain single-row header doesn't have this failure mode (there's only
    one edge to consider) but a real IC footprint routinely does.

    Counting how many pins share *this pin's own* coordinate sidesteps
    the whole-symbol shape entirely: a pin in a 12-pin column has 11
    other pins at the same X (and exits perpendicular to that, i.e.
    horizontally); a pin isolated on its own row/column falls back to
    the single-pin dominant-axis heuristic.
    """
    if len(all_pin_positions) < 3:
        return pin_exit_orientation(pin_x, pin_y, symbol_x, symbol_y)

    tol = 0.05
    same_x = sum(1 for x, y in all_pin_positions if abs(x - pin_x) < tol)
    same_y = sum(1 for x, y in all_pin_positions if abs(y - pin_y) < tol)

    dx = pin_x - symbol_x
    dy = pin_y - symbol_y

    if same_x > same_y and same_x > 1:
        # this pin shares its X with others -> it's in a vertical column -> exits horizontally
        return "right" if dx >= 0 else "left"
    if same_y > same_x and same_y > 1:
        # this pin shares its Y with others -> it's in a horizontal row -> exits vertically
        return "up" if dy >= 0 else "down"
    # no clear grouping (e.g. this pin is alone on both axes) -> single-pin heuristic
    return pin_exit_orientation(pin_x, pin_y, symbol_x, symbol_y)


@dataclass
class LabelPlacer:
    """Call `.place()` once per pin instead of the old bare `add_label()`
    call. Draws the stub wire and places the label at its far end, tracks
    used label coordinates so a genuine collision (two labels landing on
    the exact same point) is reported, and — critically — raises
    `StubCrossingError` immediately if the new stub wire geometrically
    crosses a previously-placed stub for a *different* net. That crossing
    silently bridges the two nets in KiCad's connectivity model; it isn't
    cosmetic and won't reliably show up in ERC (see `StubCrossingError`'s
    docstring for the confirmed real-world case).
    """

    ed: object
    tree: list
    stub_mm: float = DEFAULT_STUB_MM
    # Callback the generator script supplies so `.power()` can place a
    # `power:*` symbol using the script's own symbol-fetch/inject path:
    #   place_symbol(lib_name, sym_name, ref, value, x, y, rot) -> None
    # Every gen_*_sch.py already has exactly this as its `place()` helper.
    # Left None, `.power()` and `.auto()` degrade gracefully to text labels.
    place_symbol: object = None
    # Optional SymbolPlacer; when set, every power symbol `.power()` places
    # is registered so it can't silently land on top of another component.
    symbols: object = None
    _used_points: set = field(default_factory=set)
    warnings: list = field(default_factory=list)
    _pin_cache: dict = field(default_factory=dict)
    _segments: list = field(default_factory=list)  # (a, b, ref, pin_number, net_name)
    _pwr_seq: object = None
    _used_pwr_refs: set = field(default_factory=set)
    _pwr_rot_cache: dict = field(default_factory=dict)
    _relocated: set = field(default_factory=set)
    power_symbol_count: int = 0

    def _pins(self, ref: str) -> list:
        if ref not in self._pin_cache:
            self._pin_cache[ref] = self.ed.list_pins_for_symbol(self.tree, ref)
        return self._pin_cache[ref]

    def _pin_name(self, ref: str, pin_number: str) -> str:
        for p in self._pins(ref):
            if p["number"] == pin_number:
                return p["name"]
        return ""

    # -- stub geometry (shared by every terminator kind) ------------------

    def _choose_stub(self, ref, pin_number, net_name, symbol_x, symbol_y, stub_mm,
                     for_power=False):
        """Pick the stub segment for a pin: direction from the pin's real
        exit side, length long enough to clear the pin's own auto-drawn
        name text, shrunk in grid steps if it would cross another net's
        stub. Returns (orientation, ((px,py),(ex,ey))).

        Split out of `place()` so that every terminator kind — a text
        label, a graphical power symbol, and anything added later —
        shares one implementation of the geometry rules and one crossing
        check. Duplicating this per terminator is how the two-nets-
        silently-bridged bug class comes back.
        """
        px, py = self.ed.get_pin_position(self.tree, ref, pin_number)
        all_positions = [tuple(p["position_mm"]) for p in self._pins(ref)]
        preferred = pin_exit_orientation_for_symbol(
            px, py, symbol_x, symbol_y, all_positions)
        # Try the pin's natural exit side first, then the others. A pin's
        # own side can simply be full — a dense cluster of decoupling caps
        # and series resistors around an ADC will congest one flank while
        # the opposite one is empty. Leaving via another side is ordinary
        # schematic practice and always beats failing the whole run,
        # which previously forced a manual coordinate hunt per collision.
        orientations = [preferred] + [o for o in ("right", "left", "up", "down")
                                      if o != preferred]

        if stub_mm is not None:
            candidates = [stub_mm]
        elif for_power:
            # A power symbol terminator gets the SHORTEST stub, and is
            # deliberately left out of the stagger below. Its graphic is
            # taller than one 2.54mm pin row, so on a connector it will
            # always intrude on a neighbouring pin's row — the only
            # question is whose text is there. Keeping the rail tight
            # against the part puts the graphic in the empty gutter beside
            # the body, while the neighbours' net-name labels run outward
            # past it. (Doing the reverse — a long rail stub — drives the
            # graphic straight through the middle of that label text,
            # which is what the first version of this did.)
            #
            # This is also the conventional reading order: rails hug the
            # component, signal names travel out to the edge of the block.
            candidates = [DEFAULT_STUB_MM, GRID_MM]
        else:
            base = self.stub_mm
            pin_name = self._pin_name(ref, pin_number)
            if pin_name and pin_name != "~":
                needed = len(pin_name) * CHAR_WIDTH_MM + NAME_CLEARANCE_MARGIN_MM
                base = max(base, needed)
            # Fan-out stagger. On a symbol with several pins leaving the
            # same edge (a header, an IC's pin column), equal-length stubs
            # put every terminator in one tight vertical column at the
            # header's own 2.54mm pitch — and the terminators are wider
            # than that pitch. A net label's text runs several millimetres
            # sideways, and a power symbol's graphic is taller than one
            # pin row, so each one lands on its neighbours' rows. Real
            # schematics stagger these, and so do we: stepping the stub
            # length by pin position spreads the terminators diagonally so
            # each has its own clear space, without moving any pin.
            pins_here = self._pins(ref)
            if len(pins_here) >= 3:
                along = 1 if preferred in ("left", "right") else 0
                order = sorted(
                    {round(tuple(q["position_mm"])[along], 2) for q in pins_here})
                try:
                    rank = order.index(round((py if along else px), 2))
                except ValueError:
                    rank = 0
                base += (rank % _STAGGER_STEPS) * GRID_MM * 2
            base = _snap_to_grid(base)
            candidates = []
            v = base
            while v > GRID_MM:
                candidates.append(round(v, 3))
                v -= GRID_MM
            candidates.append(GRID_MM)

        chosen_seg = None
        chosen = None
        blocking = None
        orientation = preferred
        for cand_orientation in orientations:
            dxu, dyu = _DIR_VECTOR[cand_orientation]
            for stub in candidates:
                ex = round(px + dxu * stub, 3)
                ey = round(py + dyu * stub, 3)
                seg = ((px, py), (ex, ey))
                conflict = None
                for (a, b, other_ref, other_pin, other_net) in self._segments:
                    if other_net != net_name and _segments_touch(seg[0], seg[1], a, b):
                        conflict = (a, b, other_ref, other_pin, other_net)
                        break
                if conflict is None:
                    chosen, chosen_seg, orientation = stub, seg, cand_orientation
                    break
                blocking = conflict
            if chosen_seg is not None:
                break
        if orientation != preferred and chosen_seg is not None:
            self.warnings.append(
                f"{ref}.{pin_number} [{net_name}]: exits {orientation} "
                f"instead of {preferred} — its own side was congested.")

        if chosen_seg is None and self.symbols is not None:
            # Nothing worked in any direction at any length. Give the
            # symbol more room and try once more — but ONLY if none of its
            # pins have been wired yet, since moving it afterwards would
            # strand the stubs already drawn to its old pin positions.
            # One relocation attempt per symbol, ever. Retrying lets a
            # symbol wander the sheet chasing a clear route it may never
            # find, and the search restarts from each new position — a
            # cheap way to hang the generator on a dense board.
            already_wired = any(seg[2] == ref for seg in self._segments)
            if not already_wired and ref not in self._relocated:
                self._relocated.add(ref)
                new_origin = self.symbols.relocate(ref, extra_clearance_mm=5.08)
                if new_origin is not None:
                    self._pin_cache.pop(ref, None)
                    return self._choose_stub(
                        ref, pin_number, net_name,
                        new_origin[0], new_origin[1], stub_mm, for_power)

        if chosen_seg is None:
            a, b, other_ref, other_pin, other_net = blocking
            raise StubCrossingError(
                f"Stub wire for {ref}.{pin_number} [{net_name}] crosses the "
                f"stub wire for {other_ref}.{other_pin} [{other_net}] "
                f"({a} -> {b}) even shrunk to a {GRID_MM}mm minimum — this "
                f"bridges the two nets. The two components are placed too "
                f"close together for any stub length to clear; move one of "
                f"them further apart."
            )
        if chosen != candidates[0] and stub_mm is None:
            self.warnings.append(
                f"{ref}.{pin_number} [{net_name}]: stub auto-shrunk to "
                f"{chosen}mm (from {candidates[0]}mm) to clear a nearby "
                f"stub — label may sit close to the pin name; consider "
                f"more spacing here if it looks cramped."
            )
        return orientation, chosen_seg

    def _commit_stub(self, seg, ref, pin_number, net_name):
        """Draw the stub wire and register it for crossing detection.
        Returns the far endpoint, where the terminator goes."""
        for (a, b, other_ref, other_pin, other_net) in self._segments:
            if _segments_touch(seg[0], seg[1], a, b):
                self.warnings.append(
                    f"{ref}.{pin_number} and {other_ref}.{other_pin} (both "
                    f"[{net_name}]) have crossing stub wires — harmless "
                    f"(same net) but worth tidying up."
                )
        (px, py), (ex, ey) = seg
        self.ed.add_wire(self.tree, px, py, ex, ey)
        self._segments.append((seg[0], seg[1], ref, pin_number, net_name))
        return ex, ey

    # -- terminators ------------------------------------------------------

    def place(self, ref: str, pin_number: str, net_name: str,
              symbol_x: float, symbol_y: float, stub_mm: float | None = None) -> tuple[float, float]:
        """Terminate a pin with a **text net label** at the end of a stub wire.

        If the caller passes an explicit `stub_mm`, that length is fixed
        and a crossing raises `StubCrossingError` immediately (the caller
        asked for that exact geometry, so a collision means the caller's
        own layout has a real problem to fix). Otherwise — the normal
        case — a crossing is resolved automatically by shrinking the
        stub in steps down to a 1.27mm floor before giving up.

        Prefer `.auto()`, which sends standard power rails to `.power()`
        (a graphical symbol) and everything else here.
        """
        orientation, seg = self._choose_stub(
            ref, pin_number, net_name, symbol_x, symbol_y, stub_mm)
        ex, ey = self._commit_stub(seg, ref, pin_number, net_name)
        # Net label text is ALWAYS drawn horizontally, even on a vertical
        # stub. KiCad rotates a label's text to match its orientation, so
        # an "up"/"down" stub renders the net name sideways — which reads
        # badly, and lands the rotated text straight along the component
        # body it just left (confirmed on baro-bmp390: R1/R2's I2C_SCL and
        # I2C_SDA labels printed vertically down through the resistor
        # bodies and their own "4.7k" value text). Real schematics keep
        # net names horizontal regardless of wire direction. "right" only
        # sets the text's reading direction; the label still attaches at
        # the stub endpoint, so connectivity is unaffected.
        text_orientation = orientation if orientation in ("left", "right") else "right"
        self.ed.add_label(self.tree, net_name, ex, ey, text_orientation)

        key = (ex, ey)
        if key in self._used_points:
            self.warnings.append(
                f"{ref}.{pin_number} [{net_name}]: label at ({ex}, {ey}) "
                f"coincides with an already-placed label — increase stub_mm "
                f"for one of them or check for a genuine routing coincidence."
            )
        self._used_points.add(key)
        return ex, ey

    def _next_power_ref(self) -> str:
        """Allocate an unused `#PWRnn` reference.

        Seeded by scanning the tree once, so it coexists with any power
        symbols the generator script placed by hand before switching to
        `.power()` (every board here has hand-placed PWR_FLAGs).
        """
        if self._pwr_seq is None:
            used = set()
            for node in self.tree:
                if not (isinstance(node, list) and node and str(node[0]) == "symbol"):
                    continue
                r = self.ed.get_symbol_property(node, "Reference")
                if r and r.startswith("#PWR"):
                    used.add(r)
            # Start high. A generator script places its own power symbols
            # (PWR_FLAGs and the like) as #PWR01, #PWR02... and may do so
            # AFTER the first auto-allocation, so they are not in the scan
            # above. Numbering from 101 keeps the two ranges disjoint
            # instead of relying on placement order.
            self._pwr_seq = 100
            self._used_pwr_refs = used
        while True:
            self._pwr_seq += 1
            cand = f"#PWR{self._pwr_seq:02d}"
            if (cand not in self._used_pwr_refs
                    and self.ed.find_symbol_by_reference(self.tree, cand) is None):
                self._used_pwr_refs.add(cand)
                return cand

    # Power symbols are ALWAYS placed unrotated, and that is a deliberate
    # decision rather than a default left unset. Universal schematic
    # convention draws a supply rail pointing up and a ground pointing
    # down no matter which way the wire reaches it — rotating a ground
    # symbol to lie sideways because its stub happens to run horizontally
    # is not something a hand-drawn schematic does, and it makes the rail
    # harder to pick out at a glance, which is the entire reason for
    # using a symbol instead of text.
    #
    # An earlier version of this code tried to *derive* the rotation
    # empirically, by moving a placed symbol through all four rotations
    # and measuring where its pin landed. That probe could never work: a
    # `power:*` symbol's pin sits exactly ON its placement origin, so
    # rotation cannot move it, all four probes tie, and the function
    # always returned 0 while appearing to have computed something.
    POWER_ROTATION = 0.0

    def power(self, ref: str, pin_number: str, net_name: str,
              symbol_x: float, symbol_y: float, stub_mm: float | None = None,
              sym_name: str | None = None) -> tuple[float, float]:
        """Terminate a pin with a **graphical power symbol** (GND bars, rail
        arrow) instead of a text label — the way every hand-drawn schematic
        does it.

        Falls back to `.place()` (a text label) when the net isn't a
        standard global rail, or when the generator didn't supply a
        `place_symbol` callback.

        The symbol is positioned by measuring where its own pin actually
        lands and then translating the whole symbol so that pin sits
        exactly on the stub's endpoint. Placing it at the endpoint
        directly would connect only by luck: a power symbol's pin is not
        at its placement origin, and the offset changes with rotation.
        """
        lib_sym = sym_name or resolve_power_symbol(net_name)
        if lib_sym is None or self.place_symbol is None:
            return self.place(ref, pin_number, net_name, symbol_x, symbol_y, stub_mm)

        orientation, seg = self._choose_stub(
            ref, pin_number, net_name, symbol_x, symbol_y, stub_mm, for_power=True)
        ex, ey = self._commit_stub(seg, ref, pin_number, net_name)

        rot = self.POWER_ROTATION
        pwr_ref = self._next_power_ref()
        if self.symbols is not None:
            self.symbols.pending_power = (pwr_ref, ref)
        try:
            self.place_symbol("power", lib_sym, pwr_ref, net_name, ex, ey, 0)
        finally:
            if self.symbols is not None:
                self.symbols.pending_power = ()
        # Translate so the symbol's own pin lands exactly on the stub end.
        # For every stock `power:*` symbol the pin is already at the
        # origin so this is a no-op, but it is kept (and verified below)
        # because nothing guarantees that for a custom power symbol.
        self.ed.move_symbol(self.tree, pwr_ref, ex, ey, rot)
        cx, cy = self.ed.get_pin_position(self.tree, pwr_ref, "1")
        self.ed.move_symbol(self.tree, pwr_ref, round(ex + (ex - cx), 3),
                            round(ey + (ey - cy), 3), rot)

        vx, vy = self.ed.get_pin_position(self.tree, pwr_ref, "1")
        if abs(vx - ex) > 0.01 or abs(vy - ey) > 0.01:
            raise RuntimeError(
                f"power symbol {pwr_ref} ({lib_sym}) for {ref}.{pin_number} "
                f"landed its pin at ({vx}, {vy}) instead of the stub end "
                f"({ex}, {ey}) — it would be electrically dangling."
            )

        self.hide_reference(pwr_ref)
        # The symbol's Value text IS the rail name and is the thing the
        # reader should see. Set it ABSOLUTELY (not as an offset): the
        # symbol has been moved twice since it was created, and property
        # text does not travel with `move_symbol`.
        dxu, dyu = _DIR_VECTOR[orientation]
        self.set_property_pos(
            pwr_ref, "Value",
            round(ex + dxu * (POWER_BODY_MM + 1.27) + (0.0 if dxu else 1.9), 3),
            round(ey + dyu * (POWER_BODY_MM + 1.27), 3),
        )
        self.power_symbol_count += 1
        return ex, ey

    def auto(self, ref: str, pin_number: str, net_name: str,
             symbol_x: float, symbol_y: float, stub_mm: float | None = None) -> tuple[float, float]:
        """The one call a generator script should make per pin.

        Standard global rails (GND, +3V3, +5V, ...) get a graphical power
        symbol; every other net gets a text label. This is the whole
        power-symbol upgrade from a caller's point of view: swap
        `pin_label()`'s body from `.place(...)` to `.auto(...)` and the
        sheet loses its floating rail text.
        """
        if resolve_power_symbol(net_name) is not None and self.place_symbol is not None:
            return self.power(ref, pin_number, net_name, symbol_x, symbol_y, stub_mm)
        return self.place(ref, pin_number, net_name, symbol_x, symbol_y, stub_mm)


    def hide_reference(self, ref: str) -> None:
        """Hide a symbol's Reference designator text (e.g. "#PWR01").

        Every generated symbol's Reference and Value property text is
        placed at the exact same coordinate — the symbol's own placement
        origin (see `build_symbol_instance` in sch_editor.py) — with no
        offset between them. For a normal component (R1, C1, U1, ...) this
        is invisible in practice because the surrounding graphics and grid
        give it room, but power/flag symbols (#PWR01, #FLG01, ...) are
        small and their auto-numbered reference is never meaningful to a
        reader anyway — every real-world schematic hides it. Call this
        right after placing any `power:*` symbol.
        """
        import sexpdata
        s_node = self.ed.find_symbol_by_reference(self.tree, ref)
        if s_node is None:
            raise KeyError(f"no symbol with reference {ref!r}")
        for prop in self.ed.find_children(s_node, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                effects = self.ed.find_child(prop, "effects")
                if effects is None:
                    effects = [sexpdata.Symbol("effects")]
                    prop.append(effects)
                if self.ed.find_child(effects, "hide") is None:
                    effects.append([sexpdata.Symbol("hide"), sexpdata.Symbol("yes")])
                return
        raise KeyError(f"property 'Reference' not found on symbol {ref!r}")

    def hide_property(self, ref: str, prop_name: str) -> None:
        """Hide a symbol's named property text.

        Used for e.g. a PWR_FLAG's Value ("PWR_FLAG"): the flag graphic is
        the notation an EE reads, and the word next to it is redundant text
        that collides with the rail symbol the flag attaches to.
        """
        import sexpdata
        s_node = self.ed.find_symbol_by_reference(self.tree, ref)
        if s_node is None:
            raise KeyError(f"no symbol with reference {ref!r}")
        for prop in self.ed.find_children(s_node, "property"):
            if len(prop) >= 3 and prop[1] == prop_name:
                effects = self.ed.find_child(prop, "effects")
                if effects is None:
                    effects = [sexpdata.Symbol("effects")]
                    prop.append(effects)
                if self.ed.find_child(effects, "hide") is None:
                    effects.append([sexpdata.Symbol("hide"), sexpdata.Symbol("yes")])
                return
        raise KeyError(f"property {prop_name!r} not found on symbol {ref!r}")

    def offset_property(self, ref: str, prop_name: str, dx_mm: float, dy_mm: float) -> None:
        """Shift a symbol's named property text (e.g. "Value", "Reference")
        by (dx_mm, dy_mm) in MCP coords (Y up), away from wherever it
        currently sits.

        Every generated symbol's Reference AND Value property text is
        placed at the exact same coordinate — the symbol's own placement
        origin (see `build_symbol_instance` in sch_editor.py) — with no
        offset between them or from the symbol's own graphics. For a part
        with enough surrounding whitespace this can go unnoticed, but it's
        the direct cause of e.g. a capacitor's Reference ("C1") and Value
        ("100nF") text rendering on top of each other: both properties
        default to the identical point. Call this once per property that
        needs to move; leave the other one alone if it's already clear.
        """
        from kicad_claude.utils.geometry import mcp_to_kicad_xy

        s_node = self.ed.find_symbol_by_reference(self.tree, ref)
        if s_node is None:
            raise KeyError(f"no symbol with reference {ref!r}")
        page_h = self.ed.page_height_mm(self.tree)
        for prop in self.ed.find_children(s_node, "property"):
            if len(prop) >= 3 and prop[1] == prop_name:
                at = self.ed.find_child(prop, "at")
                if at is None or len(at) < 3:
                    raise ValueError(f"{prop_name} property on {ref!r} has no (at ...)")
                cur_x_k, cur_y_k = float(at[1]), float(at[2])
                cur_mcp_x, cur_mcp_y = cur_x_k, page_h - cur_y_k
                new_x_k, new_y_k = mcp_to_kicad_xy(
                    cur_mcp_x + dx_mm, cur_mcp_y + dy_mm, page_h
                )
                at[1], at[2] = round(new_x_k, 3), round(new_y_k, 3)
                return
        raise KeyError(f"property {prop_name!r} not found on symbol {ref!r}")

    def set_property_pos(self, ref: str, prop_name: str, x_mm: float, y_mm: float) -> None:
        """Put a symbol's named property text at an ABSOLUTE sheet position.

        `offset_property` shifts text relative to wherever it currently is,
        which is only meaningful if the symbol hasn't moved since. Property
        `(at ...)` nodes hold absolute sheet coordinates and are NOT updated
        by `move_symbol`, so any code that places a symbol, moves it, and
        then offsets its text leaves the text stranded at the old location.
        Anything that repositions a symbol must set text absolutely.
        """
        set_property_pos(self.ed, self.tree, ref, prop_name, x_mm, y_mm)

    def offset_value(self, ref: str, dx_mm: float, dy_mm: float) -> None:
        """Shorthand for `offset_property(ref, "Value", dx_mm, dy_mm)`."""
        self.offset_property(ref, "Value", dx_mm, dy_mm)

    def report(self) -> str:
        head = (f"{len(self._used_points)} text labels + "
                f"{self.power_symbol_count} power symbols placed")
        if not self.warnings:
            return f"{head}, no coordinate collisions."
        lines = [f"{head}. {len(self.warnings)} warning(s):"]
        lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Symbol placement collision detection
# ---------------------------------------------------------------------------

POWER_BODY_MM = 2.54          # roughly how far a power symbol's graphic
                              # extends past its own pin
MIN_SYMBOL_EXTENT_MM = 2.54   # half-body for symbols whose pins are collinear
SYMBOL_CLEARANCE_MM = 2.54    # required gap between two symbols' bodies


def set_property_pos(ed, tree, ref: str, prop_name: str, x_mm: float, y_mm: float) -> None:
    """Put a symbol's named property text at an ABSOLUTE sheet position."""
    from kicad_claude.utils.geometry import mcp_to_kicad_xy

    s_node = ed.find_symbol_by_reference(tree, ref)
    if s_node is None:
        raise KeyError(f"no symbol with reference {ref!r}")
    page_h = ed.page_height_mm(tree)
    for prop in ed.find_children(s_node, "property"):
        if len(prop) >= 3 and prop[1] == prop_name:
            at = ed.find_child(prop, "at")
            if at is None or len(at) < 3:
                raise ValueError(f"{prop_name} property on {ref!r} has no (at ...)")
            nx, ny = mcp_to_kicad_xy(x_mm, y_mm, page_h)
            at[1], at[2] = round(nx, 3), round(ny, 3)
            return
    raise KeyError(f"property {prop_name!r} not found on symbol {ref!r}")


class SymbolOverlapError(RuntimeError):
    """Two symbols were placed overlapping (or closer than the clearance).

    This is the schematic twin of `pcb_copilot.layout.geometry`'s courtyard
    collision check, and it exists for exactly the same reason: a
    generator script picks (x, y) for each symbol by hand, those numbers
    are chosen against whatever the symbol looked like at the time, and
    they do not survive the symbol changing size. On the PCB side that was
    placeholder footprints being replaced by real ones. On the schematic
    side it's the same thing one step earlier — a 14-pin real IC symbol is
    far wider than the generic box it stood in for, so coordinates picked
    for the placeholder put the decoupling caps *inside the IC body*
    (confirmed on imu-icm42688: C1 and C2 both landed within U1's outline,
    and TP3 on its edge).

    Nothing catches this otherwise. ERC checks connectivity, not geometry,
    so a symbol drawn on top of another symbol is 100% ERC-clean; the
    netlist is correct; only a human looking at the rendered sheet sees
    it. Raising at generation time turns "regenerate, render, squint,
    nudge a number, repeat" into a single explicit error naming both
    symbols and the exact overlap.
    """


def _bbox_overlap(a, b, clearance: float):
    """Overlap rectangle of two boxes grown by `clearance`, or None."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    h = clearance / 2.0
    ax0, ay0, ax1, ay1 = ax0 - h, ay0 - h, ax1 + h, ay1 + h
    bx0, by0, bx1, by1 = bx0 - h, by0 - h, bx1 + h, by1 + h
    ox0, oy0 = max(ax0, bx0), max(ay0, by0)
    ox1, oy1 = min(ax1, bx1), min(ay1, by1)
    if ox1 <= ox0 or oy1 <= oy0:
        return None
    return (ox0, oy0, ox1, oy1)


@dataclass
class SymbolPlacer:
    """Tracks where each placed symbol actually sits and refuses overlaps.

    Call `.register(ref)` immediately after placing each symbol — the
    natural home for that call is inside the generator script's own
    `place()` / `place_real()` helper, so every symbol is covered
    automatically and no future edit can forget one.

    The box is derived from the symbol's **real, post-placement absolute
    pin positions** (`list_pins_for_symbol`), not from the library
    definition plus assumed rotation math. That's deliberate: it needs no
    knowledge of the symbol-space/sheet-space coordinate flip or of
    KiCad's rotation sign, both of which have already been observed to
    behave inconsistently between EasyEDA-fetched and native symbols. For
    an IC the pins sit outside the body outline, so the pin box is a
    slightly conservative stand-in for the drawn body — which is the
    right direction to err.
    """

    ed: object
    tree: list
    clearance_mm: float = SYMBOL_CLEARANCE_MM
    # When True, a colliding symbol is MOVED to the nearest free spot
    # instead of raising. This is what makes a 69-component sheet
    # tractable: hand-picked coordinates always collide somewhere, and
    # fixing them one raised exception at a time is exactly the
    # regenerate-render-squint-nudge loop this module exists to delete.
    # Every relocation is reported, so nothing moves silently.
    auto_resolve: bool = True
    sheet_margin_mm: float = 12.7
    _boxes: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    # Set by LabelPlacer.power() just before it asks the generator script's
    # own place() helper to drop a `power:*` symbol. That helper registers
    # every symbol it places (which is what makes coverage automatic and
    # unforgettable), but a power symbol is a special case: it is *meant*
    # to sit flush against the pin it terminates. This hands register()
    # the context to apply zero clearance and to exempt the parent, so the
    # generic call site needs no special-casing.
    pending_power: tuple = ()

    def bbox(self, ref: str):
        pins = self.ed.list_pins_for_symbol(self.tree, ref)
        if not pins:
            return None
        xs = [p["position_mm"][0] for p in pins]
        ys = [p["position_mm"][1] for p in pins]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        # A 2-pin passive's pins are collinear (zero width on one axis) and a
        # 1-pin symbol is a point; neither reflects the drawn body. Give any
        # degenerate axis a real half-body so the box means something.
        if x1 - x0 < MIN_SYMBOL_EXTENT_MM:
            cx = (x0 + x1) / 2.0
            x0, x1 = cx - MIN_SYMBOL_EXTENT_MM / 2, cx + MIN_SYMBOL_EXTENT_MM / 2
        if y1 - y0 < MIN_SYMBOL_EXTENT_MM:
            cy = (y0 + y1) / 2.0
            y0, y1 = cy - MIN_SYMBOL_EXTENT_MM / 2, cy + MIN_SYMBOL_EXTENT_MM / 2
        return (round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3))

    def register(self, ref: str, clearance_mm: float | None = None,
                 allow_overlap: tuple = ()) -> None:
        """Record `ref`'s footprint on the sheet, raising if it collides.

        `allow_overlap` names symbols this one is *expected* to sit
        against — used for the graphical power symbols `LabelPlacer.power()`
        attaches directly to a component's pin, which legitimately touch
        their parent.
        """
        self.snap_pins_to_grid(ref)
        box = self.bbox(ref)
        if box is None:
            return None
        clear = self.clearance_mm if clearance_mm is None else clearance_mm
        if self.pending_power and self.pending_power[0] == ref:
            clear = 0.0
            allow_overlap = tuple(allow_overlap) + (self.pending_power[1],)

        hit = self._first_collision(ref, box, clear, allow_overlap)
        if hit is None and not self._in_bounds(box):
            # Off-sheet placements are as invisible to ERC as overlaps are,
            # and they render clipped by the frame or hidden under the
            # title block. Treat "outside the drawable area" as a collision
            # with the sheet itself so the same search pulls it back in.
            hit = ("the sheet border", box, box)
        if hit is not None and self.auto_resolve:
            box, moved = self._relocate(ref, box, clear, allow_overlap)
            if moved is None:
                hit_ref, hit_box, ov = hit
                raise SymbolOverlapError(
                    f"symbol {ref} overlaps {hit_ref} at {hit_box} and no "
                    f"free position was found anywhere on the sheet. The "
                    f"sheet is full — split the design across hierarchical "
                    f"sheets, or use a larger page."
                )
            self.warnings.append(
                f"{ref}: moved by ({moved[0]:+.2f}, {moved[1]:+.2f})mm to "
                f"clear {hit[0]}. Its scripted coordinate overlapped — "
                f"nudge it in KiCad if you want it somewhere specific."
            )
            hit = None

        if hit is not None:
            hit_ref, hit_box, ov = hit
            raise SymbolOverlapError(
                f"symbol {ref} at {box} overlaps {hit_ref} at {hit_box} "
                f"(overlap region {tuple(round(v, 2) for v in ov)}, "
                f"clearance {clear}mm). Move {ref}: it needs "
                f"{round(ov[2] - ov[0], 2)}mm more horizontal or "
                f"{round(ov[3] - ov[1], 2)}mm more vertical separation. "
                f"Symbol boxes come from real pin extents, so this is the "
                f"actual drawn size — not an estimate."
            )
        self._boxes[ref] = box
        self.autoplace_text(ref, box)
        cx = round((box[0] + box[2]) / 2.0, 3)
        cy = round((box[1] + box[3]) / 2.0, 3)
        return (cx, cy)

    def relocate(self, ref: str, extra_clearance_mm: float = 0.0):
        """Move an already-registered symbol to the nearest free spot.

        Used by LabelPlacer when a pin cannot find any clear stub in any
        direction: the symbol is simply in too crowded a neighbourhood,
        and the fix is more space, not a cleverer wire.
        """
        if ref not in self._boxes:
            return None
        box = self._boxes.pop(ref)
        clear = self.clearance_mm + extra_clearance_mm
        newbox, moved = self._relocate(ref, box, clear, ())
        if moved is None:
            self._boxes[ref] = box
            return None
        self._boxes[ref] = newbox
        self.autoplace_text(ref, newbox)
        self.warnings.append(
            f"{ref}: moved by ({moved[0]:+.2f}, {moved[1]:+.2f})mm — no "
            f"clear wire route existed at its scripted position.")
        return (round((newbox[0] + newbox[2]) / 2.0, 3),
                round((newbox[1] + newbox[3]) / 2.0, 3))

    def _in_bounds(self, box):
        page_w, page_h = self._page_size()
        m = self.sheet_margin_mm
        return (box[0] >= m and box[1] >= m
                and box[2] <= page_w - m and box[3] <= page_h - m)

    def _first_collision(self, ref, box, clear, allow_overlap):
        for other, obox in self._boxes.items():
            if other == ref or other in allow_overlap:
                continue
            ov = _bbox_overlap(box, obox, clear)
            if ov is not None:
                return (other, obox, ov)
        return None

    def _relocate(self, ref, box, clear, allow_overlap):
        """Search outward on the schematic grid for the nearest free spot.

        Searching in rings of increasing radius keeps the symbol as close
        to where the script asked for it as the sheet allows, so a
        functional grouping the author intended survives the fix. Movement
        is on the 1.27mm grid so pins stay grid-aligned.
        """
        page_w, page_h = self._page_size()
        step = GRID_MM * 2
        for ring in range(1, 121):
            r = ring * step
            for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r),
                           (r, r), (-r, r), (r, -r), (-r, -r)):
                cand = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
                if (cand[0] < self.sheet_margin_mm
                        or cand[1] < self.sheet_margin_mm
                        or cand[2] > page_w - self.sheet_margin_mm
                        or cand[3] > page_h - self.sheet_margin_mm):
                    continue
                if self._first_collision(ref, cand, clear, allow_overlap) is None:
                    ox, oy = self._origin(ref)
                    self.ed.move_symbol(self.tree, ref,
                                        round(ox + dx, 3), round(oy + dy, 3))
                    return cand, (dx, dy)
        return box, None

    def _origin(self, ref):
        from kicad_claude.utils.geometry import mcp_to_kicad_xy  # noqa: F401
        s_node = self.ed.find_symbol_by_reference(self.tree, ref)
        at = self.ed.find_child(s_node, "at")
        page_h = self.ed.page_height_mm(self.tree)
        return float(at[1]), page_h - float(at[2])

    _PAPER_MM = {"A5": (210.0, 148.0), "A4": (297.0, 210.0),
                 "A3": (420.0, 297.0), "A2": (594.0, 420.0),
                 "A1": (841.0, 594.0), "A0": (1189.0, 841.0)}

    def _page_size(self):
        page_h = self.ed.page_height_mm(self.tree)
        for node in self.tree:
            if isinstance(node, list) and node and str(node[0]) == "paper":
                size = self._PAPER_MM.get(str(node[1]).strip('"'))
                if size:
                    return size
        # Fall back to matching on height if the paper token is custom.
        for w, h in self._PAPER_MM.values():
            if abs(page_h - h) < 1:
                return w, h
        return 297.0, page_h

    def snap_pins_to_grid(self, ref: str) -> None:
        """Shift a symbol so its PINS land on the 1.27mm connection grid.

        Snapping the symbol's placement *origin* to the grid — which the
        generator scripts already do — is not the same thing and does not
        achieve this. A real EasyEDA-fetched symbol frequently carries its
        pins at a non-grid offset from its own origin, so a grid-aligned
        origin still yields off-grid pins, and every wire drawn to them
        ends off-grid too. KiCad reports each one as `endpoint_off_grid`
        (305 of them on tms-v3 alone), and off-grid endpoints are a real
        hazard, not just noise: they are what makes a wire fail to connect
        when someone later edits the sheet by hand on a normal grid.

        Measure pin 1's distance from the nearest grid intersection and
        translate the whole symbol back by that residual. Pin *pitch* is
        essentially always a grid multiple even when the origin offset
        isn't, so aligning one pin aligns them all.
        """
        pins = self.ed.list_pins_for_symbol(self.tree, ref)
        if not pins:
            return
        px, py = pins[0]["position_mm"]
        page_h = self.ed.page_height_mm(self.tree)
        # Snap in KICAD's coordinate space, not this module's. The two
        # differ by a Y flip, `y_kicad = page_h - y_mcp`, and page_h is
        # NOT a multiple of the 1.27mm grid on any ISO sheet (A4 is
        # 210mm; 210 / 1.27 = 165.35). So a Y that is perfectly grid
        # aligned here lands off-grid in the file, and KiCad — which
        # only ever sees its own coordinates — flags it. Snapping in
        # MCP space is therefore a guaranteed no-op for exactly the
        # coordinates that are broken (measured: 47 off-grid endpoints
        # before and after, on every board).
        py_k = page_h - py
        dx = _snap_to_grid(px) - px
        dy_k = _snap_to_grid(py_k) - py_k
        if abs(dx) < 1e-4 and abs(dy_k) < 1e-4:
            return
        ox, oy = self._origin(ref)
        self.ed.move_symbol(self.tree, ref,
                            round(ox + dx, 3), round(oy - dy_k, 3))

    def autoplace_text(self, ref: str, box=None) -> None:
        """Put this symbol's Reference above its body and Value below it.

        KiCad's own symbol *editor* carries sensible per-symbol text
        offsets, but symbols injected programmatically get both properties
        stamped at the placement origin with zero offset (see
        `build_symbol_instance` in sch_editor.py) — i.e. Reference and
        Value drawn exactly on top of each other, in the middle of the
        symbol's own graphics. That is the "C1/100nF printed as one
        smear" and "U1 over ICM-42688-P" defect, and it is present on
        every generated symbol on every board here.

        Doing it here, off the measured pin box, means it happens once
        for every symbol automatically. The alternative — the generator
        script calling `offset_property` per component — is what these
        scripts used to do, and it silently misses every component whose
        author forgot, which was most of them.
        """
        box = box or self._boxes.get(ref) or self.bbox(ref)
        if box is None:
            return
        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

        # Put the text on whichever side the pins DON'T leave from. Text
        # and terminators (stubs, labels, rail symbols) compete for the
        # same space, and the pins decide who wins: whatever direction the
        # pins exit is already spoken for.
        #
        # A tall-vs-wide bounding-box test is not good enough to decide
        # this — it gets vertical *connectors* backwards. A 4-pin vertical
        # header and a 2-pin vertical capacitor have the same tall, narrow
        # pin box, but the capacitor's pins exit up and down (so its text
        # belongs beside it) while the header's four pins all exit
        # sideways (so text beside it lands on the body). Reuse
        # `pin_exit_orientation_for_symbol`, which already distinguishes
        # these by counting how many pins share a coordinate.
        pins = self.ed.list_pins_for_symbol(self.tree, ref)
        positions = [tuple(q["position_mm"]) for q in pins]
        sideways = 0
        for (px, py) in positions:
            o = pin_exit_orientation_for_symbol(px, py, cx, cy, positions)
            sideways += 1 if o in ("left", "right") else -1

        if sideways >= 0:
            # Pins leave the sides -> above and below are free.
            rx, ry = round(cx, 3), round(y1 + 2.54, 3)
            vx, vy = round(cx, 3), round(y0 - 2.54, 3)
        else:
            # Pins leave top and bottom -> the flanks are free.
            rx, ry = round(x1 + 3.18, 3), round(cy + 1.27, 3)
            vx, vy = round(x1 + 3.18, 3), round(cy - 1.27, 3)

        set_property_pos(self.ed, self.tree, ref, "Reference", rx, ry)
        try:
            set_property_pos(self.ed, self.tree, ref, "Value", vx, vy)
        except KeyError:
            pass

    def report(self) -> str:
        if not self._boxes:
            return "no symbols registered."
        tail = ""
        if self.warnings:
            tail = ("\n  " + "\n  ".join(self.warnings)
                    + f"\n  ({len(self.warnings)} symbol(s) auto-relocated)")
        xs0 = min(b[0] for b in self._boxes.values())
        ys0 = min(b[1] for b in self._boxes.values())
        xs1 = max(b[2] for b in self._boxes.values())
        ys1 = max(b[3] for b in self._boxes.values())
        return (f"{len(self._boxes)} symbols placed, no overlaps; "
                f"sheet extent used: ({xs0:.1f}, {ys0:.1f}) - "
                f"({xs1:.1f}, {ys1:.1f}) mm" + tail)


def set_title_block(tree, title: str, rev: str, date: str = '',
                    company: str = '', comments=None,
                    paper: str | None = None) -> None:
    """Give the sheet a title block, and optionally set the paper size.

    Why this is here rather than in each generator
    ----------------------------------------------
    Until 2026-08-26 not one of the four boards had a `title_block` node at
    all. TITLE / AUTHOR / REVISION were set as textvars in the `.kicad_pro`,
    which do not render, so every schematic printed with Title, Date and Rev
    blank — on boards whose own CLAUDE.md convention is "put your name and
    rev on it". A printed schematic with no revision cannot be matched to the
    board it describes, which is the whole point of the field.

    Four copies of this would be four chances to drift (defect class #5:
    the second build path). One implementation, called by every generator.

    `paper` also lives here for the same reason: tms-v3 open-coded its A3
    override by walking the tree, and any other board needing a bigger sheet
    would have copied that loop.
    """
    import sexpdata

    def sym(s):
        return sexpdata.Symbol(s)

    paper_idx = None
    for i, node in enumerate(tree):
        if isinstance(node, list) and node and str(node[0]) == 'paper':
            paper_idx = i
            if paper is not None:
                node[1] = paper
            break
    if paper_idx is None:
        raise ValueError('schematic has no (paper ...) node — not a schematic?')

    # Replace an existing title_block rather than appending a second one.
    for i, node in enumerate(list(tree)):
        if isinstance(node, list) and node and str(node[0]) == 'title_block':
            tree.pop(i)
            break

    tb = [sym('title_block'), [sym('title'), title], [sym('rev'), rev]]
    if date:
        tb.insert(2, [sym('date'), date])
    if company:
        tb.append([sym('company'), company])
    for i, c in enumerate(comments or [], start=1):
        tb.append([sym('comment'), i, c])
    tree.insert(paper_idx + 1, tb)


def set_title_block_from_project(tree, pro_path, paper: str | None = None) -> None:
    """Fill the title block from the project's own text variables.

    The `.kicad_pro` already carries TITLE / REVISION / DATE / AUTHOR /
    COMPANY, set once per board. Re-typing them into the generator would make
    two copies of one fact and guarantee they drift — the same defect as two
    build paths for one board. So this reads them, and the `.kicad_pro` stays
    the single place a board is named and revised.

    AUTHOR has no dedicated KiCad title-block field; it goes in comment 1,
    which is where a hand-drawn sheet puts it.
    """
    import json
    pro_path = Path(pro_path)
    tv = {}
    if pro_path.is_file():
        try:
            tv = json.loads(pro_path.read_text()).get('text_variables', {}) or {}
        except Exception:                                    # noqa: BLE001
            tv = {}
    if not tv.get('TITLE'):
        raise ValueError(
            f'{pro_path.name} has no TITLE text variable — set it there rather '
            'than hard-coding a title in the generator.')
    author = tv.get('AUTHOR', '').strip()
    set_title_block(
        tree,
        title=tv.get('TITLE', ''),
        rev=tv.get('REVISION', '') or 'rev1',
        date=tv.get('DATE', ''),
        company=tv.get('COMPANY', ''),
        comments=[author] if author else None,
        paper=paper,
    )
