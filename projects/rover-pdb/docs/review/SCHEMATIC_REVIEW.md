# Schematic review — A10, 2026-10-04

A10 removes F1 at the owner's explicit request and directly joins P1 to RS1 on
BAT_SWITCHED. The overview, input-sheet notes and PCB match that scoped change.
Five other child sheets remain byte-identical. No onboard input fuse remains;
external battery protection is recommended and unverified. P2/P3 remain 12 V
for the owner's future expansion plans. Current checks report zero ERC errors
and warnings, no critical-net/selected-component/footprint-pin failures and no
unassigned footprints. All seven rendered sheets were visually inspected.
This is author verification, not a named owner fabrication sign-off.

The detailed P5/A10 PCB and source-bound checks are recorded in
`PCB_VERIFICATION.md` and `records/p5-pad-socket-review.json`. The initial YAML
intent still describes F1 and remains a historical comparison; it must not
restore that circuit over current native CAD. The current netmap is derived
from the installed hierarchy.

## Historical A9 finalization

Finalized 2026-10-01 for the requested schematic scope. The owner stated that
they had checked the schematic and it looked good, then requested the final
power/sourcing changes. `records/owner-review.json` binds that report to the preceding
A8 inputs. A9 is the subsequent authorized delta; its author checks below are
not a claim of personal owner reinspection or blanket acceptance of open risks.

Current schematic changes are explained in POWER_DECISIONS.md. R19=100k,
R24=22k and R15=100k produce a VIN-derived motor-enable signal within the
switch rating. Pico is USB-only; Q1 is removed and pins 39/40 are NC. J9 is
DNP with exact selected header C37208. All converter filters remain unchanged.

PCB-stage update, 2026-10-01: the owner subsequently authorized layout, including
scoped footprint assignments. The routed native PCB is now installed after
exact parity and two clean DRC runs. `PCB_FOOTPRINT_REVIEW.md` records the
footprint-only schematic delta and unchanged circuit. The schematic-finalization
checks below retain their original scope; they are not retroactive PCB approval.

## Engineering and manufacturing review items

| Priority | Question / observation | Needed review |
| --- | --- | --- |
| High | Motor regeneration has no clamp. Nominal output capacitance stores only about 11 mJ between 22.190 and 24 V. The selected PFM converter is not an energy sink. | Establish allowable motor voltage, mechanical braking energy, the energy-dissipation path and VOUT-versus-VIN behavior. Resolve the circuit/system acceptance before manufacturing release. |
| High | SW1 only drives U4 EN; it is not a power isolator. Stored energy and external backfeed can leave voltage present. Motor torque loss can release the hammer. | Confirm the required stop behavior and mechanical restraint. D2 alone cannot prove de-energization. |
| Medium | A9 derives motor EN from local VBAT and removes the independent held-up +5V source. | Verify VIN/EN during actual shutdown and hot-plug; the divider is not a guarantee against arbitrary input spikes or hard shorts. See POWER_DECISIONS.md. |
| High | The nominal motor-capacitor startup current plus an already-active 3.5 A load can exceed the replacement's 5 A rating during a short soft-start ramp. | Verify loaded startup and current-limit/hiccup behavior with actual capacitance, motor electronics and supply impedance. |
| High | A10 has no onboard battery fuse. U4 current limiting does not establish protection for input copper, each motor branch or JST contact. | Review external battery protection, prospective fault current, wiring and branch/contact protection. No external fuse is assumed fitted. |
| High | There is no battery undervoltage cutoff, reverse-polarity protection or input transient clamp. | Accept or revise the protection architecture with pack limits, harness arrangement and hot-plug/power-down transients considered. |
| Medium | Servo identity, current, pin order and missing-PWM response remain provisional. | Check the actual FS90MGR units and their plugs; confirm 3.3 V PWM and powered-servo/unpowered-Pico behavior. |
| Medium | Pico/INA226/J9 now depend on USB power; motor enable remains independent of USB. | Check unpowered-Pico/powered-servo behavior and firmware startup/command timeout. USB data can fail while VBUS remains powered. No backup power path is fitted. |
| Medium | LMR51450 support values are revised; retained LC banks and the new feed-forward networks are starting choices, not a demonstrated stable design. | Verify DC-bias curves, capacitance/ESR, loop response, load steps, foldback, thermal margin and regenerative loads. |
| Medium | The replacement is rated up to 5 A; the PCB now provides local ground copper and external thermal vias, but temperature rise is unmeasured. | Validate copper/vias, assembly, ambient temperature and simultaneous-rail loading. Do not inherit the EVM's rating without its thermal conditions. |
| Medium | Motor 22.190 V cannot stay regulated over the full 6S battery range. | Check acceptable motor performance as battery voltage falls; DESIGN_BASIS.md contains estimates, not guaranteed dropout boundaries. |
| Medium | Nominal outputs are now 11.989 / 4.988 / 22.190 V; calculated bounds are for 25 C only. | Review load voltage limits against DESIGN_BASIS.md, temperature, PFM offset and transients. |
| Medium | Module/socket footprints, surface-wire lands, board outline and mounting are implemented from the selected drawings; actual physical fit and cable retention remain untested. | Confirm purchased socket/header fit, connector pin-1 orientation, harness anchors, fuse access, capacitor height and chassis fit. |
| Medium | Shared +12V and +5V expansion rails have no reserved current or separate fault protection. | Leave P3/P4 unwired; revise budget and fault analysis before expansion. |

## Delivered schematic checks

- Seven sheets visually reviewed: overview, battery/INA226, 12 V, 5 V, motor,
  Pico/servos and DYNAMIXEL distribution. Enlarged circuit details were also
  inspected. The SW_SUPPLY label was moved clear of the switch pin number and
  the fresh changed-sheet render inspected.
- Native KiCad 10.0.6 ERC: zero errors and zero warnings.
- 85 physical symbols, 39 connected nets. Exact intended connectivity delta
  verified; retained physical-symbol and pin UUIDs preserved.
- Q1 removed; R24 added; only R19's selection, SW1/R19 connections, J9 sourcing
  and the specified Pico power pins change. JP1/J8 remain absent.
- Pico pins 39/40 gain NC markers; all 29 prior NC associations are preserved.
  Input/monitor, 12 V, 5 V and DYNAMIXEL child sheets remain byte-identical.
- Intent/native connectivity, critical connections, selected identities and
  assigned-footprint pin sets agree. Deliberately injected connection errors
  are detected by the read-only audit. P1-P4 footprints were intentionally
  unassigned at schematic finalization and have since received the owner's
  selected surface-wire footprints; see the separate footprint-assignment record.

See `records/schematic-checks-A9.json` for retained A9 checks. The last existing
preview was preserved as `records/schematic-checks-retained-20261007.json`
during cleanup, with its original source hashes; new runs write
`.pcb-copilot/preview/schematic-checks.json` at the project root for
source hashes and results. No simulation, PCB/DRC, thermal model, bench test or
manufacturing sign-off is represented by these schematic checks. The original
stop-before-PCB request was later superseded by the owner's layout instruction;
current PCB checks and remaining validation are documented separately.

## Future editing

Open the native KiCad project and make personal edits there. Current CAD takes
precedence over exported intent, a PDF, the older teaching guide and archived
revision reports. Read-only check_schematic.py reports differences but never
restores old CAD. Re-export the PDF after later edits; old hashes/checks are then
historical and must not be relabelled as a current approval.
