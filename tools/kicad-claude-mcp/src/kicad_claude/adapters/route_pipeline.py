"""The one routing path: DSN -> Freerouting -> SES -> fill -> bond -> DRC gate.

Before this module there were two routing paths that disagreed with each
other, and the one wired into the MCP tool was the worse of the two. Both are
now thin callers of `route_board`.

The pipeline exists because autorouting a board is not one step, and the
steps that follow the router are the ones that decide whether the board is
actually connected:

    export DSN      the DSN is a snapshot of the placement; a stale one
                    silently routes the PREVIOUS layout
    route           Freerouting owns signal nets and nothing else
    import SES
    fill zones      kicad-cli DRC does not fill zones, and an unfilled board
                    reports every pour-connected pad as unconnected
    bond ground     the router fragments the pours it routed through; the
                    islands it leaves behind are ours to stitch back
    DRC + gate      a .ses file on disk is not evidence of a routed board

`route_board` never reports success it has not verified. The gate result
distinguishes signal nets (the router's job, fix by rerouting) from pour nets
(a bonding job, fix by stitching), because the two failures have nothing to
do with each other and the remedies are not interchangeable.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from kicad_claude.adapters import freerouting, kicad_cli, kicad_python, sch_editor
from kicad_claude.adapters.freerouting import RouteProfile

logger = logging.getLogger("kicad-claude.adapters.route_pipeline")

#: "Pad 2 [GND] of U2 on F.Cu"
_PAD_RE = re.compile(r"Pad\s+(\S+)\s+\[([^\]]*)\]\s+of\s+(\S+)")
#: "Zone 'GND_TOP' [GND] on F.Cu, priority 0"
_ZONE_RE = re.compile(r"Zone\s+'([^']*)'\s+\[([^\]]*)\]")


def _nets_with_zones(pcb_path: Path) -> set[str]:
    """Net names that have a copper pour, read straight from the board file.

    Cheap and dependency-free: we only need the names, not the geometry.
    """
    text = pcb_path.read_text(errors="replace")
    nets: set[str] = set()
    for m in re.finditer(r"\(zone\b", text):
        chunk = text[m.start(): m.start() + 400]
        # Stock KiCAD writes (net 3)(net_name "GND"); the boards generated in
        # this workspace have no numeric net table and write (net "GND").
        n = re.search(r'\(net_name\s+"([^"]*)"', chunk) or re.search(
            r'\(net\s+"([^"]*)"', chunk
        )
        if n and n.group(1):
            nets.add(n.group(1))
    return nets


def classify_unconnected(drc: dict, pour_nets: set[str]) -> dict:
    """Split DRC unconnected items into pour-bonding vs signal-routing work.

    Returns the two buckets plus `escape_targets`, the (ref, pad) pairs that
    `kicad_python.bond_ground` knows how to try to fix.
    """
    pour_items: list[dict] = []
    signal_items: list[dict] = []
    escape_targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in drc.get("unconnected_items", []):
        descs = [it.get("description", "") for it in item.get("items", [])]
        nets = set()
        pads: list[tuple[str, str]] = []
        for d in descs:
            pm = _PAD_RE.search(d)
            if pm:
                nets.add(pm.group(2))
                pads.append((pm.group(3), pm.group(1)))
            zm = _ZONE_RE.search(d)
            if zm:
                nets.add(zm.group(2))

        entry = {
            "nets": sorted(n for n in nets if n),
            "descriptions": descs,
            "positions": [it.get("position") for it in item.get("items", [])],
        }
        if nets and nets <= pour_nets:
            pour_items.append(entry)
            for ref, pad in pads:
                if (ref, pad) not in seen:
                    seen.add((ref, pad))
                    escape_targets.append((ref, pad))
        else:
            signal_items.append(entry)

    return {
        "pour": pour_items,
        "signal": signal_items,
        "escape_targets": escape_targets,
    }


def _drc(pcb_path: Path, timeout: float) -> dict:
    return kicad_cli.run_drc(
        pcb_path,
        output_json=pcb_path.with_suffix(".drc.json"),
        severity="all",
        schematic_parity=False,
        timeout=timeout,
    )


def route_board(
    pcb_path: Path,
    *,
    profile: RouteProfile | None = None,
    passes: int | None = None,
    threads: int | None = None,
    timeout_seconds: float = 600.0,
    bond_ground: bool = True,
    escape_pads: bool = True,
    ground_net: str = "GND",
    max_escape_mm: float = 2.0,
    drc_timeout: float = 120.0,
    backup: bool = True,
) -> dict:
    """Route `pcb_path` end to end and return a verified gate result.

    `passed` is true only when DRC reports zero unconnected items. Anything
    left over is itemised, split by cause, with coordinates.
    """
    pcb_path = Path(pcb_path).expanduser().resolve()
    if not pcb_path.is_file():
        raise FileNotFoundError(pcb_path)

    result: dict = {"pcb_path": str(pcb_path), "steps": []}
    backup_path = sch_editor.backup_file(pcb_path) if backup else None
    result["backup"] = str(backup_path) if backup_path else None

    dsn_path = pcb_path.with_suffix(".dsn")
    ses_path = pcb_path.with_suffix(".ses")

    # 1. DSN must be re-exported every run: it is a snapshot of the placement.
    kicad_python.export_dsn(pcb_path, dsn_path)
    result["steps"].append("export_dsn")
    result["dsn_path"] = str(dsn_path)

    # 1b. KiCad's DSN exporter writes ONE global clearance and silently drops
    # every pad-local override, so the router lays copper through keepouts it
    # was never told about and DRC reports violations it had no way to avoid.
    # See adapters/dsn_keepouts.py — this is what cost imu-icm42688 7 DRC
    # errors around a stock KiCad fiducial.
    from . import dsn_keepouts
    _ko = dsn_keepouts.inject(
        dsn_path, dsn_keepouts.collect(pcb_path, kicad_python._run_pcbnew_script))
    if _ko:
        result["steps"].append(f"inject_keepouts({_ko})")
    result["keepouts_injected"] = _ko

    # 2. Route.
    route_result = freerouting.route(
        dsn_path,
        ses_path,
        profile=profile,
        passes=passes,
        threads=threads,
        timeout_seconds=timeout_seconds,
    )
    result["steps"].append("freerouting")
    result["freerouting"] = {
        k: route_result[k]
        for k in ("jar_version", "java", "stats", "returncode", "args")
    }

    # 3. Import, then fill: DRC does not fill zones for us.
    kicad_python.import_ses(pcb_path, ses_path)
    result["steps"].append("import_ses")
    kicad_python.fill_zones(pcb_path)
    result["steps"].append("fill_zones")

    pour_nets = _nets_with_zones(pcb_path)
    result["pour_nets"] = sorted(pour_nets)

    drc = _drc(pcb_path, drc_timeout)
    before = drc["unconnected_items_count"]
    result["unconnected_after_route"] = before
    classified = classify_unconnected(drc, pour_nets)

    # 4. Bond the pours the router fragmented, then re-verify.
    if bond_ground and classified["pour"]:
        bond = kicad_python.bond_ground(
            pcb_path,
            ground_net,
            max_escape_mm=max_escape_mm,
            escape_targets=classified["escape_targets"] if escape_pads else [],
        )
        result["steps"].append("bond_ground")
        result["ground_bond"] = bond
        drc = _drc(pcb_path, drc_timeout)
        classified = classify_unconnected(drc, pour_nets)

    remaining = drc["unconnected_items_count"]
    result["unconnected"] = remaining
    result["unconnected_resolved_by_bonding"] = before - remaining
    result["drc"] = {
        "errors": drc["errors"],
        "warnings": drc["warnings"],
        "total_violations": drc["total_violations"],
        "unconnected_items_count": remaining,
        "raw_path": drc["raw_path"],
    }
    result["remaining_pour_items"] = classified["pour"]
    result["remaining_signal_items"] = classified["signal"]
    result["passed"] = remaining == 0
    result["summary"] = _summarize(result, classified)
    return result


def _summarize(result: dict, classified: dict) -> str:
    stats = result.get("freerouting", {}).get("stats", {})
    bits = [
        f"Freerouting {result['freerouting']['jar_version']}",
        f"{result['unconnected']} unconnected after bonding "
        f"(was {result['unconnected_after_route']} after routing)",
    ]
    if stats.get("unrouted_nets"):
        names = ", ".join(n["net"] for n in stats["unrouted_nets"])
        bits.append(f"router could not route: {names}")
    if stats.get("optimizer_multithreaded_warning"):
        bits.append(
            "WARNING: multi-threaded optimizer (upstream-broken) was used — "
            "upgrade to a 2.2+ JAR on Java 25 to avoid it"
        )
    if classified["signal"]:
        bits.append(f"{len(classified['signal'])} signal-net items need routing")
    if classified["pour"]:
        bits.append(f"{len(classified['pour'])} pour items need manual bonding")
    return "; ".join(bits)
