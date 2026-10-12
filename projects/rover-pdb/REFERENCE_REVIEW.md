# Source and reference review — A9, 2026-10-01

`evidence/index.yaml` binds exact source bytes to URLs and hashes. Retrieval
does not establish design approval. The current native schematic and adopted
decisions are authoritative; the initial owner handover is a source snapshot.
Use `docs/design/POWER_DECISIONS.md` for A9 and `docs/design/PCB_DESIGN.md` for the next stage.

| Source | Use / review scope |
| --- | --- |
| TI LMR51440/LMR51450 SLUSEP7, December 2022 | Exact SDRRR variant; p.3 pin map, §§7.1/7.3 limits, §8.3.3 EN operation, §9.2 design selection, §§9.3–9.5 pp.26–28 operating/layout constraints. DRR0012G outline/land/stencil drawings are PDF pp.36–38. A9 derives EN from local VIN; the resistor network is an application choice calculated against these limits, not a copied TI circuit. |
| TI SNVU838A EVM guide, November 2022 | p.7 schematic, pp.8–9 copper layout and p.10 BOM. Its 3.3/5V circuit and four-layer thermal construction do not validate the motor rail or a two-layer PCB. |
| TI INA226 SBOS547C, August 2026 | DGS pinout, supply/measurement limits, address straps and calibration. §§8.3–8.4 p.31 cover local bypass and Kelvin sensing. Actual board accuracy still requires verification. |
| Raspberry Pi Pico 2 datasheet, release 5 | §3 pin assignment/mechanics; §§5.4–5.5 describe the onboard USB-to-VSYS power path. A9 uses that onboard path only: external pins 39/40 are NC and Q1 is removed. Figure 9 describes the superseded dual-source option, not the current circuit. |
| Bourns SRP1265A / CSS2H-2512 | Inductor ratings and recommended lands, SRP1265A p.1; shunt terminal/pad/sense geometry, CSS2H-2512 p.2. Neither establishes the PCB's temperature rise. |
| Murata GRM32ER71H106KA12 characterization / Samsung CL32B226KAJNNN characteristics | Effective-capacitance estimates for the selected ceramics. Typical curves are not guaranteed combined-condition minima; see MOTOR_FILTER_SELECTION.md and OUTPUT_FILTER_SELECTION.md. |
| Yageo RC0805FR-07100KL and RC1206FR-073K9L specifications | R19 100k / 0.125W and R20 3.9k / 0.25W identity, dimensions and ratings. |
| Uni-Royal thick-film resistor series, V.3, 2019-02-12 | R24 0805W8F2202T5E: p.2 decodes 0805/W8/F/2202, p.4 covers its range, p.5 gives ratings and derating. Exact C17560 supplier identity is separately archived. |
| JST EH / Samtec TSW / LXWCONN drawing | Pitch, connector/sockets and mechanics. Cable view is not a substitute for checking physical pin 1 on the purchased mating plug. |
| Littelfuse holder drawing / MINI fuse datasheet | Corrected holder geometry; provisional 10 A insert. No fuse-coordination conclusion. |
| Panasonic 2025 catalog | FR series rows, C1/C5 220 uF 50 V and C2 470 uF 16 V, B lead forming. |
| C&K OS series, exact MA1QN1 page | Pin 2 common; 1-2 or 2-3 switch states, 0.1 A / 12 V signal rating. |
| Kento KT-0805G package drawing p.2 | Manufacturer anode=1/cathode=2; corrected symbol/footprint mapping. |
| BOOMELE C37208 supplier record and exact linked drawing | J9 exact MPN 2.54-1x6P直针, 1×6 / 2.54mm straight header, remains DNP. Drawing retrieval is now resolved: 2.54-1xNA-H2.5-L11.2, n=6, specifies 1.00 mm PCB holes and nominal 0.64 mm square pins. Drawing comparison is in PCB_FOOTPRINT_REVIEW.md; actual purchased-part fit remains separate. |

Manufacturer pages consulted for external interfaces:
[ROBOTIS XH430-V350-R](https://emanual.robotis.com/docs/en/dxl/x/xh430-v350/),
[ROBOTIS U2D2](https://emanual.robotis.com/docs/en/parts/interface/u2d2/),
[C&K OS series](https://www.ckswitches.com/media/1428/os.pdf).
The ROBOTIS pages are external references, not immutable archived evidence.
Do not equate a configurable voltage-alarm register with a hardware voltage
rating or a braking clamp. There is no verified claim of guaranteed operation
for the proposed star wiring or benign converter-input behavior during faults.

Supplier CAD is archived separately from manufacturer evidence. It establishes
the requested supplier identity, not electrical limits or mechanical correctness.
All fitted discrete components have MPN/C-number selections; `docs/design/BOM_NOTES.md`
distinguishes module/socket/fuse purchases and non-purchased PCB features.
Live sourcing, assembly process and placement rotation remain order-stage checks.

LM73606 documents and the Diodes DMG2305UX document remain historical evidence
for earlier revisions. They must not restore removed converter support circuitry
or Q1 over the current schematic.

Active manufacturer links: [LMR51450 datasheet](https://www.ti.com/lit/ds/symlink/lmr51450.pdf)
and [LMR51450 EVM guide](https://www.ti.com/lit/ug/snvu838a/snvu838a.pdf).
The active circuit retains 33pF/1k feed-forward branches and open RT for nominal
500kHz. The 12V/5V inductors follow TI Table 9-2; the motor filter is a calculated
application choice. Current capacitor counts and selection limits are recorded
in the filter-selection notes. No source review claims measured stability,
thermal capacity, regenerative-energy handling or a manufacturing release.
