# Rover PDB physical design

PCB stage authorized **2026-10-01**. The owner's later saved geometry,
reconciled on **2026-10-05**, is **77.5 x 100 mm**, retaining four M3 mounting
holes, economical two-layer / 1 oz construction and surface wire pads. This
supersedes the earlier 80 x 100 mm layout target and initial 100 x 100 mm board.
The native A10 circuit remains authoritative. Historical layout checks do not
cover later edits; each current candidate needs its own checks and review.
Hardware validation and human release approval remain separate.

## Current owner-edited mechanics, 2026-10-05

The outline is a single closed Edge.Cuts rectangle, X=99..176.5 mm and
Y=54.2..154.2 mm, with square corners. Preserve these dimensions and the actual
hole locations in the table below. They are saved design choices, not evidence
of chassis fit. Use the current 77.5 x 100 mm dimensions in supplier quotations.

P1-P4 retain surface solder lands without their former separate retention
holes. External cable strain relief remains necessary. The owner's current
save also removes the earlier P3 USB approach keepout. R1/R2 lie within or near
that former approach in plan view; their low height does not by itself establish
a collision with the raised Pico USB plug. Verify the selected sockets, header
engagement, plug overmold and cable bend before defining a new envelope. The
P5's generic 3D board view includes two female socket bodies, but omits the
Pico module and USB cable and cannot prove USB fit.
Switch selection remains deferred; the current footprint is still for the
angled C&K OS102011MA1QN1 and is not a generic top-actuated switch footprint.

## P5: sockets, power widths and useful vias, 2026-10-04

P5 preserves the owner's outline, all retained component positions and P4's
separate 5 V force/sense repair. A10 removes F1 at the owner's explicit request,
joining P1 to RS1 on BAT_SWITCHED with a 4 mm front-layer bridge. No onboard
battery fuse remains. This is separate from motor-enable switching.

Six existing input/VBAT segments are widened: the shunt-input path uses 4 mm
where clearances allow, 3 mm on one approach and the retained 2.8 mm short
Kelvin-terminal approach. Two sections of the bottom VBAT bridge become 4 mm;
one diagonal becomes 3.3 mm. A 3 mm section remains near MOTOR_EN. Main output
routes retain 2.4 mm for 12 V, 2 mm for 5 V and 2.5 mm for VMOTOR, with 1.5 mm
motor connector branches. These are measured dimensions, not current ratings.
TI SNVA766 section 11 provides a legacy IPC-2221 comparative temperature-rise
screen; simultaneous-load temperature and copper/via bottlenecks need measurement.

The 48 added vias are 0.60 mm diameter / 0.30 mm drill, tented on both faces and
outside solder/paste openings. P1 positive has six; P2/P3/P4 each have six on
positive and six on ground; U2/U3/U4 each gain two ground vias. P1's existing
seven ground vias and the converters' earlier ground arrays remain. Four small
bottom positive-copper patches connect the wire-pad arrays to useful copper.
Both faces of every new via are connected after refill. There are no open holes
in the P1-P4 solder lands. More copper also increases hand-soldering heat demand.

All current ground zones use direct/full pad connections. Their stored thermal
spoke widths are inactive; do not describe the through-hole headers as having
thermal reliefs. The new patches also use direct connections. Review soldering
access and heat delivery with the actual iron and harness.

SKT1 has two official KiCad generic 1x20 socket STEP models at 17.78 mm row
spacing. Native geometry matches all 40 Pico 2 pad positions, with 2.54 mm pitch
and 48.26 mm pin span. The 21 x 51 mm module body is clear in plan view. The
nearest surrounding courtyard/body bounds are about 1.365 mm from C2 and
0.565 mm from optional J9. These plan-view checks do not verify the purchased
socket's contact depth, male-header engagement or the USB plug overmold.

## Historical P3: polish of the owner's saved layout

This section describes the earlier P3 implementation, before the owner's
subsequent outline, placement and USB-keepout changes. Its coordinates and
clearance envelope do not override the current mechanical table.

P3 starts from the owner's 2026-10-01 15:13 saved board. It preserves the outline,
P1-P4 surface pads without retention holes, relocated left mounting holes,
and the owner placements of the fuse, switch, shunt, bulk capacitor and Pico.
The LED and its resistor move beside the switch; INA226 and its local bypass
move slightly left to clear the USB approach. Circuit values and all schematic
files stay unchanged. Switch selection remains deferred.

An F.Cu component keepout spans absolute X=156.75..167.70 mm and
Y=55.05..73.70 mm: 10.95 mm clear width into the Pico's USB end. Copper routing
and vias are allowed beneath this approach. Verify the actual plug body, socket
height and cable bend; the keepout is a chosen envelope, not a cable datasheet.
The top fiducial moves out of this corridor. Both layers' left screw keepouts
follow H1 to (104.5,59.5) and H3 to (105.5,150.5) mm; the single stitching via
under the lower-left screw is removed.

The moved parts' local routes and labels are repaired as editable native copper.
U1 retains a 0.15 mm local clearance for its 0.5 mm pitch pads; the normal
0.20 mm net clearance and board constraints are not relaxed. The three converter
cells and their critical copper remain unchanged from the owner save.

## Historical P2: the earlier 80 mm width target

This section records the earlier narrowing rationale and routing, not a
measurement or verification of the latest owner-edited board.

The owner's request was the smallest practical width with the existing circuit,
parts and 100 mm height. P2 uses 80 mm: 20% less area than the original square.
This is a practical packing decision, not a mathematically proven minimum.
The bottom connector row, four mounting keepouts, the Pico socket and J9,
large inductors and accessible surface wire pads constrain further reduction.
A 75 mm outline needs a different arrangement, rather than simply cutting off
another 5 mm of empty board.

Each converter cell moves 3 mm left as a group. The relative component placement
and BOOT, SW, feedback and AGND copper remain intact. Power distribution and
the connections between moved blocks are rerouted as native KiCad copper.
The saved owner PCB is the starting point; neither the circuit nor the schematic
is regenerated. Keep all tracks/vias unlocked for subsequent manual edits.

The revised shunt-to-VBAT path uses a 3 mm back-layer bridge with eight 0.8 mm
diameter / 0.4 mm drill vias at each end, joining the 4 mm front trunk. Two
back-layer 5 V branches serve the auxiliary wire pads and C2/servo headers;
their layer transitions use parallel vias. The motor trunk is 2.5 mm on the
front. These dimensions describe the copper, not a measured current rating.
The DYNAMIXEL trunks remain adjacent below the connector row. Signal routes
must not merge the shunt or converter feedback sense paths into force copper.

The assembled USB plug, switch and fuse access must be checked with the real
hardware. The socket's stand-off and switch height mean a top-view overlap alone
cannot establish cable interference. Do not move the circuit or declare fit
proven based only on a generic 3D rendering.

## Physical construction and assembly

| Item | Required implementation or review |
| --- | --- |
| Outline | 77.5 x 100 mm; one closed rectangular Edge.Cuts outline with square corners. Cable exits must be shown in the board drawing. |
| Drawing position and origins | Current native page bounds X=99 to 176.5 mm, Y=54.2 to 154.2 mm. Grid and auxiliary drill/place origins retain the older (98.5,155) editing position. Existing release exports use the absolute page origin for Gerber, drill and placement files. |
| Mounting | Four 3.2 mm NPTH holes at the owner-edited coordinates listed below. Preserve this pattern; reserve a 3.5 mm radius around each actual center for screw/body/copper clearance and review actual fasteners. |
| Copper | F.Cu and B.Cu, nominal 1 oz each. Document width and via choices for the actual copper thickness; do not reuse a 2 oz current calculation. |
| Order settings | 1.6 mm FR4, green solder mask, two layers / 1 oz. Native surface finish is User defined; confirm it at checkout. The pipeline now checks a dated geometry baseline independently of project overrides, but cannot verify checkout settings. |
| Wire interfaces | P1-P4 use surface solder pads with existing pin numbers and no separate retention holes. Provide clear polarity, voltage markings, solder access and external harness strain relief; the solder joint is not the cable restraint. |
| Pico | Two real female socket rows; land/drill geometry was compared with the drawing, but actual engagement, underside clearance, USB plug access, BOOTSEL access and removal space remain unverified. The former USB keepout is absent. Preserve USB-only power. |
| Battery protection and switch | F1 is removed. Review external battery protection and motor-enable access. Switch replacement remains deferred; retain the distinction between EN disable and battery isolation. |
| Purchased vs board features | Preserve component LCSC fields and J9 DNP. Exclude test points, net ties, wire pads, fiducials and mounting features from purchased-part assembly lists as appropriate. The Pico module and socket hardware are separate physical items. |

Hole positions below are measured from the saved native CAD. Board-local
coordinates use the current **top-left** corner (99,54.2), X rightward and
Y downward; they are not coordinates relative to the lower-left editing origin.
Values are shown to 0.0001 mm for reproducibility, not as fabrication tolerances.

| Hole | Absolute X, Y (mm) | Board-local X, Y (mm) |
| --- | --- | --- |
| H1 | 103.0000, 59.2000 | 4.0000, 5.0000 |
| H2 | 172.0000, 59.2000 | 73.0000, 5.0000 |
| H3 | 103.0000, 150.2000 | 4.0000, 96.0000 |
| H4 | 172.0000, 150.2000 | 73.0000, 96.0000 |

Mounting holes may use H1-H4 and board fiducials FID1-FID3. These mechanical
references are permitted as PCB-only features by the repository parity checker;
that allowance does not waive their geometric or assembly checks. A mechanical
feature must not introduce a new electrical connection absent from the schematic.

## Placement and routing order

The page position is a drawing convenience, not an electrical design rule or
a change in physical board size. On 2026-10-01 the complete board was translated
by (+98.5,+55) mm, including every footprint, track, via, zone, keepout, text and
outline segment. That earlier translation preserved relative geometry; the P2
width reduction subsequently changes placement/routing. Engineering coordinates
in the earlier layout notes remain relative to the board's **upper-left** corner;
the editing grid's lower-left origin is a separate convenience.

KiCad distinguishes the fixed page origin from configurable grid and drill/place
origins ([KiCad 10 manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)).
The configured manufacturing exporter retains absolute coordinates for all
outputs, following its existing convention. If that convention is ever changed,
Gerbers, drills and placements must use the same new origin; changing only one
would misalign the manufacturing data. See
[JLCPCB's drill/Gerber guide](https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-7).

1. Set the outline, holes, interfaces, USB/switch access and cable exits.
   Check component bodies and socket/harness envelopes, not only pad centers.
2. Place each converter as a local functional block: VIN bypass, main input
   ceramics, IC/PGND, BOOT, inductor, output ceramics, feedback and its net tie.
   Follow TI's annotated copper example rather than schematic drawing distances.
3. Route input pulse loops, SW and BOOT first. Connect capacitor returns to
   local PGND copper. Route each analog divider return through its own NT1-NT3
   meeting point near the converter; preserve the main ground reference.
4. Route the battery/shunt power path and separate Kelvin sense takeoffs.
   Carry converter and actuator current on short, sufficiently wide copper,
   with parallel vias where a layer transition is unavoidable.
5. Route quiet feedback sense away from SW, then digital interfaces. Preserve
   a return path under signals and keep motor/servo currents out of Pico and
   INA226 return paths. Route DYNAMIXEL D+/D- together with short branches.
6. Fill copper, provide deliberate ground bonding and thermal spreading, then
   inspect current bottlenecks at pads, neckdowns, vias and thermal spokes.

Use the archived TI LMR51450 SLUSEP7 section 9.5/Figure 9-10 and SNVU838A
EVM layout views; TI INA226 layout guidance; and Bourns CSS2H-2512 measurement
geometry. Exact archived files and page locators are listed in
`PCB_DESIGN.md`. TI's EVM uses a different stackup and is a placement
reference, not a current/temperature qualification for this two-layer board.

The selected inductors, input/output capacitor counts, feedback networks,
USB-only Pico supply and EN divider remain unchanged. If routing exposes an
electrical problem requiring a circuit change, record the specific issue and
obtain scoped authority rather than editing the owner schematic through a
generator.

The 1.6 mm FR4/green combination, 3.2 mm drills and hole centers are
implementation choices within the owner's physical scope, not measurements of
the rover chassis. Exact fastener fit and clearance remain mechanical review.
Use a 0.15 mm absolute clearance floor and a 0.20 mm Default netclass. U1's
footprint has a local 0.15 mm clearance for its intrinsic fine-pitch pad spacing
and pad escape; the free routed copper and converter circuits retain 0.20 mm.
Native fixture checks confirmed that this footprint override applies to its
pad-to-pad and pad-to-track pairs while unrelated copper retains 0.20 mm.
No net-wide clearance relaxation or converter rule-area exception is required.

## Manual editing and routing defaults

The current saved native schematic hierarchy and PCB are authoritative. Start
assisted edits from copies of those files; the retired first-layout scripts are
not part of the active workflow. Save and close KiCad before
external application, then reopen the project to load changed settings.

On 2026-10-01, routing classes and presets were added to `.kicad_pro` without
changing any owner-saved copper or schematic. These are starting widths for
new routes, not automatic changes to existing segments or current ratings:

| Net | Class | Default width |
| --- | --- | ---: |
| BAT_SWITCHED | PDB_Battery | 3.5 mm |
| VBAT | PDB_VBAT | 4.0 mm |
| +12V | PDB_12V | 2.4 mm |
| +5V | PDB_5V | 2.4 mm |
| VMOTOR | PDB_Motor | 2.5 mm |
| Other nets | Default | 0.25 mm |

P5 removes the obsolete PDB_Fused class and its absent-net assignment after
F1 removal; all retained class widths and other settings remain unchanged.
Assignments use the full native hierarchical names where applicable. Default
clearance remains 0.20 mm and the via preset is 0.60 mm diameter / 0.30 mm drill.
Twenty-four positive track-width presets cover the existing routes; the
owner's existing zero/automatic choice is also retained. Select **Use netclass
width** in KiCad's track-width control for a fresh route, or intentionally
choose a preset for a local pad escape,
feedback, sense or indicator branch. A wide class on a supply net does not
require every branch on that net to carry full load current. A single small
via is not a rated replacement for a wide power trace. When starting on an
existing track, the toolbar's starting-track-width option can instead inherit
that track's width; this is normal [KiCad routing behavior](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#track_width).

Copper zones remain editable native KiCad objects. Route normally and refill
zones so that their clearances follow the new copper; do not cut out filled
ground manually merely to draw a trace. Review the remaining ground-return
paths after rerouting and rerun DRC. Existing segment widths are stored per
segment, so changes to class defaults do not resize an already routed path.
See `../review/PIPELINE_AUDIT.md` for provenance and the update safeguards.

## Candidate and verification contract

Build the candidate from the current native schematic inventory. Copy exact
footprint library IDs, reference designators, component values, LCSC properties,
intentional no-connects and DNP/assembly attributes. Keep schematic UUID paths
where possible for KiCad cross-probing. Footprint pin numbers must map to the
qualified native net names; a leading hierarchy slash alone may normalize,
but different sheet-local nets must not merge.

Submit the routed candidate through `pcb-copilot update-layout --candidate`.
Companion `.kicad_pro` and `.kicad_dru` files carry its settings into the checked
snapshot. Preview, inspect copper and assembly, then use explicit `--apply`.
The first-board path uses an empty baseline only when no current PCB exists;
it still checks physical inventory, exact net parity, placement, zone fill and
two fresh DRC runs. A partial board must not be installed as a finished result.

Any autorouter operates on a disposable candidate after critical copper is
manually engineered. Lock that copper and compare its geometry afterward.
Refill zones after routing/import and rerun native DRC; existing fill polygons
are not reliable after copper changes. Resolve DRC errors and unconnected items,
inspect warnings individually, and keep final copper images and native files
consistent. Routing statistics alone are not acceptance.

Inspect both copper layers, polarity marks, net ties, shunt sensing, screw
clearance, wire pads, connector mating directions and the 3D assembly. Confirm
paste/thermal-via choices at the WSON exposed pads against the actual assembler
process, including solder-wicking risk. Record measured geometry and known
limitations in the final handoff without claiming physical tests occurred.

## Release and prototype validation

All existing review-profile decisions remain required; the profile also calls
for explicit PCB copper and assembly review. Human sign-off must identify the
reviewer, date, decision and evidence and match the final CAD/input hashes.
Only the repository `release` command publishes fabrication output. A request
to finish the PCB is not a pre-filled engineering sign-off or assembly order.

The unresolved motor-regeneration energy path, externally driven output limit,
converter startup/load transients, EN power-down behavior, input-capacitance
margin, external protection/wire coordination and simultaneous-load temperature checks remain
visible in `../../DESIGN_BASIS.md` and `../review/SCHEMATIC_REVIEW.md`. Passive-network
simulations do not model the complete converters or establish PCB performance.
The final handoff must distinguish completed CAD checks from these future
model or hardware checks.

## Review each converter as a compact local circuit

For U2, U3 and U4, inspect TI Figure 9-10 and the EVM copper figures before
placement. Start with the IC, its 100 nF input bypass, main input ceramics,
BOOT capacitor, inductor and output ceramics. Draw the switching-current loops
over the placement before routing them. A schematic wire length says nothing
about the eventual PCB loop area. [S1, §§9.5.1–9.5.2, pp.26–28; S2, pp.8–9]

- Put each high-frequency input capacitor directly between its converter VIN
  and PGND pads, with the smallest practical copper loop. Keep the larger input
  ceramics close. Connect the input and output capacitor returns to local top
  copper at PGND. Do not make their pulse currents travel through a long analog
  return trace. [S1, §9.5.1 items 1 and 4; §9.5.1.1]
- Keep SW-to-inductor copper short and only as large as current/temperature
  requires. Do not turn SW into a broad plane. Place output ceramics near the
  inductor's output end with a close PGND return. Keep CBOOT's BOOT-to-SW loop
  short. [S1, §9.5.1.1 and Figure 9-10]
- Place RFBT/RFBB and the feed-forward RC beside FB. Route the output-sense
  trace away from SW and the inductors, using ground shielding where the stackup
  permits. The high-impedance FB segment must be short; the low-impedance output
  sense can travel farther. [S1, §9.5.1.2, pp.26–27]
- Keep AGND local to its converter and feedback return. Implement NT1–NT3 at
  the local AGND/PGND meeting point near the IC's exposed ground pad, following
  the schematic and Figure 9-10. These are copper bridges, not purchased 0 Ω
  resistors. Do not split the main ground plane into large isolated regions.
- Use wide, short input/output/ground paths and sufficient ground copper plus
  thermal vias to spread heat. Calculate widths/via count from actual current,
  copper, permissible temperature rise and layer arrangement. Measure the
  final hot-spot temperature under simultaneous rail loading; a 5 A IC label
  alone is not a 5 A PCB rating. [S1, §9.5.1 items 3–5; S2, §5]

The selected input C1 is board-level bulk storage. Whether extra local bulk is
needed depends on harness length/impedance and distance from C1 to each
converter. TI discusses additional bulk when a supply is more than a few inches
away. Evaluate this against the actual placement and input-ringing measurement;
do not remove the local ceramics because a large electrolytic exists. [S1, §9.4]

## Current monitor and interfaces

Route INA226 IN+ and IN− as separate Kelvin sense traces from the actual RS1
terminals. Neither sense trace may share a length of high-current copper whose
voltage drop would be counted as shunt voltage. Keep the pair away from the
three switch nodes. Put C3 directly at INA226 VS/GND. Bourns' shunt drawing and
TI's layout example identify the intended terminal-sense geometry. [S3, §§8.3–8.4,
p.31; S5, p.2]

Keep motor/servo supply and return currents out of the Pico, I2C and shunt-sense
paths. Preserve a continuous ground reference for signals. Group the DYNAMIXEL
D+/D− path together with short connector branches and review the full cable
topology; the PDB does not acquire arbitrary extra termination resistors merely
because these signals form a differential pair. The existing USB connection is
on the Pico module; there is no new USB differential pair to route on this PDB.

Place C2 near the servo connector bank. Mark every connector's function,
voltage, ground and pin-1 orientation on silkscreen, and make probe access to
TP1–TP6 practical. Preserve Pico USB, BOOTSEL and removal access. Keep J9's
3.3 V expansion budget shared with the Pico and INA226; an available header
contact does not establish additional regulated current capacity. [S6, §3.1]

## Source map

Page numbers below are printed page numbers unless marked PDF. Exact archived
bytes and provenance are retained in `../../evidence/index.yaml`.

| ID | Archived primary source | Sections used |
| --- | --- | --- |
| S1 | `../../evidence/files/LMR51450SDRRR_lmr51450_7f80073eb777.pdf`, TI SLUSEP7, Dec.2022 | §§9.3–9.5 pp.26–28; DRR0012G package/land/stencil drawings PDF pp.36–38 |
| S2 | `../../evidence/files/LMR51450SDRRR_snvu838a_6086805dfb70.pdf`, TI SNVU838A, Nov.2022 | §5, pp.8–9, Figures 5-1 through 5-6 |
| S3 | `../../evidence/files/INA226AIDGSR_ina226_c9b67f886d4a.pdf`, TI SBOS547C, Aug.2026 | §§8.3–8.4, p.31, Figure 8-4 |
| S4 | `../../evidence/files/SRP1265A-6R8M_srp1265a_30b470999b73.pdf`, Bourns SRP1265A | p.1 electrical/mechanical/land pattern; temperature and current curves following |
| S5 | `../../evidence/files/CSS2H-2512K-2L00F_css2h-2512_7e32b223f4b0.pdf`, Bourns CSS2H-2512 | p.2 dimensions, recommended pads and measurement geometry |
| S6 | `../../evidence/files/Pico_2_pico-2-datasheet_cbcfaf881018.pdf`, Raspberry Pi Pico 2, release 5 | §3, printed pp.7–9 (PDF pp.8–10); §5.4–5.5 powerchain |
| S7 | `../../evidence/files/254PM-1x20P-V_f0f6c3d8697d24302649e706e8fbe0d7_5778f815e84c.pdf`, LXWCONN | Socket drawing, recommended PCB dimensions |
| S8 | `../../evidence/files/01530008Z_5dd658d7c0c120ed4252709c4e00b44b_dd28a686cd10.pdf`, Littelfuse, rev.041720-A | p.2, 01530008 footprint and mechanical outline |
| S9 | `../../evidence/files/B4B-EH-A_LF_SN_eEH_9e35874bf275.pdf`, JST EH | p.1 ratings, p.2 board layout, p.4 Type A header |
| S10 | `../../evidence/files/2.54-1x6P_cb0770a379b121177c8c7d26dfb00406_013649a580c9.pdf`, BOOMELE 2.54-1xNA-H2.5-L11.2 | p.1, n=6, selected C37208 header |

## First-power measurements

Current-limited bring-up, rail voltages, input/switch-node ringing, startup,
shutdown, load transients, simultaneous-load temperature, servo behavior and
motor braking/backfeed remain physical tests. Use a short oscilloscope ground
spring for switching-ripple measurements. Set pass limits from the actual loads
and manufacturer specifications before recording a result.
