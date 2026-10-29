# A1 author inspection record

Codex, 2026-10-29. **Author inspection only; no owner or fabrication approval.**

The inspected native schematic is the one-sheet A4 root
`rs485-interface.kicad_sch`, revision A1 DRAFT. The corresponding PCB has
13 footprints (nine purchased components plus four fabricated NPTH holes),
two copper layers and a 50 x 35 mm outline. The removable shunt is a separate
accessory, not a permanent PCB connection or installed 3D body.

## Actual visual inspection

Inspected the final exported PDF/PNG at full-page scale and its circuit crop
at readable circuit scale. Checked left host-interface boundary, functional
eight-pin transceiver arrangement, directly wired local bypass/ground returns,
separate enable pulls, visible T-junction dots, explicit open termination
header, A/B/GND interface, title/revision, source notes and on-sheet assumptions.
Repaired visible power-reference noise, capacitor field collisions, rotated
jumper fields, mounting-hole field overlap and the bus-value/ground-text clash.
The final page is legible without wire/text crossings in those inspected areas.

Inspected native assembly, front copper/silkscreen, **mirrored** back copper/
silkscreen, and the high-quality transparent native 3D render. Checked the U1
pin-1 marker, J1 direction and 3V3 labels, J2 A/B ordering, removable termination
location, mounting access, visible copper endpoints and filled GND return plane.
Repaired two overlapping silkscreen captions and shortened a vertical shunt
legend that appeared clipped in the original plot. Generic official models are
visualization aids, not actual-part fit approval. No shunt is shown installed.

## Fresh software observations

- Native KiCad 10.0.6 ERC: zero violations, no exclusions or waived pin warnings.
- Native DRC: zero errors, warnings or unconnected items. Full review repeats
  two refilled DRC runs and independently checks the dated JLCPCB geometry.
- Exact native component/pin-net membership and schematic UUID-link parity pass.
- All 13 native footprint references resolve with real declared geometry;
  strict official-copy receipts and model/source hashes pass. Physical fit is false.
- Full selected-part source verification covers all nine purchased components,
  including the passives/headers, with exact manufacturer MPN associations.
- Shared placement tracking found no remaining component overlap, off-board
  placement or missing-geometry fallback. C1 was rotated beside U1 to clear the
  conservative shared envelope while retaining a short bypass connection.
- Removed two redundant covered track segments and a tiny pad step found by
  the routing-topology review. Current routing settings/topology have no advisories.
- Current full review: **12/14 checks pass**. Assembly contracts are missing for
  nine components; all five local/shared human decisions remain unsigned.
- A real public `update-schematic --candidate` preview succeeded on a fresh
  external exact snapshot. Source, snapshot and candidate inputs stayed unchanged,
  no schematic links were added, and no apply or human approval was performed.
  Its actual logs and binding are retained in `output/native-preview-proof.json`.

## Remaining engineering work

Actual host power sequencing, GPIO thresholds/leakage/reset states, part and
header/shunt fit, component orientation and supplier assembly placement,
fast-edge signal integrity on the chosen cable, termination/loading, bus-fault
behavior, ground offsets, thermal and current-limited bench measurements are
open. There is no measured link rate, isolated barrier, board surge/ESD/EMC
qualification, signed human decision or manufacturing package.

Exact reviewed CAD and output identities are recorded by
[`output/SOURCE.json`](../../output/SOURCE.json), alongside fresh raw native
reports and command logs. If those inputs change, inspect current renders again;
this author record must not be reused as an owner release decision.
