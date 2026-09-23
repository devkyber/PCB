"""Derive the connectivity contract from KiCad's native XML netlist."""

from pathlib import Path

from pcb_copilot.layout.render import schematic_inventory
from pcb_copilot.toolchain import discover_toolchain


def schematic_nets(schematic: Path) -> dict[str, set[tuple[str, str]]]:
    _, nets = schematic_inventory(discover_toolchain(Path(__file__).resolve().parents[3]), schematic)
    return nets


def extract(schematic: Path) -> dict:
    nets = {}
    for name, members in schematic_nets(schematic).items():
        for ref, pin in members:
            nets.setdefault(ref, {})[pin] = name
    return {'nets': {ref: dict(sorted(pins.items())) for ref, pins in sorted(nets.items())}}
