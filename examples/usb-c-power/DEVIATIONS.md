# Deviations and open findings

No ERC or DRC waiver is requested. No exclusion, reduced-clearance rule or
fabrication sign-off is supplied.

The unchanged official USB4105 footprint has eight native DRC errors under the
unmodified workspace geometry baseline: four 0.20 mm shell annular rings
(0.25 mm recommendation) and four 0.1944 mm GND-pad/NPTH clearances (0.25 mm
baseline). The latter also falls below the fabricator's cited 0.20 mm spacing.
See DESIGN_BASIS.md for the exact drawing comparison and the reason the
manufacturer's contact lands were preserved. This is an unresolved physical
manufacturing constraint, not a clean-DRC example.

F1 uses an explicitly manufacturer-drawing-derived footprint with the Bourns
recommended style-1 lands, rather than claiming generic 1812 pads are identical.
F1 has no 3D body model. This mixed SMT/THT example requires a suitable reflow
process for F1; it is not a hand-solder-only kit.

All physical fit, actual assembly, source/load compatibility, USB behavior,
PPTC thermal/fault behavior, transient performance and human release decisions
remain open. No sourcing or supplier assembly rotation contract is supplied.

## Declared

