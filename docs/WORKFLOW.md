# Working with a board

## Start a new board

For TMS, start with [the restart basis](../design-bases/tms/README.md); never
copy its retired test CAD. Copy templates/project into a new project folder,
set manifest names/paths, fill requirements and project review items, and
archive exact datasheets/reference circuits before drawing. Do not inherit
old netmaps, placement recipes, waivers or sign-offs.

Create fresh native KiCad files and local library tables in that folder.
The dated templates/jlcpcb-2layer-1oz files can seed native geometry/rules.
Ordinary KiCad capture and forward annotation establish the first circuit.
Optional intent previews can help. Complete routed CAD is required for checked
application and release; a missing-CAD or placement-only project cannot pass.

## Saved CAD and assisted edits

The root `.kicad_sch` hierarchy and `.kicad_pcb` are the current design, including
owner edits. The pipeline reads saved files; it cannot read unsaved changes in
an open KiCad editor. Save and close the editors before applying external edits,
then reopen the project. Read-only review and explanation do not rewrite CAD.

For a scoped change, copy the current saved design and edit that native copy.
Preserve unrelated objects, UUIDs, placement and routing. Use
`update-schematic --candidate` for native sheets or `update-layout --candidate`
for a native PCB. An intent-driven command generates a new candidate from YAML;
it is not a merge of manual drawing or routing edits. Reserve it for a new design
or an explicitly requested redraw. Old authoring scripts and exported PDF/SVG
images are never the starting point for edits to an existing board.

Every update needs a successful preview without `--apply`, followed by the same
command with `--apply`. Apply is bound to the preview's exact saved project,
candidate/intent files, companion settings and options. A later edit invalidates
the preview; rerun it on the current saved design. This detects stale inputs,
not whether a requested circuit change is a good engineering decision. During
application, input hashes are rechecked and originals retained for rollback.

Open the root schematic and PCB under `projects/BOARD/`.
Read its requirements, design basis, reference review, deviations and review profile.

## 1. Check the current state and sources

Replace `PROJECT` with the selected project folder, such as `projects/rover-pdb`.
Part examples below use Rover's exact converter identity; choose the actual
part for the board being worked on.

```powershell
uv sync
uv run pcb-copilot status PROJECT
uv run pcb-copilot research PROJECT --verify
uv run pcb-copilot research PROJECT --verify-schematic-parts
uv run pcb-copilot research PROJECT --search-plan LMR51450
uv run pcb-copilot research PROJECT --extract LMR51450
```

Archive documents with `research PROJECT --add PART URL --role ROLE` before citing
them. Reference schematic/PCB pairs can be compared with `--inspect-reference
SCHEMATIC_ID PCB_ID`. Search plans propose queries, not live search results.
The datasheet outranks a reference circuit. Record adopted choices and disagreements
in `DESIGN_BASIS.md`. Hash verification proves archive identity, not suitability.

`--verify-schematic-parts` reads the complete saved native hierarchy, including
unplaced parts and purchased passives. It requires evidence for the selected
MPN; an old datasheet attached to the same reference is insufficient. Fabricated
test pads and mounting features are counted but do not need purchased-part
datasheets. The normal datasheet review also checks native schematic components
when the PCB is empty; its existing passive exemption policy remains in place.
Neither coverage check verifies the document's pin interpretation, value choice,
circuit operation or physical fit. Record those checks separately.

For hand-authored local footprints derived from manufacturer drawings, use the
explicit library description `Manufacturer drawing-derived footprints; see
libs/footprint-provenance.yaml`. Each footprint requires one version-1 receipt
in that manifest with its project-relative path, exact SHA256, selected part
numbers, manufacturer evidence IDs, complete numbered-pad function map, author,
review date, derivation locations, limitations and `owner_signoff: false`.
The resolver verifies footprint/source hashes, part identity and pad coverage.
Changed CAD or evidence invalidates the receipt. This records source lineage;
physical fit and mandatory human acceptance remain separate. Never label a
hand-authored footprint as an LCSC import to satisfy provenance.

For project-local copies of official KiCad footprints, the strict receipt path
is triggered by the library description
`Official KiCad footprint copies; see libs/PROVENANCE.json`. The version-1
`libs/PROVENANCE.json` receipt must pin distinct archived upstream and local
files, official footprint identity/URL, selected native MPN, complete numbered
pad functions and exact-part manufacturer evidence. Local footprint bytes may
differ only by declared model-URI substitutions; every model needs separate,
hash-matching upstream/local bytes and a contained project-local URI. The narrow
fabricated-only exception covers unnumbered NPTH mounting features. See the
[GPIO example receipt](../examples/gpio-indicator/libs/PROVENANCE.json) and
[library notes](../examples/gpio-indicator/libs/README.md). This verifies local
footprint lineage and pad coverage, not upstream-download authenticity, symbol
provenance, datasheet interpretation or physical fit. `physical_fit_qualified`
must remain `false`; the human review gates still apply.

### LCSC parts and library import

```powershell
uv run pcb-copilot parts PROJECT --lookup C6890985
uv run pcb-copilot parts PROJECT --import C6890985 --mpn LMR51450SDRRR
```

Lookup fetches the exact supplier record for a C-number. Import requires a
matching manufacturer part number, converts the real symbol/footprint/models,
normalizes the footprint with native KiCad, and registers a separate `lcsc_C...`
project library. Existing imported libraries are preserved. Failed downloads or
conversion leave the project unchanged; no placeholder geometry is substituted.
Supplier JSON is archived as `cad_library` evidence with `supplier` provenance.
It does not satisfy a datasheet or reference-design requirement.

Use the returned `symbol` and `footprint` IDs in schematic intent; the optional
component `lcsc: C6890985` field verifies/preserves sourcing identity. Imported
library sourcing properties survive schematic generation. Update the PCB from
the schematic in KiCad and supply it with `--pcb`; BOM export reads its LCSC field.
Review blocks release if a selected schematic C-number differs from the PCB.
Archive the exact manufacturer datasheet using `research --add ... --role datasheet`,
then verify package dimensions and pin functions. `--lookup` is a C-number lookup,
not a live stock/price quote or a keyword catalog search.

## 2. Update the schematic

Read the current root schematic and all child sheets before editing. Preserve
owner edits; an older intent or generator must never overwrite newer CAD. A
request for PCB layout alone does not authorize schematic changes. If the owner
requests a second schematic for comparison, create a separate editable copy
from the current CAD and leave the original unchanged.

```powershell
uv run pcb-copilot update-schematic PROJECT --candidate /path/to/candidate/BOARD.kicad_sch
uv run pcb-copilot update-schematic PROJECT --intent PROJECT/schematic-intent.yaml
```

Prefer `--candidate` for owner-edited sheets. Supply the root sheet with the same
filename and its complete hierarchy in a separate working copy. Native sheet
bytes are preserved; the connectivity snapshot is derived from those sheets.
The historical YAML intent is not replayed or rewritten. A paired `--pcb` can
provide matching routed CAD for a circuit change. Inspect every preview sheet
before repeating the command with `--apply`.

Inspect every rendered sheet against
[Schematic readability](DESIGN_RULES.md#schematic-readability), plus native ERC
and findings at the returned paths. Apply the adopted Gala/Gross conventions:
functional symbol geometry, readable flow, clear junctions, voltage/load
assumptions and local calculation notes. Judge the actual drawing, not just a
checklist or its resemblance to a screenshot. Local support parts, test points, power flags,
and sheet ports should be incorporated into their circuits. A PDF file existing
is not evidence that its pages have been inspected. For drawing-only changes,
compare native exported pin-to-net membership, component properties, footprint
assignments, and intentional no-connects before and after; stop if the circuit
changes unexpectedly. After the final edits, rerun ERC and render the changed
sheets again. Record the reviewed sheet list and remaining issues in the project
review notes; do not record author visual review as owner sign-off.

Add `--apply` to
install a checked candidate. The command preserves the root design on failure,
updates hierarchical sheets and netmap together, and returns the lifecycle to
`DRAFT`. It requires exact PCB connectivity. `--reconcile-board-names` handles
hierarchy-qualified net renames only when pad membership and native rules agree.
For a circuit change, supply its matching, routed PCB with the new intent:

```powershell
uv run pcb-copilot update-schematic PROJECT --intent /path/to/new-intent.yaml --pcb /path/to/new-board.kicad_pcb --apply
```

This checks the PCB against the generated schematic, refills zones, runs DRC and
installs schematic, intent, netmap and PCB together. Preview first by omitting
`--apply`. This path replaces the old circuit intentionally; the old layout intent
is not used to constrain a different circuit. Update that intent before future
placement generation. Manual KiCad edits remain possible; reconcile intent and
netmap afterward.

Both schematic update paths also verify PCB schematic UUID links. When complete
part and pin-net parity proves an unlinked legacy board matches, preview reports
the missing IDs and apply installs only that PCB metadata with the schematic.
Already linked boards keep their PCB bytes during drawing-only native updates.
A conflicting existing link blocks; an intentional redraw that changes symbol
identities needs an explicitly reconciled native schematic/PCB candidate.

## 3. Update the layout

```powershell
uv run pcb-copilot update-layout PROJECT --intent PROJECT/layout-intent.yaml
uv run pcb-copilot update-layout PROJECT --candidate /path/to/candidate/BOARD.kicad_pcb
```

An intent produces placement/routing candidates. Default `human` routing does not
invoke an autorouter; incomplete candidates are previewable but blocked from apply.
`--route candidate_all` requests the optional Freerouting backend, which requires
Java and a configured `FREEROUTING_JAR`. Unsupported critical-only routing remains
blocked rather than silently routing other nets.

`--candidate` checks a board edited and routed in KiCad, using companion project
settings/custom rules when supplied. Both paths fill zones, check physical parts
and connectivity, verify schematic UUID links, run fresh DRC twice, compare
copper/footprints/pours and render preview artifacts. After complete part and
pin-net parity, absent schematic links are filled on the staged candidate with
the native netlist's sheet/symbol UUID paths. Copper, footprint UUIDs and
positions are preserved. Conflicting nonempty links block the update; the
pipeline does not silently re-link them by reference.

KiCad's F8 placeholder net for an explicitly unconnected pin is equivalent to
an empty PCB net only when the native schematic supplies the exact name and
pin and the PCB net contains that pin alone. Extra members still fail parity.

`routing-topology.json` identifies fully covered straight-track segments, very
short segments and off-centre pad contacts by UUID, net, layer and coordinates.
These findings are advisory: a pad edge contact can be electrically valid and
some short escapes are intentional. Inspect the local route and use KiCad's
interactive router for any authorized repair. Native DRC remains the gate for
unconnected copper; topology advice does not certify current capacity.

Review those artifacts, then use `--apply`. A candidate with
unconnected items, missing parts or lost routing cannot replace the current board.
Applying is a working-design update and invalidates prior release state.

## 4. Review and record human decisions

```powershell
uv run pcb-copilot review PROJECT
uv run pcb-copilot review PROJECT --format json
uv run pcb-copilot prepare-signoff PROJECT
uv run pcb-copilot views PROJECT
```

Review runs fourteen checks against a disposable copy: research, datasheets, ERC,
netmap freshness, physical/net parity, placement, geometric house rules, DRC,
schematic quality, routing/editability settings, routing topology, independent JLCPCB geometry,
assembly contracts and sign-off.
Routing topology, defaults and locked-copper findings are advisory; they do not
certify ampacity or enforce a uniform minimum on mixed power/sense branches.
Each result names its scope. A failed check does not hide later results.
Optional `--output` creates a new JSON/Markdown report
under `.pcb-copilot/reports/` without overwriting earlier reports.

For a portable visual handover, `pcb-copilot report PROJECT --output NEW_DIRECTORY`
runs current review and captures native schematic/assembly/copper views on
isolated copies. The self-contained `index.html` keeps findings, check scopes
and source hashes together. `verify-report DIRECTORY --project PROJECT`
checks both packet integrity and whether the current saved inputs still match.
See [the handover guide](HANDOVER.md). Viewing a packet records no approval.

`prepare-signoff` creates an unsigned `review-signoff.yaml` only when absent.
The shared policy always adds `shared.schematic-readability` and
`shared.layout-handover` to the local profile. These require actual inspection
of every sheet and current layout views; record the reviewed sheets and
remaining issues in the decision note or referenced review record. Local YAML
cannot omit or override them.

The views command freshly exports assembly/front/back SVGs with exact source
and output hashes under output/review. Bottom is mirrored for underside
inspection. It preserves native CAD and restores old outputs after failure.
Inspect the schematic preview PDF and current PCB views; old PDFs are dated
snapshots.

The responsible human completes each profile item with a reviewer, ISO date,
`accepted`/`rejected` decision and note after actual inspection or measurement.
Hashes bind decisions to the current inputs and the shared policy. A policy
change also invalidates old decisions. If inputs change, preserve the old
record in Git, remove the stale worksheet and prepare a new one; do not merely
refresh hashes under an old signature.

## 5. Release

For a JLCPCB quotation/placement review before final sign-off, run
`uv run pcb-copilot release PROJECT --preview --quantity 5`. Replace 5 with the
number of boards to assemble; the default is one. It prepares `output/jlcpcb-preview/`
with a Gerber-and-drill ZIP, grouped BOM, matching CPL and current review findings.
It does not grant release or replace `fabrication/`; a blocked review returns exit
code 1 even when the preview package was prepared. `jlcpcb-assembly.yaml`
records explicit manual-fit exclusions, geometry-bound centroid corrections,
exact-part rotation rules, model contracts and a separate supplier placement
review. Missing rotation coverage/models or missing/stale supplier review blocks
release. The file is included in source and sign-off fingerprints. See
[the assembly workflow](JLCPCB_ASSEMBLY.md) for editing and review instructions.

Publication directories, their ancestors and the operation workspace must be
ordinary contained paths. Symlinks and Windows junctions are rejected so a
preview or release cannot redirect replacement into an unrelated owner folder.
Source hashes are checked before returning a blocked result as well as before
publication. A concurrent source edit requires rerunning on the saved design.

Review independently runs the dated JLCPCB two-layer / 1 oz / green-mask geometry
baseline on a disposable copy. It cannot be weakened by project exclusions or
ignored manufacturing errors. The normal project DRC also runs. Release includes
`jlcpcb-dfm.json` plus fresh `stock.csv`, `stock.json` and hashed supplier responses.
Stock checks exact C-number/MPN identity and BOM quantity times board count. Unknown
or insufficient stock blocks release. This is LCSC retail stock, not JLCPCB assembly
allocation; extra assembly attrition, eligibility, preorder and rotations need
confirmation in the actual order. Nothing is reserved. The supplier profile is
dated and must be reviewed when process choices or capabilities change.

```powershell
uv run pcb-copilot release PROJECT
```

Release reruns the complete review, including current human decisions. A blocked
review produces findings and no new fabrication package. Success publishes
`fabrication/` containing Gerbers, Excellon drills, BOM, native positions, JLCPCB
CPL, review, source files and `SOURCE.json`. Native exports must succeed and
produce required outputs; failed publication restores the previous package.

Sources and outputs are hashed. `status` stops reporting `RELEASED` if inputs or
package contents change. Generated Gerber timestamps can vary between runs.
Check assembler orientation and unsourced/manual-fit components in the assembly
preview. This command prepares files; it does not place an order.

Keep `netmap.json`, intent and current CAD in Git. Ignore `.pcb-copilot/` and
`fabrication/`. Neither generated output nor a green machine check replaces the
engineering work in [Limitations](LIMITATIONS.md).

## Interrupted updates

Updates and releases keep recovery originals until publication succeeds. Ctrl+C
and ordinary failures restore the prior files. If restoration itself fails, the
error identifies `.pcb-copilot/recovery-*/`; an operation lock remains to prevent
another update. Inspect its journal and restore the named originals before
removing the recovery directory and `operation.lock`. A release recovery also
retains the previous fabrication package and state. If a process is forcibly
terminated before any recovery journal exists, confirm no pipeline process is
running before removing its stale lock. Keep a copy of recovery data until the
restored design has been checked.

## Keep the workspace understandable

The project README is the entry point. Keep current CAD and declared inputs at
the project root, detailed calculations under `docs/design/`, retained review
conclusions and measured reports under `docs/review/`, and human-facing exports
under `output/`. Store exact cited sources in `evidence/`, never scratch folders.
The Rover project demonstrates this structure; small projects need not create
empty subdirectories or duplicate its board-specific notes.

```powershell
uv run pcb-copilot clean projects/rover-pdb
uv run pcb-copilot clean projects/rover-pdb --apply
```

The first command lists the exact files and sizes. The second rescans and removes
only known reproducible previews, invalidating their apply authorizations. Unknown
files, current CAD, source archives, drafts, acceptance originals, recovery and
fabrication packages are retained. Active operations and unresolved recovery
block it. Save a useful final review report outside scratch before cleaning.

One-time historical cleanup needs a dependency/reference audit and a verified
external backup for untracked or owner-edited material. Extract useful assertions
and engineering lessons before removing old authoring scripts. Do not delete
code solely because Rover did not use it: shared intent generation and optional
routing still serve other projects. See [Architecture](ARCHITECTURE.md) for the
L0–L4 map, command internals and the completed Rover cleanup's recovery location.
