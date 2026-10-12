# Final order check — 2026-10-06, Korea time

Disposition: **visible orientation corrections look consistent; pause checkout
until the unresolved supplier placement and order-review choices are addressed.**
This is an author review, not a named owner's engineering sign-off.
No CAD, upload files, cart selections or order settings were changed. No order was
submitted or paid.

## What was checked

Compared the owner's new top-view screenshot (`codex-clipboard-6fbd2263-9929-450e-b7cb-558a41731f25.png`)
with current native pad nets, placements, the generated BOM/CPL and the saved
upload manifest. Inspected the live `gerbers_Y5` cart's PCB Product Detail and
PCBA Product Detail/Bill of Material. This is visual correspondence and matching
part selection, not a byte-for-byte download comparison of JLCPCB's stored Gerbers.

| Item | Observation |
| --- | --- |
| U1 | Leads now face left/right; the visible marker is upper-left, consistent with native pad 1 and TI's pinout. The prior 90-degree error is corrected. |
| J2/J3/J4/J8 | Three pins now lie horizontally along the PCB hole rows. Left-to-right native nets are signal, +5V, GND. These unshrouded straight headers are mechanically symmetric after another 180-degree turn. |
| U2/U3/U4 | Visible terminal axes and upper-left orientation marks agree with native geometry and the previous datasheet audit. Hidden pads cannot be judged from this image. |
| C1/C2/C5 | Positive side is left, negative stripe/right terminal is right, consistent with native pad nets. |
| D2 | Anode/positive side left, cathode right, consistent with this part's custom A1/K2 mapping. |
| J1/J5/J6/J7 | Pin rows and housing/key direction agree with the prior JST drawing review; locking side faces the bottom board edge. |
| SW1 | Horizontal body with actuator toward the top board edge agrees with the native footprint. |
| L1/L2 and ordinary R/C/RS1 | No additional obvious terminal-axis mismatch visible. Nonpolar end-for-end reversal is harmless. This is not measurement of lead tolerances or hidden solder joints. |
| P3 | Upper pad correctly reads +12V and lower pad GND. P1/P2/P4 labels also agree with native nets. |
| L3 | Still has no supplier body/model. Native footprint pads face left/right, but the image cannot establish the supplier's actual component orientation. A local STEP does not supply JLCPCB's library model. |

The live cart listed **25 selected part groups and no unselected parts**. Exact
MPN/C-number/reference groups matched the 71-component local BOM, including
L3 APS1365M3R3DW/C54431777 (5 pieces), SW1 OS102011MA1QN1/C226259 (5 pieces),
all four JST connectors (20 total) and all four three-pin headers (20 total).
Some passive purchase quantities exceed fitted demand, consistent with minimums
and assembly attrition. Selection is not a perpetual inventory reservation.
SKT1 sockets and Pico remain manual-fit; J9 is intentionally DNP.

**Stock distinction:** the earlier zero count for C226259 was LCSC retail stock.
It is not proof of unavailability in this JLCPCB cart: SW1 was explicitly selected,
priced and listed as JLCPCB-sourced. Do not infer that it is omitted or substitute
another switch solely from that retail result.

## Actual order settings observed

- Five PCBs and five top-side Economic PCBAs.
- FR4 TG135, two layers, 77.5 x 100 mm, 1.6 mm thick, 1 oz outer copper,
  green mask, white silk and tented vias: match the design baseline.
- HASL **with lead** selected; this is the actual finish choice, not lead-free HASL.
- Bare PCB electrical test: Flying Probe Fully Test. PCBA Function Test: No.
  The bare-board continuity test does not test powered converter behavior.
- **Confirm Parts Placement: No. Confirm Production File: No.**
- Assembly remark: No. File provided as: Complete File, just proceed with my own files.
- Tooling holes: Added by JLCPCB. Depanel boards/edge rail before delivery: No.

Before committing, enable the placement and PCB production-file review options.
Use manual confirmation if offered and pay attention to any confirmation deadline;
do not assume the order remains on hold indefinitely. Review added tooling holes
against copper, mounting holes and required clearances in the actual production files.
The exact L3 part and horizontal terminal registration need JLC engineering confirmation.

Suggested assembly remark (not sent):

> L3 is Coilank APS1365M3R3DW, C54431777, 3.3uH, nonpolar. Its model is missing
> in the preview. Please verify both terminations align left/right with the
> 3.2 x 5.0mm lands at 11.5mm pitch, and provide placement confirmation before
> assembly. Please retain the corrected U1 pin-1 upper-left orientation.

JLCPCB references:
[orientation, polarity and selected-part handling](https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2),
[production-file confirmation](https://jlcpcb.com/help/article/how-to-confirm-the-production-file),
[confirmation-dialog deadline wording](https://cart.jlcpcb.com/client/template/placeOrder/component/smtConfirmFileModal.html),
[Economic assembly tooling holes](https://jlcpcb.com/help/article/how-to-add-tooling-holes-for-pcb-assembly-order).

## Local validation and remaining design limits

All current inputs and output hashes still match `output/jlcpcb-preview/SOURCE.json`.
Fresh review: ERC 0 violations; two refilled DRC runs with 0 errors, 0 warnings
and 0 unconnected; independent JLCPCB DFM and local assembly contracts passed.
The 13 machine checks pass. The sign-off check remains 0/5 current decisions.
The original check is retained byte-for-byte at
[`records/final-order-review-2026-10-06.json`](records/final-order-review-2026-10-06.json).
It was relocated during the 2026-10-07 cleanup; the reported results and hashes
still describe the 2026-10-06 run, before the later shared review-policy update.

This remains an unvalidated power-board prototype. The documented unresolved
items include motor regeneration (no braking clamp), thermal/transient behavior,
actual USB/socket/harness mechanical fit and external battery protection (no
onboard fuse). Passing orientation or DRC does not resolve those engineering items.
See `review-profile.yaml` and `DEVIATIONS.md` for the exact outstanding scope.

During the final inspection the browser changed to a signed-out cart view. The
settings above were read directly before that change; recheck them after login.
No checkout or delete action was performed.
