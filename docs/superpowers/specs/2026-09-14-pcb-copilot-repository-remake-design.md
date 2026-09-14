# PCB Copilot Repository Remake

**Status:** Approved in chat for implementation planning  
**Date:** 2026-09-14  
**Decision:** Remake the repository as an evidence-backed, human-controlled PCB design copilot.

## 1. Product definition

This repository exists to help a human engineer build PCBs faster. It is not
an autonomous PCB engineer and it does not claim that a machine-generated
board is safe, correct, or ready to fabricate.

The copilot should remove repetitive work:

- finding and archiving relevant datasheets and reference designs;
- checking exact part numbers, document revisions, pin maps, limits, and
  recommended application circuits;
- creating a useful schematic draft instead of starting from a blank sheet;
- finding real symbols, footprints, and 3D models;
- creating an initial placement, board constraints, zones, and routing plan;
- running repeatable electrical, geometric, provenance, and fabrication
  checks; and
- producing fabrication files from a human-approved design.

The human remains responsible for requirements, engineering judgment,
safety-critical decisions, visual review, physical fit, final placement and
routing judgment, sign-off, and fabrication release.

## 2. Non-goals

The remake will not attempt to:

- replace an experienced electrical engineer across arbitrary circuits;
- infer missing safety requirements and silently treat them as approved;
- guarantee circuit correctness from ERC, DRC, or heuristic checks;
- overwrite an accepted schematic or board during routine analysis;
- hide uncertainty behind a single overall `PASS` result;
- make a one-command path from a vague idea to fabrication the default; or
- preserve historical narrative when the useful lesson is already encoded in
  a maintained rule, test, or limitation.

## 3. Core operating model

The repository uses explicit, independently runnable stages:

1. Requirements
2. Evidence package
3. Schematic draft
4. Layout draft
5. Automated and human review
6. Fabrication release

Each stage produces a proposal, report, or draft. A human accepts or rejects
the result before the next stage becomes authoritative. The user may stop,
edit in KiCad, and resume at every boundary.

The lifecycle is:

```text
Requirements
     -> human approval
Evidence package
     -> human approval
Schematic draft
     -> edit and approve in KiCad
Placement/layout draft
     -> edit and route in KiCad
Automated + human review
     -> explicit release
Fabrication package
```

The lifecycle states are `DRAFT`, `HUMAN_REVIEWED`, and `RELEASED`.
Fabrication export requires `RELEASED`. A machine check may block release,
but it does not prevent work on an incomplete draft.

## 4. Sources of truth and ownership

Accepted `.kicad_sch` and `.kicad_pcb` files are the electrical and physical
sources of truth. Project-specific generator scripts are not permanent
sources of truth after a human edits a KiCad file.

Every design-changing operation follows these rules:

- Analysis is read-only.
- Generation writes a separate draft or patch.
- Acceptance is explicit and produces a Git-visible diff.
- A failed operation leaves accepted design files unchanged.
- Human-owned files are never regenerated implicitly.
- Connectivity metadata is extracted from the accepted schematic rather than
  reconstructed by parsing a generator's source code.
- Release state applies to a specific content hash of the accepted design.
  Any later design change returns the project to `DRAFT` or
  `HUMAN_REVIEWED`, as appropriate.

`netmap.json` remains versioned during migration because it is currently the
schematic-to-PCB connectivity contract. The target implementation generates
and validates it from the accepted schematic. It may later become an internal
serialized artifact only after equivalent reviewable diffs exist.

## 5. Target repository structure

```text
README.md
docs/
  WORKFLOW.md
  ARCHITECTURE.md
  DESIGN_RULES.md
  LIMITATIONS.md
  PROJECT_FORMAT.md
src/pcb_copilot/
  cli/
  project/
  evidence/
  schematic/
  layout/
  review/
  fabrication/
projects/
  template/
  BOARD_NAME/
    project.yaml
    REQUIREMENTS.md
    DESIGN_BASIS.md
    DEVIATIONS.md
    SIGNOFF.md
    evidence/
    design/
    review/
tests/
tools/
  kicad-claude-mcp/
```

`tools/kicad-claude-mcp` stays initially because current project generators
directly import its adapters and editing APIs. Its useful interfaces may be
wrapped behind `pcb_copilot` boundaries, but it will not be removed merely to
make the tree look cleaner.

The vendored `kicad-happy` and `kicad-jlcpcb` codebases are capability
references during migration. Their useful evidence, sourcing, review, and
library-fetch behavior will be evaluated before any file-level cleanup.
Whole repositories are not deleted under this design solely because their
runtime APIs are not currently imported.

## 6. Components and responsibilities

### 6.1 Project model

The project component loads `project.yaml` and resolves paths, accepted design
files, ownership, lifecycle state, board constraints, and enabled checks. It
provides one typed project representation to the other components.

The manifest records facts that tools need, not prose already maintained in
the engineering documents. It includes:

- project identity and KiCad filenames;
- input supplies and logic domains;
- mechanical outline and layer assumptions;
- evidence index location;
- accepted human-review state and content hash;
- enabled manufacturing profile; and
- safety classification flags that select additional review items.

### 6.2 Evidence assistant

The evidence component searches for, downloads, hashes, and indexes source
documents. One physical document can have several roles, such as datasheet,
integration manual, reference design, footprint drawing, and application
note.

Each evidence record includes:

- manufacturer and exact part number;
- document title, revision, and publication date when available;
- source URL and retrieval date;
- local path, content hash, and file type;
- applicable component references;
- evidence roles and trust tier;
- extraction status; and
- unresolved conflicts or missing information.

Extracted facts retain document and page citations. Conflicting revisions or
sources remain visible. The assistant never converts an unresolved conflict
into an approved design fact.

### 6.3 Schematic assistant

The schematic component creates an engineering draft from approved
requirements and evidence. It reuses the working KiCad adapters, verified
pin-coordinate logic, symbol placement helpers, ownership protection,
netlist extraction, and parity checks already present in the repository.

The target schematic style is:

- one functional block per visually distinct region;
- local wires for short, meaningful connections;
- named labels for block boundaries and genuinely shared nets;
- graphical power symbols for power rails;
- hierarchical sheets when a circuit exceeds the documented sheet capacity;
- readable signal flow and consistent orientation;
- explicit no-connect markers with documented reasons; and
- a complete title block and revision identity.

The present label-at-every-pin generator style is not an acceptable final
draft for a complex board. ERC-clean connectivity is necessary but does not
establish readability.

“Human-level schematic” has a deliberately limited definition here: a
readable engineering draft organized into functional blocks, with verified
parts, local wiring, meaningful labels, and manageable sheet density. It does
not mean universally correct circuit judgment or publication-quality visual
polish without human review.

### 6.4 Layout assistant

The layout component verifies real footprints and proposes:

- board outline and mechanical keepouts;
- placement by functional block and signal flow;
- measured courtyard-safe positions;
- net classes and critical-net constraints;
- power and ground zones;
- critical-route priorities; and
- routing guidance or optional candidate routes.

It preserves the current coordinate conversion helpers, footprint extent and
courtyard checks, routing experiments, stitching behavior, annular-ring
correction, and DRC integration where tests show they are sound.

Final placement and routing remain human-controlled. An autorouter result is
a candidate, never evidence of good placement, return-current quality,
thermal suitability, RF correctness, or safety.

### 6.5 Review engine

The review component separates findings into three categories:

- **Machine failure:** a deterministic check such as missing connectivity,
  stale evidence, DRC error, footprint mismatch, or out-of-board pad.
- **Engineering warning:** a heuristic or context-dependent risk such as
  thermal headroom, RF stackup, dense layout, or uncertain passive choice.
- **Human decision:** a physical, experiential, or safety judgment that the
  software cannot make.

An individual check reports its exact scope. The interface never presents an
aggregate `PASS` as proof that a design is electrically correct.

Sign-off is project-specific. A simple barometer should not inherit irrelevant
module-socket, high-current, and XT60 questions merely because another board
uses them.

### 6.6 Fabrication component

The fabrication component generates Gerbers, drill files, BOM, CPL, and a
release manifest from the accepted KiCad design. The release manifest records
design hashes, tool versions, check results, human sign-off, and manufacturing
profile.

The BOM is generated from the accepted design and evidence metadata. A
hand-maintained BOM that can silently disagree with the schematic is not an
authoritative artifact.

## 7. Command behavior

The target CLI exposes independent commands rather than a mandatory cascade:

```text
pcb-copilot status PROJECT_PATH
pcb-copilot research PROJECT_PATH
pcb-copilot draft-schematic PROJECT_PATH
pcb-copilot draft-layout PROJECT_PATH
pcb-copilot review PROJECT_PATH
pcb-copilot accept PROJECT_PATH DRAFT_PATH
pcb-copilot release PROJECT_PATH
```

`status` is read-only and recommends the next useful action. Drafting commands
write proposals. `accept` and `release` are the only normal commands that
change ownership or lifecycle state.

The exact CLI spelling may change during implementation planning if the
existing command structure offers a simpler compatible transition. The
behavioral boundaries above are fixed.

## 8. Failure handling

- Missing or inaccessible evidence produces an unresolved item, not a guess.
- Conflicting datasheet revisions are reported together.
- Unsupported KiCad syntax stops the operation and preserves the accepted
  design.
- Generated drafts are written transactionally through a temporary path and
  promoted only after successful validation.
- ERC and DRC failures block release but remain normal during drafting.
- Human-review items cannot be converted into machine passes.
- Generic waivers cannot suppress safety-critical unknowns.
- Every waiver names its exact rule and scope.
- KiCad discovery, subprocess behavior, file encoding, and paths are tested
  on Windows. Hard-coded macOS paths are removed.

## 9. Preservation-first migration contract

Every implementation job begins by reading the current implementation, its
callers, tests, generated artifacts, and relevant documentation.

For each migration slice:

1. Establish the current test and gate baseline.
2. Classify affected files as `KEEP`, `REFACTOR`, `MERGE`, `GENERATED`, or
   `DELETE`.
3. Identify unique behavior and engineering evidence.
4. Transfer useful behavior with regression coverage.
5. Compare the replacement against existing boards.
6. Delete the old file only after its useful behavior or current facts have a
   verified home.
7. Commit the slice separately so Git recovery remains straightforward.

No bulk deletion is based only on a filename, age, directory name, or lack of
current imports.

The project-specific `gen_*_sch.py` and `gen_*_pcb.py` files survive the
initial cleanup. They serve as behavioral references and regression fixtures.
Reusable logic is extracted before a superseded generator is deleted.

## 10. Documentation design and cleanup

The maintained documentation set is intentionally small:

- `README.md`: product purpose, installation, and first successful command.
- `docs/WORKFLOW.md`: the assisted stage-by-stage workflow.
- `docs/ARCHITECTURE.md`: components, ownership, and source-of-truth rules.
- `docs/DESIGN_RULES.md`: maintained electrical and layout rules.
- `docs/LIMITATIONS.md`: honest automation limits and required human work.
- `docs/PROJECT_FORMAT.md`: project manifest and directory contract.

Project documentation remains with its board:

- `REQUIREMENTS.md`
- `DESIGN_BASIS.md`
- `DEVIATIONS.md`
- `SIGNOFF.md`
- genuine project-specific PDR and safety analysis documents

The migration performs these merges and deletions:

- Merge `docs/QUICKSTART.md` and `docs/SETUP.md` into `README.md`, then delete
  the originals.
- Consolidate `docs/pcb-design-workflow.md` into `docs/WORKFLOW.md`.
- Rename and trim `docs/pcb-design-rules.md` into
  `docs/DESIGN_RULES.md`.
- Reduce `CLAUDE.md` to a short operating contract and move explanatory
  material into maintained documentation.
- Migrate current recurring lessons from `docs/archive/` into rules, tests,
  limitations, or project records, then delete the archive.
- Move `docs/tms-v3-pdr.md` into the TMS V3 project.
- Migrate still-valid facts from project `EVALUATION.md` files into
  requirements, design bases, deviations, or tests, then delete the
  evaluations.
- Replace the stale handwritten TMS V3 BOM with generated BOM output.
- Remove the four identical `build.sh` wrappers after one cross-platform CLI
  covers their behavior.
- Remove exact duplicate PDFs after the unified evidence index allows one
  file to carry several evidence roles.
- Stop tracking reproducible `STATUS.md` and `HUMAN_WORK.md` reports and
  generate them locally when requested.
- Reassess `PIPELINE.json` during the state-model migration. Its existing
  drift-detection behavior must move to the new project/review state before
  the tracked files are removed.
- Replace generic sign-off templates with project-relevant checks.

The cleanup explicitly preserves all current datasheets, reference designs,
accepted KiCad files, real symbols, footprints, 3D models, current
requirements, current design decisions, deviations, safety records, and
working validation logic unless a verified canonical replacement exists.

## 11. Verification strategy

### 11.1 Unit tests

Unit coverage includes:

- project manifest loading and validation;
- Windows and portable KiCad discovery;
- UTF-8 file handling;
- evidence identity, hashing, roles, and revision conflicts;
- pin-map extraction and citations;
- ownership and lifecycle transitions;
- transactional draft writes;
- waiver scope;
- schematic geometry and hierarchy checks;
- footprint and courtyard geometry; and
- release-state invalidation after design changes.

### 11.2 Regression fixtures

The four existing boards are regression fixtures:

- `baro-bmp390` exercises a human-owned small schematic.
- `imu-icm42688` exercises a compact generated sensor board and exact
  datasheet application values.
- `gnss-neom9n` exercises an integration manual, RF constraints, backup
  power, and several interfaces.
- `tms-v3` exercises hierarchy, module sockets, mixed-signal design, power,
  high-current connectors, and safety-critical human decisions.

Migration checks compare component references, pin/net membership, explicit
no-connects, footprints, board nets, and critical constraints. Cosmetic
format changes are allowed only when connectivity remains equivalent and the
rendered result improves.

### 11.3 Integration and visual checks

- Run the installed KiCad CLI for ERC, DRC, rendering, and fabrication
  exports.
- Open migrated projects in KiCad to catch parser-compatible but unusable
  output.
- Render schematics and inspect page density, overlap, text clipping, signal
  flow, junction use, and block separation.
- Verify that TMS V3 becomes a sensible multi-sheet schematic.
- Confirm that no accepted file changes during a failed or read-only command.

## 12. Migration sequence

1. Baseline and dependency inventory
2. Documentation truth and deletion of proven stale material
3. Cross-platform package, CLI, and project model
4. Unified evidence store
5. Schematic assistant and board-by-board migration
6. Layout assistant and board-by-board migration
7. Review and release model
8. Fabrication output
9. Final deletion of superseded implementations and generated artifacts
10. Full regression, KiCad-open, and documentation-consistency review

The repository must remain usable after every numbered phase.

## 13. Success criteria

The remake is successful when:

- a new board begins from a researched, cited, useful draft rather than a
  blank schematic;
- exact part numbers, pin maps, limits, and recommended values are
  re-checkable against archived evidence;
- every stage can be run, reviewed, edited, and resumed independently;
- accepted schematics and boards are never silently regenerated;
- the small reference boards produce readable single-sheet schematics;
- TMS V3 produces readable multi-sheet functional organization;
- existing board connectivity survives migration;
- Windows is a supported and tested environment;
- each maintained documentation question has one authoritative answer;
- project sign-off contains relevant human decisions rather than generic
  boilerplate;
- fabrication output identifies the exact reviewed design revision; and
- no deleted file contained unique current behavior or engineering evidence.

## 14. Known limitations after the remake

Even when every success criterion is met, the copilot cannot prove:

- that requirements are complete;
- that a selected topology is optimal or safe in every operating condition;
- that a datasheet or reference design is free from error;
- analog performance without suitable simulation and measurement;
- EMC, thermal, vibration, tolerance, and mechanical performance without
  domain-specific analysis and physical validation;
- connector orientation and module fit without comparison to real hardware;
- manufacturing yield; or
- that a visually readable schematic communicates intent as well as an
  experienced human's final editorial pass.

These are displayed as limitations or human-review requirements, never
silently converted into automated passes.

## 15. Future work

After the core remake is stable, future work may add:

- manufacturer/distributor API integrations with stock and lifecycle data;
- confidence-scored extraction from tables and application schematics;
- reusable topology templates with explicit applicability constraints;
- schematic visual-diff and review tooling;
- placement scoring using signal flow, return paths, thermal needs, and
  mechanical constraints;
- SPICE setup assistance for selected analog and power blocks;
- impedance calculations tied to an exact board-house stackup;
- enclosure and ECAD/MCAD clearance exchange;
- assembly drawing and bring-up test-plan generation; and
- measured-result feedback that links bench findings to the next revision.

These extensions remain proposals until the foundational ownership,
evidence, and review model is reliable.
