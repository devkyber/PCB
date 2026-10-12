# Limits and next work

## Can it make a human-level schematic?

Not reliably or autonomously. The current pipeline can give an engineer a
connected, sourced, editable starting point with functional grouping and
checks; it cannot infer missing requirements, select every topology, settle
conflicting sources, judge failure modes, or certify the design. The working
schematics remain `DRAFT` designs awaiting
human page-by-page review. TMS's controller and connector sheets still rely
heavily on labels. ERC and schematic/PCB parity do not measure readability or
correctness of the engineering choices.

The intended value is to save repetitive time: find and preserve sources,
transcribe verifiable pin/value facts, begin a schematic, flag mismatches,
offer placement/routing proposals, and make unresolved decisions explicit.
Whether this saves time in a real owner-led design session remains unmeasured.

## What checks do not prove

- Source-byte verification does not prove every needed datasheet, erratum,
  reference schematic, or reference PCB has been found or correctly applied.
  The CLI produces search plans but has no live search provider. Exact Eagle
  schematic/board comparison is narrower than a layout suitability review;
  ambiguous PDFs and unsupported CAD need human inspection.
- Schematic intent validation, ERC, and exact PCB pin-net parity can preserve
  an old circuit mistake. A clean result does not establish supply margins,
  analog accuracy, RF behavior, power integrity, or fail-safe behavior.
- Graphical clearance diagnostics cover supported power glyphs and nearby
  power/label text. They do not inspect every pin name, field, wire, symbol
  body, page-flow choice, or annotation. Inspect every KiCad/PDF page.
- Layout updates validate candidates before replacing the current PCB. Placement is heuristic; optional routing is not evidence
  of good return paths, EMI, thermal design, or manufacturing quality.
  DRC does not replace assembly and mechanical review. STEP export can be
  partial when component models are missing.
- Schematic UUID-link checks prevent forward-annotation identity from being
  omitted or silently reassigned. They do not decide which circuit revision
  is correct. Missing links are inferred only on candidates with full part/net
  parity; stale links require explicit reconciliation.
- Routing topology findings are advisory geometry checks for straight tracks
  and ordinary pad contacts. A connected pad edge is not necessarily a mistake,
  and a short segment is not necessarily redundant. Via/arc/zone topology,
  custom/offset pad anchors, current bottlenecks and return paths still need
  separate inspection. Native DRC determines electrical connectivity.
- The design-rule checker covers only 4 of 42 historical numbered sections.
  Current `review` aggregates fourteen packaged checks; even its per-sheet title/density check does not judge
  visual flow. Board-specific hash-bound sign-off is now checked, but no human
  decisions have been migrated or recorded for the current revisions.
  Release reruns all checks and requires current human decisions. An
  isolated green result is insufficient.
- Assembly contracts check exact part/footprint/pad geometry before applying a
  JLCPCB rotation offset, local model files/transforms, and net-linked wire-pad
  labels. They do not infer physical pin 1, prove imported model accuracy, or
  synchronize KiCad models with JLCPCB. A separate named supplier placement
  review tied to current PCB/BOM/CPL bytes is required by release. DRC alone
  cannot establish these facts. See [assembly workflow](JLCPCB_ASSEMBLY.md).

## Open decisions by project

- **Rover PDB:** motor regeneration, simultaneous-load temperature, converter
  transients, mechanical fit and harness protection remain engineering checks.
  Its completed routing and clean CAD checks do not resolve those questions.
  The comparison projects and older teaching guide are archived outside the
  repo. The owner closed development on 2026-10-07; use `projects/rover-pdb` and
  its README and design basis for the current owner-edited board.
- **TMS V3:** ADS1256 external reference is absent from the present circuit;
  the historical U2.15 deviation misidentifies RESET as DVDD. The owner must
  measure actual nichrome cold resistance/current and pulse duration, verify
  connector/relay/copper margin, regulator thermal budget, isolated return,
  reset/brownout safety, XBee physical fit, and dummy-load behavior. Do not
  fabricate or energize the ignition output while these remain unresolved.

Each board's `REQUIREMENTS.md`, `DESIGN_BASIS.md`, `REFERENCE_REVIEW.md`,
`DEVIATIONS.md`, and `review-profile.yaml` provide the specific sources and
open decisions. Only current hash-bound human decisions count as approvals.
The assistant must surface missing inputs, not invent numbers or check boxes.

## Remaining engineering work

The software pipeline supports checked updates and transactional fabrication
export. It has not resolved the board-specific engineering decisions above.
Placement intents are proposals; TMS candidates may remain blocked, and an
unrouted candidate cannot replace a routed PCB. Source discovery and many visual,
RF, thermal and mechanical judgments still require an engineer.

The engineer remains responsible for visual inspection, critical calculations,
physical fit, staged bench validation, and the release decision. For TMS V3,
energetic testing is outside the authority of this pipeline.
