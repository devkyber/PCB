# Revision B author inspection — 2026-10-29

Reviewer: Codex, acting as schematic/layout author. This is an **unbuilt
educational DRAFT**, not a human release decision, measured result, mechanical
qualification or permission to fabricate. All six human decisions remain unsigned.

## Connector correction

J1 is now GCT USB4125-GF-A, the six-contact power-only receptacle with a
1.00 mm shell stake. The GCT A6 drawing and A3 specification are archived as
exact manufacturer bytes. The drawing's 0.60 × 1.20 mm plated shell slots inside
1.10 × 1.70 mm copper provide 0.25 mm annular rings. There are no locating-peg
NPTHs. The official KiCad footprint preserves those lands and holes exactly;
only its declared model URI changes to pinned project-local bytes.

This resolves the original eight USB4105 geometry findings by changing the
selected connector, rather than relaxing rules, trimming specified contact
lands, adding exclusions or supplying a waiver. The original drawing is cited
in DESIGN_BASIS.md to explain the comparison; superseded library/model copies
were removed only after a full external backup was hashed and verified.

## Scoped native update and preservation

The external candidate started from the saved revision-A native CAD. J1 and
eight local escape tracks were replaced; all seven existing vias, fifteen other
segments, four outline edges, mounting holes, and other nine footprint
geometries/placements/identities were retained. All fifteen unrelated schematic
instances are unchanged. J1's schematic/footprint UUID and native path remain
linked. The project settings and custom rules are byte-identical to revision A.

KiCad made the existing 0.15 mm font default explicit in fourteen hidden MPN/
Manufacturer fields while serializing the PCB. Those presentation metadata
changes are recorded separately; no unrelated pad, copper or placement changed.
[Preservation comparison](../../output/revision/preservation-verified.json)
and [local copper receipt](../../output/revision/copper-preservation.json)
record the checked scope.

The public paired native-candidate preview returned exit 0. Its one-page PDF,
layout SVG and native 3D candidate were inspected before the identical matching
apply returned exit 0. The sole advisory finding concerns STEP/model completeness;
F1 still intentionally has no body model. [Raw preview](../../output/revision/preview.stdout.json)
and [apply](../../output/revision/apply.stdout.json) retain the actual results.
No construction recipe was replayed over the saved design.

## Final visual inspection

The final root sheet `/`, titled **USB-C 5 V bench power entry**, revision B,
was inspected again from native PDF/PNG at page scale and enlarged input/CC
circuit scale. The six-contact symbol, manufacturer pin allocation, separate
5.1 kOhm CC branches, real source power flags, visible junction dots, series
fuse, TVS polarity, LED path, J2 directions and on-sheet assumptions were checked.
Ten existing junction dots remain explicitly visible at 0.9144 mm diameter.
There are no data/SBU contacts or obsolete no-connect markers on the replacement.

The final assembly, front copper, mirrored underside and transparent native
3D PNG were inspected. J1 faces the unchanged board edge; its new contact
escapes reach their actual pad anchors without joining the CC branches.
The original lower-layer VBUS bridge and GND pour remain; the fuse/output/TVS/
LED circuits retain their geometry. Reference labels, output pin labels, mounting
holes and DRAFT legend remain legible. F1's absent 3D body is visible as pads.
These observations do not qualify soldering, fit, thermal behavior or cable forces.

## Actual checks and limits

| Check | Result |
| --- | --- |
| Fresh native ERC | 0 violations; exit 0. |
| Fresh native refilled DRC | 0 errors, 0 warnings, 0 unconnected; violation-sensitive exit 0. |
| Independent dated JLCPCB geometry | Pass under the unchanged workspace profile. |
| Exact native schematic/PCB parity | Parts, values, footprint IDs, pin-net sets and forward-annotation paths agree. |
| Local footprint receipts | All 10 references resolve; lineage/pad coverage only, physical fit unqualified. |
| Purchased-part evidence | All 8 purchased parts have exact selected-MPN manufacturer coverage; H1/H2 are fabricated features. |
| Archive integrity | Indexed source bytes verify, including the new GCT documents. |
| Routing settings / topology | 28 straight tracks, 7 vias, no locks or topology findings. No ampacity conclusion is implied. |
| Registered review | 12/14 pass; exit 1 for missing supplier assembly contracts/F1 body model and unsigned human decisions. |

Checks and native exports ran on a new disposable external copy. The complete
63-entry input ledger and all retained output byte counts/hashes are bound in
[SOURCE.json](../../output/SOURCE.json). Saved source and disposable input
hashes matched before/after those operations. The manifest binds this dated
result; a later source edit requires fresh checks and renders.

The 4.75–5.25 V source and 500 mA total application budget are unchanged and
must be separately qualified. No PD or advertised-current detector, active
limiter, regulator, reverse blocking or inrush control was added. The 0.75 A
PPTC is not a 500 mA limiter and the TVS clamp is not 5 V overvoltage protection.
Physical fit, reflow/assembly, source/load/cable behavior, PPTC fault/recovery/
thermal behavior, TVS coordination and all human release decisions remain open.
