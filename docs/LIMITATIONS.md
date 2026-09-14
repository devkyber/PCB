# Limitations and Future Work

## Honest answer: can this produce a human-level schematic?

It can produce a useful first draft and, with strong intent and evidence,
sometimes a schematic that looks professionally organized. It cannot reliably
produce or certify a human-expert design on its own.

“Human-level” contains several different abilities: selecting an appropriate
topology, noticing missing requirements, interpreting ambiguous datasheets,
reasoning about failure modes, drawing a reviewable page, anticipating layout
and mechanical effects, and accepting safety responsibility. Automation is
strongest at retrieval, transcription, consistency, repetitive CAD work, and
known-rule checks. It is weakest where requirements are incomplete, sources
conflict, physical behavior dominates, or judgment depends on experience and
measurement.

The realistic goal is therefore a copilot that gives a capable human a
well-sourced, connected, readable starting point and a precise list of what
still needs judgment. That can materially reduce design time without claiming
autonomy.

## What the system can help with

- Search, archive, hash, classify, and cite component documents.
- Extract exact pins, values, and connections from supported source formats.
- Compare a proposed circuit with datasheets and reference designs.
- Generate functional-block schematic and PCB drafts from explicit intent.
- Preserve netlists, run ERC/DRC, check parity, and detect stale artifacts.
- Measure known geometric relationships such as placement clearance.
- Prepare candidate routing and fabrication packages for inspection.
- Maintain a review trail tied to exact accepted design hashes.

## What it cannot establish

- That requirements are complete or represent the real use case.
- That a circuit is stable, accurate, safe, or robust outside modeled checks.
- Analog performance, EMC, thermal behavior, RF behavior, signal integrity,
  power integrity, or transient survival without appropriate analysis and
  measurement.
- Mechanical fit, connector usability, assembly quality, or enclosure effects
  from a 2D rule pass alone.
- Correct interpretation of every datasheet, especially conflicting revisions,
  diagrams, errata, implicit conditions, and application-specific caveats.
- Suitability for high-current, battery, rocket, pyrotechnic, medical, mains,
  automotive, or other consequential use.
- That a DRC-clean autoroute is a good layout.

## Current repository limitations

- The legacy pipeline contains Unix/macOS assumptions. Foundation discovery
  now supports Windows and dotted KiCad versions, but remaining wrappers have
  not all migrated.
- `kipython` is not currently discovered on this Windows host, although
  KiCad’s bundled Python exists. PCB checks that import `pcbnew` need the
  portable adapter work planned later.
- The enforcement self-test currently assumes an ignored `drc-report.json`
  exists in the source project; a clean checkout exposes that fixture bug.
- Existing schematics were generated with label-heavy stubs and measured zero
  junctions. Electrical connectivity may exist, but visual review quality is
  insufficient—especially for TMS V3.
- TMS V3 needs hierarchy. Crowding 69 components on one page is not repaired
  by tighter spacing.
- The design-rule checker covers 4 of 42 historical numbered subsections.
- Current sign-off forms contain generic questions; project-specific,
  hash-bound review profiles are not implemented yet.
- Evidence is split between datasheet and reference-design indexes until the
  structured evidence migration is complete.
- Freerouting is nondeterministic and has known keepout/via limitations. Its
  result remains a candidate.
- Existing PCB files use a short `(net "NAME")` encoding accepted by KiCad but
  noncanonical for external text consumers.

## Human responsibilities

The human owner must supply missing requirements, choose among real tradeoffs,
review every schematic and PCB visually, verify critical calculations, resolve
conflicting evidence, inspect mechanical and assembly views, perform staged
bench tests, and decide whether fabrication or operation is acceptable.

For TMS V3, this includes measured igniter resistance/current, connector and
relay margin, reset/brownout safety, isolated-return intent, regulator thermal
budget, dummy-load procedure, and explicit authorization before any energetic
test. Similar domain-specific review applies to GNSS RF, IMU mechanics, and
barometer port/environment design.

## Planned work

1. Unify evidence records, exact-document verification, and cited extraction.
2. Add transactional schematic intents, functional blocks, hierarchy,
   rendering metrics, previews, and stale-safe acceptance.
3. Add real-footprint layout intents, measured placement, constraints, and
   optional candidate routing.
4. Unify typed findings, fault coverage, relevant sign-off, transactional
   fabrication, and hash-bound release.
5. Remove superseded files only after replacement, caller, fact, and behavior
   checks pass.

The [implementation roadmap](superpowers/plans/2026-09-14-pcb-copilot-remake-roadmap.md)
contains the test and migration gates for this work.
