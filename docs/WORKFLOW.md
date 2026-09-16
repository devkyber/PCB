# PCB Copilot Workflow

This is the canonical operator workflow. PCB Copilot is supplementary: it
collects evidence, prepares reviewable drafts, runs checks, and keeps the
record coherent while a human makes design decisions.

## 1. Start with status

```powershell
uv sync
uv run pcb-copilot status projects/baro-bmp390
```

Status is read-only. It reports the manifest, lifecycle, accepted design
paths, evidence availability, toolchain, recorded hashes, and one next action.
It does not run generators or rewrite tracked reports.

The legacy all-board summary is also read-only. It reads stored pipeline
reports and current board hashes without rebuilding a board:

```powershell
uv run python docs/pipeline.py --status
```

These legacy checking commands remain valid during migration:

```powershell
uv run python docs/pipeline.py projects/<board> --check
uv run python docs/run_gates.py projects/<board>/<board>.kicad_pcb
uv run python docs/audit_workflow.py
```

`--check` does not rebuild design files, but it still rewrites check and status
reports. The direct gate runner likewise writes ERC and DRC reports. Use the
package `status` command or legacy `--status` when the operation must be
read-only.

The full compatibility pipeline is mutating.

```powershell
uv run python docs/pipeline.py projects/<board>
```

It runs `env → research → sch → erc → pcb → route → gates → fab`. On a legacy
project it can regenerate the accepted schematic and PCB, route, refill and
ground-bond the PCB, export fabrication files when all gates pass, and rewrite
pipeline, check, and human-work reports. `SCHEMATIC_OWNER` defaults to
`generated` when the marker is absent; a changed generated schematic stops at
the ownership tripwire unless `--regenerate` is supplied to discard it
deliberately. Setting the owner to `human` prevents schematic regeneration and
makes the pipeline derive `netmap.json` from that schematic, but it does not
protect the PCB from its legacy generator or routing stages. Do not run the
full command on an accepted board unless those mutations are intended and
reviewed.

## 2. Define the board before choosing parts

For a new legacy project, create its directory first, then scaffold the gate
records:

```powershell
uv run python docs/run_gates.py --init projects/<board>
```

The project directory must already exist. `--init` creates missing
`REQUIREMENTS.md`, `DESIGN_BASIS.md`, `DEVIATIONS.md`, `SIGNOFF.md`, and
`evidence/index.yaml` records plus the evidence files directory.
It never overwrites an existing file. It does not create KiCad design files or
a PCB Copilot project manifest.

Write measurable requirements in the project’s `REQUIREMENTS.md`: purpose,
supply range, worst-case current, interfaces, outline, mounting, operating
environment, and success criteria. A heading without substantive content is
not a captured requirement.

Human-owned inputs stay explicit. Examples include TMS igniter resistance and
pulse current, GNSS antenna/stackup choice, IMU axis orientation and mounting
rigidity, and the barometer’s mechanical port/standoff arrangement. The
assistant must report these as open decisions rather than inventing numbers.

## 3. Collect evidence

Datasheets, reference schematics, and reference PCB layouts are three distinct
research deliverables of equal workflow importance. Search manufacturer EVMs,
evaluation kits and integration guides first, then credible open hardware.
The datasheet remains the authority when a reference conflicts with device
requirements. A downloaded schematic does not establish PCB-layout coverage.

```powershell
uv run pcb-copilot research projects/baro-bmp390 --search-plan BMP390
uv run pcb-copilot research projects/baro-bmp390 --inspect-reference SCHEMATIC_EVIDENCE_ID PCB_EVIDENCE_ID
```

`--search-plan` prints queries; it does **not** perform a live web search or
claim that research is complete. The assistant executes the searches and
records query/date, candidates, source identity, variant/revision, rejected
results and access failures in `REFERENCE_REVIEW.md`. Archive selected native
CAD and supporting PDFs, inspect both circuit and copper views, and compare
them with requirements and the datasheet. Record relevant choices and
differences in `DESIGN_BASIS.md`, including layout choices.

`--inspect-reference` takes two IDs from `evidence/index.yaml`. It verifies
their bytes before comparing an Eagle schematic's mapped pads with its board,
checks package names and explicit values, and reports routing/layer/polygon
metadata. It is read-only and reports mismatches with a nonzero exit code.
It does not run DRC, prove completion of routes, or certify layout suitability.
KiCad reference-pair inspection and automatic live-search providers are not
implemented in this command. Unsupported sources require explicit inspection;
they must never silently count as inspected or validated.

Keep four statuses separate in the review: **searched**, **archived**,
**inspected**, and **compared/validated within a stated scope**. Missing
reference designs or unavailable layout files remain visible findings during
drafting; release review must address coverage and unresolved comparisons.

Use this trust order:

1. Manufacturer datasheet, integration manual, EVM, or application note.
2. Proven open-hardware CAD from vendors such as Adafruit or SparkFun.
3. Teaching or community material for rationale, never as sole pin-level
   authority.
4. Symbol, footprint, and 3D-model libraries as implementation inputs that
   still require verification.

The datasheet outranks a reference design. Modules often need both a component
datasheet and an integration or socket pinout manual. Archive the exact bytes,
source URL, retrieval date, part identity, and document role before citing a
fact. Reject HTML login or error pages masquerading as PDFs.

Use the unified research command for archive verification, collection, and
exact extraction from supported CAD sources:

```powershell
uv run pcb-copilot research projects/baro-bmp390 --verify
uv run pcb-copilot research projects/baro-bmp390 --add BMP390 https://example.invalid/manufacturer-document.pdf --role datasheet
uv run pcb-copilot research projects/baro-bmp390 --extract BMP390
```

The example URL illustrates syntax only and must not be archived. `--verify`
is read-only and verifies the indexed bytes, hashes, media types, and source
URLs; board-level coverage remains enforced by `check_research.py` and
`check_datasheets.py`. `--extract` prints cited exact facts when a supported
Eagle schematic is present, lists PDFs and other sources that still need human
review, surfaces conflicts, and proposes `DESIGN_BASIS.md` rows without editing
that file. Use `--trust-tier` when the default `manufacturer` classification is
not accurate.

Compatibility commands remain available during migration:

```powershell
uv run python docs/collect_references.py suggest BMP390
uv run python docs/collect_references.py add projects/baro-bmp390 BMP390 https://example.invalid/manufacturer-document.pdf
uv run python docs/fetch_reference_doc.py eagle projects/baro-bmp390/evidence/files/BMP390_Adafruit_20BMP390.sch BMP390
uv run python docs/check_research.py projects/baro-bmp390/baro-bmp390.kicad_pcb
```

Research is advisory while drafting and blocking when release readiness is
evaluated.

Record key comparisons in `DESIGN_BASIS.md`: our choice, reference choice,
source, and `Match` or `Deviate: reason`. A reasoned deviation is valid; an
implicit difference is not.

## 4. Draft the schematic

During the remake, accepted schematics stay untouched until explicit
acceptance. Generate a draft from a reviewed intent file with:

```powershell
uv run pcb-copilot draft-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
```

The command prints a JSON report with the draft ID and artifact paths under
`.pcb-copilot/drafts/`. It preserves the source intent beside `preview.pdf`,
`erc.json`, `metrics.json`, and `review.json`. An exit code of 1 indicates
blocking machine findings; the draft remains available for inspection. Missing
or mismatched pin-map citations are explicit review advisories during drafting
and acceptance; evidence requirements remain blocking at release. A failed PDF or ERC
export is recorded as a failure and does not discard the schematic.

For a generic part without verified pin-map evidence, set
`pin_map_evidence_id: null` and supply a substantive `pin_map_review_note`.
Do not borrow an unrelated IC's citation to suppress the finding. The renderer
still validates all actual library pins against connected and explicit NC
assignments, even when the intent omits its optional pin inventory.

The draft must include functional blocks, local drawn wires, graphical power
symbols, boundary labels, complete titles, explicit no-connects, evidence
references, ERC output, quality metrics, and a rendered PDF. Hierarchy is used
when a sheet would otherwise be crowded; TMS V3 is the required multi-sheet
proof case.

Review the rendered page, not only ERC. Confirm flow, grouping, symbol and pin
identity, values, power paths, labels, page boundaries, and readable spacing.
ERC proves only the rule set that it implements.

The preview also reports suspected stock power-glyph contacts with other power
glyphs or visible power Value/local/hierarchical labels. These are conservative
review advisories, not electrical blockers or automatic repairs. Each finding
identifies its sheet and symbol/label (and directly attached component pin when
available). Bounds use millimetres from the sheet's lower-left corner, unlike
KiCad's top-left file coordinates: the checker preserves file X and transforms
Y to `sheet_height - file_Y` before computing bounds. Unsupported geometry
produces an explicit `power-clearance-unchecked` advisory. No findings does not
establish complete graphical clearance: wires, pin names and ordinary component
fields are outside this diagnostic's scope.

## 5. Draft placement and routing

Resolve and measure the real footprint before choosing coordinates. Place
fixed mechanical items first, then ICs/modules, decoupling, clocks, protection,
connectors, and remaining passives. Evaluate placement before blaming an
autorouter: moving a major module can improve completion more than extra route
passes.

The separate layout-draft interface is a future workflow concept. No
`pcb-copilot draft-layout` command exists today. Until it is implemented and
verified, use the compatibility pipeline and board-specific legacy generators
without treating them as the new draft/accept interface.

The future interface is intended to default to human routing, with
critical-only and candidate-all modes producing candidates rather than
automatically accepted boards. Regardless of entry point, inspect the board in
KiCad and 3D view. Check connector access, mounting, return paths, decoupling,
crystal/RF geometry, high-current paths, copper pours, silkscreen, assembly,
and mechanical fit.

Legacy routing entry points must use the shared routing pipeline: DSN export,
route, SES import, zone fill, ground bonding, and final DRC. The MCP
`autoroute_pcb` route and `docs/route_and_fill.py` provide that behavior. A raw
Freerouting JAR invocation bypasses the fill and bonding steps, so its output
is not a valid finished board.

## 6. Review and accept

The final command surface separates three categories:

- machine failures: deterministic checks or tools could not establish a fact;
- engineering warnings: a condition needs judgment or measured inputs;
- human decisions: project-specific sign-off that automation cannot perform.

Acceptance is explicit and stale-safe. A draft records the schematic and PCB
hashes it started from; acceptance refuses it if either accepted design changed
in the meantime. Acceptance updates only the requested artifact and derived
connectivity record.

After inspecting the preview, explicitly accept its ID:

```powershell
uv run pcb-copilot accept projects/baro-bmp390 DRAFT_ID
```

Replace `DRAFT_ID` with the ID printed by `draft-schematic`. Acceptance checks
the original files, preview artifact hashes, and intent
versus KiCad netlist. It installs the root and child sheets, refreshes
`netmap.json`, marks schematic ownership human, and records the reviewed file
hashes. PCB bytes are unchanged. Changed child sheets invalidate review state.
Moving a flat local net into a child sheet can add a KiCad sheet-name prefix.
Comparison permits that only when the entire physical pin group is identical;
split nets, shorts, missing pins and unrelated renames still fail. Acceptance
retains KiCad's actual qualified names in `netmap.json`. It does not rename PCB
nets: reconcile those explicitly and rerun schematic/PCB parity before release.
Acceptance records outstanding evidence findings without treating them as
release approval.
Backups and a transaction record remain under `.pcb-copilot/acceptances/ID`.
Ordinary write failures roll back completed replacements. If the process is
interrupted, a remaining `accept.lock` means the transaction needs recovery
from that backup before retrying; do not simply delete the lock.

Use the existing gate runner and sign-off files for release review.
A checked box requires reviewer identity and date. Never bulk-check a review
form. The review is evidence that an activity happened, not proof that the
human conclusion was correct.

## 7. Release and fabricate

The unified release command is planned in Plan 5, not implemented yet. Its
required behavior is to run the complete check registry even after one check
fails, validate hash-bound sign-off, and generate fabrication output
transactionally. Output
must record accepted design hashes, Git revision, tool versions, reviewer,
review results, and hashes of all generated files.

For the compatibility pipeline, fabrication remains the last stage:

```text
env → research → sch → erc → pcb → route → gates → fab
```

Before ordering, independently inspect the Gerber viewer, drill set, BOM, CPL,
layer stack, copper weight, board thickness, finish, polarity, rotations, and
mechanical dimensions. Fabrication files are derived artifacts, never design
authority.

## 8. Declare deviations narrowly

Put each waiver under `## Declared` in `DEVIATIONS.md`:

```text
U1.5 | 2.2 | Pin 5 is a configuration input, not a supply pin.
```

The scope identifies one numbered rule or one evidence gate such as
`reference`, `basis`, or `datasheet`. A waiver never excuses unrelated checks.
Struck-out rows are withdrawn. `docs/deviations.py` remains the only parser
until it is moved intact behind the package API.

## 9. Diagnose the right question

```powershell
uv run python docs/selftest_enforcement.py
uv run python docs/run_gates.py projects/baro-bmp390/baro-bmp390.kicad_pcb
uv run python docs/audit_workflow.py
```

- The self-test asks whether enforcement is wired and can actually fail.
- The gate runner asks whether one board passes the implemented checks.
- The audit asks whether promised workflow controls are present across boards.

Do not substitute one answer for another. See [Architecture](ARCHITECTURE.md)
and [Limitations](LIMITATIONS.md).
