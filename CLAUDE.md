# PCB Copilot Workspace Instructions

This repository builds a human-controlled PCB assistant. The human owns the
requirements, current KiCad designs, unresolved engineering choices, visual
review, bench validation, and release decision. Automation performs evidence
collection, drafting, consistency checks, and repeatable packaging.

## Read first

- [Current designs and quick start](README.md)
- [Operator workflow](docs/WORKFLOW.md)
- [Architecture and authority](docs/ARCHITECTURE.md)
- [Design rules](docs/DESIGN_RULES.md)
- [Limitations and human responsibilities](docs/LIMITATIONS.md)

## Non-negotiable operating rules

1. Read a project's `REQUIREMENTS.md`, `DESIGN_BASIS.md`, `DEVIATIONS.md`,
   `review-profile.yaml`, and `project.yaml` before changing its design.
2. Root `.kicad_sch` and `.kicad_pcb` files are the current working sources of
   truth. Generate into a temporary candidate; change root CAD only through an
   explicit `--apply` after checks. Applying does not imply human approval.
3. Never invent missing owner inputs, pin mappings, electrical limits,
   footprints, stackups, currents, or safety conclusions.
4. Archive exact source bytes and provenance before citing a datasheet or
   reference design. The datasheet outranks the reference circuit.
5. Preserve `netmap.json` and run schematic/PCB parity after connectivity
   changes.
6. Use `scripts/deviations.py` as the single scoped-waiver parser.
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
uv run pcb-copilot update-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
uv run pcb-copilot review projects/baro-bmp390
uv run pytest -q -m "not slow and not network"
```

The historical `scripts/selftest_enforcement.py` is not yet migrated to the
current command surface. Study or port it only in a disposable repository copy:
it temporarily replaces evidence files and touches board modification times.

The old pipeline and helpers remain only where behavior or callers have not
been migrated. Read their callers and characterization tests before removal.
Delete only after their current behavior and factual content are preserved.

## Gate Rule during migration

The legacy `scripts/pipeline.py` and direct `scripts/export_fab.py` CLIs now
refuse execution. Use `pcb-copilot` for current work. Evidence archive, verification,
and supported exact extraction live behind `pcb-copilot research`. A file
existing, a command returning zero, or an older report is not evidence. Every
gate must prove it ran against the current design and have a fault test.

## Current known boundary

All four root schematics now contain the improved working drawings. TMS V3 has
an overview plus six functional sheets, and its routed board retains its
geometry after exact net-name/class reconciliation. Human schematic and PCB
reviews remain pending. Layout drafting requires physical parts on an existing
PCB; it does not replace the rooted routed boards. GNSS/TMS layout blockers
remain, as do TMS safety decisions. `review` runs current checks in a disposable
copy and checks board-specific hash-bound sign-off. No current human decisions
have been carried over from legacy checkboxes. `update-layout` and `release`
are not implemented. Consult [Limitations](docs/LIMITATIONS.md) and
never call a board finished merely because it opens or passes ERC/DRC.
