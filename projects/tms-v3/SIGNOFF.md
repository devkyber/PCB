# TMS V3 — human sign-off

> Legacy checklist for old scripts only. The current `pcb-copilot review`
> reads `review-profile.yaml` and hash-bound `review-signoff.yaml`, not these
> boxes. Ticking this file does not approve the current design.

Read by `docs/run_gates.py`. Every unchecked box fails the gate.

Checking a box records that the step was **performed**. It does not, and
cannot, record that it was performed *correctly* — that is the honest limit
of this file. Its purpose is to make the human steps visible and countable
alongside the automated ones, so a board cannot reach fabrication with them
silently skipped.

Sign by replacing `[ ]` with `[x]` and adding your initials and the date.

## Module socket pinouts (workflow Step 2.3b)

No automated check in this workspace can verify these. `validate_pcb.py`
flags the sockets and stops there.

- [ ] **J7/J8 Teensy 4.1** — pin order checked against `evidence/files/card11a_rev4_web.pdf`, with the physical module in hand. Confirm: pin 1 is the USB end on BOTH rows; J7 is the Vin/GND/3.3V row; no power rail lands on a GPIO. Teensy 4.x is **not 5V tolerant**.
- [ ] **J9 XBee 3** — pin order checked against `evidence/files/xbee3_hardware_ref.pdf` p.45. Confirm: pin 1 = VCC, pin 2 = DOUT → Teensy RX, pin 3 = DIN ← Teensy TX, pin 10 = GND.
- [ ] **J9 footprint fit** — `libs/tms.pretty/XBee_THT_20pin_P2.00mm.kicad_mod` is HAND-AUTHORED from the vendor mechanical drawing. Offer a physical XBee (or a printed 1:1 plot) against it: 2.00mm pitch, rows 22.0mm apart, pins 1-10 down one side and 11-20 up the other.

## Parts and sourcing

- [ ] **Y1 crystal** — no datasheet on file; LCSC C891749 is dead in the catalog. Confirm the 22pF load caps (C8/C9) against whichever crystal is actually bought.
- [ ] **LCSC coverage** — 44 of 53 electrical parts still carry no LCSC part number. JLCPCB assembly cannot quote those lines.
- [ ] **J1/J2 connectors** — labelled "XT60" but placed as 2-pin 2.54mm headers. This is the battery and ignition current path. Either fit real XT60 footprints or change the label.
- [ ] **Extended-part fee** — 6 unique extended-tier parts, ~$18 one-time JLCPCB setup. Accept or substitute basic-tier equivalents.

## Declared deviations

- [ ] **DEVIATIONS.md reviewed** — 3 decoupling deviations from `docs/DESIGN_RULES.md` 2.2 are declared with reasons. Agree with each, or reject and rework.

## Final visual review (workflow Phase 5.2)

- [ ] Opened in KiCad, 3D view checked for mechanical fit and part collisions
- [ ] Silkscreen readable, pin-1 markers present and correct on every IC
- [ ] Board outline and mounting holes checked against the enclosure
