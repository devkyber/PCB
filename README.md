# PCB Copilot

A KiCad workspace and one command-line pipeline for PCB design: preserve source
research, update schematics and layouts, check the current design, and export a
reviewed fabrication package.

## Current designs

| Board | Schematic | PCB |
| --- | --- | --- |
| BMP390 barometer | [Open](projects/baro-bmp390/baro-bmp390.kicad_sch) | [Open](projects/baro-bmp390/baro-bmp390.kicad_pcb) |
| ICM-42688 IMU | [Open](projects/imu-icm42688/imu-icm42688.kicad_sch) | [Open](projects/imu-icm42688/imu-icm42688.kicad_pcb) |
| NEO-M9N GNSS | [Open](projects/gnss-neom9n/gnss-neom9n.kicad_sch) | [Open](projects/gnss-neom9n/gnss-neom9n.kicad_pcb) |
| TMS V3 | [Open seven-sheet project](projects/tms-v3/tms-v3.kicad_sch) | [Open](projects/tms-v3/tms-v3.kicad_pcb) |

These root KiCad files are the working designs. Each board keeps its requirements,
design basis, intent, libraries and exact source evidence beside them. All four
remain drafts with engineering decisions and human review outstanding.

## Use the pipeline

Install Python 3.11+, [uv](https://docs.astral.sh/uv/) and KiCad 10.

```powershell
uv sync
uv run pcb-copilot status projects/baro-bmp390
uv run pcb-copilot research projects/baro-bmp390 --verify
uv run pcb-copilot parts projects/baro-bmp390 --lookup C5124834
uv run pcb-copilot update-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
uv run pcb-copilot update-layout projects/baro-bmp390 --intent projects/baro-bmp390/layout-intent.yaml
uv run pcb-copilot review projects/baro-bmp390
uv run pcb-copilot prepare-signoff projects/baro-bmp390
uv run pcb-copilot release projects/baro-bmp390
```

Updates preview by default; `--apply` installs only a checked candidate and
invalidates prior release state. Layout can also import a routed `--candidate
PATH.kicad_pcb`. Circuit changes can pair a new schematic intent with `--pcb`
for one checked update. Release runs a fresh review and refuses unresolved checks or
unsigned/stale human decisions. It never fills in sign-off on your behalf.

Read [Workflow](docs/WORKFLOW.md), [Design rules](docs/DESIGN_RULES.md),
[Limitations](docs/LIMITATIONS.md), and [Architecture](docs/ARCHITECTURE.md).

## Repository contents

- `projects/`: current CAD, local libraries, requirements and source evidence.
- `src/pcb_copilot/`: the pipeline and its checks.
- `packages/kicad-claude-mcp/`: the small local CAD/routing dependency.
- `tests/`: connectivity, geometry, evidence, transaction and export regressions.
- `docs/`: the four operator/maintainer guides linked above.

`.git` stores history; `.venv` is the installed Python environment. A board-local,
ignored `.pcb-copilot` folder is created on demand for previews and release state.
Supplier parts are imported with `parts PROJECT --import C_NUMBER --mpn PART`.
Datasheets, reference designs and project libraries remain versioned inputs.
Fabrication output is generated under `projects/BOARD/fabrication/`.

Run `uv run pytest -q` for the retained suite. Tests marked `slow` require native
CAD tooling; `uv run pytest -q -m "not slow and not network"` omits those marked
integrations. Some current-project tests also require KiCad. No tests authorize
fabrication of a real board.
