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

## 4. Existing implementation baseline

This is a migration of a working prototype, not a greenfield rewrite. The
current repository has three valuable layers:

1. `tools/kicad-claude-mcp` provides tested KiCad editing, hierarchy, routing,
   validation, manufacturing, BOM, and project APIs.
2. `docs/*.py` provides workspace-specific evidence, orchestration, ownership,
   review, routing post-processing, and fabrication behavior.
3. The four boards and their engineering records are case studies containing
   real failures, corrections, and expected outputs.

The remake treats these as architectural inputs. New package boundaries will
first wrap or import working code. Logic moves only after characterization
tests establish its current behavior; replacing a useful implementation with
an unproven abstraction is not progress.

### 4.1 Capability reuse map

| Existing capability | Current implementation | Treatment in the remake |
|---|---|---|
| Fixed stage order and fabrication interlock | `scripts/pipeline.py` | Keep the release-time enforcement. Split drafting into independent commands, but make `release` run every prerequisite check so a user cannot forget one. |
| Research is advisory while designing and blocking at release | `pipeline.ADVISORY`, `check_research.py`, `run_gates.py` | Keep. This supports iteration without converting missing evidence into approval. |
| Separate machinery, board, and workflow questions | `selftest_enforcement.py`, `run_gates.py`, `audit_workflow.py` | Keep these as distinct layers. The audit must continue calling the real gates rather than reimplementing them. |
| Enforcement wiring plus strength testing | Synthetic hook events and fault injection in `selftest_enforcement.py` | Keep and expand. Every new blocking check needs a fault that proves it can fail, not only a registration test. |
| Verified evidence acquisition | `collect_references.py` URL verification, content sniffing, local archive, and provenance rows | Keep the behavior; replace separate folder indexes with one structured multi-role evidence index. |
| Exact source extraction | `fetch_reference_doc.py` Eagle parsing, raw download, PDF rendering, and page selection | Keep and expose through the evidence assistant. Add structured fact records rather than replacing the extraction path. |
| Datasheet content validation | `check_datasheets.py` and research archive integrity checks reject HTML renamed as PDF | Keep and generalize to every evidence type. File extension alone never establishes evidence. |
| Evidence priority and explicit disagreement | Datasheet/reference hierarchy and `DESIGN_BASIS.md` rows | Keep. Add the documented module exception: an integration manual may be the wiring authority while the datasheet remains the electrical-limit authority. |
| Narrow, reviewable exceptions | `deviations.py` as the single parser; exact `## Declared` containment; ref and scope matching; struck-out rows disabled | Keep as one shared implementation. Do not create another waiver parser in the new package. |
| Human-edit protection | `SCHEMATIC_OWNER`, canonicalized schematic hashes, drift tripwire, and `--regenerate` refusal | Keep and generalize from schematic ownership to accepted schematic and PCB revisions. |
| One connectivity handoff | `extract_netmap.py` and versioned `netmap.json` | Keep during migration. The extractor already reproduced 283 declared pin assignments across all four boards with zero differences. |
| Electrical parity beyond DRC | `check_netlist_parity.py` compares net sets and per-net pin membership through KiCad | Keep. It catches electrically absent pads that have no ratsnest and are therefore invisible to DRC. |
| Schematic geometry protection | `LabelPlacer`, `SymbolPlacer`, grid conversion, crossing detection, title-block helpers, and sheet-density checks | Keep and extend. Use the existing collision/grid work while adding functional blocks, local wires, and actual hierarchy. |
| Real-footprint placement geometry | `PlacementTracker`, union of courtyard and pad extents, coordinate conversion helpers, anchor handling, and near-pin placement | Keep as the basis of layout proposals. Preserve its fail-fast errors and measured-coordinate approach. |
| Route completion pipeline | Shared DSN export, Freerouting, SES import, zone fill, ground bonding, DRC, `route_best_of.py`, `stitch_vias.py`, and `fix_via_annular.py` | Keep as an optional candidate-routing backend. Preserve version-specific behavior and post-route verification; do not promote it to final-layout authority. |
| Pad-local routing keepouts | `dsn_keepouts.py` injection and pad-specific clearance handling in ground bonding | Keep. A board-wide clearance cannot replace footprint-local rules. Document Freerouting's remaining via limitation. |
| Honest check scope | `check_design_rules.py` states that it covers 4 of 42 numbered rule sections | Keep this transparency. Every new check publishes what it proves and what remains human review. |
| Physical and semantic PCB validation | `validate_pcb.py` checks placeholders, dimensions, routing presence, edges, pads, courtyards, symbol presence, module sockets, and connector class | Keep, split into testable checks, and retain exact failure details. |
| Human work aggregation | Dated `SIGNOFF.md` enforcement and `human_work.py` aggregation | Keep the mechanism, replace generic checklists with project-relevant questions, and generate the aggregate report on demand. |
| Fabrication correctness and provenance | `export_fab.py` reads LCSC data from the PCB, re-origins CPL coordinates to the board, and stamps design/check provenance | Keep. Generate only from an explicitly released design. |
| Contextual feedback | `.claude/rules/` plus session-start, post-edit, and stop hooks | Keep the intent. Replace Bash/macOS assumptions with portable optional integrations and retain synthetic-event verification. |

### 4.2 Board-derived engineering assets

The current board records demonstrate an effective evidence-to-decision loop
that the new workflow must preserve:

- `baro-bmp390` caught missing board-level bulk decoupling and corrected a
  reference-design conclusion by returning to the manufacturer specification.
- `imu-icm42688` recovered the missing 2.2 uF capacitor, corrected the VDDIO
  capacitor to 10 nF, and grounded pins that the datasheet did not permit to
  float.
- `gnss-neom9n` showed that a module integration manual can contain mandatory
  wiring absent from the datasheet: grounded V_USB, 1 uF at VCC, and RF-input
  ESD protection.
- `tms-v3` caught invented module pin maps, an unverified crystal-load choice,
  missing DVDD decoupling, connector-class mismatches, route post-processing
  defects, and unresolved ignition-current and thermal questions.

These are not historical decoration. Current facts remain in each project's
requirements, design basis, deviations, evidence, and safety records. General
failure patterns become checks or maintained limitations; only duplicated or
superseded narrative is deleted.

### 4.3 Recurring defect classes remain design constraints

The categories already named in `docs/ARCHITECTURE.md` remain mandatory review
questions during the remake:

- Can the check actually fail under fault injection?
- Does a fresh template accidentally satisfy its own check?
- Is a useful tool invoked by a real path rather than mentioned only in prose?
- Is an exception wider than the exact condition it waives?
- Are two parsers or two build paths interpreting the same source differently?
- Did a fix reach every generated and accepted artifact?
- Is a gate reading output from the current run rather than stale state?
- Is the result deterministic, or does it report repeated measurements and the
  worse outcome?

These constraints apply to the new CLI and package just as they apply to the
existing scripts.

## 5. Sources of truth and ownership

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

## 6. Target repository structure

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

This is the target shape, not a big-bang directory move. During migration,
the existing `docs/*.py` commands remain callable. When a capability moves,
the old path first becomes a compatibility entry point that calls the new
implementation. Hooks, board scripts, tests, and documentation are updated
before that entry point is deleted.

`tools/kicad-claude-mcp` stays initially because current project generators
directly import its adapters and editing APIs. Its useful interfaces may be
wrapped behind `pcb_copilot` boundaries, but it will not be removed merely to
make the tree look cleaner.

The vendored `kicad-happy` and `kicad-jlcpcb` codebases are capability
references during migration. Their useful evidence, sourcing, review, and
library-fetch behavior will be evaluated before any file-level cleanup.
Whole repositories are not deleted under this design solely because their
runtime APIs are not currently imported.

## 7. Components and responsibilities

### 7.1 Project model

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

### 7.2 Evidence assistant

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

### 7.3 Schematic assistant

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

The target is a useful supplementary engineering draft: functional blocks,
traceable part evidence, local wiring, meaningful labels, and manageable
sheet density that help the engineer build faster. The engineer supplies
circuit judgment and reviews and edits the result. Human-level autonomy is
not a goal or an acceptance criterion.

### 7.4 Layout assistant

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

### 7.5 Review engine

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

### 7.6 Fabrication component

The fabrication component generates Gerbers, drill files, BOM, CPL, and a
release manifest from the accepted KiCad design. The release manifest records
design hashes, tool versions, check results, human sign-off, and manufacturing
profile.

The BOM is generated from the accepted design and evidence metadata. A
hand-maintained BOM that can silently disagree with the schematic is not an
authoritative artifact.

## 8. Command behavior

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

Independent drafting does not remove the current pipeline's strongest safety
property. `release` is a strict orchestrator: it refreshes evidence status,
derives and checks the netmap, runs ERC, schematic-quality, placement,
design-rule, parity, DRC, and dated human-sign-off checks, and only then calls
fabrication export. It always emits the complete review report even when an
early prerequisite fails, while preventing later mutating stages from running.
This preserves the useful parts of fixed stage order without forcing a full
regeneration during ordinary design work.

The exact CLI spelling may change during implementation planning if the
existing command structure offers a simpler compatible transition. The
behavioral boundaries above are fixed.

## 9. Failure handling

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

## 10. Preservation-first migration contract

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

## 11. Documentation design and cleanup

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

## 12. Verification strategy

### 12.1 Unit tests

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

### 12.2 Regression fixtures

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

### 12.3 Integration and visual checks

- Run the installed KiCad CLI for ERC, DRC, rendering, and fabrication
  exports.
- Open migrated projects in KiCad to catch parser-compatible but unusable
  output.
- Render schematics and inspect page density, overlap, text clipping, signal
  flow, junction use, and block separation.
- Verify that TMS V3 becomes a sensible multi-sheet schematic.
- Confirm that no accepted file changes during a failed or read-only command.

## 13. Migration sequence

1. Complete capability and dependency inventory across workspace docs,
   scripts, tool APIs, hooks, tests, and all four boards
2. Characterization tests for every capability classified `KEEP` or
   `REFACTOR`, including fault injection for blocking checks
3. Documentation truth and deletion of only proven stale narrative
4. Cross-platform package, compatibility entry points, CLI, and project model
5. Unified evidence store built on the existing collection and extraction
   behavior
6. Schematic assistant built on the existing KiCad and schematic-layout
   helpers, followed by board-by-board migration
7. Layout assistant built on the existing placement and route pipeline,
   followed by board-by-board migration
8. Review and release model built on the existing gates, audit, self-test,
   sign-off, and fabrication interlock
9. Fabrication output built on the existing BOM, CPL, Gerber, and provenance
   behavior
10. Final deletion of superseded implementations, generated artifacts,
    duplicate evidence, and obsolete documentation
11. Full regression, KiCad-open, fault-injection, and
    documentation-consistency review

The repository must remain usable after every numbered phase.

## 14. Success criteria

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

## 15. Known limitations after the remake

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

## 16. Future work

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
