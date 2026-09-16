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

This list describes the copilot's scope, not completion of every new command.
Evidence and schematic assistance are implemented; the new layout and release
interfaces remain planned, with legacy tools retained during migration.

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
- Accepted schematics were generated with label-heavy stubs and measured zero
  junctions. Electrical connectivity may exist, but visual review quality is
  insufficient—especially for TMS V3. New drafts have measured row spacing,
  local drawn wiring, power symbols, titles and functional blocks, but have
  not replaced accepted files.
- TMS V3 now has a seven-page draft (overview plus six functional sheets).
  Human review is pending. Its local net names gain sheet prefixes; acceptance
  preserves those names and will require explicit PCB net-name reconciliation.
- Schematic placement is heuristic. Body/pin obstacles and outward label
  alignment improve readability but do not constitute a sheet-wide graphical
  collision solver. The existing `no_symbol_or_text_overlap` helper checks only
  duplicate symbol origins, not text or glyph extents. Inspect every PDF page.
- Circuit parity preserves old mistakes too. The TMS reference review found
  ADS1256 VREF_P/VREF_N connected only to U2 and C7, contrary to the design-basis
  external-reference claim. This requires engineering reconciliation, not a
  silent renderer correction or a passing ERC result.
- The design-rule checker covers 4 of 42 historical numbered subsections.
- Current sign-off forms contain generic questions; project-specific,
  hash-bound review profiles are not implemented yet.
- Evidence archival is unified and hash-verified, but automatic fact extraction
  is currently narrow: exact Eagle schematic connectivity is supported, while
  PDFs and other CAD formats are queued for human review rather than guessed.
- Reference research is a separate deliverable for schematics and PCB layouts.
  The CLI can generate search queries but has no live web-search provider;
  searches are performed by the assistant and recorded per project. Indexed
  Eagle schematic/board pairs can now be compared for physical pad-net
  membership, packages and explicit values. This does not validate layout
  performance, finish PCB visual review, or run reference-board DRC.
- `pcb-copilot research --verify` proves archive integrity, not that every
  needed part has been identified. The board-level evidence gates still own
  completeness checks during this migration.
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

1. Extend cited extraction to more CAD formats and conservative PDF tables,
   while retaining explicit human review for ambiguous diagrams.
2. Finish human review of all four schematic drafts and accept only explicitly
   approved revisions; improve remaining label/power-glyph collision handling.
3. Add real-footprint layout intents, measured placement, constraints, and
   optional candidate routing.
4. Unify typed findings, fault coverage, relevant sign-off, transactional
   fabrication, and hash-bound release.
5. Remove superseded files only after replacement, caller, fact, and behavior
   checks pass.

The [implementation roadmap](superpowers/plans/2026-09-14-pcb-copilot-remake-roadmap.md)
contains the test and migration gates for this work.
