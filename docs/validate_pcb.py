#!/usr/bin/env python3
"""
PCB validation script — checks a .kicad_pcb file for common defects
that our evaluation scorecard identified.

Usage:
    python3 docs/validate_pcb.py projects/<board>/<board>.kicad_pcb

Checks:
  1. Placeholder footprints (Conn_01x* used for ICs)
  2. Fiducials present (≥3 for JLCPCB PCBA)
  3. Board dimensions vs component count (density check)
  4. Silkscreen text present (board name, revision, author)
  5. Edge clearance (components ≥1mm from edge)
  6. Unrouted nets (checks for traces/segments existing)
"""

import re
import sys
import os


def read_pcb(path):
    with open(path, "r") as f:
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
    """FAIL if <3 fiducial marks found."""
    count = text.lower().count("fiducial")
    if count >= 3:
        return "PASS", f"{count} fiducials found"
    if count > 0:
        return "WARN", f"Only {count} fiducial(s) — need ≥3 for JLCPCB PCBA"
    return "FAIL", "No fiducials found — JLCPCB PCBA will reject. Add 3× fiducial pads (1mm pad, 2mm mask opening)"


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
    silk_texts = re.findall(r'\(gr_text\s+"([^"]*)".*?\(layer\s+"[FB]\.Silkscreen"\)', text, re.DOTALL)
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
    """FAIL if no routed traces (segments) exist — board is placement-only."""
    segment_count = text.count("(segment ")
    via_count = text.count("(via ")
    if segment_count == 0:
        return "FAIL", "No routed traces (segments) found — board has placement only, no copper connections. Route traces before fabrication."
    return "PASS", f"{segment_count} trace segments, {via_count} vias routed"


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
        ("Edge clearance", check_edge_clearance),
    ]

    print(f"\n{'='*60}")
    print(f"  PCB Validation: {board_name}")
    print(f"{'='*60}\n")

    fail_count = 0
    warn_count = 0

    for name, fn in checks:
        status, msg = fn(text)
        icon = {"PASS": "✓", "FAIL": "✗", "WARN": "!", "INFO": "·", "SKIP": "-"}[status]
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
