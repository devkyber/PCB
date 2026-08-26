"""Phase 6 — autorouting tools.

Tools:
    autoroute_pcb     — full pipeline: DSN → Freerouting → SES → fill → bond → DRC gate
    export_dsn        — export-only (for driving Freerouting's GUI yourself)
    import_ses        — import an existing .ses back into the active PCB
    fill_zones        — fill every zone and save (DRC does not do this for you)
    bond_ground       — stitch pour islands / escape isolated pads, standalone
    routing_status    — what router and JVM this workspace will actually use

`autoroute_pcb` returns a verified gate: `passed` is true only when DRC finds
zero unconnected items. It used to return success whenever a .ses file
appeared on disk, which is not the same thing and hid real defects on every
board in this workspace.

The DSN export and SES import shell out to KiCAD's bundled Python 3.9 because
`kicad-cli` v10 doesn't expose Specctra interchange. Freerouting itself is
invoked as a JAR via `java`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from kicad_claude import state
from kicad_claude.adapters import (
    freerouting,
    kicad_python,
    route_pipeline,
    sch_editor,
)
from kicad_claude.adapters.freerouting import RouteProfile

logger = logging.getLogger("kicad-claude.tools.routing")


def register(mcp) -> None:
    """Register Phase 6 tools on the FastMCP instance."""

    @mcp.tool()
    def export_dsn(output_path: str | None = None) -> dict:
        """Export the active PCB to Specctra DSN.

        If `output_path` is None, writes alongside the active .kicad_pcb with
        the same stem and `.dsn` extension.
        """
        pcb_path = state.get_active_board_path()
        out = (
            Path(output_path).expanduser()
            if output_path
            else pcb_path.with_suffix(".dsn")
        )
        kicad_python.export_dsn(pcb_path, out)
        return {"dsn_path": str(out), "size_bytes": out.stat().st_size}

    @mcp.tool()
    def import_ses(ses_path: str) -> dict:
        """Apply a Freerouting `.ses` session into the active `.kicad_pcb` (in-place).

        A backup of the PCB is saved under `<project>/.backups/` before the import.
        Zones are filled afterwards, because DRC will not fill them for you.
        """
        pcb_path = state.get_active_board_path()
        ses = Path(ses_path).expanduser()
        backup = sch_editor.backup_file(pcb_path)
        kicad_python.import_ses(pcb_path, ses)
        kicad_python.fill_zones(pcb_path)
        return {
            "pcb_path": str(pcb_path),
            "ses_path": str(ses),
            "backup": str(backup) if backup else None,
            "zones_filled": True,
        }

    @mcp.tool()
    def fill_zones() -> dict:
        """Fill every zone on the active board and save.

        Required before DRC on any board with a pour: `kicad-cli pcb drc` does
        not fill zones, and an unfilled board reports every pour-connected pad
        as unconnected.
        """
        pcb_path = state.get_active_board_path()
        kicad_python.fill_zones(pcb_path)
        return {"pcb_path": str(pcb_path), "zones_filled": True}

    @mcp.tool()
    def bond_ground(
        net: str = "GND",
        max_escape_mm: float = 2.0,
        escape_targets: list[list[str]] | None = None,
    ) -> dict:
        """Stitch a fragmented pour back together on the active board.

        Autorouting carves traces through a pour and leaves islands behind;
        an island no via reaches is floating copper that DRC reports as
        unconnected. This places one stitching via per orphaned island, and
        optionally escapes isolated pads (`[["U2","5"], ...]`) to the
        opposite-layer pour with a via and a short stub.

        Anything it cannot fix within the clearance rules is returned in
        `unstitchable` / `unescapable` with coordinates, to route by hand.
        """
        pcb_path = state.get_active_board_path()
        backup = sch_editor.backup_file(pcb_path)
        targets = [tuple(t) for t in (escape_targets or [])]
        result = kicad_python.bond_ground(
            pcb_path, net, max_escape_mm=max_escape_mm, escape_targets=targets
        )
        result["backup"] = str(backup) if backup else None
        result["pcb_path"] = str(pcb_path)
        return result

    @mcp.tool()
    def routing_status() -> dict:
        """Report which Freerouting JAR and JVM this workspace will actually use.

        Freerouting 2.2+ requires Java 25; 2.1.x runs on Java 21 but its route
        optimizer is multi-threaded and upstream-broken. Run this when a route
        looks wrong before assuming the board is at fault.
        """
        jars = [
            {"jar": str(p), "version": ".".join(str(x) for x in v),
             "needs_java": freerouting.required_java_major(v)}
            for v, p in freerouting.available_jars()
        ]
        info: dict = {"jars_found": jars}
        try:
            jar, java, version = freerouting._ensure_environment()
            info.update({
                "selected_jar": str(jar),
                "selected_version": ".".join(str(v) for v in version) if version else "unknown",
                "java": str(java),
                "java_major": freerouting.java_major(java),
                "optimizer_is_broken": bool(version and version < (2, 2, 0)),
            })
        except freerouting.FreeroutingError as e:
            info["error"] = str(e)
        return info

    @mcp.tool()
    def autoroute_pcb(
        passes: int = 50,
        timeout_seconds: float = 900.0,
        threads: int = 1,
        bond_ground: bool = True,
        escape_pads: bool = True,
        ground_net: str = "GND",
        max_escape_mm: float = 2.0,
        via_costs: int | None = 50,
        prefer_horizontal_top: bool = True,
        fanout: bool = True,
    ) -> dict:
        """Route the active PCB end to end and verify the result with DRC.

        DSN export → Freerouting → SES import → zone fill → ground bonding →
        DRC. Returns `passed` (zero unconnected items), plus the leftovers
        split into `remaining_signal_items` (reroute these) and
        `remaining_pour_items` (bond these), each with coordinates.

        Args:
            passes: Freerouting `-mp`. 2.2+ stops on its own when the score
                stops improving, so a high value costs nothing but time.
            threads: 1 keeps the optimizer single-threaded. On a 2.1.x JAR
                this is ignored upstream and the broken optimizer runs anyway.
            bond_ground: stitch pour islands the router fragmented.
            escape_pads: also try to escape isolated pads to the pour.
            via_costs: higher makes the router prefer detours over layer changes.
            prefer_horizontal_top: horizontal on top, vertical on bottom.
            fanout: SMD fanout pre-pass (2.3+; ignored by older JARs).
        """
        pcb_path = state.get_active_board_path()
        profile = RouteProfile(
            passes=passes,
            threads=threads,
            preferred_direction_horizontal=(
                [prefer_horizontal_top, not prefer_horizontal_top]
            ),
            via_costs=via_costs,
            fanout=fanout,
        )
        return route_pipeline.route_board(
            pcb_path,
            profile=profile,
            passes=passes,
            threads=threads,
            timeout_seconds=timeout_seconds,
            bond_ground=bond_ground,
            escape_pads=escape_pads,
            ground_net=ground_net,
            max_escape_mm=max_escape_mm,
        )
