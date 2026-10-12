# Declared Deviations — gnss-neom9n

A rule you cannot meet is an engineering decision. Decisions get written down
with a reason; they do not get quietly dropped from the report. Anything
`check_design_rules.py` flags that is NOT listed here is a hard failure.

Format — one per line:

    <part.pin> | <rule number> | <reason>

Example:

    U99.3 | 2.2 | VREF_N is a reference pin, not a supply rail; the 2mm
                 decoupling rule does not apply. Bypassed at the ADC's AVDD.

## Declared

    C3 | 2.2 | VCC carries 1uF (C3, 0.78mm from pin 23) + 10uF bulk (C4) and
               NO separate 100nF. Rule 2.2's generic "100nF per supply pin"
               is overridden here by the module vendor's specific instruction:
               UBX-19014286 §4.9.1 asks by name for "a 1 uF cap right next to
               the module VCC pin", and u-blox's own minimal design (Figure
               31) shows no 100nF on VCC at all. There is physically no room
               for both: U2's pads extend 0.9mm past its courtyard and the
               LDO output column ends 1.42mm away, which is narrower than a
               0603 on its side. Given a choice between the manufacturer's
               named value and a house default, the manufacturer wins.
               The NEO-M9N is a shielded module with its own internal
               decoupling behind that pin.

    BT1 | reference | NOT SOURCED VIA LCSC, deliberately. The footprint
               Battery_Panasonic_CR1220-VCN_Vertical_CircularHoles is the
               Panasonic CR1220 cell WITH SOLDER TABS (-VCN), not a holder.
               It is a soldered-in primary lithium cell, so JLCPCB will not
               fit it in any case — batteries are excluded from SMT assembly
               — and it is hand-fitted after the board arrives. Datasheet on
               file (Panasonic Energy, CR1220).
               Consequence, accepted: the backup cell is NOT field-
               replaceable. In exchange it cannot vibrate loose, which on a
               rocketry board is the better trade. If replaceability matters
               more, switch to a socketed holder and regenerate the footprint
               to match the specific holder chosen — do not reuse this one.
