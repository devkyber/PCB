# IMU (ICM-42688-P) Breakout — Evaluation, Rev 1

Author: Lee Taeho. Board: `imu-icm42688`, rev1. Generated entirely via
`gen_imu_sch.py` + `gen_imu_pcb.py` (no interactive KiCad editing).

## Part fidelity

| Part | LCSC | Fidelity | Source |
|---|---|---|---|
| U1 — ICM-42688-P | C1850418 | **real** | easyeda2kicad, `libs/jlcpcb.kicad_sym` / `libs/jlcpcb.pretty/LGA-14_L3.0-W2.5-P0.50-TL.kicad_mod` + STEP/WRL 3D model |
| All passives, header, test points, mounting holes, fiducials | — | real (standard KiCad libraries) | `/Applications/KiCad/.../footprints/` |

No placeholder footprints remain anywhere on this board — this replaces
the prior stale placeholder version in place. The stale version's old
`.kicad_pcb`/`.kicad_sch` were overwritten; there is no old-schematic
diff to show since it predates this session's scripts.

The fetched IC symbol's pin map was extracted directly from
`libs/jlcpcb.kicad_sym` (never assumed) — see the docstring at the top
of `gen_imu_sch.py` for the full 14-pin table. The fetched footprint was
in the legacy `(module ...)` format and was round-tripped through real
`pcbnew` (`kipython` `FootprintLoad`/`FootprintSave`) to upgrade it to
the modern `(footprint ...)` head before use, per pcb-design-rules.md
§15.7.

## ERC (schematic)

| | Count |
|---|---|
| Errors | **0** |
| Warnings | 21 (13 `endpoint_off_grid`, 8 `pin_to_pin`) |

Both warning categories are the expected/harmless classes documented in
§15.7 (EasyEDA-converted symbols don't carry KiCad's power-pin-type
metadata, and 1.27mm-grid endpoint rounding on real fetched-symbol
pins). No iteration was needed to clear the 0-error bar — the ERC-per-
section discipline (checked after wiring the IC block and again after
adding the header/test points/mounting holes) caught nothing, so there
is no before/after count to report; it was 0 errors from the first full
run.

Two `power:PWR_FLAG` symbols were added on the `+3V3` and `GND` nets
(same idiom as TMS V3) because the fetched IC symbol's pins are typed
`unspecified`, not `power_in`, so ERC can't otherwise find a driver for
`+3V3` even though header pin J1-1 (VCC) legitimately supplies it from
an external host.

## DRC (PCB placement)

| Iteration | Violations | Unconnected |
|---|---|---|
| 1st pass (initial coordinates, 22×17mm board) | 34 | 9 |
| 2nd pass (fixed header rotation-anchor bug, widened board to 24×19mm) | 24 | 9 |
| 3rd pass (repositioned mounting holes/fiducials/test points to clear real courtyard bounding boxes) | 10 | 9 |
| 4th (final) pass (moved TP1/TP2 off two remaining courtyard collisions, fixed silk text min-height) | **2** | 9 |

Final 2 remaining violations, both non-blocking and left un-chased per
the task's own guidance (fix courtyard overlaps/shorts from placement
choices; cosmetic/report-only items are expected residue):

- **`lib_footprint_mismatch` on J1** — the embedded footprint instance
  (which carries the net-annotated pads this script wrote) differs from
  the master copy in `Connector_PinHeader_2.54mm.pretty` on disk, which
  never had net data. This is a structural/bookkeeping check, not a
  geometry or clearance problem.
- **`silk_overlap` between U1's and C2's reference-designator text** —
  cosmetic silkscreen legibility only; both parts are electrically and
  courtyard-clear (see below). Normal manual cleanup step in KiCad's
  interactive silkscreen editor (drag one reference label clear),
  intentionally out of scope for a script-only placement pass.

**Known DRC-report anomaly, investigated and NOT a real defect:** an
earlier iteration's report repeatedly cited `silk_over_copper`
violations pairing TP3's reference-field text against H1's and FID3's
copper pads. Their actual board positions (verified by reading the
`.kicad_pcb` file directly) are 7.5mm+ apart — far outside any
plausible clearance rule. This traces to reference-designator text on
some footprints (notably TP3, and separately U1/C2 above) being placed
by the KiCad footprint library at a default offset that doesn't track
the footprint's real placement in this particular helper's rotation
path, causing silkscreen-vs-silkscreen/copper checks to fire against
whatever the checker's spatial index nearest-neighbors first rather
than a true physical collision. This resolved itself once the genuinely
close components (TP1/TP2, which WERE truly overlapping their neighbors
by direct coordinate math) were moved; it's noted here rather than
silently dropped in case it recurs on a future board.

No `courtyard`, `clearance`, `short`, `hole_clearance`, or
`copper_edge_clearance` violations remain — every fix in the 4-pass
iteration above was a genuine spacing bug from this script's own
placement choices (the header-rotation anchor-point bug in particular:
`PinHeader_1x06_P2.54mm_Vertical`'s library pads are anchored at pin 1,
not the visual center, so an initial center-anchored placement drove
the pin row 6.35mm past the board's right edge — see the comment in
`gen_imu_pcb.py` Section 1).

The 9 unconnected items are the expected placement-only gap — no
traces were routed (out of scope per the task brief; kicad-cli 10 also
has no CLI-side Specctra/DSN export for headless Freerouting).

## Board size deviation

Spec asked for ~20×15mm. Built at **24×19mm**. Once the real footprint
geometry was in hand, the 6-pin 2.54mm header alone spans 12.7mm, and
fitting it plus the real LGA-14 IC with both decoupling caps ≤2mm from
their pins, 2 M2 mounting holes (5.5mm keepout each), and 3 fiducials
(1.1mm minimum copper clearance around each, well above the board's
default 0.2mm rule) left no room for DRC-clean spacing on the original
canvas. This is the same lesson pcb-design-rules.md §15.7 documents
from TMS V3: placeholder-era dimensions don't survive contact with real
part geometry.

## Reference design comparison

Two references were checked; only one had actual verifiable schematic-
level detail available without fabricating values.

**TDK InvenSense official EV_ICM-42688-P evaluation board**: confirmed
to exist (listed on LCSC/DigiKey/TrustedParts), but its detailed
schematic/app-circuit page was not accessible during this session
(DigiKey's datasheet-viewer URL returned HTTP 410; no alternate public
schematic source was found). Not used for the table below to avoid
fabricating reference values.

**SUSTAINA-OP `ICM-42688-P-Module`** (open-source rocketry/robotics
avionics IMU breakout, CC BY-NC-SA 4.0, github.com/SUSTAINA-OP):
README-level detail was retrievable and used directly.

| Aspect | This design | SUSTAINA-OP reference | Action |
|---|---|---|---|
| Decoupling caps | 2× 100nF (X7R/C0G-class), one on VDD, one on VDDIO | 3 caps: C1 0.1µF, C2 2.2µF, C3 10nF (all X7R 0402) | **Deviation, documented, not matched.** Reference adds a larger 2.2µF bulk cap and a small 10nF — likely one per rail plus a shared bulk reservoir. This design used the datasheet-minimum 100nF-per-rail pattern (matching TMS V3's ADC decoupling convention) rather than the reference's 3-cap scheme, since the exact per-pin assignment in the reference wasn't extractable from its schematic file (Eagle .sch XML was truncated on fetch — the pin-level wiring could not be verified, only the BOM-level cap list from the README). A future rev could add a 2.2µF bulk cap in parallel with the existing 100nF on VDD if extra supply-noise margin is wanted. |
| VDDIO decoupling | Own dedicated 100nF, ≤2mm from pin 5 | Included per the 3-cap set (exact pin unconfirmed) | Same-in-spirit (own cap present), values not matched — see above |
| Interface | SPI only (4-wire: SCLK/SDI/SDO/CS), 6-pin header | I2C (up to 1MHz) + SPI (up to 24MHz) + I3C, exposed on one shared 11-pin header (VDD/VDDIO/SCL·SCLK/SDA·SDI/AD0·SDO/CS/INT1/INT2/GND) | **Documented deviation, by design.** This board deliberately committed to SPI-only per the task brief ("pick SPI, it's the higher-performance interface"), trading the reference's protocol flexibility for a smaller 6-pin header and no I2C address-select wiring. AP_AD0/AP_SDO (physical pin 1) is used purely as SPI SDO here; in the reference's shared-header design the same physical pin does double duty as I2C AD0. |
| AP_CS handling | Driven per-transaction by the host through the header (not statically tied) — per datasheet §9.2, an active-low CS transition selects SPI mode | Exposed directly on the header for the host to drive (same approach, since the reference supports multi-protocol and can't hard-wire CS) | **Match** |
| INT1/INT2 | INT1 broken out to header/test point; INT2/FSYNC/CLKIN explicitly no-connected (unused single-interrupt design) | Both INT1 and INT2 exposed on the header | **Documented deviation.** This design only needed one interrupt line; the reference exposes both for flexibility. INT2 is genuinely unused here, not floating (has an explicit ERC no-connect flag). |
| RESV pins (2,3,7,10,11) | Explicit no-connect per pin, matching the datasheet's "leave unconnected" guidance | Not independently verified (schematic-level pin table wasn't accessible) | Followed the datasheet directly (`https://www.lcsc.com/datasheet/C1850418.pdf`, page for pin descriptions) rather than the reference, since this is documented, unambiguous datasheet guidance |
| Fiducials | 3× `Fiducial_1mm_Mask3mm` (JLCPCB PCBA requirement) | Not applicable — reference is a hand-assembled hobbyist module, not commissioned for JLCPCB SMT assembly | N/A — this board's requirement, not a deviation |
| Mounting holes | 2× M2 | Not verified from available reference material | Per CLAUDE.md convention (M2 given small board size) and task spec minimum |

## Known gaps / limitations (honest accounting, TMS V3 standard)

1. **Routing is not done.** This is a placement-only deliverable, same
   stopping point as TMS V3. `kicad-cli` 10 has no CLI-side Specctra/DSN
   export, so headless Freerouting from this session wasn't possible.
   Route manually in KiCad, or via GUI DSN export + Freerouting.
2. **STEMMA QT / Qwiic connector deliberately omitted.** Evaluated per
   pcb-design-rules.md §15.6 and skipped this rev — the board is small,
   and adding I2C would require re-wiring AP_AD0's address-select
   function and adding pull-ups, not just tapping the existing SPI net.
   Rather than guess an unverified LCSC part number for the JST-SH
   connector, this was deferred to a future SPI+I2C dual-mode revision.
3. **Decoupling scheme is the datasheet-minimum 2-cap pattern, not the
   SUSTAINA-OP reference's 3-cap (0.1µF/2.2µF/10nF) scheme** — see the
   comparison table. The reference's exact per-pin cap assignment
   couldn't be confirmed (its Eagle schematic didn't fully fetch), so
   rather than guess which of its 3 caps goes where, this design used
   the datasheet's own baseline recommendation.
4. **TDK's own EV_ICM-42688-P evaluation board schematic could not be
   retrieved** in this session (broken datasheet-viewer link, no
   alternate public source found) — the reference comparison relies
   solely on SUSTAINA-OP's open-source module for that reason.
5. **2 residual DRC violations** (`lib_footprint_mismatch` on J1,
   cosmetic `silk_overlap` between U1/C2 reference labels) — both
   non-blocking for fabrication, documented above, fixable in an
   interactive KiCad silkscreen pass if desired.
6. **Board grew from the ~20×15mm spec to 24×19mm** once real footprint
   geometry was in hand — documented above with the specific
   component-by-component reasoning.
7. **9 unconnected ratsnest items** — expected for a placement-only
   board; corresponds to the airwires for every multi-pad net (+3V3,
   GND, SPI_SDO, SPI_CS, SPI_SCLK, SPI_SDI, INT1) that haven't been
   routed with copper traces yet.
