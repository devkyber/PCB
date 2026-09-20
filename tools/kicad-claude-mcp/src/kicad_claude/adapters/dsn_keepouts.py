"""Conservative DSN clearance envelopes for netless pads such as fiducials.

KiCad's exporter can omit pad/footprint-local clearances. Collect the native
copper bounding geometry and insert circumscribed envelopes on actual pad
copper layers. All-net solid keepouts cannot represent a connected pad's
same-net exception: reject those rather than blocking its intended connection.

Freerouting has been observed to ignore these envelopes for vias, even with
via_keepout syntax. Exported syntax is not proof of enforcement; native DRC and
human review remain necessary. This adapter is shared with route_pipeline.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

_RULE_RE = re.compile(
    r"(?m)^    \(rule\s*\(width\s+([\d.]+)\)\s*\(clearance\s+([\d.]+)\)"
)

_COLLECT_SCRIPT = r"""
import sys, json, pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
if board is None:
    raise ValueError('Cannot load board')
out = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        c = max(int(pad.GetLocalClearance() or 0), int(fp.GetLocalClearance() or 0))
        if c <= 0 or not pad.IsOnCopperLayer():
            continue
        box = pad.GetBoundingBox()
        layers = [board.GetLayerName(i) for i in range(pcbnew.PCB_LAYER_ID_COUNT)
                  if pcbnew.IsCopperLayer(i) and board.IsLayerEnabled(i) and pad.IsOnLayer(i)]
        out.append(dict(ref=fp.GetReference(), pad=pad.GetNumber(),
            x_nm=(box.GetLeft()+box.GetRight())/2, y_nm=(box.GetTop()+box.GetBottom())/2,
            w_nm=box.GetWidth(), h_nm=box.GetHeight(), clearance_nm=c,
            layers=layers, net=pad.GetNetname(),
            shape='circle' if pad.GetShape()==pcbnew.PAD_SHAPE_CIRCLE else 'bounds'))
print(json.dumps(out))
"""


def collect(pcb_path: Path, runner) -> list:
    """Inspect native local rules. A failed inspection is never an empty success."""
    try:
        raw = runner(_COLLECT_SCRIPT, str(pcb_path))
        pads = json.loads(raw.strip().splitlines()[-1])
        if not isinstance(pads, list):
            raise TypeError("collector did not return a pad list")
        for pad in pads:
            _validate_pad(pad)
        return pads
    except Exception as exc:
        raise ValueError(f"Cannot inspect DSN local-clearance pads: {exc}") from exc


def _validate_pad(pad):
    for key in ("x_nm", "y_nm", "w_nm", "h_nm", "clearance_nm"):
        value = pad[key]
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"invalid pad geometry: {key}")
        if key in ("w_nm", "h_nm", "clearance_nm") and value <= 0:
            raise ValueError(f"nonpositive pad geometry: {key}")
    for key in ("ref", "pad", "net", "shape"):
        if not isinstance(pad[key], str):
            raise TypeError(f"invalid pad field: {key}")
    if (
        not isinstance(pad["layers"], list)
        or not pad["layers"]
        or not all(isinstance(x, str) for x in pad["layers"])
    ):
        raise ValueError("missing actual pad copper layers")


def inject(dsn_path: Path, pads: list) -> int:
    """Inject conservative netless-pad envelopes; errors leave DSN unchanged.

    Only KiCad's micrometre DSN dialect is supported. Rectangular/custom pad
    bounds use the diagonal so rotated corners cannot escape the envelope.
    Managed IDs include geometry and are idempotent per pad/layer/kind; existing
    unrelated keepouts do not suppress required envelopes. Typed clearance
    applicability is not inferred: every declared numeric clearance is used
    conservatively when deciding whether a local override needs protection.
    """
    if not pads:
        return 0
    path = Path(dsn_path)
    text = path.read_text(encoding="utf-8")
    if not re.search(r"\(resolution\s+um\s+[\d.]+\)", text):
        raise ValueError(
            "Cannot inspect DSN: unsupported or missing micrometre resolution"
        )
    try:
        start = text.index("\n  (structure")
        end = text.index("\n  )", start)
    except ValueError as exc:
        raise ValueError("Cannot inspect DSN: unsupported structure layout") from exc
    structure = text[start:end]
    match = _RULE_RE.search(structure)
    if match is None:
        raise ValueError("Cannot inspect DSN: global clearance rule missing")
    # A typed rule (e.g. smd_smd) or a net-class rule can be weaker than the
    # untyped structure rule. Use the lowest declared clearance as a lower
    # bound for every pad instead of claiming to resolve rule applicability.
    clearance = min(
        float(value) for value in re.findall(r"\(clearance\s+([\d.]+)(?=\s|\))", text)
    )
    layers = set(re.findall(r'\(layer\s+"?([A-Za-z0-9_.]+)"?\s+\(type\s+', structure))
    lines = []
    for pad in pads:
        _validate_pad(pad)
        if pad["clearance_nm"] / 1000 <= clearance:
            continue
        if pad["net"]:
            raise ValueError(
                f"Cannot represent connected pad {pad['ref']}.{pad['pad']} local clearance as an all-net keepout"
            )
        if not set(pad["layers"]) <= layers:
            raise ValueError(
                "Cannot inspect DSN: pad copper layer missing from structure"
            )
        diameter = (
            max(pad["w_nm"], pad["h_nm"])
            if pad["shape"] == "circle"
            else math.hypot(pad["w_nm"], pad["h_nm"])
        )
        diameter = math.ceil((diameter + 2 * pad["clearance_nm"]) / 1000)
        x, y = pad["x_nm"] / 1000, -pad["y_nm"] / 1000
        digest = hashlib.sha256(json.dumps(pad, sort_keys=True).encode()).hexdigest()[
            :16
        ]
        for layer in pad["layers"]:
            for kind in ("keepout", "via_keepout", "wire_keepout"):
                label = f"pcb-copilot-{digest}-{layer}-{kind}"
                if f'({kind} "{label}"' not in text:
                    lines.append(
                        f'    ({kind} "{label}" (circle {layer} {diameter} {x:.12g} {y:.12g}))'
                    )
    if lines:
        path.write_text(
            text[:end] + "\n" + "\n".join(lines) + text[end:], encoding="utf-8"
        )
    return len(lines)
