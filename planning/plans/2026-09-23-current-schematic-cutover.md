# Current Schematic Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the improved schematic work in the four current KiCad projects through one transactional command, without claiming human sign-off.

**Architecture:** Reuse the renderer and review checks already in the package. Treat its candidate directory as a short-lived transaction, then apply checked files through the existing rollback mechanism. Fix known rendering defects before changing root KiCad files. This is the schematic subproject of the approved repository cutover; review/release, PCB routing, and final deletion have separate dependent plans.

**Tech Stack:** Python 3.10+, Pydantic 2, KiCad 10, pytest, Git.

**Spec:** `planning/specs/2026-09-23-single-current-pipeline-cutover-design.md`

## Global Constraints

- Root KiCad files are the visible working design.
- A failed operation leaves the root design unchanged.
- Applying a schematic invalidates prior human sign-off; it must not mark the result human-reviewed.
- Keep electrical connectivity, pin maps, references, footprints, evidence, and PCB parity explicit.
- Do not promote an unrouted PCB candidate as part of this plan.
- Work and commit on main; do not push.

## Review Focus

- A generator failure must leave the root schematic and netmap byte-identical.
- A stale candidate must not overwrite a newer current schematic.
- A multi-sheet apply must roll back every changed sheet if a later write fails.
- TMS local labels must retain their hierarchy-qualified KiCad net names.
- A schematic with unresolved electrical differences must fail apply rather than present a green report.

---

### Task 1: Correct power glyph spacing in generated schematics

**Files:**
- Modify: `src/pcb_copilot/schematic/power.py`
- Modify: `tests/schematic/test_power_diagnostics.py`

**Interfaces:**
- Consumes: `power_stub_length(ed, tree, ref, pin, origin) -> float | None`.
- Produces: the same API with enough spacing for non-adjacent power pins in one symbol column.

- [ ] **Step 1: Write a failing real-render test.** Render the BMP390 intent into a copied project, parse the result, and assert `power_clearance_findings` contains no `power-glyph-collision` on U1.
- [ ] **Step 2: Run `uv run pytest tests/schematic/test_power_diagnostics.py -k bmp_power_spacing -q`.** Expect failure naming the current U1.3/U1.5 clash.
- [ ] **Step 3: Change the stub staggering rule in `power_stub_length` so both adjacent and every-other-row power pins have positive glyph clearance.** Keep grid alignment and the existing crossing checks.
- [ ] **Step 4: Run the focused power tests and the full deterministic suite.** Expect no BMP glyph clash and no changed netlist.
- [ ] **Step 5: Commit the generator and test change.**

### Task 2: Make schematic apply preserve honest review state

**Files:**
- Modify: `src/pcb_copilot/accept.py`
- Modify: `src/pcb_copilot/state.py`
- Modify: `tests/schematic/test_accept.py`
- Modify: `tests/test_state.py`

**Interfaces:**
- Consumes: `accept_schematic(project, draft) -> AcceptanceResult`.
- Produces: an applied current schematic with a current machine review record, `Lifecycle.DRAFT`, and invalidated old sign-off/release hashes.

- [ ] **Step 1: Write failing tests.** Assert a schematic apply does not yield `HUMAN_REVIEWED`, old release hashes no longer match, and a hierarchy write failure restores all original sheets.
- [ ] **Step 2: Run the targeted tests.** Expect failure because acceptance currently records `HUMAN_REVIEWED`.
- [ ] **Step 3: Change acceptance state semantics without weakening file-hash and rollback validation.**
- [ ] **Step 4: Run the targeted tests and full deterministic suite.**
- [ ] **Step 5: Commit the state correction.**

### Task 3: Expose a single current schematic command

**Files:**
- Create: `src/pcb_copilot/schematic/update.py`
- Modify: `src/pcb_copilot/cli.py`
- Create: `tests/schematic/test_update_schematic.py`
- Modify: `tests/schematic/test_schematic_cli.py`

**Interfaces:**
- Produces: `update_schematic(project: Project, intent_path: Path, apply: bool) -> dict`.
- Produces: `pcb-copilot update-schematic PROJECT --intent FILE [--apply]`.

- [ ] **Step 1: Write failing CLI tests.** Without `--apply`, assert root hashes do not change and a summary is printed. With `--apply`, assert current schematic changes, PCB bytes stay identical, and reported lifecycle is DRAFT.
- [ ] **Step 2: Run the targeted CLI tests.** Expect the new command to be rejected.
- [ ] **Step 3: Implement the command around the existing renderer, review, and transaction.** Remove the temporary candidate after successful apply; on failure retain a readable error while leaving root files unchanged. Keep a temporary preview available for the command duration, and print its review findings.
- [ ] **Step 4: Run CLI tests and the full deterministic suite.**
- [ ] **Step 5: Commit the command.**

### Task 4: Promote the four corrected schematics

**Files:**
- Modify: `projects/baro-bmp390/*.kicad_sch`, `projects/baro-bmp390/netmap.json`
- Modify: `projects/imu-icm42688/*.kicad_sch`, `projects/imu-icm42688/netmap.json`
- Modify: `projects/gnss-neom9n/*.kicad_sch`, `projects/gnss-neom9n/netmap.json`
- Modify: `projects/tms-v3/*.kicad_sch`, `projects/tms-v3/netmap.json`
- Modify: `tests/schematic/test_quality.py`

**Interfaces:**
- Consumes: `pcb-copilot update-schematic PROJECT --intent FILE --apply`.
- Produces: root KiCad schematics as the latest working schematic design.

- [ ] **Step 1: Record root schematic, PCB, and evidence hashes; run preview review for each board.**
- [ ] **Step 2: Resolve each blocking electrical, visual, and hierarchy finding in generator or intent with a failing test before editing implementation.**
- [ ] **Step 3: Apply one board at a time, beginning with BMP390, and render/open each current schematic.**
- [ ] **Step 4: Compare component, pin-net, footprint, ERC, and PCB parity results against the previous current design; verify PCB and protected evidence hashes did not change.**
- [ ] **Step 5: Update baseline tests to test the new working schematics, then run the full deterministic suite and commit each board separately.**

After these tasks, write and execute the dependent review/release, layout, and repository cleanup plans. Their acceptance criteria are in the approved spec; this plan does not mark those phases complete.
