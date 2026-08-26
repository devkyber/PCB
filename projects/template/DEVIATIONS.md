# Declared Deviations — template

A rule you cannot meet is an engineering decision. Decisions get written down
with a reason; they do not get quietly dropped from the report. Anything
`check_design_rules.py` flags that is NOT listed here is a hard failure.

Format — one per line:

    <part.pin> | <rule number> | <reason>

Example:

    U99.3 | 2.2 | VREF_N is a reference pin, not a supply rail; the 2mm
                  decoupling rule does not apply. Bypassed at the ADC's AVDD.

(The example uses U99 on purpose: a plausible designator here would be
parsed as a real waiver. Put real entries under "## Declared" below —
nothing above that heading waives anything.)

## Declared
