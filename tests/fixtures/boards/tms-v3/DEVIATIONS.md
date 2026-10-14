# TMS V3 — declared deviations from docs/DESIGN_RULES.md

Read by the `pcb-copilot review` design-rule check. Format, one per line:

    <part.pin>  |  <rule number>  |  <reason>

A rule that cannot be met is an engineering decision, and engineering
decisions get written down with a reason. Anything NOT listed here is a
hard violation and fails the build. Adding a line is a deliberate act — it
should be reviewed like any other change, and a human should agree with it.

## Declared

Review warning (2026-09-17): the historical U2.15 row below calls the pin DVDD.
The archived `evidence/files/ADS1256_ti.pdf` p.5 identifies pin 15 as RESET and
pin 16 as DVDD. The existing waiver text/scope is retained for owner review;
it does **not** cover U2.16. Remeasure the actual DVDD bypass before proposing
any replacement waiver. This annotation grants no new exception.

Only lines under this heading waive anything. Text above it is
documentation. Before 2026-08-26 this file had no such heading, and the
parser silently fell back to reading the WHOLE file — the mode that
produced four separate false-waiver bugs.

The scope field (middle) must be a numbered rule from
`docs/DESIGN_RULES.md`, or one of `reference` / `basis` / `datasheet`
to excuse a research gate. A waiver is only as wide as its scope.

U2.3  | 2.2 | VREF_N. C7 is a single cap across VREF_P/VREF_N (pins 3-4) and can only hug one of them; it sits 2.4mm from VREF_P and 3.0mm from VREF_N. Splitting into two caps would need a schematic change. HUMAN: confirm against the TI ADS1256 EVM reference layout before fab.
U2.15 | 2.2 | DVDD. 2.3mm rather than 2.0mm. Pins 14 and 15 are on OPPOSITE sides of the SSOP-28 (1-14 down, 15-28 up), and the pin-15 side also carries XTAL1/XTAL2, where rule 5.1 gives the crystal first claim on the space. C6 is as close as the 0.5mm reflow clearance of rule 1.2 permits.
~~U3.13 | 2.2 | DVDD. 3.1mm.~~ **WITHDRAWN 2026-08-26 — this was not a
        geometry conflict, it was a missing capacitor.** C10 and C11 were
        BOTH decoupling pin 12 (AVDD) and nothing was decoupling pin 13
        (DVDD); the "3.1mm" was the distance to an unrelated cap. TI
        SBAS501 section 9.3.3: "AVDD, AVSS ... and DVDD must be decoupled
        with at least a 0.1uF capacitor ... as close to the power-supply
        pins of the device as possible." C11 is now the DVDD cap on +3V3,
        placed at pin 13, and the rule passes on its merits.
        Lesson: a deviation that explains away a symptom stops anyone
        looking for the cause.
