# PCB Copilot

PCB Copilot is a human-controlled assistant for researching, drafting,
checking, and packaging KiCad boards. Its purpose is to remove repetitive
work—not to pretend that software can independently approve an electrical
design.

The useful target is practical leverage:

- locate and archive datasheets, integration manuals, and reference designs;
- extract exact pin, value, and connection facts with citations;
- prepare a connected, readable schematic draft instead of a blank sheet;
- propose placement, constraints, and optional routing candidates;
- run repeatable ERC, DRC, parity, evidence, ownership, and release checks;
- show unresolved engineering judgments to the human who owns the board.

Accepted `.kicad_sch` and `.kicad_pcb` files remain the sources of truth.
Drafting never silently overwrites them. A person reviews and accepts each
material change, and fabrication stays blocked until the accepted revision has
current evidence and sign-off.

## Current state

The remake is being delivered incrementally. The foundation now provides a
root Python workspace, Windows/KiCad 10 discovery, four-board preservation
baselines, safe project manifests, lifecycle protection, and a read-only
status command. Existing scripts remain available while their behavior is
characterized and moved behind package APIs.

```powershell
uv sync
uv run pcb-copilot --version
uv run pcb-copilot status projects/baro-bmp390
uv run pytest -m "not slow and not network" -q
```

The repository currently contains four real boards: `baro-bmp390`,
`imu-icm42688`, `gnss-neom9n`, and `tms-v3`. Do not regenerate or accept one
merely to make a check green. Existing failures and open owner decisions are
part of the engineering record.

## Read next

- [Workflow](docs/WORKFLOW.md) — operator sequence and commands
- [Architecture](docs/ARCHITECTURE.md) — authority, state, gates, and preserved components
- [Design rules](docs/DESIGN_RULES.md) — enforced rules and human review scope
- [Limitations](docs/LIMITATIONS.md) — honest capability boundary and future work
- [Project format](docs/PROJECT_FORMAT.md) — manifest and directory contract
- [Approved remake design](docs/superpowers/specs/2026-09-14-pcb-copilot-repository-remake-design.md)
- [Implementation roadmap](docs/superpowers/plans/2026-09-14-pcb-copilot-remake-roadmap.md)

## Safety rule

Passing automation means that the implemented checks found no blocking
condition. It does not mean the circuit is correct, safe, manufacturable in
its operating environment, or suitable for a rocket, battery, RF, precision
measurement, or pyrotechnic system. The named human reviewer owns those
decisions.
