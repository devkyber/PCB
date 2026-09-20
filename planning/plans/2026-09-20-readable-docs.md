# Reader-only Docs Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline for this single relocation task. The owner requested implementation on main with minimal delegation.

**Goal:** Make `docs/` contain only guides a person reads to understand and use this repository.

**Architecture:** Move the 22 compatibility Python modules to `scripts/` at the same directory depth. Move the approved specification/plans to `planning/specs/` and `planning/plans/`, and rule provenance to `migration/legacy-design-rules.md`. Update callers without changing algorithms or accepted designs.

**Tech Stack:** Python, PowerShell, pytest, Git.

**Spec:** Owner request: "docs should be the files i can read to understand the repo".

## Global Constraints

- Preserve accepted CAD, evidence bytes, libraries, intents, settings, sign-offs and local drafts.
- No board generators, full pipeline or enforcement self-test may run against this checkout.
- Keep the seven reader guides flat in `docs/`; do not leave executable compatibility shims there.
- Existing `docs/*.py` shell commands migrate to `scripts/*.py`; document that change.

## Task 1: Separate reader documentation from executable and maintainer files

**Files:** `docs/*.py` -> `scripts/*.py`; former docs/superpowers plan/spec directories -> `planning/{plans,specs}/`; rule history -> `migration/legacy-design-rules.md`; consuming paths in `src/`, `tests/`, `.claude/`, project generators/build wrappers and readable documentation.

**Interfaces:** Preserve Python module names, signatures, CLI flags and safety checks. Only their repository paths change. `docs/README.md` is the reading-order entry point.

- [x] Add a subprocess test running `scripts/pipeline.py --status` outside the repository working directory; assert all four board IDs and successful exit. Run it before moving files and confirm missing-script failure.
- [x] Move tracked files; update exact script paths and import directories, maintainer links, inventory and reader navigation.
- [x] Run the regression and the full non-network suite: `uv run pytest -m 'not network' -q -rs`. Verify selected protected hashes and evidence integrity; inspect the relocation diff for changes beyond paths and navigation.
- [x] Request one bounded read-only review, fix findings, and repeat relevant verification.
- [x] Commit only this relocation on main; do not push. Report the final docs contents and test scope.

## Verification and remaining local housekeeping

2026-09-21: 684 passed, 48 skipped, 3 deselected; two legacy docstring escape
warnings. Source/new-test lint passed. All 37 protected hashes match; all 40
evidence records verify. Thirty-four executable ASTs are unchanged after
normalizing the intended docs/scripts path and variable renaming. Unix file
modes are preserved. Reviewer findings about two tool templates and ten
executable flags were fixed and re-reviewed successfully.

Empty-directory/cache deletion was rejected by the environment before execution.
The local `docs/__pycache__`, `docs/archive`, `docs/history`, and
`docs/superpowers` directories remain; no alternate deletion method was used.
The Git tree contains only the seven reader guides under `docs/`.
