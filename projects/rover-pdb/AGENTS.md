# Owner-controlled schematic

Current revision: **A10, 2026-10-04**. This is the single active Rover PDB project,
renamed from `rover-pdb-readable`. Its earlier comparison design is archived
outside the repository; never restore that design over owner edits. Follow the root workspace
protocol and `docs/DESIGN_RULES.md`, including the owner's adopted Gala/Gross
schematic conventions. Do not use Superpowers.

## Current electrical decisions

- The owner requested removing F1 on 2026-10-04. P1 positive now connects
  directly to RS1 on BAT_SWITCHED; there is no onboard battery fuse. Do not
  restore F1 or VBAT_FUSED from old intent. An external battery fuse remains
  recommended, but its presence, selection and coordination are unverified.
- U2-U4: LMR51450SDRRR / C6890985, RT open for nominal 500 kHz.
- L1=6.8 uH; L2=4.7 uH / SRP1265A-4R7M / C780205;
  L3=3.3 uH / Coilank APS1365M3R3DW / C54431777 (stock substitution 2026-10-05).
- 12 V: four 22 uF C20-C23. 5 V: five C24-C28 plus C2 bulk.
  Motor: four 10 uF C16-C19 plus C5 220 uF. Each input retains two 10 uF
  plus 100 nF. Do not restore historical counts or inductors.
- Motor enable: local VBAT -> R19 100k -> SW_SUPPLY, with R24 22k from
  SW_SUPPLY to AGND_4; SW1 pin 1=SW_SUPPLY, pin 2=MOTOR_EN, pin 3=NC.
  R15 100k pulls MOTOR_EN to AGND_4. Do not restore the former +5V drive.
- SW1 and the indicator are on the motor sheet. JP1 remains removed. The owner has reused J8 for SERVO AUX, with R6 10k; preserve both.
  R20=3.9k / 0.25W / 1206, RC1206FR-073K9L / C137289.
- Pico 2 is USB-only. Q1 is removed; carrier pins 39/40 are NC.
  Do not restore the superseded PDB-backup power path.
- J9 is an optional DNP 1x6 header, BOOMELE / C37208: pin 1=3V3,
  2=GP18, 3=GP19, 4=GP20, 5=GP21, 6=GND. DNP is intentional.

See `DESIGN_BASIS.md`, `docs/design/POWER_DECISIONS.md`, `docs/design/OUTPUT_FILTER_SELECTION.md`
and `docs/design/MOTOR_FILTER_SELECTION.md` for calculations and evidence. Historical
guide examples and the initial handover do not override current native CAD.

## Owner edits and authorized PCB stage

The owner reported personally reviewing A8 and finding it satisfactory, then
requested final changes and repository cleanup. That report is not a named,
hash-bound fabrication sign-off or a waiver of engineering checks. A9's
changed circuitry has separate author verification; do not attribute that
review to the owner without further evidence.

The root `.kicad_sch` files are the source of truth. Never regenerate,
replace, restore, normalize, annotate or otherwise write them unless the user
explicitly requests that specific schematic change in the current conversation.
Do not infer schematic write permission from a later request to make the PCB.

Read the current schematic and every child sheet before subsequent work.
Treat `schematic-intent.yaml` and `netmap.json` as derived snapshots that can
become stale: reconcile them FROM current CAD, never in the other direction.
For an authorized scoped schematic edit, use a native candidate copied from
the current saved hierarchy; do not regenerate it from YAML. Preserve PCB owner
edits in the same way. Read-only requests must not save either CAD file. Save and
close KiCad before external application, then reopen it. Preview and apply must
use identical input hashes; an intervening owner save requires a new preview.
Preserve UUIDs, references, wires, values and placement during authorized
edits. Back up or use a Git diff before changing CAD. Use pcb-copilot's
scoped native-candidate preview/apply workflow with explicit `--apply` and inspect every
rendered sheet before handover. A clean ERC does not replace visual review.

On 2026-10-01 the owner explicitly requested PCB design through completion.
The owner subsequently requested the smallest practical width. Their later
saved outline, reconciled on 2026-10-05, is 77.5 x 100 mm with square corners;
this supersedes the earlier 80 x 100 mm layout target. Retain four M3 mounting holes,
two copper layers with 1 oz copper, and surface wire-solder pads. See
`docs/design/PCB_DESIGN.md` and `REQUIREMENTS.md` for the layout and review contract.
The earlier stop-before-layout boundary is superseded; the restrictions on
owner-edited schematics remain in force. A footprint-field edit requires its
own scoped authorization and must preserve the circuit and other owner edits.

Create and check the layout candidate, then install it with pcb-copilot
`update-layout --candidate ... --apply`. Preserve the current circuit. Read
`docs/design/PCB_DESIGN.md` for the consolidated routing checklist and source map.
Do not fabricate human approval or bypass `release`. Detailed design notes and
retained historical reports now live under `docs/design/` and `docs/review/`;
start from README.md to find them. Old construction scripts were removed after
retaining their useful checks; no recipe may regenerate this existing board.
