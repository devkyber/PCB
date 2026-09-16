# Review refresh implementation report

## Scope and result

Implemented the bounded Plan 3 Tasks 6/7 follow-up on base `4ce83e3`: an existing
schematic draft can now be re-reviewed after manual edits with
`pcb-copilot review-draft PROJECT_PATH DRAFT_ID`. The command does not render a
new schematic, accept a design, or change accepted project state.

`draft-schematic` and `review-draft` now call the same report assembly. That
assembly performs the existing preview, ERC, metrics, evidence, netlist
extraction, and intent-connectivity/name parity checks; writes external-tool
outputs in a fresh staging directory; publishes final-path outputs; and
publishes `review.json` last. Report shape and report-driven exit codes are the
same for generation and refresh.

## Changes

- Added the `review-draft` CLI with `PROJECT_PATH DRAFT_ID` positional arguments.
- Refactored schematic report creation into one shared implementation used by
  both draft generation and re-review.
- Reused acceptance loaders for draft ID, project identity, root, kind, and
  accepted-base validation. Base validation now has one shared helper used by
  review and acceptance.
- Re-review follows the draft root and contained child hierarchy, loads the
  draft's saved `schematic-intent.yaml`, and never calls the renderer.
- Input hashes are captured before intent parsing. CAD, hierarchy membership,
  intent bytes, and accepted-base state are checked after external review and
  again immediately before `review.json` publication.
- Fresh ERC, metrics, and PDF outputs are staged. A failed rerun removes the
  prior final PDF, publishes a current failed ERC record, and cannot retain a
  successful report. Returned and persisted report paths name final draft
  files, never temporary staging paths.
- Every refreshed report resets `human_review` to `pending`; the project
  lifecycle remains `DRAFT` until a separate explicit acceptance.
- Acceptance now directs operators with edited/missing review artifacts to the
  exact `review-draft` command instead of telling them to regenerate the draft.

## Regression coverage

`tests/schematic/test_review_draft.py` covers:

1. Root and child visible-text edits are preserved byte-for-byte; old
   acceptance refuses them; refresh hashes the edited files; prior approval is
   reset to pending; accepted files and lifecycle stay unchanged; explicit
   acceptance then installs the edited hierarchy.
2. A child net-name/connectivity contradiction produces
   `intent-netlist-mismatch`, leaves the schematic and saved intent unchanged,
   and blocks acceptance.
3. Injected ERC/PDF failures cannot reuse a prior PDF or success report and do
   not alter CAD.
4. Invalid IDs, project identity, layout kind, traversing child references, and
   stale accepted bases are rejected before review outputs change; draft
   metadata/base hashes remain intact.
5. CAD edits injected during an external command are retained but cannot be
   sealed; prior outputs remain unchanged and acceptance refuses them.
6. An intent edit injected immediately after parsing is detected because its
   initial hash preceded parsing; stale parsed intent cannot be sealed against
   newer bytes.
7. The CLI returns the established report schema with zero/nonzero report exit
   semantics, while normal draft generation continues through the same checks.

## TDD evidence

- RED: `uv run pytest tests/schematic/test_review_draft.py::test_review_preserves_manual_hierarchy_edits_and_refreshes_acceptance -q`
  failed at collection because `review_draft` did not exist.
- GREEN: the same test passed (`1 passed in 10.74s`) after the shared review path
  and actionable acceptance error were implemented.
- RED: `uv run pytest tests/schematic/test_review_draft.py::test_review_draft_cli_returns_report_schema_and_blocking_exit_code -q`
  failed with argparse `invalid choice: 'review-draft'`.
- GREEN: the same CLI regression passed (`1 passed in 18.00s`) after registering
  and dispatching the command.
- RED: `uv run pytest tests/schematic/test_review_draft.py::test_intent_edit_while_loading_cannot_be_sealed_with_stale_parsed_intent -q`
  failed because no `RuntimeError` was raised, demonstrating the parse-before-hash
  window.
- GREEN: the same regression passed (`1 passed in 14.13s`) after moving initial
  hashing before intent parsing.

## Verification

- `uv run pytest tests/schematic/test_review_draft.py tests/schematic/test_accept.py tests/schematic/test_schematic_cli.py -q`
  — `15 passed in 183.34s`.
- Approval-reset strengthening rerun:
  `uv run pytest tests/schematic/test_review_draft.py::test_review_preserves_manual_hierarchy_edits_and_refreshes_acceptance -q`
  — `1 passed in 10.77s`.
- `uv run ruff check src/pcb_copilot/schematic/commands.py src/pcb_copilot/accept.py src/pcb_copilot/cli.py tests/schematic/test_review_draft.py`
  — `All checks passed!`.
- The controller owns the full non-network suite and real-board reruns; neither
  was duplicated here.

## Files

- `src/pcb_copilot/schematic/commands.py`
- `src/pcb_copilot/accept.py`
- `src/pcb_copilot/cli.py`
- `tests/schematic/test_review_draft.py`
- `.superpowers/sdd/2026-09-14-pcb-copilot-03-schematic/review-refresh-report.md`

## Self-review and limitations

Self-review found no unaddressed correctness, containment, or stale-success
issue within this slice. Draft and hierarchy paths are validated before tools
run; only staged review outputs are published; report publication is last; and
acceptance independently recomputes every required artifact hash.

The intent parity check intentionally remains the existing
`normalize_intent_netmap` contract: connected physical pin inventory/grouping
and retained net names. It does **not** validate symbol Value, Footprint,
`lib_id`, or no-connect identity. Adding those checks is separate scope.

This is a bounded fail-closed publication design, not a generalized lock or
multi-file transaction. If publication itself is interrupted after one output
move, the previous `review.json` no longer matches the output set and acceptance
refuses it. Input changes after the final snapshot check are likewise rejected
by acceptance's current-byte hash comparison. Manual CAD and intent files are
never rolled back or rewritten by review.
