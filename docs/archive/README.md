# Superseded documents

Kept for provenance, **not** as current design authority. These documents
describe earlier revisions or design-stage explanations; their technical and
safety claims require rechecking against current requirements and archived
manufacturer evidence. No runtime check consumes them.

A design decision is easier to re-litigate than to reconstruct, so the
documents that produced the current design are worth keeping — but a
superseded document sitting beside a current one is a drift hazard, which is
the failure mode this workspace exists to eliminate. Hence: out of the way,
and labelled.

| Retained file | Historical scope | Current authority / migration status |
|---|---|---|
| [tms-v2-summary.md](tms-v2-summary.md) | TMS V2 (2025-TMS-3.0) design summary | [V3 PDR](../tms-v3-pdr.md); current project requirements and design basis take precedence. |
| [tms3-design-review.md](tms3-design-review.md) | Review of the V2 EasyEDA export that informed the V3 spec | [V3 PDR](../tms-v3-pdr.md) and [current design basis](../../projects/tms-v3/DESIGN_BASIS.md). |
| [tms-v3-relay-and-adc-explained.md](tms-v3-relay-and-adc-explained.md) | Design-stage teaching explanation of the relay and ADC front end | Retained pending fact-level migration; explanatory rationale is not verified component suitability or safety sign-off. |

The following files were previously removed, rather than retained in this
archive, after being identified as stale or duplicate records:

- `docs/tms-v3-pdr.html` — a **stale, shorter** rendering of `tms-v3-pdr.md`
  (3,914 words against 4,900). Two documents claiming to be the same spec.
- `projects/tms-v3/BUILD.md` — a hand-written build sequence. `build.sh` was
  collapsed into a shim over `docs/pipeline.py` precisely so there would be
  one build path; a prose copy of that sequence re-created the second one.
- `projects/tms-v3/BLOCKERS.md` — hand-maintained status ("2 DRC errors, 5
  unconnected") next to machine-generated `STATUS.md`. It was already wrong.

No further archive deletion is approved by this index. Before removing a
retained file, preserve any still-valid unique facts in the maintained project
records, rules, tests, or limitations and record its replacement in the
migration inventory.
