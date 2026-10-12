# PCB footprint review

Author drawing review, 2026-10-01. This records geometry inspected for the
new PCB; it does not claim physical sample fitting or owner fabrication
approval. Native schematic values, nets and pin numbering remain authoritative.
The library review was followed by the separately authorized assignment of
12 native instance Footprint properties, including the owner's surface-wire
pads P1–P4. This used the scoped draft/review/accept transaction with explicit
`--apply`. `records/FOOTPRINT_ASSIGNMENT_REVIEW.json` records the before/after hashes:
every other schematic byte, all native pin-to-net membership and all seven
rendered page pixel hashes were unchanged. Native ERC reported zero violations.
The schematic intent, BOM and netmap were reconciled from this accepted CAD;
the pre-assignment originals are retained in the transaction backup.

## A10/P5 current additions, 2026-10-04

F1 is removed from the active schematic and PCB at the owner's request. The
holder dimensions below are historical evidence, not a current purchase or fit
requirement. Other land patterns and all retained component placements remain.

SKT1's forty copper pads were already present; its missing 3D socket bodies
were caused by absent model associations. P5 attaches two installed official
KiCad `PinSocket_1x20_P2.54mm_Vertical.step` models, at offsets (0,0,0) and
(17.78,0,0), scale 1 and rotation 0. The model SHA-256 is
`67a3d0f947fe942d90f24443ba7223e7a1eb2f68d501fe478af50aaadb16e107`.
The shared local footprint receives only these two model nodes; its remaining
parsed geometry and properties are unchanged. SKT1 remains fitted manually,
excluded from automatic BOM/positions and not DNP.

This is a generic display model, 50.8 x 2.54 x 8.5 mm, not an exact LXWCONN
mechanical model. The selected drawing gives 51.3 +/-0.3 x 2.5 +/-0.15 mm and
8.5 +/-0.15 mm height; use its maximum envelope for mechanical clearance.
Official Pico 2 Figures 3 and 4 match all forty carrier positions: 2.54 mm pitch,
17.78 mm row spacing, 48.26 mm pin span and USB toward negative Y. The 21 x
51 mm module body has no overlapping surrounding component bounds in plan
view. The actual socket contact engagement and USB cable are still unverified;
the selected socket drawing does not specify contact engagement depth.

P1-P4 remain solid surface lands. Added nearby vias are tented on both faces
and outside solder/paste apertures, with useful copper on both layers. They
are not wire-insertion holes or a substitute for cable restraint.

## Historical assignments and checked geometry

All coordinates below are millimetres in the unrotated footprint, viewed from
the component side. Board placement rotates the whole footprint and its pad
mapping together.

| References | Footprint | Drawing comparison / disposition |
| --- | --- | --- |
| U2–U4 | `rover:LMR51450_DRR_WSON12_3x3` | Retain. TI DRR0012G copper/paste dimensions match: body 3 × 3; perimeter lands 0.62 × 0.25 at x=±1.39, pitch 0.50; EP13 1.30 × 2.50. The two EP paste windows are 1.21 × 1.10 at y=±0.65, about 82% coverage. |
| L1–L3 | `rover:SRP1265A_LeadFrame_13.5x12.5_P11.1` | New local SMD footprint, replacing the imported value-specific name. Bourns recommends 14.2 outside span, 8.0 inner gap, 5.0 pad height: each land is therefore 3.10 × 5.00 at x=±5.55. Body nominal 13.5 × 12.5; maximum 14.0 × 12.8. Courtyard ±7.35 × ±6.65 allows at least 0.25 beyond lands/body. Applies to 3R3M, 4R7M and 6R8M without changing their electrical values or supplier identities. |
| RS1 | `rover:CSS2H_2512_6.35x3.05` | New local footprint. Bourns recommends 1.80 × 3.40 lands with a 3.40 inner gap; centres x=±2.60. This corrects the generic 2512 footprint's narrower 1.225 mm lands. Body nominal 6.35 × 3.05. |
| SKT1 | `rover:Pico2_Sockets_LXWCONN_254PM_1x20` | New local footprint for two actual 254PM-1x20P-V sockets. 1.02 drills follow the socket drawing; 1.80 copper pads, 2.54 pitch, 17.78 row spacing. Pin 1=(0,0), 20=(0,48.26), 21=(17.78,48.26), 40=(17.78,0). The socket body is 51.30 × 2.50 nominal, height 8.50 ±0.15. Both socket bodies and the Pico 51 × 21 body are drawn. USB faces negative Y. |
| NT1–NT3 | `rover:AGND_Tie_LMR51450` | New copper-only net tie sized to the WSON geometry. Place its origin at the associated IC origin plus (0,+0.75), then rotate with the IC. Pad 1=AGND at (+0.99,0); pad 2=GND at (+0.72,0); both 0.20 × 0.20. The 0.20-high copper bridge spans x=0.62…1.09, overlapping EP13's edge at 0.65 and pin 8's inner edge at 1.08. Net-tie group `1,2`; no purchased part, paste or independent courtyard. |
| F1 | `rover:Fuseholder_Littelfuse_01530008Z` | Retain corrected THT footprint. Contact drills 1.27 (0.050 inch); contact offsets x=±1.73, y=∓3.81 match drawing 0.068 / 0.150 inch, rounded by 0.0028 mm in x. Centre NPTH 3.7846 (0.149 inch), 7.62 contact Y spacing. Current pad diameter 2.032 provides 0.381 nominal annular ring. |
| D2 | `rover:KT0805G_0805_A1_K2` | Retain identity and polarity; adjust lands to the exact drawing's 1.00 × 1.40 with 0.90 gap, centres x=±0.95. Pad 1 is anode on the right; pad 2 is cathode on the left, with cathode-side marking. This polarity is intentionally different from generic KiCad LED numbering. |
| J1/J5/J6/J7 | `Connector_JST:JST_EH_B4B-EH-A_1x04_P2.50mm_Vertical` | Retain. Pads 1–4 at x=0/2.5/5/7.5, y=0; 0.95 drills fall within JST's 0.90…1.00 reference hole range. Type A 4-way body 12.5 wide × 3.8 deep; footprint body x=−2.5…10.0, y=−1.6…2.2 agrees. JST drawing is from the mounting side. Preserve pin 1, and J1 pin 2 remains NC. |
| J9 | `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical` | Retain and keep DNP. Newly retrieved exact supplier-linked BOOMELE family drawing specifies 2.54 pitch and 1.00 PCB holes, matching the standard footprint. Square pins nominal 0.64; body width 2.54, body height 2.50; mating pin 5.7 ±0.2, tail 3.0 ±0.2. The previous unavailable-drawing limitation is closed. |
| C1/C5 | `Capacitor_THT:CP_Radial_D10.0mm_P5.00mm` | Retain. Panasonic EEUFR1H221B: nominal 10 diameter × 16 high, 0.6 lead, B-form 5.0 lead pitch. Diameter tolerance +0.5; height allowance +1.5. Footprint polarity 1=positive, 2=negative must match the board labels. |
| C2 | `Capacitor_THT:CP_Radial_D8.0mm_P5.00mm` | Retain specifically for selected **B-form** EEUFR1C471B. Nominal 8 diameter × 11.5 high, 0.6 lead. Natural long-lead version is 3.5 pitch; the selected B-form is 5.0 pitch. Do not substitute a straight-lead variant and assume the same mechanics. |
| SW1 | `Button_Switch_THT:SW_Slide_SPDT_Angled_CK_OS102011MA1Q` | Retain. Selected OS102011MA1QN1 appears on the C&K drawing's PDF p.6 / printed I-42. Pin pitch 2.0, support-hole centres −2.1/+6.1 relative to pin 1; supports 1.5 drills. Standard electrical drills 0.9 provide 0.1 more nominal clearance than drawing 0.8. Non-shorting switch: position 1 joins 1–2, position 2 joins 2–3. Actuator extends toward positive local Y. |

## Routing and assembly consequences

- RS1's main pads are the power-current lands. Take INA226 sense traces
  separately from the inner pad edges near the resistor terminals (local
  x=−1.70 and +1.70, y≈0), following Bourns' Kelvin drawing. Feed the high
  current from the outer land sides. Do not share a length of current-carrying
  track before the sense takeoff. The source does not dimension the sense-neck
  shape; this footprint deliberately leaves that routing to the PCB.
- The WSON EP must be soldered. The retained stencil uses TI's example for a
  0.125 mm stencil. This library contains no thermal-via holes: the PCB author
  must place ground thermal vias and review solder-wicking against the actual
  assembly process. For the low-cost process, keep through-vias outside the
  solder/paste area and connect them by short, wide ground copper where
  geometry permits; do not claim this has the EVM's thermal performance.
- The tiny NT bridge is designed for the specific WSON pad geometry. Keep
  its polarity/orientation aligned with pin 8 and EP13. It is not an acceptable
  substitute for a broad main ground plane or a power-current route.
- SKT1 needs two female sockets and a Pico module, with male headers if the
  module is bare. The assembly underside, USB cable approach and removal
  space must stay clear. The drawing envelope is not proof of actual header
  engagement or connector height stack-up. No incompatible Pico W model is
  attached to this non-W footprint.
- Historical F1's NPTH was a board-lock hole, not a copper terminal. Its holder
  and fuse insert were separate parts; neither is fitted in A10.
- P1–P4 surface-wire pads are a new explicit owner choice handled by the PCB
  author; they are outside this footprint-library subtask. Cable strain relief
  is still needed because pads alone do not retain a pulled cable.

## Evidence inspected

Exact source bytes and URLs are in `../../evidence/index.yaml`. The relevant drawings
were rendered locally with PyMuPDF and visually inspected, including dimensions
that text extraction alone does not preserve:

- TI `LMR51450SDRRR_lmr51450_7f80073eb777.pdf`, PDF pp.36–38:
  DRR0012G outline, land pattern and stencil.
- Bourns `SRP1265A-6R8M_srp1265a_30b470999b73.pdf`, p.1:
  common selected lead-frame body and recommended lands.
- Bourns `CSS2H-2512K-2L00F_css2h-2512_7e32b223f4b0.pdf`, p.2:
  resistor dimensions, main pads and sense routing.
- LXWCONN `254PM-1x20P-V_f0f6c3d8697d24302649e706e8fbe0d7_5778f815e84c.pdf`,
  p.1; Raspberry Pi `Pico_2_pico-2-datasheet_cbcfaf881018.pdf`, PDF p.8.
- Littelfuse `01530008Z_5dd658d7c0c120ed4252709c4e00b44b_dd28a686cd10.pdf`,
  p.2, centre 01530008 drawing.
- JST `B4B-EH-A_LF_SN_eEH_9e35874bf275.pdf`, pp.2 and 4.
- Kento `KT-0805G_de342fde3322df0797012cd7a04e2194_853e6752f600.pdf`, p.2.
- Panasonic `EEU-FR1H221B_d9089262f7a6df5ba99d8a966a03ede0_bf99d179b367.pdf`,
  PDF pp.14, 17 and 19: FR-A outline, 16 V/470 uF row and 50 V/220 uF row.
- C&K `OS102011MA1QN1_9e68893bade4341f8dc17b91bf8fc979_96f8f741dec9.pdf`,
  PDF p.6, printed I-42.
- BOOMELE `2.54-1x6P_cb0770a379b121177c8c7d26dfb00406_013649a580c9.pdf`,
  p.1, n=6. Retrieved from the C37208 datasheet link and added to the evidence
  index; SHA-256 `013649a580c9ee0d2a54502601713be2b1811ff6d44e21887c8077307a7c2dea`.

## Verification scope

### SRP1265A 3D display correction, 2026-10-01

L1-L3 now attach the archived supplier SRP1265A-220M family WRL model in
`../../libs/lcsc_C2041326.3dshapes`, with zero offset/rotation and unit scale.
This corrects missing inductor bodies in the 3D viewer; the copper footprints
were already present and are unchanged. Bourns' p.1 drawing groups 220M,
6R8M, 4R7M and 3R3M in the same lead-frame construction. Model mesh bounds
are approximately 13.5001 x 12.4998 x 6.3010 mm, centered in X/Y with Z=0
at the seating plane. The contacts align with the footprint's X-axis lands.
The shared model's top marking is not the selected inductance. The schematic
and BOM retain 6.8, 4.7 and 3.3 uH. Use the datasheet maximum envelope
14.0 x 12.8 x 6.5 mm for mechanical clearance, not nominal model bounds.
The source model bytes were not modified.

### RS1 manufacturer 3D model, 2026-10-01

RS1 and its shared `rover:CSS2H_2512_6.35x3.05` footprint now attach Bourns'
unmodified CSS2H-2512 family STEP model, downloaded from the manufacturer's
[engineering files](https://www.bourns.com/resources/design-tools/engineering-files-list?Folder=css2h-2512).
The original ASCII STEP bytes are retained in
`evidence/files/CSS2H-2512_b11b79a9d324.stp`; the evidence index records their URL
and SHA-256. Its text/plain media classification describes the archive's ASCII
file detection; the content is ISO-10303-21 STEP.

KiCad/OpenCascade tessellation gives approximately 6.35002 x 3.05 x 0.82808 mm.
Use rotation (-90, 0, 0) degrees and offset (-3.17501, -1.525, 0) mm, at unit
scale, to center the contacts on the existing X-axis lands and place the
seating surface at footprint Z=0. Native isolated and whole-board renders were
inspected. This is a typical family model, not a guaranteed mechanical envelope:
the selected CSS2H-2512K-2L00F has a datasheet maximum height of 1.09 mm. Use
that maximum for enclosure clearance; do not infer the maximum from this model.

Only the model node changed in the PCB. All other parsed board contents,
including copper, zones, outline, footprints and pad geometry, are identical.
All schematic files and project settings are byte-identical. Both fresh DRC
runs report zero errors, warnings and unconnected items. Exact preview/apply
bindings and hashes are in [rs1-model-review.json](records/rs1-model-review.json).

### Original land-pattern checks

The five created/revised local footprints were loaded and saved by native
KiCad 10.0.6. Pad numbers, coordinates and dimensions were then inspected.
An isolated native footprint review board was plotted to SVG and rendered;
the combined footprint view and an enlarged WSON/net-tie view were inspected.
Review intermediates were moved to the verified pre-cleanup archive described
in PIPELINE_AUDIT.md. The small measured reports remain in `records/initial-layout/`;
the isolated review board was not the project PCB. The drawing check establishes land-pattern intent, not
manufactured fit, assembly rotation acceptance, solder quality or thermal
qualification. Final board DRC and assembly/mechanical review remain required.
