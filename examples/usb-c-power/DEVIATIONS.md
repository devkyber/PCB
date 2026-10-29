# Deviations and open findings

No ERC or DRC waiver is requested. No exclusion, reduced-clearance rule or
fabrication sign-off is supplied.

Revision B replaces USB4105-GF-A with the six-contact power-only USB4125-GF-A.
Its exact official footprint has 0.25 mm shell annular rings and no locating
NPTH. This resolves the former eight native DRC findings through compatible
connector geometry, without changing the rules or trimming manufacturer lands.
Native ERC/refilled DRC and exact schematic/PCB parity are clean under their
stated scope. Actual physical fit and manufacturing acceptance remain unsigned.

F1 uses an explicitly manufacturer-drawing-derived footprint with the Bourns
recommended style-1 lands, rather than claiming generic 1812 pads are identical.
F1 has no 3D body model. This mixed SMT/THT example requires a suitable reflow
process for F1; it is not a hand-solder-only kit.

All physical fit, actual assembly, source/load compatibility, USB behavior,
PPTC thermal/fault behavior, transient performance and human release decisions
remain open. No sourcing or supplier assembly rotation contract is supplied.

## Declared

