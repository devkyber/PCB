#!/usr/bin/env python3
"""Reliable reference-document fetching — fixes the "couldn't fetch actual
sources" problem from the sensor-module evaluation round.

Three fetches failed that round, each for a different, previously
undiagnosed reason:

  1. TDK's official EV_ICM-42688-P schematic — dead/broken link, no
     verification step caught it before being reported as "unavailable."
  2. SUSTAINA-OP's per-pin cap wiring (a GitHub-hosted Eagle .sch) —
     WebFetch's HTML-to-markdown + AI-summarization pipeline truncated
     the file and lost the pin-level detail. Tested against a real
     Adafruit Eagle .sch this round: WebFetch's summary layer discards
     exactly the kind of exact-value, exact-pin ground truth a hardware
     comparison needs.
  3. u-blox's NEO-M9N hardware integration manual — a large vector-graphic
     PDF, unreadable through WebFetch's markdown conversion.

This module fixes (2) and (3) directly, and gives (1) a verification step
so a dead link is caught immediately instead of silently reported as "not
found" after the fact.

  - fetch_raw(url, out_path)              curl-based direct download,
                                           bypassing WebFetch's summary
                                           layer entirely. Use for anything
                                           you need EXACT content from:
                                           source files, XML, PDFs.
  - verify_url(url)                       HEAD request; returns
                                           (alive: bool, status: int).
                                           Call before treating a link as
                                           a real source.
  - parse_eagle_schematic(sch_path)       returns real part values AND
                                           pin-level net connections from
                                           a .sch file — ground truth, not
                                           a summary. This is what would
                                           have resolved the SUSTAINA-OP
                                           and TDK cap-value ambiguity.
  - render_pdf_pages(pdf_path, pages,     renders specific PDF pages to
    out_dir, zoom)                        PNG via PyMuPDF for visual
                                           reading (Read tool) when text
                                           extraction fails or the content
                                           is a vector diagram (wiring
                                           diagrams, pinout tables) — the
                                           exact method that recovered the
                                           HF46F relay's real pinout this
                                           session after WebFetch's PDF
                                           text extraction came back
                                           garbled.

Requires: curl (system), PyMuPDF (`pip3 install pymupdf` — pure wheel, no
poppler/system deps needed, unlike pdftoppm).
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))


# --------------------------------------------------------------------------- #
# Direct, unsummarized fetching
# --------------------------------------------------------------------------- #

def fetch_raw(url: str, out_path: str | Path, timeout: int = 30) -> Path:
    """Download a URL byte-for-byte via curl. Use this instead of WebFetch
    whenever you need EXACT content — source files, XML/JSON, PDFs — not a
    natural-language summary. WebFetch's summarization step is fine for
    "what does this page say," and actively harmful for "what is the exact
    value on this specific pin," which is what a reference-design
    comparison actually needs.

    Raises RuntimeError with the curl exit code / stderr on failure —
    don't silently produce an empty file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["curl", "-sL", "--fail", "--max-time", str(timeout), url, "-o", str(out_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"fetch_raw failed for {url!r} (curl exit {result.returncode}): "
            f"{result.stderr.strip()}. Do not report this URL as a working "
            f"reference source — verify_url() it and find an alternate."
        )
    if out_path.stat().st_size == 0:
        raise RuntimeError(f"fetch_raw got a 0-byte response for {url!r} — likely a redirect to an error page.")
    return out_path


def verify_url(url: str, timeout: int = 10) -> tuple[bool, int]:
    """HEAD-request a URL and return (alive, http_status). Call this
    BEFORE citing a link as a reference source in an evaluation — a dead
    link reported as "couldn't fetch, unknown reason" should instead be
    reported as "verified dead, HTTP 404" or similar, which is a stronger,
    more honest claim and tells the next person not to retry it."""
    result = subprocess.run(
        ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url],
        capture_output=True, text=True,
    )
    try:
        status = int(result.stdout.strip())
    except ValueError:
        return False, 0
    return (200 <= status < 400), status


def github_raw_url(owner_repo: str, path: str, ref: str = "master") -> str:
    """Build a raw.githubusercontent.com URL from a repo + path. Handles
    spaces in filenames (common in Eagle-exported repos, e.g. Adafruit's
    "Adafruit BMP390.sch") via URL-encoding — a plain WebFetch on the
    github.com/.../blob/... HTML page renders the file through GitHub's
    UI chrome and frequently truncates large XML files; the raw endpoint
    returns the exact bytes."""
    import urllib.parse
    encoded_path = "/".join(urllib.parse.quote(seg) for seg in path.split("/"))
    return f"https://raw.githubusercontent.com/{owner_repo}/{ref}/{encoded_path}"


# --------------------------------------------------------------------------- #
# Eagle .sch / .brd XML — real ground truth, not a lossy summary
# --------------------------------------------------------------------------- #

def parse_eagle_schematic(sch_path: str | Path) -> dict:
    """Parse an Eagle .sch file and return real, exact data:
      {
        'parts': {name: {'value': str|None, 'deviceset': str, 'device': str, 'library': str}},
        'nets':  {net_name: [ 'PARTNAME.PINNAME', ... ]},
      }
    This is what resolves "what value is on this pin" questions that
    WebFetch's AI-summary of the same file cannot answer reliably —
    tested against Adafruit's real BMP390 breakout .sch this session:
    recovered exact cap values (0.1uF/10uF/10uF) AND confirmed which
    specific IC pins each connects to (VDD+VDDIO share one 100nF cap),
    settling an ambiguity a summary-based fetch left undetermined.
    """
    tree = ET.parse(sch_path)
    root = tree.getroot()

    parts = {}
    for part in root.iter("part"):
        name = part.get("name")
        parts[name] = {
            "value": part.get("value"),
            "deviceset": part.get("deviceset"),
            "device": part.get("device"),
            "library": part.get("library"),
        }

    nets = {}
    for net in root.iter("net"):
        name = net.get("name")
        pins = [f"{p.get('part')}.{p.get('pin')}" for p in net.iter("pinref")]
        if pins:
            nets[name] = pins

    return {"parts": parts, "nets": nets}


def find_pins_for_part(parsed: dict, part_name: str) -> dict[str, list[str]]:
    """Given parse_eagle_schematic() output, return {net_name: [pin, ...]}
    for every net that part_name appears on — i.e. "what is every pin of
    this specific component connected to, and by what net name."""
    result: dict[str, list[str]] = {}
    for net_name, pins in parsed["nets"].items():
        matches = [p.split(".", 1)[1] for p in pins if p.startswith(f"{part_name}.")]
        if matches:
            result[net_name] = matches
    return result


# --------------------------------------------------------------------------- #
# PDF page rendering — for when text extraction fails or content is visual
# --------------------------------------------------------------------------- #

def render_pdf_pages(pdf_path: str | Path, pages: list[int], out_dir: str | Path,
                      zoom: float = 3.0) -> list[Path]:
    """Render specific 1-indexed PDF pages to PNG for visual reading via
    the Read tool. Use when WebFetch's text extraction on a PDF comes back
    empty/garbled (common for vector-graphic wiring diagrams, pinout
    tables, and mechanical drawings) — this is the exact method that
    recovered the HF46F relay's real coil/COM/NO pinout this session after
    text extraction failed on the manufacturer's PDF.

    Requires PyMuPDF (`pip3 install pymupdf`) — no system poppler/pdftoppm
    dependency, unlike the Read tool's built-in PDF page renderer.
    """
    import fitz  # PyMuPDF

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    written = []
    mat = fitz.Matrix(zoom, zoom)
    for page_num in pages:
        page = doc[page_num - 1]
        pix = page.get_pixmap(matrix=mat)
        out_path = out_dir / f"page_{page_num}.png"
        pix.save(str(out_path))
        written.append(out_path)
    return written


# The package implementation is now authoritative; these names remain the
# compatibility surface used by existing scripts and command invocations.
from pcb_copilot.evidence.extract import (  # noqa: E402
    find_pins_for_part as _find_pins_for_part,
    parse_eagle_schematic as _parse_eagle_schematic,
    render_pdf_pages as _render_pdf_pages,
)

parse_eagle_schematic = _parse_eagle_schematic
find_pins_for_part = _find_pins_for_part
render_pdf_pages = _render_pdf_pages


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCLI usage:")
        print("  python3 fetch_reference_doc.py verify <url>")
        print("  python3 fetch_reference_doc.py eagle <path-to.sch> [part_name]")
        print("  python3 fetch_reference_doc.py pdf <path-to.pdf> <out_dir> <page1,page2,...>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "verify":
        alive, status = verify_url(sys.argv[2])
        print(f"{'ALIVE' if alive else 'DEAD'} (HTTP {status}): {sys.argv[2]}")
    elif cmd == "eagle":
        parsed = parse_eagle_schematic(sys.argv[2])
        print(f"{len(parsed['parts'])} parts, {len(parsed['nets'])} nets")
        if len(sys.argv) > 3:
            part_name = sys.argv[3]
            print(f"\n{part_name}: {parsed['parts'].get(part_name)}")
            print(f"Nets touching {part_name}:")
            for net, pins in find_pins_for_part(parsed, part_name).items():
                print(f"  {net}: pins {pins}")
        else:
            for name, info in sorted(parsed["parts"].items()):
                print(f"  {name}: {info['value']} ({info['deviceset']})")
    elif cmd == "pdf":
        pdf_path, out_dir, pages_str = sys.argv[2], sys.argv[3], sys.argv[4]
        pages = [int(p) for p in pages_str.split(",")]
        written = render_pdf_pages(pdf_path, pages, out_dir)
        for p in written:
            print(p)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
