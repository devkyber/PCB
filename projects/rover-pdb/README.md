# Rover PDB: start here

The owner closed Rover work on 2026-10-07. This is the sole retained Rover
project. Cleanup preserved its native CAD and current manufacturing-preview
files byte-for-byte. Earlier development checks below retain their dated scope;
closing development does not create a fabrication sign-off.

Open [rover-pdb.kicad_pro](rover-pdb.kicad_pro) in KiCad. The saved seven-sheet
[schematic](rover-pdb.kicad_sch) and [PCB](rover-pdb.kicad_pcb) are the current
owner-editable design. **PCB P5 / circuit A10 with owner edits and L3 stock substitution, 2026-10-05**, retains the owner's
**77.5 × 100 mm** outline, two copper layers / 1 oz, four M3 holes, surface
wire pads and the saved placement, except small L3/TP4 clearance adjustments. The switch choice is deferred. All seven
schematic files preserve owner circuitry, including F1 removal and the added
J8/R6 servo channel. L3 remains 3.3 uH with a new MPN and matching footprint. P2/P3 remain 12 V for the owner's future expansion plans.

**The reviewed updates are applied.** P5 adds two female-socket 3D models,
widens six battery-path segments and adds 48 useful, tented vias beside solid
wire pads and converter grounds. A10 removes F1 and bridges the input to RS1;
there is no onboard battery fuse. P4's separate wide 5 V force connection,
labels, mounting keepouts and manual Pico-fitting metadata are retained.
Motor-energy handling, final switch choice, physical fit and prototype
measurements remain open; this is not a fabrication release. See the
[current verification](docs/review/PCB_VERIFICATION.md).

The 18 V Jetson / independent 12 V comparison was retired at the owner's
request. It and the superseded A3 teaching guide are recoverable from
`C:/Users/tae06/.codex/archives/pcb/cleanup-20261007/PCB.zip`.

- [Schematic PDF, A10](output/pdf/rover-pdb-schematic-A10.pdf)
- [Current PCB assembly and copper PDF, P5](output/pdf/rover-pdb-pcb-review.pdf)
- [Current 3D assembly view](output/review/assembly-3d.png)
- [Schematic BOM](output/schematic-bom.csv) and [purchase notes](docs/design/BOM_NOTES.md)
- [Pipeline walkthrough and provenance](docs/review/PIPELINE_AUDIT.md)

The PCB PDF is regenerated from current CAD and its manifest records source
hashes. The schematic PDF is an A10 review snapshot. Later manual CAD edits can
make either export stale; edit the native files, never an exported drawing.
Native tracks/vias are editable. Routing classes are defaults for new copper,
not automatic resizing or proof of current capacity.

P5 passes native schematic/PCB parity and placement, with **0 DRC errors,
0 warnings and 0 unconnected items** after refill. All **19/19** checked power
paths remain connected when thin power-net tracks are removed in a disposable
fault test. This detects dependence on sense-size copper, not ampacity.
F1 removal combines the two historical fuse connections into one direct input
connection; the P4 control passes 20/20. All 482 native tracks and 167
vias are unlocked. The four bottom-edge connector
pin legends are printed on the back at 1 mm height; the PDF's back view is
viewed from underneath, so those labels read correctly.

## What stays at the root

| Files | Why they are necessary |
| --- | --- |
| `.kicad_pro`, `.kicad_pcb`, root and child `.kicad_sch` | KiCad's editable project and design |
| `project.yaml`, `netmap.json`, `review-profile.yaml` | Pipeline configuration, connectivity contract and human review requirements |
| `REQUIREMENTS.md`, `DESIGN_BASIS.md`, `REFERENCE_REVIEW.md`, `DEVIATIONS.md` | Declared engineering inputs read by the shared pipeline |
| `fp-lib-table`, `sym-lib-table`; `libs/`, `symbols/`, `footprints/` | Self-contained symbols, real pad geometry and 3D models |
| `evidence/` | Exact manufacturer/supplier sources and provenance |
| `AGENTS.md`, `SCHEMATIC_OWNER` | Scope and owner-edit preservation instructions |
| `schematic-intent.yaml` | Historical comparison/generation input, not authority over saved CAD |
| `check_schematic.py` | Extra Rover-specific pin-map and adopted-circuit assertions |

## Open the detail only when needed

| Folder / document | Purpose |
| --- | --- |
| [Current design basis](DESIGN_BASIS.md) | Adopted component choices and electrical calculations |
| [Power controls](docs/design/POWER_DECISIONS.md) | USB-only Pico and VIN-derived motor-enable behavior |
| [12 V / 5 V filters](docs/design/OUTPUT_FILTER_SELECTION.md), [motor filter](docs/design/MOTOR_FILTER_SELECTION.md) | Capacitor/inductor decisions and derating evidence |
| [PCB design](docs/design/PCB_DESIGN.md) | Physical construction, routing defaults, datasheet page map and bench checks |
| [JLCPCB workflow and L3 substitution](docs/design/JLCPCB.md) | Current manufacture files, stock checks, manual KiCad steps and Coilank selection |
| [Schematic review](docs/review/SCHEMATIC_REVIEW.md) | Author checks and unresolved decisions |
| [Footprint review](docs/review/PCB_FOOTPRINT_REVIEW.md), [power layout](docs/review/PCB_POWER_LAYOUT_REVIEW.md), [verification](docs/review/PCB_VERIFICATION.md) | Recorded geometry, physical routing decisions and measured CAD checks |
| `docs/review/records/` | Small original machine reports and owner-review records, with snapshot-specific scope |
| [Layout tools](layout/README.md) | Three read-only audit/export tools; no board-regeneration recipe |
| [Simulations](simulation/README.md) | Actual passive-network results and prepared vendor converter cases; explicit limitations |

## Current circuit in brief

See [the JLCPCB workflow](docs/design/JLCPCB.md) for the current upload package,
stock report and repeatable commands. Older PDF/review links below describe their
named revisions and are not regenerated manufacturing sources.

Three LMR51450 converters supply nominal 12 V, 5 V and 22.19 V. L1/L2/L3 are
6.8/4.7/3.3 µH; RT is open for nominal 500 kHz. The input banks each retain two
10 µF plus 100 nF. Output ceramics are four 22 µF, five 22 µF and four 10 µF,
respectively, with the adopted bulk capacitors. Motor EN comes from the local
VIN-derived switch network and is pulled low with the switch open. Pico is
USB-only; J9 is an optional DNP four-GPIO expansion header. Follow native CAD
and the design basis for exact values and connections.

## Work on this board

Read [AGENTS.md](AGENTS.md) and the [shared workflow](../../docs/WORKFLOW.md).
Save and close KiCad before assisted writes. Start each candidate from current
saved CAD; preview and inspect it before applying. An older generation recipe
must never restore older routing or component values over owner edits.

```powershell
uv run python projects/rover-pdb/check_schematic.py
uv run pcb-copilot research projects/rover-pdb --verify
uv run pcb-copilot review projects/rover-pdb
uv run pcb-copilot clean projects/rover-pdb
```

`clean` is a preview unless `--apply` is supplied; it removes only named,
reproducible preview files. It does not remove the folders of useful documents
above. The deep 2026-10-01 cleanup archived historical drafts/recovery copies
outside the repo before removal. Its backup and retention policy are recorded
in the [architecture guide](../../docs/ARCHITECTURE.md#cleanup-and-retention).

This is the baseline Rover project. On 2026-10-01 it was renamed from
`rover-pdb-readable`, preserving the owner's saved CAD bytes. The earlier
LM73606 comparison project was moved intact outside the repository to
`C:/Users/tae06/.codex/archives/pcb/rover-consolidation-20261001-114628/original-rover/`.
Historical reports and the teaching guide retain their former project names;
they are records of earlier revisions, not alternate current designs.

Current CAD checks do not establish motor-regeneration handling, thermal/load-step behavior,
assembly fit or harness protection. Five project decisions plus the two shared
human release decisions remain required; only `pcb-copilot release` creates
manufacturing output. The retained upload preview remains a dated snapshot.
