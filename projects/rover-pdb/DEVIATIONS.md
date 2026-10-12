# Current deviations and validation limits

Current schematic: **A10, 2026-10-04**. No electrical-rule errors are
intentionally waived. The owner reported positive personal review of A8 and
requested A9 finalization; no named, hash-bound release sign-off or blanket
waiver is recorded. Author checks of A9's changes do not become owner acceptance.

| Item | Current disposition |
| --- | --- |
| Owner-controlled CAD | Native schematics are authoritative. Future writes require the owner's explicit request; old intent, guide examples and the original project cannot overwrite manual edits. |
| PCB workflow | The owner authorized PCB design on 2026-10-01. Use a checked layout candidate and explicit `update-layout --apply`; preserve the native circuit. Exact PCB parity and fresh DRC are required before applying the finished candidate and are not assumed passed. |
| Physical baseline | The owner's saved geometry, reconciled on 2026-10-05, is a 77.5 x 100 mm rectangle with square corners; it supersedes the earlier 80 x 100 mm target and original 100 x 100 mm outline. Retain the current four-hole M3 pattern recorded in REQUIREMENTS.md, two layers / 1 oz and surface wire-solder pads. This does not transfer TI EVM thermal claims or establish enclosure fit. |
| Converter selection | U2-U4 are LMR51450SDRRR / C6890985. LM73606-specific connections are historical. Nominal 500 kHz uses RT open; PG is intentionally unused. |
| Motor enable | A9 replaces +5V drive with the local-VBAT 100k/22k pre-switch divider and retained 100k EN pull-down. SW1 sees a divided voltage below its 12 V DC rating. This removes the independent held-up source; normal hot-plug/shutdown still needs board measurement. See `docs/design/POWER_DECISIONS.md`. |
| Pico supply | USB-only; Q1 removed and carrier pins 39/40 NC. USB data loss still requires a firmware timeout; USB removal does not turn off the independent motor rail. |
| Expansion and indicator | J9 is intentionally DNP but has an exact optional part, C37208. R20 is 3.9k / 0.25W for about 5 mA through D2. The LED is not evidence of active discharge or a safe actuator state. |
| Output LC banks | L1/L2/L3 are 6.8/4.7/3.3 uH. Ceramics are four 22 uF on 12 V, five on 5 V, and four 10 uF on the motor rail, with retained bulk capacitors. Typical calculations do not prove loop stability, loaded startup or load-step performance. |
| Input capacitance | Each converter retains two 10 uF / 50 V plus 100 nF. Murata's typical curve indicates about 11.5 uF per pair at 25.2 V; combined tolerance/temperature margin is limited. The three-part recommendation in `docs/design/MOTOR_FILTER_SELECTION.md` is not implemented and is not current CAD. |
| Voltage/current limits | Divider bounds use 25 C feedback limits, not a full-temperature guarantee. Motor dropout and actual thermal/current capability require validation; component ratings do not establish a board rating. |
| Motor energy / stop behavior | No braking clamp, dump resistor, active discharge or galvanic motor disconnect is fitted. Regeneration and actual motor/servo stop behavior remain system engineering work. SW1 disables U4 rather than isolating battery power. |
| Battery and branch protection | F1 is removed at the owner's request. No onboard fuse, automatic battery undervoltage cutoff, reverse-polarity protection or input transient clamp is fitted. An external battery fuse remains recommended; fitting and coordination are unverified. Converter current limiting does not protect an input-copper short. |
| Converter footprint | Local `rover:LMR51450_DRR_WSON12_3x3` corrects supplier geometry; source archive retained. Pad/paste/thermal-via geometry and assembly rotation require layout review. |
| Inductor footprints and stock | L1/L2 retain the local SMD SRP1265A footprint (3.1 x 5 mm lands at +/-5.55 mm). L3 changes from unavailable C1329348 to Coilank APS1365M3R3DW / C54431777, still 3.3 uH, using 3.2 x 5 mm lands at +/-5.75 mm. L3 moves 0.15 mm left and TP4 moves 0.35 mm left to clear the genuine enlarged courtyard; routed segments are preserved. See `docs/design/JLCPCB.md`. |
| F1 removal | A10 removes the symbol, holder footprint and its holes, joining P1 to RS1 on BAT_SWITCHED. The older footprint and source drawings are historical. |
| D2 numbering | Symbol and footprint follow Kento: pin 1 anode, pin 2 cathode. Do not substitute generic KiCad numbering without preserving electrical and physical mapping. |
| P1-P4 footprints | Scoped surface-wire footprints are assigned and installed: P1 6 x 8 mm lands / 12 mm pitch; P2-P4 5 x 6 mm / 9 mm pitch, with no paste. The owner's removal of their optional retention holes from board and libraries remains current. External cable retention and soldering access require physical review; pinouts are unchanged. |
| SKT1 footprint | Local footprint now uses selected socket geometry and 1.02 mm drills. Drawing review is complete; purchased-part fit, header engagement, height and underside clearance remain physical checks. |
| Pico USB mechanics | The owner removed the earlier P3 USB approach keepout. Current R1/R2 placement overlaps part of that approach in plan view; a collision is not established because the module is socketed above the board. Verify the actual plug/socket/header envelope and cable bend before declaring fit or defining a replacement keepout. |
| Sourcing and assembly | Use active CAD/BOM identities and archived evidence. A footprint or LCSC code does not establish stock, assembly availability, orientation or fit. Module/socket items remain separate purchases; see `docs/design/BOM_NOTES.md`. |

`docs/review/SCHEMATIC_REVIEW.md` records schematic check scope. `docs/design/PCB_DESIGN.md`
retains the pre-layout source checklist; `docs/design/PCB_DESIGN.md` records the authorized
physical-design stage. These notes are not ERC exclusions, DRC waivers or
fabrication approval. No executable rule waiver is added by this update.

## Declared

None. The dispositions above document design differences and remaining
validation work; they do not waive any research, electrical or release gate.
