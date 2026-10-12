# Rover PDB: JLCPCB component orientation audit

Inspected 2026-10-06 (Asia/Seoul). Board A10 / PCB P5. This records the supplied
preview before correction, not fabrication sign-off. The subsequent local fixes
are described below; a new JLCPCB upload review is still required.

## Corrections in the pipeline

Exact-part export rules now apply U1 -90 degrees (CPL 270) and J2/J3/J4/J8 -90
degrees (CPL 0). Native footprint angles and routed copper are preserved. Rules
cover all 71 assembled references across 25 exact parts; the five corrected
placements remain `derived_from_preview`, and L3's vendor orientation remains
`unverified`, until the new upload is inspected.

P2/P3/P4 labels now resolve from the adjacent pad's actual net. This fixes P3:
upper pad 2 = +12V, lower pad 1 = GND. The reusable output-pad footprint uses the
same net variables. L3 has a local datasheet-derived maximum-envelope STEP model
with explicit dimensions and simplifications; its independent JLCPCB model is
still absent from the previously inspected supplier preview.

See [causes, safeguards and manual instructions](../../../../docs/JLCPCB_ASSEMBLY.md).
The findings/table below retain the original preview observations for comparison.

### Applied-board validation, 2026-10-06

- Native candidate preview/apply completed with zero blocking findings. Final
  ERC: 0 violations. Final DRC: 0 errors, 0 warnings, 0 unconnected in two
  zone-refilled runs. Independent dated JLCPCB DFM baseline passed.
- All seven schematic files are byte-identical to the saved baseline. The
  candidate retained all 449 track segments, 168 vias and nine zones exactly;
  all 93 footprint positions, pad geometry/nets, properties and UUIDs were retained.
- The candidate silk plot and final native 3D render were visually inspected.
  P3's upper +12V/lower GND and L3's horizontal terminal axis are clear. Labels
  meet the project's 1 mm height minimum. These are local CAD views, not a
  verification of the corrected supplier upload.
- Targeted regression run: 78 passed (four slow tests excluded). A subsequent
  41-test assembly/export/release run, including native export/gate tests, passed.
  These suites overlap; do not add their counts as unique tests.
- The complete five-board preview was rebuilt through `release --preview
  --quantity 5`: nine Gerber layers, PTH/NPTH drills, 71 matching BOM/CPL
  designators, 25 part groups, drawings, STEP/render and hash manifests. Every
  published output hash and the Gerber ZIP integrity were checked.
- Stock fetched at 2026-10-06 00:37 KST: L3 C54431777 had 987, demand five.
  SW1 C226259 had zero, demand five; other 24 groups met this retail quantity
  check. LCSC retail stock does not establish JLCPCB assembly allocation.
- Fabrication remains blocked: supplier placement review is absent for the new
  upload, SW1 has the retail shortage, and five engineering decisions are unsigned.

**Five assembly orientations are wrong in the supplied/live preview: U1, J2, J3, J4 and J8. Sixty-five other assembly components look correctly oriented. L3 is unverified because its body/model is missing. P3 has a separate, confirmed reversal of its printed power labels.**

All directions below use the top view with BATTERY at the top and DATA IN / LEFT / HAMMER / RIGHT at the bottom. The inventory covers all 71 CPL components and all 22 other native footprints.

[Original user-supplied preview, preserved without alteration](../../evidence/assembly/orientation-preview-2026-10-06.png)

## Findings requiring action

| Reference | Observed problem | Required result |
| --- | --- | --- |
| U1 / INA226AIDGSR / C49851 | JLC model leads face up/down; PCB pads face left/right. The model pin-one dot is lower-left; native pad 1 and the board triangle are upper-left. | Rotate the displayed part **90 degrees clockwise**, so pin 1 is upper-left and all ten leads lie over the two pad rows. |
| J2, J3, J4, J8 / TSW-103-07-G-S / C3335811 | Each displayed three-pin header is vertical across a horizontal row of PCB holes. | Rotate each displayed header **90 degrees**, placing all three pins on its own horizontal hole row. The board connections are **signal, +5 V, GND from left to right**. These unshrouded straight headers are physically equivalent after a further 180-degree turn. |
| P3 / 12V AUX | The upper pad is actually +12 V, but its silk says GND. The lower pad is actually GND, but its silk says +. | Correct the printed labels to match the saved copper, or resolve any intended circuit change separately. Do not follow the current labels when wiring. A CPL edit cannot fix printed Gerber labels. |
| L3 / APS1365M3R3DW / C54431777 | No visible component body/model. | Check terminal registration in a usable supplier/engineering preview: both terminations must face left/right. It is nonpolar. The live BOM has this exact part selected, quantity 5 for this order, so the blank model does not by itself mean it was omitted from the order. |

P3 was independently read using KiCad 10 pcbnew as well as the s-expression parser: pad 2 at (104.700, 107.400) mm is +12V; pad 1 at (104.700, 116.400) mm is GND. Embedded F.Silkscreen text GND is at (108.884829, 107.800) mm; the + text is at (108.900, 116.400) mm. KiCad Y increases downward.

## Assembly-export correction, not a PCB rotation

The native footprints are already aligned with the saved routed pads. The old
exporter adjusted selected component centers but passed through native KiCad
angles, without exact-part JLC rotation corrections. JLC documents that its
zero-degree orientation can differ from the CAD library, and that positive CPL
angles are counterclockwise.

The following correction targets are now applied by the local exporter. They have
not been re-uploaded to JLCPCB; the resulting supplier preview needs verification.

| Reference | Current local CPL angle | Derived JLC CPL angle | Offset |
| --- | ---: | ---: | ---: |
| U1 | 0 | 270 | -90 degrees |
| J2 | 90 | 0 | -90 degrees |
| J3 | 90 | 0 | -90 degrees |
| J4 | 90 | 0 | -90 degrees |
| J8 | 90 | 0 | -90 degrees |

When correcting it manually, select just the affected part(s) in JLC Component Placements and use the control for rotating individual parts about their own centers. Check pin 1 and every lead/hole afterwards. Do not use group rotation around a shared center, which would move the parts. A reusable exporter correction must be bound to the exact part and footprint, then verified in the new JLC preview.

## Every assembly component

Looks correct means the visible terminal axis and any visible pin/polarity/keying marks agree with the saved board. It does not certify hidden leads, dimensional tolerances or the factory machine program. Ordinary resistors, ceramic capacitors and these two-terminal inductors have no electrical polarity: upside-down reference text or a 180-degree end-for-end reversal is harmless, provided the terminals align.

| Ref | Exact part / LCSC | Result | Orientation check |
| --- | --- | --- | --- |
| C1 | EEU-FR1H221B / C1579630 | Looks correct | Positive left, negative/striped side right; agrees with native pad 1 positive and pad 2 GND. |
| C2 | EEU-FR1C471B / C1579437 | Looks correct | Positive left, negative/striped side right; agrees with native pad 1 positive and pad 2 GND. |
| C3 | CL21B104KBCNNNC / C1711 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C5 | EEU-FR1H221B / C1579630 | Looks correct | Positive left, negative/striped side right; agrees with native pad 1 positive and pad 2 GND. |
| C10 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C11 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C12 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C13 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C14 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C15 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C16 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C17 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C18 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C19 | GRM32ER71H106KA12L / C77102 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C20 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C21 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C22 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C23 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C24 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C25 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C26 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C27 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C28 | CL32B226KAJNNNE / C309062 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C30 | CL21B104KBCNNNC / C1711 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| C31 | CL21B104KBCNNNC / C1711 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| C32 | CL21B104KBCNNNC / C1711 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| C33 | CL21B104KBCNNNC / C1711 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C34 | CL21B104KBCNNNC / C1711 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C35 | CL21B104KBCNNNC / C1711 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C39 | CL10C330JB8NNNC / C1663 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C40 | CL10C330JB8NNNC / C1663 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| C41 | CL10C330JB8NNNC / C1663 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| D2 | KT-0805G / C2297 | Looks correct | Anode + left, cathode - right; JLC polarity overlay agrees with native LED_A / GND pads. |
| J1 | B4B-EH-A(LF)(SN) / C160258 | Looks correct | Horizontal pin row; circuit 1 / GND at left, locking side toward bottom board edge. Body/keying direction matches silk and JST drawing. |
| J2 | TSW-103-07-G-S / C3335811 | WRONG | 90-degree turn required; three pins must be horizontal over S / +5V / GND. |
| J3 | TSW-103-07-G-S / C3335811 | WRONG | 90-degree turn required; three pins must be horizontal over S / +5V / GND. |
| J4 | TSW-103-07-G-S / C3335811 | WRONG | 90-degree turn required; three pins must be horizontal over S / +5V / GND. |
| J5 | B4B-EH-A(LF)(SN) / C160258 | Looks correct | Horizontal pin row; circuit 1 / GND at left, locking side toward bottom board edge. Body/keying direction matches silk and JST drawing. |
| J6 | B4B-EH-A(LF)(SN) / C160258 | Looks correct | Horizontal pin row; circuit 1 / GND at left, locking side toward bottom board edge. Body/keying direction matches silk and JST drawing. |
| J7 | B4B-EH-A(LF)(SN) / C160258 | Looks correct | Horizontal pin row; circuit 1 / GND at left, locking side toward bottom board edge. Body/keying direction matches silk and JST drawing. |
| J8 | TSW-103-07-G-S / C3335811 | WRONG | 90-degree turn required; three pins must be horizontal over S / +5V / GND. |
| L1 | SRP1265A-6R8M / C2041326 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| L2 | SRP1265A-4R7M / C780205 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| L3 | APS1365M3R3DW / C54431777 | UNVERIFIED | No visible model. Nonpolar; terminations must be left/right. Exact part selected in live BOM. |
| R1 | RC0805FR-074K7L / C60816 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| R2 | RC0805FR-074K7L / C60816 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| R3 | RC0805FR-0710KL / C84376 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R4 | RC0805FR-0710KL / C84376 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R5 | RC0805FR-0710KL / C84376 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R6 | RC0805FR-0710KL / C84376 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R10 | RC0805FR-07100KL / C96346 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R11 | RC0805FR-07100KL / C96346 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R12 | RC0805FR-07100KL / C96346 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R13 | RC0805FR-07100KL / C96346 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| R14 | RC0805FR-07100KL / C96346 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| R15 | RC0805FR-07100KL / C96346 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| R16 | 0805W8F1912T5E / C17508 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R17 | 0805W8F7151T5E / C17806 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R18 | 0805W8F3741T5E / C65649 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R19 | RC0805FR-07100KL / C96346 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| R20 | RC1206FR-073K9L / C137289 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R21 | 0805W8F1001T5E / C17513 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R22 | 0805W8F1001T5E / C17513 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R23 | 0805W8F1001T5E / C17513 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| R24 | 0805W8F2202T5E / C17560 | Looks correct | Nonpolar; visible terminals and PCB pads both face up/down. 180-degree reversal is harmless. |
| RS1 | CSS2H-2512K-2L00F / C2093761 | Looks correct | Nonpolar; visible terminals and PCB pads both face left/right. 180-degree reversal is harmless. |
| SW1 | OS102011MA1QN1 / C226259 | Looks correct | Body horizontal; actuator faces top board edge. Native pin 1 is right, pin 2 center, pin 3 left. |
| U1 | INA226AIDGSR / C49851 | WRONG | 90 degrees clockwise required; pin 1 upper-left, leads left/right. |
| U2 | LMR51450SDRRR / C6890985 | Looks correct | Pin-one dot upper-left; six terminals on each of the left/right sides. Matches TI top-view pinout. |
| U3 | LMR51450SDRRR / C6890985 | Looks correct | Pin-one dot upper-left; six terminals on each of the left/right sides. Matches TI top-view pinout. |
| U4 | LMR51450SDRRR / C6890985 | Looks correct | Pin-one dot upper-left; six terminals on each of the left/right sides. Matches TI top-view pinout. |

## Remaining footprints and intentionally absent parts

| Ref | What it is | Assessment |
| --- | --- | --- |
| FID1 | Fiducial | Optical fiducial copper feature, not an assembled part; rotation irrelevant. |
| FID2 | Fiducial | Optical fiducial copper feature, not an assembled part; rotation irrelevant. |
| FID3 | Fiducial | Optical fiducial copper feature, not an assembled part; rotation irrelevant. |
| H1 | MountingHole_3.2mm_M3 | M3 mounting hole, not an assembled part; rotation irrelevant. |
| H2 | MountingHole_3.2mm_M3 | M3 mounting hole, not an assembled part; rotation irrelevant. |
| H3 | MountingHole_3.2mm_M3 | M3 mounting hole, not an assembled part; rotation irrelevant. |
| H4 | MountingHole_3.2mm_M3 | M3 mounting hole, not an assembled part; rotation irrelevant. |
| J9 | EXP / DNP | Intentionally DNP expansion header. If fitted later: pin 1 / 3V3 at bottom, pin 6 / GND at top. |
| NT1 | AGND tie | Copper net tie, not an assembled part; no body or placement orientation. |
| NT2 | AGND tie | Copper net tie, not an assembled part; no body or placement orientation. |
| NT3 | AGND tie | Copper net tie, not an assembled part; no body or placement orientation. |
| P1 | BATTERY IN | Bare wire pads, no factory body. Positive left, GND right; printed labels agree. |
| P2 | JETSON / BARREL | Bare wire pads, no factory body. GND upper, +12V lower; printed labels agree. |
| P3 | 12V EXP / UNWIRED | WRONG SILK: upper pad +12V, lower GND; current printed labels are reversed. |
| P4 | 5V EXP / UNWIRED | Bare wire pads, no factory body. GND upper, +5V lower; printed labels agree. |
| SKT1 | Pico 2 / 2x20 sockets | Intentionally manual-fit Pico sockets. No model expected in factory assembly. Pico USB end belongs at the top; pad 1 is upper-left. |
| TP1 | VBAT | Bare test-point pad, not an assembled part; rotation irrelevant. |
| TP2 | VMOTOR | Bare test-point pad, not an assembled part; rotation irrelevant. |
| TP3 | +12V | Bare test-point pad, not an assembled part; rotation irrelevant. |
| TP4 | +5V | Bare test-point pad, not an assembled part; rotation irrelevant. |
| TP5 | +3V3 | Bare test-point pad, not an assembled part; rotation irrelevant. |
| TP6 | GND | Bare test-point pad, not an assembled part; rotation irrelevant. |

## Evidence and scope

- Inspected the supplied image and the live JLC Component Placements view in 2D, using selection/zoom for lead and polarity checks. The live Bill of Materials showed all 25 part groups confirmed, including L3 / C54431777. No rotation/position edit or purchase was made.
- [INA226 manufacturer datasheet, page 3](https://www.ti.com/lit/ds/symlink/ina226.pdf): top-view pin numbers and orientation.
- [LMR51450 manufacturer datasheet, page 3](https://www.ti.com/lit/ds/symlink/lmr51450.pdf): WSON pin map; the retained project PDF was used.
- [Kento KT-0805G manufacturer drawing, page 2](../../evidence/files/KT-0805G_de342fde3322df0797012cd7a04e2194_853e6752f600.pdf): anode 1 and cathode 2 marking.
- [JST EH manufacturer drawing, pages 2 and 4](https://www.jst-mfg.com/product/pdf/eng/eEH.pdf): pin 1 and locking side, viewed from the mounting surface.
- [Existing footprint review and retained drawings](PCB_FOOTPRINT_REVIEW.md): exact capacitor, inductor, switch, shunt and connector geometry.
- [JLC orientation/marking FAQ](https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2): different zero orientations and interpretation of plus/minus markings.
- [JLC CPL specification](https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly): positive rotation is counterclockwise.

The native PCB and all seven schematic files match the manufacturing preview manifest. The local BOM and CPL also match their output hashes. The current .kicad_pro differs from that old manifest; this inspection does not renew the previous complete release check.

| Audited input | SHA-256 |
| --- | --- |
| Native PCB | `66929103bf0c38b567745b3df253a7b00421f4ce7b72103dd865abccc4b490cd` |
| BOM | `1c051c9020bcfb9c131686bbf6781a4b72ed9643d4d04e372deb1a53e0ab6887` |
| CPL | `6f49041727910565369a1909fe99600f757a40acdc7cf167b2b5b54e222efb07` |
| Supplied image | `1d33af553ef092a0453bc28f149b4657ea2d99d1489f5734b8fe7514d631e7ba` |
