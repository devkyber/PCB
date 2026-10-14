# PCB Copilot

One KiCad workspace and one CLI: **read the saved design → prepare a scoped
candidate → check it → review it → apply → release when approved**.
The current native CAD is authoritative. Generators and old snapshots do not
replace owner edits. Start with the [working workflow](docs/WORKFLOW.md).

## Open a board

| Project | Role | Open in KiCad |
| --- | --- | --- |
| [Rover PDB](projects/rover-pdb/README.md) | Completed owner work; sole retained Rover board | [Project](projects/rover-pdb/rover-pdb.kicad_pro) |
| [TMS A2](projects/tms/README.md) | Installed schematic and component verification; PCB and qualification pending | [Project](projects/tms/tms.kicad_pro) |

TMS was recreated from [recorded decisions and exact research](design-bases/tms/README.md).
Its [component guide](projects/tms/docs/design/COMPONENT_VERIFICATION.md) explains
all 120 parts and remaining qualifications. Retired TMS CAD is a frozen regression
input under `tests/fixtures/boards/tms-v3`, never an active project.

CAD checks are scoped checks, not fabrication approval. Each project's
requirements, design basis, deviations and review profile state what remains.
The owner retired the sensor projects and Rover comparison on 2026-10-07.
Recovery archives and the cleanup boundary are recorded in
[Architecture](docs/ARCHITECTURE.md#cleanup-and-retention).

## Daily commands

Install Python 3.11+, uv and KiCad 10, then run `uv sync` once.
Replace `PROJECT` with a project folder such as `projects/rover-pdb`.

| Intent | Command |
| --- | --- |
| See saved state | `uv run pcb-copilot status PROJECT` |
| Verify archived sources | `uv run pcb-copilot research PROJECT --verify` |
| Inspect exact supplier identity | `uv run pcb-copilot parts PROJECT --lookup C6890985` |
| Preview an edited native schematic hierarchy | `uv run pcb-copilot update-schematic PROJECT --candidate C:/work/rover-pdb.kicad_sch` |
| Preview an edited native PCB | `uv run pcb-copilot update-layout PROJECT --candidate C:/work/rover-pdb.kicad_pcb` |
| Run current review | `uv run pcb-copilot review PROJECT` |
| Create an unsigned human review worksheet | `uv run pcb-copilot prepare-signoff PROJECT` |
| Check and export an approved package | `uv run pcb-copilot release PROJECT` |
| Preview removal of reproducible preview files | `uv run pcb-copilot clean PROJECT` |

Save and close KiCad before external application. Inspect the preview, then
repeat the identical update command with `--apply`. Any intervening saved edit
requires a fresh preview. Intent-driven generation and optional autorouting are
advanced creation paths described in the workflow; use native candidates for
ordinary maintenance of an owner-edited board.

## Where to look, from the surface down

| Level | Location | What belongs there |
| --- | --- | --- |
| L0: operate | This README; project README | Entry points and current deliverables |
| L1: understand | [Workflow](docs/WORKFLOW.md), [Architecture](docs/ARCHITECTURE.md) | Commands, internal stages, file ownership and cleanup |
| L2: design | `projects/BOARD/` | Native CAD, declared inputs, local libraries and exact source evidence |
| New project inputs | `templates/project/`; `templates/jlcpcb-2layer-1oz/` | Requirement/profile/intent skeleton and the dated native geometry baseline |
| L3: inspect implementation | `src/pcb_copilot`, `packages/kicad-claude-mcp` | CLI stages and the small CAD adapter dependency |
| L4: verify behavior | `tests`, adapter tests | Connectivity, geometry, source, update, cleanup and export regressions; frozen board inputs live only in `tests/fixtures/boards` |
| Generated work | `.pcb-copilot/`; `fabrication/` | Reproducible previews/state; gated manufacturing packages |

Read [Design rules](docs/DESIGN_RULES.md) for engineering/drawing conventions and
[Limitations](docs/LIMITATIONS.md) for what machine checks cannot establish.
The [Rover audit](projects/rover-pdb/docs/review/PIPELINE_AUDIT.md) is the
concrete worked example. Its archived construction code is not a second pipeline.
The [shared lessons and enforcement map](docs/ARCHITECTURE.md#rover-lessons-used-by-the-shared-pipeline)
apply to every board. Release always requires the shared schematic-readability
and layout-handover decisions as well as the project's own review items.

Run `uv run pytest -q` for the full suite. `-m "not slow and not network"` skips
marked integrations; some current-project tests still invoke KiCad. `.git` is
history and `.venv` is the installed environment, not clutter to delete routinely.
