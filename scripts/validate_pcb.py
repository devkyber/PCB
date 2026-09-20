#!/usr/bin/env python3
"""
PCB validation script — checks a .kicad_pcb file for common defects
that our evaluation scorecard identified.

Usage:
    python3 scripts/validate_pcb.py projects/<board>/<board>.kicad_pcb

Checks:
  1. Placeholder footprints (Conn_01x* used for ICs)
  2. Fiducials present (3 recommended for PCBA; JLCPCB auto-adds if absent)
  3. Board dimensions vs component count (density check)
  4. Silkscreen text present (board name, revision, author)
  5. Edge clearance (components ≥1mm from edge)
  6. Unrouted nets (checks for traces/segments existing)
  7. Pads inside the board outline (real pad geometry, not the footprint anchor)
  8. Courtyard collisions (components physically overlapping)
  9. Module socket pinouts (flags for mandatory human sign-off)
 10. DRC report present, fresh, and clean (absence of a report is a FAIL)
"""

import re
import sys
import os

# Hooks and piped commands on Windows can inherit a legacy console encoding.
# Preserve the report instead of crashing on engineering symbols such as ≥.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


def read_pcb(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def find_all_footprints(text):
    """Extract footprint references and their library footprint names."""
    fps = []
    for m in re.finditer(
        r'\(footprint\s+"([^"]+)".*?\(property\s+"Reference"\s+"([^"]+)"',
        text,
        re.DOTALL,
    ):
        fps.append((m.group(2), m.group(1)))
    return fps


def check_placeholders(text):
    """FAIL if any IC-designated component uses a generic connector footprint."""
    fps = find_all_footprints(text)
    placeholders = []
    ic_prefixes = ("U", "IC")
    placeholder_patterns = ("Conn_01x", "Conn_02x", "PinHeader", "PinSocket")
    for ref, lib_fp in fps:
        if any(ref.startswith(p) for p in ic_prefixes):
            if any(pat in lib_fp for pat in placeholder_patterns):
                placeholders.append(f"{ref} → {lib_fp}")
    if placeholders:
        return "FAIL", f"Placeholder footprints on ICs: {', '.join(placeholders)}"
    return "PASS", f"All {len(fps)} footprints are specific (no generic connectors on ICs)"


def check_fiducials(text):
    """WARN (not FAIL) if <3 distinct fiducial footprint instances found.

    JLCPCB auto-adds fiducials during panelization if a board has none, so this
    is a placement-accuracy recommendation, not an order-acceptance requirement.
    Self-placed fiducials still help, especially for fine-pitch (<0.5mm) parts.
    """
    count = len(re.findall(r'\(footprint\s+"[^"]*[Ff]iducial[^"]*"', text))
    if count >= 3:
        return "PASS", f"{count} fiducial footprint instances found"
    if count > 0:
        return "WARN", f"Only {count} fiducial(s) — 3 in an L-pattern recommended for best placement accuracy"
    return "WARN", "No fiducials found — JLCPCB will auto-add its own for assembly, but for fine-pitch parts (<0.5mm) consider adding 3× self-placed fiducials (1mm pad, 2mm mask opening) for better alignment"


def check_board_dimensions(text):
    """Extract board outline and report dimensions + component density."""
    xs, ys = get_board_bounds(text)
    if not xs:
        return "WARN", "Could not parse board outline from Edge.Cuts layer"

    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    area = w * h
    num_fps = len(find_all_footprints(text))
    density_note = ""
    if num_fps > 0 and area > 0:
        approx_fp_area = num_fps * 12  # rough 3×4mm average per component
        density = (approx_fp_area / area) * 100
        if density < 20:
            density_note = f" — density ~{density:.0f}% (LOW, board may be oversized)"
        else:
            density_note = f" — density ~{density:.0f}%"
    return "INFO", f"Board: {w:.1f}mm × {h:.1f}mm = {area:.0f}mm², {num_fps} components{density_note}"


def check_silkscreen(text):
    """Check for board identification text on silkscreen."""
    silk_texts = re.findall(r'\(gr_text\s+"([^"]*)".*?\(layer\s+"[FB]\.SilkS"\)', text, re.DOTALL)
    has_rev = any("rev" in t.lower() for t in silk_texts)
    has_name = len(silk_texts) > 0

    prop_texts = re.findall(r'\(property\s+"Value"\s+"([^"]+)"', text)

    if not silk_texts and not prop_texts:
        return "FAIL", "No silkscreen text found — add board name, revision, author"

    issues = []
    if not has_rev:
        issues.append("no revision marking")
    if issues:
        return "WARN", f"Silkscreen present but: {', '.join(issues)}"
    return "PASS", f"Silkscreen OK ({len(silk_texts)} text items)"


def check_traces_exist(text):
    """FAIL if no routed traces (segments) exist — board is placement-only.

    Matches "(segment" followed by whitespace of any kind (space or
    newline+indent) — KiCad's own pretty-printer puts the first child
    element on its own line rather than after a literal space, which a
    plain text.count("(segment ") silently misses.
    """
    segment_count = len(re.findall(r"\(segment\s", text))
    via_count = len(re.findall(r"\(via\s", text))
    if segment_count == 0:
        return "FAIL", "No routed traces (segments) found — board has placement only, no copper connections. Route traces before fabrication."
    return "INFO", (
        f"{segment_count} trace segments, {via_count} vias present. "
        "NOTE: this only proves copper EXISTS, not that routing is COMPLETE — "
        "see the DRC report check for unconnected nets."
    )


def get_board_bounds(text):
    """Extract board edge coordinates from Edge.Cuts layer."""
    xs, ys = [], []
    for m in re.finditer(r'\(gr_line\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+\(end\s+([\d.]+)\s+([\d.]+)\).*?\(layer\s+"Edge\.Cuts"\)', text):
        xs.extend([float(m.group(1)), float(m.group(3))])
        ys.extend([float(m.group(2)), float(m.group(4))])
    if not xs:
        for m in re.finditer(r'\(gr_rect\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+\(end\s+([\d.]+)\s+([\d.]+)\).*?\(layer\s+"Edge\.Cuts"\)', text, re.DOTALL):
            xs.extend([float(m.group(1)), float(m.group(3))])
            ys.extend([float(m.group(2)), float(m.group(4))])
    return xs, ys


def check_edge_clearance(text):
    """Check that pads aren't too close to the board edge."""
    xs, ys = get_board_bounds(text)
    if not xs:
        return "SKIP", "No board outline found to check edge clearance"

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    too_close = []
    for m in re.finditer(r'\(footprint\s+"[^"]+"\s+\(layer\s+"[^"]+"\)\s+\(uuid\s+"[^"]+"\)\s+\(at\s+([\d.]+)\s+([\d.]+)', text):
        cx, cy = float(m.group(1)), float(m.group(2))
        margin = min(cx - min_x, max_x - cx, cy - min_y, max_y - cy)
        if margin < 1.0:
            too_close.append(f"({cx},{cy}) margin={margin:.1f}mm")

    if too_close:
        return "WARN", f"{len(too_close)} component(s) within 0.5mm of board edge"
    return "PASS", "All components ≥0.5mm from board edge"


# ---------------------------------------------------------------
# Geometry-aware checks (added Rev F)
#
# The original edge-clearance check tested a footprint's ORIGIN (its
# `(at x y)` anchor) against the board outline. For a 1x24 pin header the
# anchor is pin 1, not the centre, so a header whose body hangs 15mm off
# the board edge reports a comfortable margin and PASSes. Every check
# below works on real pad / courtyard geometry instead.
# ---------------------------------------------------------------

import math


def _iter_footprint_blocks(text):
    """Yield the raw s-expression text of each top-level (footprint ...)."""
    i = 0
    while True:
        i = text.find("\n\t(footprint ", i)
        if i < 0:
            return
        j = i + 1
        depth = 0
        k = j
        n = len(text)
        while k < n:
            c = text[k]
            if c == '"':
                k += 1
                while k < n and (text[k] != '"' or text[k - 1] == "\\"):
                    k += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        yield text[j:k + 1]
        i = k


def _fp_ref(block):
    """Reference designator, in EITHER of KiCad's two spellings.

    Legacy footprints write `(fp_text reference "J9")` rather than
    `(property "Reference" "J9")`. Reading only the modern form made
    tms-v3's XBee socket invisible to the courtyard, parity and
    connector-class checks — a part the checks cannot see cannot be
    reported on, so everything passed.
    """
    m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
    if m:
        return m.group(1)
    m = re.search(r'\(fp_text\s+reference\s+"([^"]+)"', block)
    return m.group(1) if m else "?"


def _fp_anchor(block):
    m = re.search(r"\n\t\t\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)", block)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0)


def _rotate(px, py, deg):
    """KiCad footprint-local -> board transform (Y down, angle CCW on screen)."""
    a = math.radians(deg)
    return (px * math.cos(a) + py * math.sin(a),
            -px * math.sin(a) + py * math.cos(a))


def _pad_extents(block):
    """(min_x, min_y, max_x, max_y) over every pad, in board coords."""
    anchor = _fp_anchor(block)
    if anchor is None:
        return None
    ox, oy, rot = anchor
    xs, ys = [], []
    for m in re.finditer(
        r'\(pad\s+"[^"]*"\s+\w+\s+\w+\s*\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)'
        r'\s*\(size\s+([\d.]+)\s+([\d.]+)\)',
        block,
    ):
        px, py = float(m.group(1)), float(m.group(2))
        pad_rot = float(m.group(3) or 0.0)
        sw, sh = float(m.group(4)), float(m.group(5))
        dx, dy = _rotate(px, py, rot)
        # Serialized board pad angles are absolute; only the pad position
        # remains footprint-local. Adding rot here counts rotation twice.
        total = pad_rot % 180.0
        if abs(total) < 0.01:
            hw, hh = sw / 2.0, sh / 2.0
        elif abs(total - 90.0) < 0.01:
            hw, hh = sh / 2.0, sw / 2.0
        else:
            angle = math.radians(total)
            hw = (abs(sw * math.cos(angle)) + abs(sh * math.sin(angle))) / 2
            hh = (abs(sw * math.sin(angle)) + abs(sh * math.cos(angle))) / 2
        xs += [ox + dx - hw, ox + dx + hw]
        ys += [oy + dy - hh, oy + dy + hh]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _courtyard_extents(block):
    """(min_x, min_y, max_x, max_y) over F.CrtYd/B.CrtYd graphics."""
    anchor = _fp_anchor(block)
    if anchor is None:
        return None
    ox, oy, rot = anchor
    xs, ys = [], []
    for m in re.finditer(
        r"\(fp_(?:line|rect)\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)"
        r'(?:(?!\(fp_).)*?\(layer\s+"[FB]\.CrtYd"\)',
        block,
        re.DOTALL,
    ):
        for px, py in ((float(m.group(1)), float(m.group(2))),
                       (float(m.group(3)), float(m.group(4)))):
            dx, dy = _rotate(px, py, rot)
            xs.append(ox + dx)
            ys.append(oy + dy)
    for m in re.finditer(
        r"\(fp_circle\s*\(center\s+([-\d.]+)\s+([-\d.]+)\)\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)"
        r'(?:(?!\(fp_).)*?\(layer\s+"[FB]\.CrtYd"\)',
        block,
        re.DOTALL,
    ):
        cx, cy, ex, ey = (float(m.group(i)) for i in range(1, 5))
        r = math.hypot(ex - cx, ey - cy)
        dx, dy = _rotate(cx, cy, rot)
        xs += [ox + dx - r, ox + dx + r]
        ys += [oy + dy - r, oy + dy + r]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def check_pads_inside_board(text):
    """FAIL if any pad extends past (or within 0.3mm of) the board outline.

    Catches the anchor-vs-extent class of bug: a footprint whose `(at)`
    origin is comfortably inside the board while its actual pads hang off
    the edge. This is what let TMS V3's J7/J8 1x24 Teensy headers run
    15mm past the bottom edge while the old check reported PASS.
    """
    xs, ys = get_board_bounds(text)
    if not xs:
        return "SKIP", "No board outline found"
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)

    outside, tight = [], []
    for block in _iter_footprint_blocks(text):
        ext = _pad_extents(block)
        if ext is None:
            continue
        ref = _fp_ref(block)
        if ext[0] < min_x or ext[1] < min_y or ext[2] > max_x or ext[3] > max_y:
            over = max(min_x - ext[0], min_y - ext[1], ext[2] - max_x, ext[3] - max_y)
            outside.append(f"{ref} (+{over:.1f}mm past edge)")
        else:
            margin = min(ext[0] - min_x, ext[1] - min_y,
                         max_x - ext[2], max_y - ext[3])
            if margin < 0.3:
                tight.append(f"{ref} ({margin:.2f}mm)")

    if outside:
        return "FAIL", (
            f"{len(outside)} footprint(s) have pads OUTSIDE the board outline: "
            + ", ".join(outside)
            + ". Check the footprint's anchor — 1xN headers anchor on pin 1, not centre."
        )
    if tight:
        return "WARN", f"Pads within 0.3mm of board edge: {', '.join(tight)}"
    return "PASS", "All pads inside the board outline with ≥0.3mm edge margin"


def check_courtyard_overlap(text):
    """FAIL on overlapping courtyards — components physically on top of each other.

    Placement coordinates picked against placeholder footprints do not
    survive contact with real ones. On TMS V3 this put C1/C3/C5/C6 inside
    the ADS1256's SSOP-28 land pattern, shorting +5V to +3V3.
    """
    boxes = []
    for block in _iter_footprint_blocks(text):
        crt = _courtyard_extents(block)
        pad = _pad_extents(block)
        cand = [e for e in (crt, pad) if e]
        if not cand:
            continue
        ext = (min(e[0] for e in cand), min(e[1] for e in cand),
               max(e[2] for e in cand), max(e[3] for e in cand))
        boxes.append((_fp_ref(block), ext))
    if not boxes:
        return "SKIP", "No courtyard or pad geometry found in footprints"

    # These are axis-aligned bounding boxes, so a rotated footprint's box is
    # slightly larger than the part. Overlaps under 0.1mm are therefore
    # reported as WARN (verify in KiCad) rather than FAIL.
    hits, marginal = [], []
    for i in range(len(boxes)):
        ra, a = boxes[i]
        for j in range(i + 1, len(boxes)):
            rb, b = boxes[j]
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox <= 0.01 or oy <= 0.01:
                continue
            label = f"{ra}/{rb} ({ox:.2f}×{oy:.2f}mm)"
            (hits if min(ox, oy) >= 0.1 else marginal).append(label)

    def _fmt(lst):
        return ", ".join(lst[:8]) + (f" … +{len(lst) - 8} more" if len(lst) > 8 else "")

    if hits:
        extra = f" (+{len(marginal)} marginal <0.1mm)" if marginal else ""
        return "FAIL", f"{len(hits)} courtyard collision(s) — components overlap: {_fmt(hits)}{extra}"
    if marginal:
        return "WARN", (
            f"{len(marginal)} marginal overlap(s) <0.1mm (bounding-box test, may be "
            f"rotation artefact — confirm in KiCad): {_fmt(marginal)}"
        )
    return "PASS", f"No courtyard collisions across {len(boxes)} footprints"


def check_drc_freshness(pcb_path):
    """FAIL unless a DRC report newer than the .kicad_pcb exists AND is clean.

    Absence of evidence is a FAIL here, not a PASS. The old validator
    reported ALL PASS on a board that had a 54-violation, 97-unconnected
    DRC report sitting unread next to it.
    """
    import glob
    import json

    d = os.path.dirname(os.path.abspath(pcb_path)) or "."
    reports = glob.glob(os.path.join(d, "*drc*.json"))
    if not reports:
        return "FAIL", (
            "No DRC report found next to the board. Run:\n"
            f"         kicad-cli pcb drc --format json -o {os.path.splitext(os.path.basename(pcb_path))[0]}.drc.json {os.path.basename(pcb_path)}"
        )
    newest = max(reports, key=os.path.getmtime)
    if os.path.getmtime(newest) < os.path.getmtime(pcb_path):
        return "FAIL", (
            f"DRC report {os.path.basename(newest)} is OLDER than the board file — stale. Re-run kicad-cli pcb drc."
        )
    try:
        with open(newest) as f:
            rep = json.load(f)
    except Exception as e:
        return "FAIL", f"Could not read DRC report {os.path.basename(newest)}: {e}"

    viol = rep.get("violations", [])
    unconn = rep.get("unconnected_items", [])
    parity = rep.get("schematic_parity", [])
    if viol or unconn or parity:
        from collections import Counter
        kinds = Counter(v.get("type", "?") for v in viol)
        detail = ", ".join(f"{k}×{n}" for k, n in kinds.most_common(6))
        return "FAIL", (
            f"DRC ({os.path.basename(newest)}): {len(viol)} violations [{detail}], "
            f"{len(unconn)} unconnected net(s), {len(parity)} schematic-parity issue(s). "
            "Unconnected items mean the board is NOT fully routed."
        )
    return "PASS", f"DRC clean ({os.path.basename(newest)}, newer than board)"


MODULE_HINTS = ("teensy", "xbee", "arduino", "esp", "raspberry", "pi", "feather",
                "nucleo", "pico", "nano", "socket", "module")


def check_module_socket_pinouts(text):
    """WARN — every module socket needs its pinout checked against the vendor card.

    A module socket's pin order is fixed by the vendor's board, not by
    what is convenient. Sequentially assigning nets down a 1xN header
    produces a netlist that passes ERC, passes DRC, and destroys the
    module. No automated check in this workspace can verify this; it
    needs a human with the vendor pinout diagram open.
    """
    suspects = []
    for block in _iter_footprint_blocks(text):
        lib = re.search(r'\(footprint\s+"([^"]+)"', block)
        lib = lib.group(1) if lib else ""
        npads = len(re.findall(r'\(pad\s+"', block))
        if npads < 8:
            continue
        if not re.search(r"PinHeader|PinSocket|Conn_", lib, re.I):
            continue
        ref = _fp_ref(block)
        val = re.search(r'\(property\s+"Value"\s+"([^"]+)"', block)
        val = val.group(1) if val else ""
        suspects.append(f"{ref} ({val or lib}, {npads} pins)")

    if not suspects:
        return "PASS", "No multi-pin module sockets on this board"
    return "WARN", (
        f"{len(suspects)} module socket(s) need HUMAN pinout sign-off against the "
        f"vendor pinout card: {', '.join(suspects)}. "
        "Verify pin-1 orientation, physical pin order, connector pitch, and that "
        "no power rail lands on a signal pin. ERC/DRC cannot catch this."
    )


def check_symbol_footprint_parity(pcb_path):
    """FAIL — every schematic symbol that has a footprint must BE on the board.

    Found on gnss-neom9n, 2026-08-25: `SW1`, the reset button, was in the
    schematic with a footprint assigned and had **no footprint on the PCB at
    all**. Every gate passed. The board would have been fabricated with no
    reset button and nothing anywhere would have said so.

    Why nothing caught it: the DRC-report reader below looks for a
    `schematic_parity` key, and the pipeline never passes `--schematic-parity`
    to kicad-cli, so that list is always empty and always reports "0
    schematic-parity issue(s)" — a check that cannot fail is worse than no
    check, because the report reads like a pass.

    And simply switching the flag on does not fix it: kicad-cli returns 72
    parity items for this board, of which 72 are cosmetic — `Description`
    field text differing between symbol and footprint, and net names differing
    only by KiCad's leading `/`. A gate that cries 72 times about nothing is
    a gate people learn to skip past. So this checks the one thing that is
    always a real defect and never a matter of taste: presence.

    Reference designators only (`^[A-Z]+[0-9]+$`), which excludes the bare
    library-symbol definitions in `lib_symbols` and the `#PWR`/`#FLG` symbols
    that intentionally have no footprint.
    """
    sch_path = pcb_path[:-len('.kicad_pcb')] + '.kicad_sch'
    if not os.path.exists(sch_path):
        return "SKIP", "no matching .kicad_sch beside the board"

    ref_re = re.compile(r'\(property\s+"Reference"\s+"([A-Za-z]+[0-9]+)"')
    with open(sch_path, encoding='utf-8', errors='replace') as fh:
        sch_refs = set(ref_re.findall(fh.read()))
    # Read the BOARD through _fp_ref, which understands the legacy
    # `(fp_text reference ...)` spelling too. A bare property regex made a
    # legacy-form footprint look absent from the board, which this check
    # would then have reported as a schematic symbol that was never placed.
    pcb_refs = {r for r in (_fp_ref(b) for b in _iter_footprint_blocks(read_pcb(pcb_path)))
                if re.fullmatch(r'[A-Za-z]+[0-9]+', r or '')}

    # Fiducials and mounting holes are mechanical features that legitimately
    # exist only on the board — some generators give them schematic symbols,
    # some do not, and neither is wrong. Exempt them from the PCB-only
    # direction. The reverse direction stays strict for everything: a symbol
    # with a footprint that never reached the board is always a defect.
    PCB_ONLY_OK = ('FID', 'H', 'MH', 'LOGO', 'REF')
    missing = sorted(sch_refs - pcb_refs)
    extra = sorted(r for r in pcb_refs - sch_refs
                   if not re.match(r'(%s)\d+$' % '|'.join(PCB_ONLY_OK), r))
    if missing or extra:
        bits = []
        if missing:
            bits.append("IN SCHEMATIC, NOT ON BOARD: " + ", ".join(missing))
        if extra:
            bits.append("ON BOARD, NOT IN SCHEMATIC: " + ", ".join(extra))
        bits.append("A symbol with no footprint is a part that will not be "
                    "fabricated. Add it to the PCB generator's placement list.")
        return "FAIL", "\n         ".join(bits)
    return "PASS", f"{len(sch_refs)} symbol(s), every one placed on the board"


# Connector families whose whole point is current capacity or retention.
# If a part CLAIMS to be one of these, a 2.54mm pin header is not a
# substitute — it is a different part with roughly 5% of the current rating.
HIGH_CURRENT_HINTS = (
    'xt60', 'xt30', 'xt90', 'ec3', 'ec5', 'deans', 'anderson', 'powerpole',
    'screw terminal', 'terminal block', 'barrier strip', 'spade',
    'banana', 'bullet', 'ring terminal', 'wago',
)
GENERIC_HEADER_RE = re.compile(r'(?i)pinheader|pinsocket|conn_01x|conn_02x')


def check_connector_class(pcb_path):
    """FAIL — a connector's declared type must match its footprint family.

    Found on tms-v3, 2026-08-25. Four connectors on the battery and IGNITER
    path declared themselves one thing and were footprinted as another:

        J1  "XT60-ELEC"  / "Electronics battery XT60U-F"  -> PinHeader_1x02
        J2  "XT60-IGN"   / "Igniter battery XT60U-F"      -> PinHeader_1x02
        J5  "ARM-SW"     / "External ARM switch screw terminal" -> PinHeader_1x02
        J6  "E-MATCH"    / "E-match output screw terminal"      -> PinHeader_1x02

    An XT60 is rated 60A continuous. A 2.54mm header pin is rated about 3A.
    This board fires pyrotechnic igniters from a 2S LiPo, so the difference
    is not a BOM inconvenience.

    Nothing caught it because every other check was satisfied: ERC saw two
    pins, DRC saw two pads, the netlist was correct, and the courtyard fit.
    The claim lived in the Value and Description fields and the reality
    lived in the footprint, and no check compared them.

    Heuristic by nature — it reads declared intent from text. That is
    exactly why it names what it found and points at DEVIATIONS.md rather
    than trying to be clever: a deliberate header stand-in for a connector
    that will be flying leads is a legitimate choice, once someone says so.
    """
    sch_path = pcb_path[:-len('.kicad_pcb')] + '.kicad_sch'
    text = read_pcb(pcb_path)

    # Declared intent: Value from the board, Description from the schematic
    # (KiCad does not copy Description onto the footprint).
    desc = {}
    if os.path.exists(sch_path):
        with open(sch_path, encoding='utf-8', errors='replace') as fh:
            sch = fh.read()
        for m in re.finditer(
                r'\(property\s+"Reference"\s+"([A-Za-z]+[0-9]+)"'
                r'(?:(?!\(property\s+"Reference").)*?'
                r'\(property\s+"Description"\s+"([^"]*)"', sch, re.S):
            desc[m.group(1)] = m.group(2)

    bad = []
    for block in _iter_footprint_blocks(text):
        ref = _fp_ref(block)
        if not ref:
            continue
        lib = re.search(r'\(footprint\s+"([^"]+)"', block)
        lib = lib.group(1) if lib else ''
        if not GENERIC_HEADER_RE.search(lib):
            continue
        val = _fp_value(block) if '_fp_value' in globals() else ''
        m = re.search(r'\(property\s+"Value"\s+"([^"]*)"', block)
        val = m.group(1) if m else ''
        claim = (val + ' ' + desc.get(ref, '')).lower()
        for hint in HIGH_CURRENT_HINTS:
            if hint in claim:
                bad.append(f'{ref} ({val or "no value"}) claims "{hint}" '
                           f'but is footprinted as {lib.split(":")[-1]}')
                break
    if bad:
        return "FAIL", ("\n         ".join(bad) + "\n         "
                        "A 2.54mm header pin is rated ~3A; XT60/screw terminals "
                        "exist because the current or the retention matters. "
                        "Fit the real footprint, or declare the substitution in "
                        "DEVIATIONS.md with the actual current it must carry.")
    return "PASS", "no connector claims a footprint family it does not have"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_pcb.py <path-to-.kicad_pcb>")
        sys.exit(1)

    pcb_path = sys.argv[1]
    if not os.path.exists(pcb_path):
        print(f"Error: file not found: {pcb_path}")
        sys.exit(1)

    text = read_pcb(pcb_path)
    board_name = os.path.basename(pcb_path).replace(".kicad_pcb", "")

    checks = [
        ("Placeholder footprints", check_placeholders),
        ("Fiducials for PCBA", check_fiducials),
        ("Board dimensions", check_board_dimensions),
        ("Silkscreen content", check_silkscreen),
        ("Trace routing", check_traces_exist),
        ("Edge clearance (origins)", check_edge_clearance),
        ("Pads inside board outline", check_pads_inside_board),
        ("Courtyard collisions", check_courtyard_overlap),
        ("Module socket pinouts", check_module_socket_pinouts),
    ]

    checks.append(("Symbol/footprint parity",
                   lambda _t: check_symbol_footprint_parity(pcb_path)))
    checks.append(("Connector class vs footprint",
                   lambda _t: check_connector_class(pcb_path)))

    print(f"\n{'='*60}")
    print(f"  PCB Validation: {board_name}")
    print(f"{'='*60}\n")

    fail_count = 0
    warn_count = 0

    checks.append(("DRC report", lambda _t: check_drc_freshness(pcb_path)))

    for name, fn in checks:
        status, msg = fn(text)
        # ASCII markers keep this report usable when Windows launches Python
        # with a legacy console encoding (for example from hooks or pipes).
        icon = {"PASS": "P", "FAIL": "X", "WARN": "!", "INFO": "i", "SKIP": "-"}[status]
        print(f"  [{icon}] {status:4s}  {name}")
        print(f"         {msg}\n")
        if status == "FAIL":
            fail_count += 1
        elif status == "WARN":
            warn_count += 1

    print(f"{'='*60}")
    if fail_count > 0:
        print(f"  RESULT: {fail_count} FAIL, {warn_count} WARN — fix FAILs before fabrication")
        sys.exit(1)
    elif warn_count > 0:
        print(f"  RESULT: ALL PASS, {warn_count} WARN — review warnings")
        sys.exit(0)
    else:
        print(f"  RESULT: ALL PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
