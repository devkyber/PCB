# TMS A2 electrical schematic review

Date: 2026-10-14. Author: Codex. Status: installed schematic, DRAFT.
The owner authorized the schematic-stage installation; engineering, PCB and
fabrication approval remain open. No human review decision is signed here.

## Final corrections

A2 replaces the buck with LMR51430YFDDCR, selects exact passive orders and
sizes its 3.3 uH / 30 uF input / 100 uF output nominal network against the
stated 1 A load and capacitor derating screen. It separates the unintended
battery-to-EN short, adds the 47 pF XBee bypass and input TVS, adds TXU0204
power-off UART buffering, and uses supported Serial3 TX14/RX15/CTS19/RTS18.

The ADS1256 requires buffer ON. The pressure divider now drives an OPA388
buffer and 47 ohm / 10 nF ADC network. Unused ADC inputs are NC; ADS1220
CLK3/DGND4/AVSS5 stay grounded. J5 drill is 1.50 mm and J6 is the PCB-mount
XT60PW-F. All three AMASS connectors are corrected to **positive pad 2,
return pad 1**, against the actual assigned footprint polarity markings.
Digi's early revision-B brownout erratum is documented; specify/inspect
revision C or later. USB module recovery is performed off the carrier.

The complete [component guide](../design/COMPONENT_VERIFICATION.md) records
purpose, value/rating, exact order, source pages/hashes and remaining checks
for all 120 references. The [firmware contract](../design/FIRMWARE_CONTRACT_A2.md)
records the untested configuration requirements. External sockets, harness,
protection and enclosure items are listed separately and remain unqualified.

## Bound verification

- 120 physical parts; 380 pins; 59 explicit NCs; 69 expected connected nodes.
- Exact selected-part evidence covers all 110 purchased references with no
  missing association; all archived evidence passes integrity checks.
- Independent node, NC, symbol-instance metadata and connector-polarity
  checks pass. Five deliberate defects are rejected: EN short, missing RF
  bypass, wrong ADS1220 CLK NC, unsupported CTS, and reversed connector polarity.
- Normal shared footprint resolver and pin/pad check pass for all 120 parts.
  Five local footprints have manufacturer-source-bound receipts. This proves
  source lineage and covered geometry/pad mapping, not purchased-part fit.
- Fresh native ERC: zero violations. Eight sheets pass machine quality checks.
- 215 focused evidence/review/footprint tests pass (five dependency deprecation
  warnings). Tests of the gates are separate from hardware validation.
- All eight rendered sheets inspected at page and circuit scale. Overview,
  power, controller, thrust, reference, pressure, radio and ignition were
  reviewed for functional pin arrangement, signal/power flow, labels, NCs,
  loops, notes, title blocks and text/wire collisions. The final connector,
  radio and thrust revisions were re-inspected after correction.
- The final guide pages were rendered and visually reviewed, with no detected
  out-of-page text; table pagination was corrected before publication.
- 97 retained physical UUIDs preserved; 23 parts added; C9 removed.

## Installation authorization and scope

The user answered **Install reviewed A2 schematic (Recommended)** to:

> Allow a schematic-stage exception to install the reviewed A2 circuit,
> libraries, netmap and verification documents? It has 120 components / 380
> pins, clean ERC, complete selected-part evidence and pin/pad checks. Normal
> apply fails on the empty PCB. This changes no PCB files and grants no
> fabrication or live-ignition approval; remaining physical and bench
> qualifications stay open.

The normal checked update requires a matching routed PCB (shared
WORKFLOW section 2). Its native outline operation fails on this empty board.
The authorized exception uses the shared transaction lock, editor-lock
check, input/target hash guards and rollback path. It preserves PCB, project,
design-rule, manifest and all unrelated owner files. Active prior review/release
state is invalidated. Exact scope and hashes are in the installation receipt.

## Remaining qualifications and release status

The full current pipeline remains blocked on empty-board netlist parity,
placement/copper, DRC/DFM, assembly and 0/12 current human decisions. Geometry
checks that pass on an empty PCB do not qualify placement or routing.

Before layout is finalized, resolve enclosure/outline and purchased parts,
socket/connector polarity and revision/fit, return paths and actual harness
ratings. Before hardware acceptance, demonstrate rail/transient/thermal and
reference-loop stability, RF ripple, input sequencing/ESD, sensor loading,
calibration/temperature/bandwidth, sampling/SD throughput and dummy-load
reset/brownout/interlock/fault behavior. The author assumptions are explicit
contracts, not measured facts or a promise of flawless operation. No fabrication
or live-ignition approval exists.

## Installed-root recheck

Fresh checks against the installed root reproduce zero ERC violations, all
380 pin/NC/polarity checks, all 120 footprint maps and all 110 required
selected-part evidence associations. The complete pipeline has the same six
expected release blockers. Installed CAD and published PDFs match the reviewed
bytes; PCB/project/rule/manifest hashes are unchanged. See
[installed check record](records/electrical-a2-installed-checks-20261014.json)
and [installed pipeline report](records/electrical-a2-installed-review-20261014.json).
