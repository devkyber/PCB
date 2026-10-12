# Declared Deviations — imu-icm42688

A rule you cannot meet is an engineering decision. Decisions get written down
with a reason; they do not get quietly dropped from the report. Anything
`check_design_rules.py` flags that is NOT listed here is a hard failure.

Format — one per line:

    <part.pin> | <rule number> | <reason>

Example:

    U99.3 | 2.2 | VREF_N is a reference pin, not a supply rail; the 2mm
                 decoupling rule does not apply. Bypassed at the ADC's AVDD.

## Declared

    J1 | 12.1 | J1 is the only through-hole part on the board and rule 12.1
                asks for thermal relief on THT pads in a ground pour, for
                hand-solderability. The GND zones here use SOLID pad
                connection instead, because every other netted pad is SMD
                and a starved thermal spoke on a 0402 decoupling cap is a
                high-inductance ground on a part whose datasheet allows
                only 10 mVpp of supply noise (DS-000347 §3.3.2). J1 pin 2
                is therefore harder to hand-solder — use a higher iron
                temperature and more dwell. Accepted: one connector pin is
                worth less than the rail integrity of the whole board.
