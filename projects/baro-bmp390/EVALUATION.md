# baro-bmp390 rev1 — Evaluation

> **SUPERSEDED IN PART, 2026-08-25.** The decoupling row in the table below
> reached the opposite conclusion to `DESIGN_BASIS.md` on the same question,
> and this file was the one that was wrong. It argued that Adafruit's 10uF
> served *their* regulator and so did not apply here. Two things are wrong
> with that:
>
> 1. The Eagle netlist, read directly, puts `C5` (10uF) and `C6` (0.1uF) on
>    the `3.3V` net **together with `IC1.VDD` and `IC1.VDDIO`** — the rail
>    the sensor actually runs on, not a regulator-only node.
> 2. The argument inverts. No onboard regulator means the rail arrives down
>    a QT cable with no local source stiffening it, which needs bulk **more**
>    than a board with a regulator 5mm away, not less.
>
> The datasheet settles it independently: §1 specifies **`VDD ripple max.
> 50 mVpp`**. That is a requirement on the board, and 2 x 100nF against a
> 730uA conversion transient down a cable is not a rail you could show
> compliance on. `C3`, 10uF at the J1 entry, was added as a result.
>
> Two documents on one board reached opposite conclusions and nothing
> noticed. Read `DESIGN_BASIS.md` as authoritative where they differ; the
> rest of this file (part fidelity, pin map, ERC/DRC history) still stands.


## Part fidelity

BMP390, LCSC C5124834, fetched via `easyeda2kicad --full --lcsc_id C5124834`.
All three artifacts generated successfully — **real fidelity**, not
placeholder:

- `libs/jlcpcb.kicad_sym` — real 10-pin symbol, pin names/numbers extracted
  and verified against the pin map below (not assumed from memory).
- `libs/jlcpcb.pretty/LGA-10_L2.0-W2.0-P0.50-BL.kicad_mod` — real LGA-10
  pad geometry (10 distinct 0.3x0.3mm castellated pads at real offsets,
  not a generic 2-pad placeholder). Round-tripped through `kipython`
  (pcbnew) to upgrade from the legacy `(module ...)` head to the modern
  `(footprint ...)` head required by the pcb_editor adapter.
- `libs/jlcpcb.3dshapes/LGA-10_L2.0-W2.0-P0.50-BL.{step,wrl}` — real 3D
  models generated.

Real pin map (extracted directly from the fetched `.kicad_sym`, per
docs/pcb-design-rules.md §15.7 — never trust a remembered pinout):
`1=VDDIO 2=SCK 3=VSS 4=SDI 5=SDO 6=CSB 7=INT 8=VSS 9=VSS 10=VDD`.

## ERC

`kicad-cli sch erc` — **0 errors**, 23 warnings, all in the two expected/
harmless classes documented in §15.7: `endpoint_off_grid` (13),
`pin_to_pin` (10). Both are systematic noise from EasyEDA-converted
symbols losing KiCad's electrical pin-type metadata, not real defects.

## DRC

`kicad-cli pcb drc --refill-zones` — **6 violations** (placement-only
board, routing intentionally out of scope):

| Type | Count | Assessment |
|---|---|---|
| `starved_thermal` | 2 | GND zone thermal-relief spoke count on two adjacent LGA-10 VSS pads (pins 8, 9) — a fill-quality nit on unrouted copper, not a short or clearance violation; resolves naturally once traces are routed and the zone refills. |
| `silk_edge_clearance` | 2 | Reference-designator silkscreen (`H1`, `FID1`) clipped by the board edge — cosmetic only, common for edge-adjacent mechanical features, does not affect fab or assembly. |
| `silk_over_copper` | 2 | Board-ID silkscreen text lightly clips `H2`'s mounting-hole pad silk-mask keepout — cosmetic, does not affect solder mask opening on any signal pad. |

Zero shorts, zero courtyard overlaps, zero copper-edge-clearance
violations, zero co-located holes in the final board — all of these
appeared during iteration (see "Known gaps" below) and were fixed by
recomputing real pin/courtyard geometry rather than reusing guessed
coordinates.

15 unconnected ratsnest items — expected: this is placement only, no
traces were routed (kicad-cli 10 has no CLI DSN export; per CLAUDE.md,
routing is out of scope for this phase).

## Reference-design comparison (Adafruit BMP390 breakout, EagleCAD)

Adafruit's schematic (`adafruit/Adafruit-BMP3xx-PCB`, `Adafruit BMP390.sch`)
and the Bosch BMP390 datasheet (BST-BMP390-DS002-07, §6.3 Figure 25) were
both consulted directly (not from memory).

| Aspect | Your Design | Adafruit Reference | Bosch Datasheet (Fig. 25) | Action |
|---|---|---|---|---|
| VDD/VDDIO decoupling | 100nF each (C1, C2) | 10uF bulk (C4/C5) + 0.1uF (C6) on a regulated 3.3V rail | 100nF each (C1, C2) | **Match Bosch exactly.** Adafruit's larger bulk caps serve their onboard AP2112K-3.3 regulator's output stability, not the BMP390 itself — not applicable here since this board has no onboard regulator. |
| CSB (mode select) | Hard-tied to VDDIO (+3V3) | Pulled high via 10k resistor (R1) to 3.3V, with an optional diode from a header CS pin for SPI fallback | Datasheet shows CSB tied to VDDIO directly, with a footnote (*) recommending an MCU GPIO drive it at POR for extra robustness | **Documented deviation from Bosch's ideal (GPIO-driven).** This board has no onboard MCU (STEMMA QT delegates compute to the host), so a hard tie is the only option without adding a GPIO header — same simplification Adafruit uses (pull-up instead of a driven pin). |
| SDO (I2C address select) | Hard-tied to VDDIO -> address 0x77, no jumper | Pulled high via 10k (R4) to 3.3V (0x77 default) + brought to header pin 5 + solder jumper (SJ1) to GND for field-selectable 0x76 | "SDO pin cannot be left floating" — direct tie to VSS or VDDIO shown in Fig. 25, no resistor | **Known limitation:** no field-selectable address. Acceptable for a single-sensor, fixed-purpose avionics breakout (this board's use case) but a real capability gap vs. Adafruit's board if multiple BMP390s ever need to share one I2C bus. |
| I2C pull-ups (SDA/SCL) | On-board, 4.7kOhm (R1, R2) | On-board, 10k (R2 4-pack), on the sensor (3.3V) side of a BSS138 level shifter | 4.7kOhm recommended (Fig. 25 notes) | **Match Bosch's recommended value exactly**, stricter than the generic 10k habit Adafruit and many breakouts default to. |
| Level shifting | None — 3.3V-only board | BSS138 dual N-MOSFET level shifter, lets 3-5V hosts talk to the 3.3V BMP390 | N/A (datasheet assumes single-voltage-domain I2C) | **Documented deviation.** This board assumes the STEMMA QT host provides a clean 3.3V rail directly (as most STEMMA QT hosts do) — no onboard regulator or level shifting. A 5V-only host (e.g. classic Arduino Uno on Qwiic-via-adapter) is out of scope for rev1. |
| Onboard 3.3V regulation | None — host-supplied +3V3 only | AP2112K-3.3 LDO from VIN (3-5V) | N/A | **Documented deviation**, simplification for a dedicated 3.3V-host use case (avionics stack), reduces BOM/board area. |
| Fiducials | 3x, `Fiducial_1mm_Mask3mm` | Present (FID3, FID4 in Eagle source) | N/A | Match. |
| Mounting holes | 2x M2 | 2x (Eagle `MOUNTINGHOLE` parts, size not confirmed from schematic alone) | N/A | Meets the spec minimum (>=2). |

## Known gaps / limitations

1. **Board grew from ~15x15mm to 18x26mm.** The real
   `JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal` STEMMA QT footprint
   has a measured courtyard of ~7.8mm x 6.6mm (mounting tabs included) —
   far larger than the "4.5x6mm minimal" estimate in
   `docs/pcb-design-rules.md` §15.6. A true 15x15mm board cannot fit this
   connector plus 2 mounting holes plus 3 fiducials without violating
   courtyard/edge clearances. This is the same §15.7 lesson repeated on
   a new part family: measure real courtyards from the fetched footprint,
   never trust a doc estimate.
2. **No solder-jumper address selection on SDO.** Hard-tied to VDDIO
   (0x77 fixed). If a design later needs two BMP390s on one bus, this
   board needs a rev with a jumper or resistor-swap option — see the
   comparison table above.
3. **No I2C fallback/level-shifting for 5V hosts.** 3.3V-only. A host
   supplying 5V on the STEMMA QT VCC pin would exceed the BMP390's VDDIO
   absolute max — out of scope for rev1, flagged here rather than left
   implicit.
4. **CSB hard-tied rather than GPIO-driven.** Matches Bosch's simplified
   Figure 25 diagram and common industry practice (including Adafruit's
   own board), but is not Bosch's stated ideal (a footnoted recommendation
   for POR robustness that requires a host GPIO this board doesn't expose).
5. **Traces are not routed.** This phase is placement-only per
   CLAUDE.md/kicad-cli 10's lack of CLI DSN export — Freerouting or
   manual routing in KiCad is the next step before fabrication.
6. **INT pin routed to a bare test point (TP1), not a connector pin.**
   STEMMA QT is a 4-pin standard (GND/3V3/SDA/SCL) and doesn't carry
   INT; a host wanting hardware interrupts must fly a wire to TP1.
