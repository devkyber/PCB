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

For current legacy behavior, these commands remain valid during migration:

```powershell
uv run python docs/pipeline.py projects/baro-bmp390 --check
uv run python docs/run_gates.py projects/baro-bmp390/baro-bmp390.kicad_pcb
uv run python docs/audit_workflow.py
```

## 2. Define the board before choosing parts

Write measurable requirements in the project’s `REQUIREMENTS.md`: purpose,
supply range, worst-case current, interfaces, outline, mounting, operating
environment, and success criteria. A heading without substantive content is
not a captured requirement.

Human-owned inputs stay explicit. Examples include TMS igniter resistance and
pulse current, GNSS antenna/stackup choice, IMU axis orientation and mounting
rigidity, and the barometer’s mechanical port/standoff arrangement. The
assistant must report these as open decisions rather than inventing numbers.

## 3. Collect evidence

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

The draft must include functional blocks, local drawn wires, graphical power
symbols, boundary labels, complete titles, explicit no-connects, evidence
references, ERC output, quality metrics, and a rendered PDF. Hierarchy is used
when a sheet would otherwise be crowded; TMS V3 is the required multi-sheet
proof case.

Review the rendered page, not only ERC. Confirm flow, grouping, symbol and pin
identity, values, power paths, labels, page boundaries, and readable spacing.
ERC proves only the rule set that it implements.

## 5. Draft placement and routing

Resolve and measure the real footprint before choosing coordinates. Place
fixed mechanical items first, then ICs/modules, decoupling, clocks, protection,
connectors, and remaining passives. Evaluate placement before blaming an
autorouter: moving a major module can improve completion more than extra route
passes.

The planned layout command writes a separate draft:

```powershell
uv run pcb-copilot draft-layout projects/baro-bmp390 --intent projects/baro-bmp390/layout-intent.yaml --route human
```

`human` is the default routing policy. `critical_only` and `candidate_all`
produce candidates, never automatically accepted boards. Inspect the board in
KiCad and 3D view. Check connector access, mounting, return paths, decoupling,
crystal/RF geometry, high-current paths, copper pours, silkscreen, assembly,
and mechanical fit.

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

Release runs the complete check registry even after one check fails, validates
hash-bound sign-off, and generates fabrication output transactionally. Output
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
