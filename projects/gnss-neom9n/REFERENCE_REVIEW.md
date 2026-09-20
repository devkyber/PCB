# NEO-M9N reference research

Research date: 2026-09-17. Assistant research and transcription; human
engineering acceptance and review of our actual PCB remain pending.

## Searches actually performed

| Query | Outcome |
| --- | --- |
| `site.u-blox.com NEO-M9N integration manual minimal design PCB layout` | Found the manufacturer integration manual and product page. The already archived manual contains the minimal schematic and RF/supply layout illustrations. |
| `"NEO-M9N-00B" manufacturer evaluation board PCB layout CAD Gerber` | No selected downloadable manufacturer full PCB CAD/stackup was acquired. Footprint-library results are not board-layout evidence. |
| `site.github.com/sparkfun NEO M9N schematic brd` | Found SparkFun's official breakout and MicroMod repositories. Selected the breakout U.FL variant, which is closer to our antenna connector; did not substitute the chip-antenna, SMA, or MicroMod board. |
| `"NEO-M9N" U.FL SparkFun schematic PCB layout V10` | Confirmed the open-hardware source family; native CAD was acquired from the official repository. A request to the SparkFun hookup guide resources page returned HTTP 403 in the web tool. Native CAD acquisition succeeded independently. |

Source pages: [u-blox product](https://www.u-blox.com/en/product/neo-m9n-module),
[SparkFun repository](https://github.com/sparkfun/SparkFun_u-Blox_NEO_M9N).
The native pair is pinned to commit
`c38db3261ddbcdcfee0c42a4aebe22bbd574111f`, not a moving branch URL.
Full source URLs, acquisition dates, and SHA-256 identities are in
`evidence/index.yaml`.

## Archived and inspected sources

| Source | Local evidence | Inspection scope |
| --- | --- | --- |
| u-blox NEO-M9N-00B data sheet, UBX-19014285 R08, 2025-10-09 | `files/NEO-M9N-00B_NEO-M9N-00B_DataSheet_UBX-19014285.pdf` | Read revision history; visually inspected pp.8-9 pin assignment and Table 9. This is the exact accepted module variant's pin authority. |
| u-blox integration manual, UBX-19014286 R10, 2025-03-27 | `files/NEO-M9N-00B_NEO-M9N_Integrationmanual_UBX-19014286.pdf` | Visually inspected p.71 Figure 31 minimal schematic and p.81 Figures 39/40 RF trace and VCC-pad layout. These are manufacturer circuit/layout examples, not complete EVM CAD. |
| SparkFun U.FL breakout, schematic marked V10 | `files/NEO-M9N-00B_SparkFun_GPS_NEO_M9N_uFL_df70b2d67fa6.sch` | Parsed native device-to-pad mapping, explicit values, and nets. U1 is `U-BLOX_NEO-M9N`, package `NEO-M9N`, with all 24 pad numbers represented. The CAD omits the `-00B` order suffix; exact purchased variant is therefore unconfirmed. Indexed under our target part for applicability, not as proof of its procurement identity. |
| Matching SparkFun native board | `files/NEO-M9N-00B_SparkFun_GPS_NEO_M9N_uFL_963d63cb9c1d.brd` | Native pair metadata: 135 connected pads compared, zero mismatches; 349 routed wires, 207 vias, copper layers 1/16, GND polygons on both layers. Later limited explicit-copper visual inspection is recorded below; fill and engineering validation remain open. |

The pair inspector verified package identity and explicit values as well as
pad-net membership. This does not establish filled-zone connectivity, routing
completion, DRC, impedance, or electrical correctness. The license at the
same pinned commit specifies hardware CC BY-SA 4.0; preserve attribution and
check its terms before distributing adaptations.

## Applicability and differences

The manufacturer's minimal circuit supports our grounded unused V_USB,
ground pins, receiver interfaces and recovery test point. Its layout examples
show RF grounding vias and a close VCC bypass connection. These support future
review of our return paths and decoupling; they do not prove our routing meets
the examples. No RF width or stackup is copied into the intent.

SparkFun uses USB, so its V_USB is powered; our USB is unused and pin 7 stays
grounded. SparkFun routes the antenna net from RF_IN to U.FL and a bias feed
through FB1, with R14 and C1 in the VCC_RF supply path. Our accepted design has
no antenna bias feed and retains its unresolved passive/active antenna owner
decision. SparkFun's rechargeable backup cell and diode/resistor supply path
are also different from our primary CR1220 cell directly on V_BCKP. Its I2C
pull-ups are 2.2k; ours remain 4.7k. None of these reference choices changes
the accepted circuit.

Existing `DESIGN_BASIS.md` and `DEVIATIONS.md` remain authoritative for the
current local choices. Supply headroom at VIN = 3.3 V, antenna selection and
siting, and environmental limits remain owner questions.

## Migration checks and unresolved evidence

`schematic-intent.yaml` transcribes all 24 accepted physical components plus
the two existing power flags onto one A3 sheet. Values, symbol identifiers,
footprints, and all 65 pin-net declarations match the saved netmap. All eight
no-connect markers were checked against actual accepted schematic pin
positions: U2 pins 5/6/14/15/16/17 and H1/H2 pin 1. The accepted files were not
regenerated or accepted by this work.

U1 uses the archived XC6206 family SOT-23 pin table; U2 uses the exact -00B
datasheet. SW1 cites the B3U-1000P switch drawing. Generic passives, connectors,
test points, mounting holes and power assertions have explicit review notes
instead of unrelated evidence hashes. The CR1220 sheet does not establish the
exact VCN solder-tab-to-pad mapping, so BT1's pin-map citation remains null.
D1's indexed document identifies RClamp0521PA in SLP1006P2, while the accepted
value/footprint are RCLAMP0521P and D_0402_1005Metric: the intent preserves them
and flags ordered-package/polarity review rather than asserting equivalence.

Still required before relying on this research for layout or release:

- Complete native fill/mechanical/clearance review beyond the limited derived
  copper views below, and confirm the exact ordering variant.
- Compare our actual copper, RF geometry, ground return, antenna protection,
  and supply decoupling against the manufacturer and reference views.
- Record any adopted layout choice or justified difference in the design
  basis after human review. Complete manufacturer PCB CAD was not acquired.
- Human review of the migrated draft remains pending. Archive integrity and
  pair consistency are narrow checks, not release approval.

## Latest draft inspection

Draft `20260916T181255Z-schematic-c088e056` supersedes the earlier previews.
The assistant inspected the complete A3 PDF and enlarged receiver detail,
including the battery, U.FL connector, module pin banks, and title block.
The CLI returned exit 0 with no blocking findings or intent/netlist mismatch.
There are 21 ERC review warnings about unspecified pin types and 22 unresolved
pin-map citation advisories. Metrics: 24 physical components, 33 power symbols,
8 junctions, drawn-connection ratio 0.748, and title/revision/date present.

Block headings are now visible. BT1 reference/value text is beside the battery
and clear of its vertical leads; J2 reference/value text is above the connector
and clear of its ground lead. The earlier field/body collisions are corrected.
The D_SEL pull-up is grouped with interface mode/reset/recovery and connected
by boundary labels; this grouping preserves the same electrical net.

Left labels now extend away from pin numbers. The V_BCKP and J2 RF_IN text
proximity is improved. A remaining collision is explicit: U2 pin 12's ground
triangle overlaps the RF_IN label on pin 11. The preview report now flags that
specific contact as a non-blocking `power-text-collision`. The page remains
pixel-identical to the previously inspected preview; detection did not alter
placement. The lower half of the A3 sheet
is mostly unused. These are visible review issues, not hidden by the passing
connectivity check.

Git comparison confirmed the accepted `.kicad_sch`, `.kicad_pcb`, and
`netmap.json` remain unchanged. No acceptance or human sign-off was performed.

## Limited explicit-copper inspection — 2026-09-20

The controller visually inspected separate F.Cu/B.Cu exports of the archived
SparkFun board using KiCad 10.0.6. Source SHA-256 stayed
`963d63cb9c1d6d63123480ce3a4592504efa401d70e35f3a331b009f1f357717`.
The first Eagle import loaded 94 footprints, 556 tracks/vias and five zones,
but saving project settings failed and the unmodified derived export rejected
UNDEFINED layers. A source-specific in-memory workaround omitted exactly 41
imported graphics: J3 USB-C's 16 layer-46 Milling wires/arcs; four stand-offs
JP101/JP31/JP41/JP91 with four layer-41/42 restriction arcs each; and eight
board layer-47 dimensions plus one text. Layer-39 stand-off keepout circles
were retained. No archived XML bytes were edited and no general repair was added.

SaveBoard with skip-settings and a fresh-process reload preserved all 94
footprint anchors/rotations, 157 pads (positions, sizes, rotations, drills,
shapes and nets), and 556 track/via endpoints, widths, layers and nets exactly
relative to the imported board. Five zone records remain by count only.
The successful diagnostic emitted SWIG removed-object warnings; an earlier
via.GetWidth probe asserted and was corrected to explicit F.Cu diameter access.
These diagnostics do not constitute a clean production pipeline or source-format
semantic equivalence test.

Ignored artifacts are under `.pcb-copilot/reference-review/eagle-import-20260920/`:
`reference-explicit-copper-only.kicad_pcb` and
`copper/reference-explicit-copper-only-{F_Cu,B_Cu}.svg` with 2000px PNGs.
Both exports use top view with Edge.Cuts/F.SilkS overlay; B.Cu is not mirrored.
No filled plane or refill was used. The views show central U1 NEO-M9N, upper-left
J3 USB-C, upper-right J13 U.FL, right-edge Qwiic J4, C4=1uF immediately right
of the module beside U2 regulator, many vias around/under the module and back
trace bundles around its upper/lower perimeter. Native source contacts place
U1.11, J13.FEED and FB1.1 on GPS_ANT1; FB1.2 supplies a separate ANT_VCC branch
with R14/C1. These are source observations, not copied placement constraints.

Omitted milling/restriction graphics prohibit mechanical, clearance, pour, DRC
or fabrication approval of the derived board. Native Eagle fill equivalence,
RF impedance/width/stackup, -00B procurement identity and suitability for our
different circuit remain unverified. Proposed local grouping and the unresolved
RF-notch representation are documented in DESIGN_BASIS.md.
