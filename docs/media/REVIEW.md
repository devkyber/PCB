# Media author inspection

Reviewed 2026-10-29 (Asia/Seoul) by Codex as the asset author. This records actual
visual inspection and source checks; it is not a named human engineering sign-off.

## Schematics and board views

All seven freshly exported Rover sheets were inspected at page and readable
circuit scale: system overview, battery/INA226, 12 V Jetson supply, 5 V servo
supply, 22.19 V motor supply, Pico/servos, and DYNAMIXEL distribution. Their
existing owner content, DNP marks and individual revision labels remain intact.
These are current native exports, not a requalification of the closed board.

The GPIO indicator's single sheet was inspected at page and circuit scale,
including all four branches, the header map, current-bound notes, visible
T-junction dots and the title block. Assembly, front copper and mirrored underside
views were inspected. The initial invisible dots were made explicit by the board
author without changing connectivity, then fresh native checks and views were run.

## Landing-page images and motion

The hero, native-CAD gallery and GPIO showcase were inspected for composition,
labels and clipping. The social image was refitted to a 1280 × 640 canvas after
the initial crop clipped its footer; the final footer and margins were inspected.

The four workflow scenes were checked against the captured command results:
archive verification, real missing-preview rejection and the actual 12/14 Rover
review with datasheet/sign-off blockers. The 48-view GPIO turntable comes from
native renders; its views retain common scale/framing and prototype labels.
The GIF/MP4 files were decoded and their displayed frames inspected. Models are
visualization aids, not evidence of a manufactured board or actual package fit.

## Scoped-change proof

The final one-page preview and circuit detail were inspected before the
disposable apply. The exact reviewed PDF hash is
`c851d75a6a605b8058d269924d2c9db5ff0cdacb90f9818b316d349690fdd473`.
The short `DEMO-P2` revision fits the title block. An earlier appended revision
clipped and was rejected; that packet was never applied.

The completed [proof](change-proof.md) records preview success, stale apply
rejection, fresh preview success and reviewed apply success. Native electrical
inventories agree; only the disposable schematic revision changes and its PCB
bytes remain unchanged. All 439 pre-existing Rover/TMS project files checked
against the session's byte hashes remained unchanged.

Source and output byte identities are in [the Rover manifest](manifest.json),
[example manifest](example-manifest.json) and [proof manifest](proof-manifest.json).
Hardware qualifications and human release decisions remain open; no fabrication
release or owner signature was created.
