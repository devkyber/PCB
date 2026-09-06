# Superseded documents

Kept for provenance, **not** for reference. Nothing here is current, and no
check reads any of it.

A design decision is easier to re-litigate than to reconstruct, so the
documents that produced the current design are worth keeping — but a
superseded document sitting beside a current one is a drift hazard, which is
the failure mode this workspace exists to eliminate. Hence: out of the way,
and labelled.

| File | What it was | Superseded by |
|---|---|---|
| `tms-v2-summary.md` | TMS V2 (2025-TMS-3.0) design summary | `docs/tms-v3-pdr.md` |
| `tms3-design-review.md` | PDR review of the V2 EasyEDA export that produced the V3 spec | `docs/tms-v3-pdr.md`, `projects/tms-v3/DESIGN_BASIS.md` |

Removed outright rather than archived, because their content survives verbatim
elsewhere and two copies of one fact is worse than none:

- `docs/tms-v3-pdr.html` — a **stale, shorter** rendering of `tms-v3-pdr.md`
  (3,914 words against 4,900). Two documents claiming to be the same spec.
- `projects/tms-v3/BUILD.md` — a hand-written build sequence. `build.sh` was
  collapsed into a shim over `docs/pipeline.py` precisely so there would be
  one build path; a prose copy of that sequence re-created the second one.
- `projects/tms-v3/BLOCKERS.md` — hand-maintained status ("2 DRC errors, 5
  unconnected") next to machine-generated `STATUS.md`. It was already wrong.
- `tms-v3-relay-and-adc-explained.md` — a walkthrough of TMS V3's relay and
  ADC front end, written while that board was being designed. Board-specific
  teaching material, referenced by nothing; kept because the reasoning about
  the relay contact rating is still the clearest write-up of it.
