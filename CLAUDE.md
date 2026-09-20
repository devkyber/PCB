# PCB Copilot Workspace Instructions

This repository builds a human-controlled PCB assistant. The human owns the
requirements, accepted KiCad designs, unresolved engineering choices, visual
review, bench validation, and release decision. Automation performs evidence
collection, drafting, consistency checks, and repeatable packaging.

## Read first

- [Purpose and quick start](README.md)
- [Selected results and progress](docs/PROGRESS.md)
- [Operator workflow](docs/WORKFLOW.md)
- [Architecture and authority](docs/ARCHITECTURE.md)
- [Design rules](docs/DESIGN_RULES.md)
- [Limitations and human responsibilities](docs/LIMITATIONS.md)
- [Project manifest and state](docs/PROJECT_FORMAT.md)

## Non-negotiable operating rules

1. Read a project's `REQUIREMENTS.md`, `DESIGN_BASIS.md`, `DEVIATIONS.md`,
   `SIGNOFF.md`, and `project.yaml` before changing its design.
2. Accepted `.kicad_sch` and `.kicad_pcb` files are sources of truth. Generate
   only into a separate draft and require explicit acceptance.
3. Never invent missing owner inputs, pin mappings, electrical limits,
   footprints, stackups, currents, or safety conclusions.
4. Archive exact source bytes and provenance before citing a datasheet or
   reference design. The datasheet outranks the reference circuit.
5. Preserve `netmap.json` and run schematic/PCB parity after connectivity
   changes.
6. Use `docs/deviations.py` as the single scoped-waiver parser.
7. Use the existing schematic and PCB coordinate/placement helpers; do not add
   inline coordinate conversions or hand-guessed pin endpoints.
8. Treat ERC, DRC, design-rule checks, and autorouting as evidence with stated
   scope, not certification.
9. Run every relevant check and its fault test before claiming completion.
10. Fabrication is last and must describe the exact reviewed design hashes.

## Current commands

```powershell
uv sync
uv run pcb-copilot status projects/baro-bmp390
uv run pcb-copilot research projects/baro-bmp390 --verify
uv run pcb-copilot research projects/baro-bmp390 --extract BMP390
uv run python docs/run_gates.py projects/baro-bmp390/baro-bmp390.kicad_pcb
uv run python docs/audit_workflow.py
```

Run `uv run python docs/selftest_enforcement.py` only in a disposable repository
copy: it temporarily replaces evidence files and touches board modification times.

The old pipeline and helper scripts remain compatibility entry points during
migration. Read their callers and characterization tests before moving them.
Delete nothing merely because a replacement is planned; the migration
inventory must show a verified destination, no live callers, and no behavior
or factual loss.

## Gate Rule during migration

`docs/pipeline.py --status` remains a legacy summary; the full pipeline is
mutating and its accepted-PCB routing call is rejected by draft-only wrappers.
Use the independent draft commands in `docs/WORKFLOW.md`. Evidence archive,
verification, and supported exact extraction now live behind
`pcb-copilot research`; the old research scripts remain compatibility wrappers.
A file existing, a command returning zero, or a generated report from an older
run is not evidence. Every gate must
prove it ran against the current design and must have a fault-injection test
showing that the failure path fires.

## Current known boundary

Accepted legacy schematics and new drafts are different artifacts. The selected
drafts have local wiring and junctions; TMS V3 has an overview plus six functional
sheets. Schematic and PCB human reviews remain pending. Layout drafting currently
requires the circuit's physical parts on an existing PCB; GNSS/TMS placement
blockers remain. Do not call a board finished because it opens or passes ERC/DRC.
Consult [Limitations](docs/LIMITATIONS.md) and leave unresolved decisions visible.
