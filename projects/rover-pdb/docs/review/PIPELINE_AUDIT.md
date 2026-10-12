# Rover: which pipeline was used, and what was learned

Audit and cleanup: 2026-10-01. This is a reference case, not fabrication approval.
The owner-saved PCB at this audit is
`3aaae121b3b91d51d99ec410163e8463f194a423afc63366893a8b54d38ff525`;
installed settings are
`2598f247f15976b32d0421ad260ddb5981252aa68dbb1fc42fe5d3946cdb3ee4`.
Later owner edits take precedence and need their own checks.

The subsequent **80 x 100 mm P2** update is recorded in
[current PCB verification](PCB_VERIFICATION.md#current-p2-80-x-100-mm). It uses
the same native-candidate pipeline, preserving the saved circuit and converter
cells. Explicit power routing precedes constrained routing of 23 signal/indicator
connections. The pipeline validates and installs the finished candidate; it is
not an autonomous power-layout designer. The repair also added a tested
read-only inventory path for an open-outline baseline. Candidate outline,
parity, placement, refill, two DRC runs and complete-routing gates remain active.

## Actual construction and acceptance

| Stage | What happened | Retained evidence |
| --- | --- | --- |
| Schematic footprint fields | Twelve explicitly authorized assignments; circuit preserved | [Assignment review](records/FOOTPRINT_ASSIGNMENT_REVIEW.json) |
| Electrical source | Fresh native schematic XML, real footprint identities and pad nets | Native schematic; [independent audit](../../layout/audit_net_intent.py) |
| Placement, converter cells and main power paths | Explicit project-specific `pcbnew` construction, with source-based loop/return decisions | [Power-layout review](PCB_POWER_LAYOUT_REVIEW.md); [build report](records/initial-layout/build-report.json) |
| Quiet feedback and Kelvin sensing | Explicit routing; pin/net intent checked separately from DRC | [Static authored reference](../../layout/authored-copper-reference.json) |
| Four residual connections | Grid routing for LED_A, MOTOR_EN, SW_SUPPLY and the VMOTOR indicator branch | [Routing report](records/initial-layout/signal-routing.json); [route audit](records/initial-layout/GRID_ROUTING_AUDIT.json) |
| Finishing | Mounting keepouts, labels, fiducials and final unlock | [Annotation report](records/initial-layout/final-annotation.json) |
| Installation | Shared `update-layout --candidate` with parity, placement, zone refill and two DRC runs | [Initial apply](records/initial-layout/apply-result.json) |
| Models, unlocked copper and drawing-sheet placement | Separate scoped updates, with geometry-preservation checks | [Verification history](PCB_VERIFICATION.md); corresponding `records/*-apply.json` |
| Owner save and routing defaults | Kept the saved PCB exactly; updated only project settings | [Settings record](records/routing-settings-review.json) |
| Full review/release attempt | Shared checks passed on the initial snapshot; five unsigned human decisions blocked release | [Review output](records/initial-layout/full-review-output.txt); [release attempt](records/initial-layout/release-attempt.txt) |

The initial accepted board used 373 explicitly constructed tracks and 106 vias,
plus 57 tracks and six vias for the four grid-routed paths. The motor load uses
wide power copper; the grid-routed VMOTOR branch supplies only its indicator.
The owner's later save added seven and removed five segments, and changed two
footprint records and both copper zones. The audited saved board has 432 tracks
and 112 vias. Do not restore original geometry merely to match historical counts.

The generic placement/intent generator did not produce this accepted layout.
An attempted Freerouting run did not produce an imported SES result. The shared
pipeline checked and installed a completed external candidate; claiming that
it autonomously designed the whole board would be inaccurate.

## Useful lessons implemented

| Rover finding | Shared pipeline or retained engineering response |
| --- | --- |
| Old recipes can overwrite manual edits | Native schematic/PCB candidates; exact preview bindings; GUI-lock and concurrent-save checks |
| DRC can miss an internally consistent wrong net assignment | Fresh schematic-to-pad parity, plus independent authored-reference net checks |
| Power-net width defaults were absent | Netclass defaults and width/via presets; advisory routing-settings review |
| Temporary routing locks obstructed owner edits | Editability check and an explicit handover convention; never silently unlock owner items |
| Old SVGs could be stamped with a new source hash | Fresh three-view export and source/image hash manifest before PDF publication |
| Failed exports could leave stale preview artifacts | Shared preview publisher removes missing outputs from the current attempt |
| Reviewing copied unrelated guide/simulation trees | Review now snapshots declared inputs only and checks for intervening owner edits |
| Scratch directories held unique research | Datasheets go to indexed evidence; curated checks go to review records |
| First-layout scripts accumulated as a second workflow | Seven obsolete authoring modules removed after preserving an independent reference and layout lessons |

The current [layout tools](../../layout/README.md) are read-only audit and
review exports. The audit exports current schematic connectivity itself. It
checks native pad membership and wrong-net assignments on surviving historical
geometry; missing or new historical geometry is a review difference, not a
command to undo the owner's reroute. Its static reference identifies the original
source and recipe hashes. It does not prove every newly added route is sensible.

Manufacturer-specific reasoning remains in [PCB design](../design/PCB_DESIGN.md),
[footprints](PCB_FOOTPRINT_REVIEW.md) and [power layout](PCB_POWER_LAYOUT_REVIEW.md).
Critical loops and returns still require engineering review; this is not an
ampacity, thermal, EMI or regeneration certificate.

## What remains, and why

Keep native CAD, local libraries and exact source evidence together. Keep the
small measured reports under `records/`; they substantiate historical claims.
Real passive simulation results remain with their model limitations clearly
marked. The superseded A3 guide was archived during the owner's 2026-10-07
cleanup; its exact source and PDF remain in that recovery archive. There is one
retained Rover project at `projects/rover-pdb`, formerly `rover-pdb-readable`.
The earlier comparison design's 68 files remain intact outside the repository at
`C:/Users/tae06/.codex/archives/pcb/rover-consolidation-20261001-114628/original-rover/`.
Consolidation preserved the current owner's saved CAD bytes and did not renew
the historical electrical or layout checks described in this audit.

Removed material includes completed draft/acceptance work trees, intermediate
boards and renders, obsolete authoring helpers, the redundant guide package,
stale screenshots and the duplicate extracted vendor model. The vendor example
can be restored from its SHA-verified source ZIP. Schematic presentation rules
now have one authority in the shared design rules; the separate A3 style memo
and duplicated layout handoff were consolidated.

Full pre-cleanup recovery is outside the repository:
`C:/Users/tae06/.codex/archives/pcb/repo-cleanup-20261001-042706/`.
Its `before-cleanup.zip` and `manifest.json` were verified before removal.
Historical script paths inside retained JSON reports describe that archive;
they are not current commands or broken runtime dependencies.

Ordinary maintenance uses `pcb-copilot clean PROJECT` to preview its narrow
allowlist, then `--apply` to remove only reproducible preview files. It refuses
active operations, unresolved recovery, path links and declared input targets.
It never recursively deletes arbitrary `.pcb-copilot` contents.

## Validation and limits

The PCB/settings snapshot identified at the start of this audit passed exact native pin/net parity and
two refilled DRC runs, each with zero errors, warnings and unconnected items.
Those results are retained in the settings record above. The cleanup did not
change native CAD or renew a human approval. Fresh review views are bound to
[review-source.json](../../output/review/review-source.json); their successful
rendering alone is not a fresh electrical check.

Before this cleanup, the broad non-slow/non-network software run reported
567 passes and one unrelated TMS fixture failure: a saved owner edit has 18
junctions while that test expects 19. The same test passes on committed TMS
sheets. The owner drawing and that test expectation were left unchanged.
Cleanup regression results and retained limitations are reported with handover.

After cleanup, the [fresh shared review](records/cleanup-review.json) passed all
ten automated checks, including ERC, exact native parity and two refilled DRC
runs with zero errors, warnings or unconnected items. Its only blocker is the
same five unsigned human decisions. The final combined cleanup/regression run
passed 81 tests; separate adapter/geometry/export runs passed 115 tests. Evidence
integrity passed for all six projects, and 87 current native CAD/library files
matched their pre-cleanup bytes. Local Markdown links were checked after moves.
