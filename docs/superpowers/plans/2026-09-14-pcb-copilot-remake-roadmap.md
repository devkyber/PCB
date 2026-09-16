# PCB Copilot Remake Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the current PCB workspace into an evidence-backed, human-controlled PCB copilot without losing proven behavior or current engineering evidence.

**Architecture:** Execute five independently reviewable subsystem plans in dependency order. Existing commands remain callable through compatibility entry points until the replacement is characterized against all four boards; destructive cleanup happens only in the final plan after provenance, parity, and regression checks pass.

**Tech Stack:** Python 3.10+, `uv`, pytest 8+, Pydantic 2, PyYAML 6, KiCad 10 CLI/pcbnew through kipython, the vendored `kicad-claude-mcp` package, and Git.

**Spec:** `docs/superpowers/specs/2026-09-14-pcb-copilot-repository-remake-design.md`

## Global Constraints

- User clarification (2026-09-16): reference schematic AND PCB-layout search,
  acquisition, inspection and scoped validation are first-class requirements,
  alongside datasheet research. Track those stages separately. Search seeds,
  downloaded files and archive-integrity checks alone never mean research is
  complete. Each board needs a source/variant-aware reference review and
  design-basis comparisons; missing layout references remain explicit.

- Accepted `.kicad_sch` and `.kicad_pcb` files are the electrical and physical sources of truth.
- Analysis is read-only; generation writes a separate draft; acceptance and release are explicit.
- Never silently overwrite a human-owned or accepted design.
- Every implementation job begins by reading the current implementation, callers, tests, outputs, and related documentation.
- Preserve current behavior through characterization tests before moving or deleting code.
- Every new blocking check needs a fault-injection test that proves it can fail.
- Research remains advisory during drafting and blocking at release.
- Release always runs the full review suite and emits a complete report even after an early failure.
- Windows and KiCad 10.0 dotted-version installs are first-class tested targets.
- `deviations.py` remains the only waiver parser until its tested implementation is moved intact.
- `netmap.json` remains versioned until a verified replacement provides equally reviewable connectivity diffs.
- Generated status and fabrication outputs must identify the exact design hash they describe.
- Delete a file only after its current facts or unique behavior have a verified canonical destination.

---

## Plan Set

Current checkpoint (2026-09-17): Plans 1 and 2 package migrations are in place;
Plan 3 Tasks 1–7 are implemented and Task 8 has four circuit-preserving intents
and rendered drafts. No new board draft has been accepted. Human visual review
is next. Reference coverage is partial and tracked per board. Plans 4 and 5
are not complete; no compatibility code is deleted merely to shorten the tree.

Execute these plans in order. Each plan ends in working, independently testable software and a reviewer checkpoint.

1. [`2026-09-14-pcb-copilot-01-foundation-and-docs.md`](2026-09-14-pcb-copilot-01-foundation-and-docs.md)
   - Capability inventory and characterization baseline
   - Root Python workspace and Windows toolchain discovery
   - Project manifest, lifecycle, ownership, and read-only status CLI
   - Documentation consolidation without premature code deletion

2. [`2026-09-14-pcb-copilot-02-evidence.md`](2026-09-14-pcb-copilot-02-evidence.md)
   - Structured multi-role evidence index
   - Existing URL/payload verification and exact-document extraction
   - Board-by-board evidence migration and safe duplicate removal

3. [`2026-09-14-pcb-copilot-03-schematic.md`](2026-09-14-pcb-copilot-03-schematic.md)
   - Transactional draft workspaces
   - Functional-block schematic intent
   - Local wiring, hierarchy, rendering, quality checks, and explicit acceptance
   - Existing-board parity migration, including multi-sheet TMS V3

4. [`2026-09-14-pcb-copilot-04-layout.md`](2026-09-14-pcb-copilot-04-layout.md)
   - Real-footprint resolution and measured geometry
   - Placement/constraint proposals
   - Optional candidate routing with existing post-processing
   - Human-controlled PCB acceptance

5. [`2026-09-14-pcb-copilot-05-review-release-cleanup.md`](2026-09-14-pcb-copilot-05-review-release-cleanup.md)
   - Typed findings and complete review orchestration
   - Project-specific human sign-off
   - Hash-bound release and fabrication package
   - Final compatibility removal and documentation/file cleanup

## Cross-Plan Interfaces

The plans share these stable names. Later plans must not rename them without updating all earlier tests and this roadmap.

```python
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field

class Lifecycle(str, Enum):
    DRAFT = "DRAFT"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    RELEASED = "RELEASED"

class FindingKind(str, Enum):
    MACHINE_FAILURE = "machine_failure"
    ENGINEERING_WARNING = "engineering_warning"
    HUMAN_DECISION = "human_decision"

class Finding(BaseModel):
    check_id: str
    kind: FindingKind
    summary: str
    detail: str
    blocking: bool
    refs: list[str] = Field(default_factory=list)

class Project:
    root: Path
    manifest_path: Path
    schematic_path: Path
    pcb_path: Path
    evidence_index_path: Path

load_project(path: Path) -> Project
canonical_design_hash(path: Path) -> str
run_review(project: Project) -> list[Finding]
```

## Specification Coverage Audit

| Approved design requirement | Owning implementation tasks |
| --- | --- |
| Human-controlled copilot, explicit lifecycle, source-of-truth rules | Foundation Tasks 4-6; Schematic Task 7; Layout Task 7; Release Tasks 4-6 |
| Preserve proven pipeline, gates, evidence, ownership, netmap/parity, helpers, routing, and fabrication behavior | Foundation Tasks 2-3; Evidence Tasks 2-6; Release Tasks 1-3 and 8-9 |
| One coherent project structure and command surface | Foundation Tasks 1, 4, and 6; Release Task 9 |
| Datasheet discovery, exact-document checks, extraction, and confidence | Evidence Tasks 1-6 |
| Intent-first, readable, hierarchical schematic assistance | Schematic Tasks 1-6 |
| Separate drafts, preview, quality gate, acceptance, and stale-draft protection | Schematic Tasks 1, 5, and 7; Layout Tasks 1, 6, and 7 |
| Real footprints, measured geometry, placement constraints, and optional routing | Layout Tasks 1-6 |
| Typed review findings, full-suite execution, waivers, sign-off, and hash-bound release | Release Tasks 1-7 |
| Four-board migration with TMS V3 multi-sheet proof | Evidence Task 6; Schematic Task 8; Layout Task 8; Release Task 10 |
| Documentation consolidation and evidence-based deletion | Foundation Task 7; Release Task 9 |
| Honest limitations, future work, and operator workflow | Foundation Task 7; Release Task 10 |
| Fault-injection, regression, Windows, KiCad 10, and clean-tree verification | Foundation Tasks 2-3; every subsystem completion gate; Release Tasks 2, 8, and 10 |

## Roadmap Verification

- [ ] Run every plan's targeted tests before moving to the next plan.
- [ ] Run `uv run pytest -q` from the repository root after every plan.
- [ ] Run `uv run python docs/selftest_enforcement.py` after any gate, hook, parser, or compatibility-entry-point change.
- [ ] Run `uv run python docs/audit_workflow.py` after each board migration.
- [ ] Record the four-board netmap and KiCad-open baseline before schematic or PCB mutation.
- [ ] Confirm `git status --short` contains only the files owned by the current task before each commit.
- [ ] Stop at each plan boundary for a human review of the diff and generated KiCad previews.

## Completion Gate

The remake is complete only when all five plans pass, all four accepted boards open in KiCad, existing connectivity remains accounted for, TMS V3 has a readable hierarchical schematic draft, release cannot run on stale or unsigned design hashes, and every planned deletion has a recorded replacement or proof of duplication.
