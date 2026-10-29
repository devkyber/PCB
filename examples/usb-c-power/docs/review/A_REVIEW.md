# Revision A author inspection — 2026-10-29

Reviewer: Codex, acting as schematic/layout author. This is **not a human
release decision**, physical qualification, measured result or fabrication
approval. Lifecycle remains DRAFT and no review-signoff file is supplied.

## Inspected sheets and views

The single root sheet `/`, titled **USB-C 5 V bench power entry**, was inspected
from the final native PDF/PNG at full-page scale and at readable circuit scale.
The USB/CC and LED/output regions were separately inspected in enlarged native
PDF renders. The title, date, revision, on-sheet operating assumptions,
intentional data/SBU no-connects, visible local CC branches, source power flags,
series fuse, TVS polarity, LED path and J2 pin allocation were checked.

The last presentation corrections made horizontal fields legible, moved the
LED value clear of its symbol and raised output assumptions clear of the title
block. Native pin-to-net membership and symbol UUIDs were preserved for field
edits; the final schematic/PCB parity check includes forward-annotation paths.
No electrical change was made to hide a layout finding.

A subsequent drawing review found that the ten existing junction nodes had
zero diameter and were invisible in the native PDF. Their diameters are now
explicitly0.9144 mm. The candidate AST differed only at those existing diameter
values; wire topology, junction/symbol UUIDs, component properties, no-connects,
native pin-net membership and PCB bytes were preserved. The public native
schematic preview returned exit0 with no findings; its complete page and VOUT
branch detail were visually inspected before the matching apply returned
exit0. [Preview/apply receipts](../../output/revision/revision.json) retain the
actual command results. The final native PDF/PNG were inspected again at page
and circuit scale, confirming visible VOUT and GND junction dots. That scoped
drawing acceptance does not clear the eight existing PCB manufacturing errors.

The final native front-copper, mirrored underside, assembly drawing and native
3D PNG were inspected. The USB front edge aligns with the board edge; CC1/CC2
remain separate; the VBUS bridge is on the bottom layer; the top fuse/output
trunk, LED branch and TVS-to-ground-via connection are visible; the bottom GND
pour is continuous around those routes. References, output labels, mounting
holes and the DRAFT legend were checked. The absent F1 body is visible as pads
in the 3D view and is deliberately documented. These observations are not
current-capacity, mechanical, thermal, transient or assembly qualification.

## Actual software results

| Check | Actual result / boundary |
| --- | --- |
| Native KiCad ERC | 0 violations; process exit0. |
| Native refilled DRC | 8 errors, 0 warnings, 0 unrouted; explicit violation-sensitive process exit5. |
| Independent dated JLCPCB geometry check | Same8 connector findings; remains blocked. |
| Exact native schematic/PCB parity | Parts, values, footprint IDs, pin-net sets and schematic UUID paths agree. |
| Local footprint receipts | All10 physical references resolve; exact official copies for9 instances, manufacturer-derived F1 lands for1. Lineage/pad coverage only, physical fit unqualified. |
| Exact purchased-part coverage | All8 purchased physical parts have matching selected-MPN manufacturer evidence; H1/H2 are fabricated NPTH features. |
| Archive integrity | All indexed source bytes verify. |
| Adafruit reference pair | Pinned rev-B Eagle pair:24 compared numbered pad memberships, no mismatches. This checks the reference pair, not this board's physical fit or DRC. |
| Routing state / topology | 23 straight tracks,7 vias,0 locks; shared topology audit reports no findings. Native routing widths/classes/presets are retained. |
| Registered review | 10/14 checks pass; process exit1. DRC, JLCPCB DFM, assembly contracts and sign-off remain blocked. |

The eight J1 native errors are exactly four `annular_width` findings
(0.20 mm shell rings versus0.25 mm recommended baseline) and four
`hole_clearance` findings (0.1944 mm GND-pad/peg-hole clearance versus0.25 mm
baseline). The GCT drawing's specified contact solder area and hole geometry
were retained. There are no rule relaxations, DRC exclusions or waiver rows.

## Preserved sources and remaining work

All checks/renders ran on a disposable external copy of the declared inputs.
The complete source input hash map, native version, command exits, unedited
logs and retained output hashes are in [SOURCE.json](../../output/SOURCE.json).
Both source and disposable input hashes were compared before/after and remained
unchanged. The manifest binds this dated result; edits require fresh checks and
renders. Exact results are in [review-a.json](../../output/review-a.json),
[erc.json](../../output/erc.json), [drc.json](../../output/drc.json) and
[parity.json](../../output/parity.json).

Before fabrication, resolve the connector land/fabricator conflict and obtain
the project-specific assembly and human decisions. Qualify actual source
advertisement/budget, cable/load inrush, PPTC derating/trip/recovery, TVS pulse
and prolonged-fault behavior, downstream voltage tolerance, physical fit,
reflow/hand-assembly sequence, mounting clearance and LED usefulness. No hardware
has been built or measured. The 500 mA budget, 0.75 A PPTC hold value and TVS
clamp voltage must not be conflated with safe system protection or USB approval.
