# Power-layout source review and placement template

2026-10-01. Author engineering review for the first A9 PCB candidate. This
document is a placement/routing recommendation, not owner sign-off, thermal
qualification, or a claim that motor regeneration is solved. Native schematic
values and nets remain authoritative. No CAD was edited during this review.

## Source images inspected

Actual PDF figures were rendered and visually inspected, rather than inferred
from extracted text alone:

- `../../evidence/files/LMR51450SDRRR_lmr51450_7f80073eb777.pdf`: SLUSEP7,
  December 2022, p.3 pin map/Table 6-1; pp.26-27 sections 9.5.1 through
  9.5.1.2; p.28 Figure 9-10; pp.36-37 DRR0012G package/land pattern.
- `../../evidence/files/LMR51450SDRRR_snvu838a_6086805dfb70.pdf`: SNVU838A,
  November 2022, p.7 Figure 4-1; pp.8-9 Figures 5-1 through 5-6, including
  the top, inner and bottom copper images.
- `../../evidence/files/INA226AIDGSR_ina226_c9b67f886d4a.pdf`: SBOS547C,
  August 2026, p.31 sections 8.3/8.4 and Figure 8-4.
- `../../evidence/files/CSS2H-2512K-2L00F_css2h-2512_7e32b223f4b0.pdf`:
  p.2, Recommended Pad Layout and Recommended Measurements images.

TI's EVM is four layers with 2 oz outer and 1 oz inner copper. The owner-selected
two-layer, 1 oz prototype is therefore not thermally equivalent to that EVM.
The layouts demonstrate topology; they do not establish this board's current
rating. The selected lower-cost stackup needs actual temperature measurements.

## Repeated converter cell

The following millimetre coordinates are a practical seed for a cell with input
on the right and output on the left. Origin is the IC center. Positive Y is
down the page, as in KiCad. These offsets are author proposals, not dimensions
specified by TI. Final native-pad/courtyard inspection and DRC govern placement.

Use the existing LMR51450 footprint at 0 degrees:

| Pads | Native coordinates relative to IC | Function |
| --- | --- | --- |
| 1, 2, 3 | x=-1.39; y=-1.25, -0.75, -0.25 | SW |
| 4 | (-1.39, +0.25) | BOOT |
| 5, 6 | (-1.39, +0.75), (-1.39, +1.25) | PG and RT, intentionally NC |
| 7 | (+1.39, +1.25) | FB |
| 8 | (+1.39, +0.75) | AGND |
| 9 | (+1.39, +0.25) | EN |
| 10, 11, 12 | x=+1.39; y=-0.25, -0.75, -1.25 | VIN |
| 13 | (0,0), land 1.3 x 2.5 | PGND exposed pad |

| Part/function | Proposed center or region | Required electrical orientation |
| --- | --- | --- |
| U2/U3/U4 | (0,0), 0 degrees | Native pin map above |
| L1/L2/L3, SRP1265A | (-11,-0.75), horizontal terminal axis | Right pad SW; left pad VOUT |
| C33/C34/C35, BOOT 0805 | (-3,+0.75), vertical terminal axis | Upper pad SW; lower pad BOOT |
| C30/C31/C32, HF input 0805 | (+0.95,-2.9), horizontal terminal axis | Left pad GND; right pad VIN |
| Pair of input 1210 MLCCs | (+4.8,-2), (+8.8,-2), vertical terminal axes | Upper pads GND; lower pads VIN |
| Output 1210 MLCCs | y=+8.5, x=-16.5,-12.5,-8.5,-4.5 | Upper pads VOUT; lower pads GND |
| Fifth 5 V output MLCC | (-0.5,+8.5) | Upper pad VOUT; lower pad GND |
| Feedback divider / feed-forward | x=+2.5..+9, y=+2..+7 | Short FB midpoint; quiet VOUT sense |
| EN pull/divider parts | To right of EN, away from SW copper | Preserve A9 topology and pin order |

Inductor terminal centers after adopting Bourns' recommended land pattern are
approximately x=-16.55 and -5.45, y=-0.75. Its approximately 13 mm courtyard
spans x=-17.5..-4.5, y=-7.25..+5.75. Overall cell allocation is approximately
x=-19..+11, y=-7.5..+11 mm. A 21 mm vertical cell pitch is plausible; bulk
capacitors and output connectors require additional space outside this core.

The bootstrap capacitor is deliberately close to the IC and SW landing,
within the corridor between the IC and inductor. Its exact orientation must
be derived from pad-to-net mapping, not a visual assumption about pad 1.
Avoid a detour around the inductor for the BOOT trace. The suggested 0805
courtyard can abut the IC courtyard; validate actual library extents.

```text
      Local top GND return / HF cap        input MLCC GND pads
                GND--C_HF--VIN                C_IN   C_IN
                        |                       |      |
 VOUT--[large L]--SW--[IC + DAP]-----------------VIN bus
                    C_BOOT  | FB / EN support
                            | quiet analog area
                            + GND thermal-via fan
   output capacitors: VOUT pads / GND pads
   broad output bus         broad local GND return
```

### Route in this order

1. Join all three VIN pads and all three SW pads with short local copper.
   VIN12 to C_HF and C_HF GND to DAP13 form the smallest input commutation
   loop. Keep this loop entirely on F.Cu; a return through a distant via and
   bottom pour is not an equivalent substitute.
2. Connect the two larger input capacitors into that same local VIN/GND
   structure. Their ground ends belong to the local top PGND copper, with
   nearby ground vias as additional parallel return/heat paths.
3. Connect SW directly to the inductor's right terminal. Use a small, broad
   shape rather than a large SW plane. The suggested inductor orientation
   keeps its SW terminal a few millimetres from the IC. Keep SW on F.Cu;
   do not run it to a test-point antenna, under Pico/INA, or under FB wiring.
4. Connect BOOT4 to its capacitor and the other capacitor pad directly to
   local SW. Check that the BOOT trace clears the nearby SW capacitor pad;
   neither their similar voltage movement nor adjacency makes them one net.
5. Route the inductor's left VOUT terminal around its left/bottom perimeter
   to the output-cap VOUT bus. Take output power westward from this bus.
   Return the output-cap ground pads to the local PGND copper using a broad
   top path and parallel bottom ground, not a narrow shared signal return.
6. Route the divider, feed-forward branch and AGND connection. The FB
   midpoint must be short and away from SW/inductor. On the two-layer board,
   a bottom VOUT-sense trace can avoid the switching area, but there is no
   intervening shield layer as in TI's four-layer recommendation. Do not
   represent a bottom trace directly beneath SW as shielded.
7. Route low-current EN and other control connections. For U4, R15/R24 and
   the switch supply divider return to AGND_4 exactly as captured in A9.

Keep most of B.Cu as a continuous GND plane. Avoid long signal routes that cut
it into strips under the converter cells. Stitch local top/bottom grounds
near input and output capacitor returns. Wide power copper and many ground
vias help, but neither proves a thermal rating. Do not put mounting/cable
forces into ceramic capacitors or WSON packages.

## AGND tie at the exposed pad

TI Table 6-1 explicitly requires a small AGND-to-PGND net tie. Figure 9-10
shows AGND returning inward toward the exposed-pad ground. Preserve the
separate schematic AGND_2/3/4 nets and NT1/2/3.

The AGND pin's inward copper edge is x=+1.08; the DAP edge is x=+0.65.
Thus the physical gap is only 0.43 mm, at y=+0.75. A very small copper-only
net-tie feature there is suitable. A proposed approximately 0.20 mm tall
bridge avoids the adjacent 0.5 mm-pitch pins; declare its two pads as an
actual KiCad net-tie group. NT pad 1 is AGND; pad 2 is GND. Verify this mapping
before generating geometry. No BOM part is installed.

The generic 0.5 mm-high net-tie may encroach on neighboring pad clearances if
placed at the IC pins. Do not silence such DRC errors. Use appropriate local
copper-only geometry, or a carefully routed nearby tie that does not make FB
cross the analog return. The divider bottom connects to the AGND side of the
tie. Do not create a second AGND connection elsewhere through a poured zone.

## Exposed pad and thermal vias without an added via-in-pad process

The TI DRR drawing requires the exposed pad to be soldered. Its example has
three 0.2 mm vias in the pad and states that vias under paste should be filled,
plugged or tented. That illustration does not mean ordinary open holes under
our solder paste are acceptable for the selected assembly process.

For this prototype, retain the footprint's two paste windows and use a solid
F.Cu connection from DAP13 to a ground tongue below the IC. Start with six
ordinary tented ground vias outside the exposed-pad mask/paste opening, at
local x=-0.45,+0.45 and y=+2.1,+3.0,+3.9 mm. Proposed drill is 0.30 mm and
pad diameter 0.60 mm. Inspect actual mask clearance, feedback routes and
bootstrap geometry before use; these are placement seeds, not compulsory
locations. Fan outward into more GND stitching and broad B.Cu ground.

Do not use thermal-relief spokes between DAP13 and the local ground tongue,
or between these thermal vias and their ground planes. Do not place an
unfilled hole inside the DAP or under either paste aperture. Additional
ground vias near input/output capacitor returns stay outside their solder
lands. Ordinary tenting does not imply a guaranteed filled/capped via.

JLCPCB's current [via-covering guide](https://jlcpcb.com/help/article/pcb-via-covering)
distinguishes tented, plugged and filled/capped processes. It recommends
tented holes no larger than 0.4 mm where possible; ordinary soldermask
plugging cannot be assumed for in-pad holes or holes too near pads. Its
[capability page](https://jlcpcb.com/capabilities/pcb-capabilities/) gives
separate rules for filled vias and mask clearances. These sources were checked
on 2026-10-01. Confirm the final process in the order preview; this review does
not place an order or claim filled vias are included.

Adjacent-via heat extraction is a lower-cost compromise against the EVM's
in-pad array and four copper layers. Bench measurements at actual ambient,
enclosure and combined rail loads remain necessary; reduce load or revise
the thermal construction if temperatures are excessive.

## INA226 and the 2 mOhm shunt

The INA226 datasheet p.31 explicitly calls for Kelvin/4-wire sensing and a
nearby VS bypass capacitor. Bourns' resistor p.2 shows separate thin sense
fingers at the inner sides of its two power solder pads.

- A9 polarity is RS1 pad 2 = fuse side / INA226 IN+ pin 10;
  RS1 pad 1 = VBAT / INA226 IN- pin 9. Do not assume that pad 1 is the
  positive-current input. U1 VBUS pin 8 goes to the post-shunt VBAT side.
- Route the heavy battery path into and out of the broad outer portions
  of the shunt lands. Bring two separate low-current sense tracks from the
  resistor terminals' inner edges directly to IN+ and IN-. Do not begin
  the sense tracks on copper carrying appreciable battery current.
- Keep the sense pair together, short, and away from the three SW nodes,
  inductors and motor connector return path. Prefer the same layer and
  similar surroundings; exact length matching is not the primary issue.
- A generic two-pad 2512 footprint does not automatically provide the
  Bourns-recommended Kelvin geometry. Preserve two electrical pad numbers
  while making the separate sense takeoffs explicit in actual copper.
- Place C3 directly between VS pin 6 and GND pin 7, with a short local
  return and nearby GND via. Keep the I2C traces on the quiet side of U1.
- At 2 mOhm, even 0.1 mOhm of unintended load-carrying resistance in the
  measured path adds 5% error. Sense routing matters more than making the
  two thin traces visually identical in length.

## Implemented converter-cell geometry

`layout/converter_cells.py` implements the three cells with U2/U3/U4 at
(39,33), (39,55), (39,77) mm. Native pads and exact nets come from the fresh
schematic XML/loaded footprints. The module checks expected placement and
same-net endpoints before routing. It does not write the schematic or libraries.

Native courtyard/DRC checks refined the seed offsets above:

- L1-L3 centers are now (-11.5,-0.75), accommodating the actual 14.7 mm
  courtyard without colliding with BOOT capacitors.
- Input capacitor centers use y=-2.4; EN resistors use (+7,+1.5).
- Divider bottoms use (+4,+3.2); tops use (+4,+6.9).
- Feed-forward resistor/capacitor centers are (+7.5,+4.3)/(+7.5,+7.6).
- U4 R19/R24 centers are (+11.8,+1.5)/(+10,+4.2).
- The BOOT escape at x=-1.9875 and EN dogleg at y=+0.38 preserve at least
  0.20 mm clearance without moving the WSON or altering circuit values.

The three cells add 222 locked tracks and 43 locked, explicitly tented vias,
including six adjacent ground thermal vias per converter. Top-layer VIN,
SW, BOOT and ground loops are manually routed. VOUT sensing uses two vias
and a short bottom route away from the inductor/SW area. Output ceramic
ground paths remain continuous on top copper; the main board ground planes
provide additional copper after integration.

Fresh isolated native DRC with Default 0.20 mm clearance found no shorts,
clearance violations, crossing tracks, track-width violations or courtyard
overlaps in these cells. The isolated board retains four expected missing
connections between the separate cells' shared VBAT and GND nets; the parent
board connects them. Unfilled-plane thermal vias are expected to report
one-layer dangling until integration. Reference-label positioning and library
configuration are handled by the parent board. This is not a claim of clean
full-board DRC. Enlarged copper renders of U2, U3 and U4 were inspected after
the final route adjustments.

| External port | U2 | U3 | U4 |
| --- | --- | --- | --- |
| VIN | (51.8,32.075) | (51.8,54.075) | (51.8,76.075) |
| VOUT west bus | (19.5,40.025) | (19.5,62.025) | (19.5,84.025) |
| Local GND return | (40.7,43.4) | (40.7,65.4) | (40.7,87.4) |

U4 MOTOR_EN is exposed at R15 pad 1, (46.9125,78.5); SW_SUPPLY at
R19 pad 2, (49.8875,78.5). These are low-current connections to SW1;
they are not motor power ports.

## Final filled-board author review, 2026-10-01

Reviewed the fully routed candidate by copying it before inspection. Source:
the archived `.pcb-copilot/layout-work/rover-pdb.kicad_pcb`. Reviewed snapshot SHA-256:

`BC76965FAAE2CB058E0833D09B7B02B2386FB78CE860A72562EB3A1FE837A624`

Historical image evidence is in `.pcb-copilot/power-board-review` inside the
verified pre-cleanup archive (see PIPELINE_AUDIT.md), originally named
`snapshot-final.kicad_pcb`, `front-final.svg/png` and `back-final.svg/png`.
The SVGs were exported by KiCad 10.0.6 from the native filled board, with
front copper plus fabrication outlines and bottom copper respectively.
Both complete copper renders were visually inspected. Native pad/zone
settings and the current native DRC JSON were also read.

An earlier full-board review found a same-net error that DRC did not report:
the bottom +5 V distribution bridge intersected U3's thin output-voltage
sense route. That could divert load current through the feedback takeoff.
The corrected bridge runs from (37.3,60.4) through (47,60.4) and
(51.1,64.5) to (56.1,64.5) mm. In the final filled render it remains
separate from the U3 sense route and its via at (44.5,64.4) mm. Four
ordinary plated vias at each power-bridge end share the layer transition;
they do not qualify the bridge for an unmeasured continuous current.

Final observations:

- The shared post-shunt VBAT trunk has a 4 mm main vertical section;
  its upper approach remains 2.8 mm. Three local input banks join through
  short branches. No new copper bottleneck was found at the widened trunk.
- Ground copper remains broad through the three converter cells on the
  bottom layer. The added MOTOR_EN, SW_SUPPLY and LED routes stay east of
  the critical converter loops. Their clearances do not cut the main
  converter-side ground area into a narrow return neck.
- The bottom ground area above the motor connector row remains continuous
  back toward U4 and the battery return. The communication traces are
  below this connector row; the motor power distribution is on top.
  This visual continuity check is not an extraction of return impedance.
- The short, manually routed VIN/HF-capacitor/PGND loops, BOOT connections,
  compact SW copper, local AGND ties and output-capacitor ground copper
  survive integration. The bottom sense routes are away from SW copper.
- Shunt force copper enters/leaves the outer sides of RS1. The two sense
  traces still leave the inner terminal edges separately, at approximately
  (54.3,12) and (57.7,12) mm. Neither takeoff was engulfed by the widened
  battery trunk. INA226 bypass placement and its nearby ground return
  remain intact.
- The six adjacent ground vias per converter remain outside exposed-pad
  paste. EP and ceramic capacitor ground pads connect directly to ground
  copper. Through-hole ground pads use explicit 0.6 mm thermal bridges
  and 0.25 mm gaps; the filled views show thermal relief on both layers.
  These settings balance hand soldering and return connectivity, but do
  not establish the finished assembly's temperature rise.

The inspected native DRC report, dated `2026-10-01T01:33:35`, contains zero
violations, zero unconnected items and zero schematic-parity entries under
the recorded enabled checks. No further actionable power-layout or
current-return topology defect was identified in this candidate. This
verdict applies only to the snapshot hash above and is an **author review**,
not the owner's fabrication approval. Later copper changes require another
filled-board inspection.

## Acceptance boundary

Inspect the filled copper of each of the three cells at readable scale,
including paste/mask, DAP ground escape, AGND tie, both sense takeoffs and
both capacitor return paths. Native connectivity/DRC and rendering are
required after routing. These checks do not resolve regeneration, loaded
startup, converter stability, fuse coordination, power-down transients,
actual cable retention or maximum continuous load.
