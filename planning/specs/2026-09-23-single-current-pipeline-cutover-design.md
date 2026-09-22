# Single Current Pipeline Cutover Design

**Date:** 2026-09-23  
**Status:** Draft for written review  
**On approval, supersedes:** The draft/accept lifecycle and compatibility-retention decisions in `2026-09-14-pcb-copilot-repository-remake-design.md`

## 1. Purpose

PCB Copilot is a human-controlled engineering assistant. Its job is to shorten the slow, repetitive parts of board development: finding and preserving source evidence, checking part numbers and constraints, preparing a readable schematic, helping with placement and routing, and producing review and release evidence.

It is not intended to replace an engineer, claim human-level judgment, or silently release hardware. The engineer remains responsible for architecture, unresolved electrical decisions, safety decisions, exceptions, and final sign-off.

The repository will expose one current pipeline and one current design for each board. The root KiCad project files are the live design. Persistent parallel draft and accepted trees are removed. Git is the history and rollback mechanism.

## 2. Problems Being Corrected

The repository currently contains useful work, but it presents several overlapping models at once:

- root KiCad files that still show the older design;
- newer schematic and layout candidates under `.pcb-copilot`;
- legacy generators, shell wrappers, status files, and pipeline manifests;
- a new Python package and CLI that do not yet replace every legacy capability;
- old plans and migration material that describe earlier repository states;
- multiple helper tool trees whose relationship to the product is unclear.

This makes real progress difficult to see and encourages accidental use of an obsolete path. Simply copying the latest candidates over the root files is not acceptable: the four current PCB candidates are unrouted, and replacing the routed boards now would discard 968 existing tracks and vias in total.

## 3. Product Principles

The cutover follows these rules:

1. **Human control is mandatory.** The pipeline proposes, checks, records, and applies requested changes. It does not make unreviewed engineering decisions.
2. **There is one public command surface.** `pcb-copilot` is the only supported entry point.
3. **There is one visible design state.** A board's root KiCad files are its current working design.
4. **No regression is called progress.** A readable but electrically incomplete schematic, or a placed but unrouted PCB, cannot replace a more complete current file merely because it is newer.
5. **Evidence is preserved.** Datasheets, reference designs, citations, provenance, and protected source hashes survive the cleanup.
6. **Changes are transactional.** Failed generation or validation leaves the current KiCad files unchanged.
7. **Git stores history.** Generated draft archives, status mirrors, and hand-maintained history folders are not retained in the final repository.
8. **Documentation describes the current product.** Historical plans remain available in Git, not in the final working tree.

## 4. Canonical User Workflow

The final command surface is:

```text
pcb-copilot status PROJECT
pcb-copilot research PROJECT [research options]
pcb-copilot update-schematic PROJECT --intent FILE [--apply]
pcb-copilot update-layout PROJECT --intent FILE [--apply]
pcb-copilot review PROJECT
pcb-copilot release PROJECT
```

`update-schematic` and `update-layout` build and validate a temporary transaction. Without `--apply`, they render a preview and report findings without changing the current design. With `--apply`, they replace the current files only after the machine-enforceable gates pass. Temporary transaction output is removed after apply or rejection and is ignored by Git.

The old public commands are removed after their capabilities are covered:

- `draft-schematic`
- `draft-layout`
- `approve-layout-preview`
- `review-draft`
- `accept`

The change is intentional: review is a continuing property of the current design, not a second persistent design tree. Applying a design change invalidates prior sign-off and release evidence until review runs again.

## 5. Canonical Project State

Each board has one `project.yaml` and one set of current KiCad files. The project manifest identifies:

- current project, schematic, PCB, and hierarchical sheet files;
- intent files used to recreate or update them;
- evidence roots and protected-source hashes;
- current review state;
- human decisions, deviations, and sign-off state;
- release outputs, which are generated rather than hand maintained.

The repository does not check in `.pcb-copilot/drafts`, accepted copies, copied previews, or generated status mirrors. `.pcb-copilot` may exist locally as an ignored transaction cache, but it is never the location the user must open to see the latest design.

## 6. Transaction and Failure Model

Every mutating operation follows the same sequence:

1. Load the manifest, intent, evidence, and current KiCad design.
2. Create a transaction in a board-local ignored temporary directory.
3. Generate or modify copies, never the root files directly.
4. Run structural, connectivity, evidence, and KiCad checks.
5. Render review artifacts and compare the candidate with the current design.
6. If `--apply` is absent, report the result and remove the transaction.
7. If `--apply` is present and all required gates pass, atomically replace the affected current files.
8. Invalidate stale sign-off and release metadata.
9. Remove the transaction.

If generation, parsing, KiCad validation, replacement, or cleanup fails, the command restores the pre-operation files and exits with an actionable error. A partially updated hierarchy is never considered current.

## 7. Schematic Cutover

The newer schematic work is promoted only after it is completed and corrected. Per board, the implementation must:

- reconcile symbols, references, footprints, values, pins, and net names with the intent and current PCB;
- verify source-backed constraints and part numbers;
- resolve unconnected or ambiguous connectivity rather than hiding it graphically;
- produce a readable page layout with deliberate grouping, junctions, labels, and hierarchy;
- run KiCad parsing and ERC, recording any approved exceptions;
- verify connectivity parity with the project netmap and PCB expectations;
- render the full schematic for human visual review;
- replace the root schematic and all affected child sheets as one transaction.

The TMS570 design additionally requires hierarchy-qualified net reconciliation. A matching local label name on two different sheets must not be treated as proof that the hierarchical design is connected correctly.

The four root schematics must visibly change from the September 6 versions before schematic cutover is considered complete.

## 8. PCB Cutover

The current routed boards remain canonical until the new path can produce a board that is at least as complete and electrically consistent. The implementation order is:

1. BMP280
2. ICM-42688-P
3. NEO-M8N
4. TMS570LC4357

For BMP280 and ICM-42688-P, retain the useful new placement work, reconcile it with the promoted schematic, then route and validate it before replacing the root PCB.

For NEO-M8N and TMS570LC4357, resolve the recorded placement blockers first, then perform placement, routing, zone fill, and review. Zero-movement candidates are not promoted as layout improvements.

PCB apply gates include:

- exact schematic-to-PCB component and net reconciliation;
- complete required footprint placement with no unexplained collisions;
- routing completeness appropriate to the board and no accidental loss of existing connectivity;
- filled zones and reviewed stack-up, rules, widths, clearances, and via choices;
- KiCad DRC results with explicit, source-backed exceptions;
- rendered front, back, and relevant 3D views;
- comparison with the previous board, including footprints, tracks, vias, zones, and unrouted items;
- human approval of RF, power, safety, thermal, mechanical, and high-speed decisions that automation cannot establish.

A lower track or via count is allowed only when the comparison explains why the removed copper is intentional and connectivity remains complete.

## 9. Review and Release

`pcb-copilot review` replaces scattered validation scripts and hand-written status summaries. It produces one current report containing:

- evidence and provenance status;
- part-number and document-revision checks;
- schematic structural, connectivity, ERC, and visual findings;
- PCB parity, placement, routing, zone, DRC, and visual findings;
- unresolved human decisions and deviations;
- sign-off validity.

`pcb-copilot release` is unavailable until review passes and required human sign-offs are current. It produces BOM, fabrication, assembly, and evidence outputs from the current design. Generated release output is reproducible and is not treated as a second source of design truth.

The TMS570 board remains blocked from release until its safety-related decisions and sign-offs are complete. The GNSS board remains blocked from release until its RF and antenna-related blockers are resolved. These blocks do not prevent continued work on the current design.

## 10. Code and Repository Cutover

Required behavior is moved behind `src/pcb_copilot` before the old implementation is removed. Characterization tests may temporarily protect legacy behavior, but compatibility is not a final product feature.

The final repository keeps only:

```text
README.md
CLAUDE.md
docs/
pyproject.toml
uv.lock
src/pcb_copilot/
tests/
projects/template/
projects/<board>/
packages/kicad-claude-mcp/   # only if still an active, tested runtime dependency
```

The final `docs/` directory contains only the short reader documentation required to understand and use the repository. The exact current document set is maintained by the documentation index.

The local KiCad support package is retained only if the product imports and tests it as an active dependency. If retained, it moves from an ambiguous `tools/` location to `packages/kicad-claude-mcp`. Only APIs used by PCB Copilot and their supporting tests remain. Reference or experimental tool trees are removed after any required behavior is migrated.

## 11. Deletion Inventory

The following are deleted when their replacement gate is satisfied:

- root `HUMAN_WORK.md` after its live decisions are represented by `review`, deviations, and sign-off;
- per-board `STATUS.md` and `PIPELINE.json` after `status` and project state are authoritative;
- per-board `build.sh`, `gen_*.py`, and `SCHEMATIC_OWNER` after the package path has parity and tests;
- hand-maintained BOM files after `release` reproduces and verifies them;
- GNSS `EVALUATION.md` after cited design facts move into current requirements, design basis, and evidence records;
- public compatibility scripts after all callers and characterization-only tests are removed;
- `.claude/` repository automation after equivalent portable enforcement is part of `pcb-copilot`;
- obsolete migration inventories after the cutover is complete;
- superseded specs and implementation plans after implementation is verified;
- unused `kicad-happy` and `kicad-jlcpcb` trees after required capabilities are migrated or proven unnecessary;
- persistent `.pcb-copilot` draft and accepted histories after current files are promoted and verified;
- empty, copied, generated, or historical project folders that are not required to open, review, or release the current design.

Deletion is gated by replacement, not by age alone. Protected evidence and current engineering decisions are migrated before their old container is removed. Git provides recovery for intentionally deleted repository history.

## 12. Testing Strategy

Tests are reorganized around the final public behavior:

- CLI contract and manifest loading;
- evidence integrity and protected-source hashes;
- transactional update and rollback behavior;
- schematic connectivity, hierarchy, and visual-quality metrics;
- PCB parity, placement, routing, and non-regression comparisons;
- review findings and sign-off invalidation;
- reproducible release outputs;
- end-to-end tests for the template and four real boards;
- native KiCad open, ERC, DRC, and render checks where available.

Legacy compatibility tests are removed only after final-behavior tests cover the retained capability. Network-dependent research tests remain separated from deterministic repository verification.

## 13. Implementation Sequence

1. Implement unified review and release behavior in the package.
2. Implement transactional `update-schematic` and `update-layout`, then remove the persistent draft/accept command model.
3. Complete and promote the four schematics, including TMS hierarchy reconciliation.
4. Complete and promote the four PCBs in increasing order of complexity without routing regression.
5. Convert each project to the canonical format and remove per-project mirrors, generators, and stale reports.
6. Reduce support packages to active dependencies and remove reference tool trees.
7. Delete compatibility scripts, platform-specific enforcement, migration material, and superseded planning files.
8. Rewrite the reader documentation against the resulting repository and run final verification.

Each step is committed separately on the main branch. No remote push is part of this work.

## 14. Definition of Done

The cutover is complete only when all of the following are true:

- `pcb-copilot` is the only documented and supported pipeline entry point;
- no tracked persistent draft or accepted-copy tree exists;
- each board opens from its root KiCad files and those files are the latest reviewed working design;
- all four root schematics contain the completed readable schematic work;
- no root PCB is replaced by an unrouted or less complete candidate;
- all four PCB cutovers pass reconciliation, routing, DRC, comparison, and visual review gates;
- review and release use the current root design and produce reproducible outputs;
- protected evidence hashes remain unchanged unless an explicit source update is reviewed;
- obsolete generators, wrappers, reports, status mirrors, plans, migration files, and unused tool trees are absent;
- repository search finds no callers of removed commands or files;
- the deterministic test suite passes, with network tests reported separately;
- native KiCad checks and rendered comparisons have been inspected;
- `docs/` contains only accurate reader documentation for the finished repository;
- the working tree is clean and the result is committed locally.

This definition deliberately distinguishes visible progress from infrastructure progress: the work is not finished merely because the package or tests improve. The current KiCad files must show the improved design.
