# Declared Deviations — baro-bmp390

A rule you cannot meet is an engineering decision. Decisions get written down
with a reason; they do not get quietly dropped from the report. Anything
`check_design_rules.py` flags that is NOT listed here is a hard failure.

Format — one per line:

    <part.pin> | <rule number> | <reason>

Example:

    U99.3 | 2.2 | VREF_N is a reference pin, not a supply rail; the 2mm
                 decoupling rule does not apply. Bypassed at the ADC's AVDD.

## Declared

    U1.5 | 2.2 | Pad 5 is SDO, not a supply pin. Datasheet §6.3 Fig 25 ties it
                 to VDDIO to select I2C address bit X of 111011X (= 0x77); the
                 net is +3V3 only because that is what "address = 1" means on
                 this part. A decoupling capacitor within 2mm of an address
                 strap decouples nothing. The rule is right and the checker is
                 net-based, so it cannot see the difference — hence this line.
                 VDD (pad 10) and VDDIO (pad 1) are the real supply pins and
                 both meet 2.2 with C1 and C2.

    U1.6 | 2.2 | Pad 6 is CSB, interface select, same case as U1.5. Tied to
                 VDDIO per Fig 25 to select I2C over SPI. Not a rail.
