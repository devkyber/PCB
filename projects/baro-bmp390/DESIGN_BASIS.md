# Design Basis — baro-bmp390

Every key part's circuit names what it was learned from. A departure nobody
wrote down is indistinguishable from an oversight — that is why this file
exists. Verdicts must be `Match` or `Deviate: <reason>`.

## Sources archived for this board

| File | What it is | Trust tier |
|---|---|---|
| `evidence/files/BMP390-datasheet.pdf` | Bosch BST-BMP390-DS002-07 Rev 1.7 — **§6.3 Fig 25 is the manufacturer's own I2C connection diagram** | Tier 0 (the part's own specification; outranks every row below) |
| `evidence/files/BMP390_Adafruit_20BMP390.sch` | Adafruit BMP390 breakout, **Eagle source** — exact values and pin-level nets, not a summary | Tier 2 (open hardware, widely built) |
| `evidence/files/BMP390_Adafruit_20BMP390.brd` | same board's layout | Tier 2 |

Extracted with `docs/fetch_reference_doc.py eagle <file> <PART>`, which reads
the Eagle XML directly. WebFetch summarises and loses exactly the pin-level
detail every row below depends on.

Datasheet ground truth (read from the PDF on disk, §6.3 Fig 25 and its notes,
not recalled): **"the recommended value for C1, C2 is 100 nF and for R1, R2 is
4.7 kΩ"**; CSB → VDDIO, with a footnote that a programmable pin driving VDDIO
at POR is preferred; SDO → VDDIO or VSS selects address bit X of `111011X`.

Reference ground truth (verified, not recalled):
`IC1 BMP388/390` — `VDD`+`VDDIO` on 3.3V; `C5 10uF` and `C6 0.1uF` on 3.3V;
`C4 10uF` on the 5V input; `R1 10K` pull-up on `CSB`; `R4 10K` pull-up on
`SDO/ADR` with `SJ1` solder jumper to GND; `INT` broken out.

Our pin map is from `libs/jlcpcb.kicad_sym`, not assumed:
1 VDDIO · 2 SCK · 3 VSS · 4 SDI · 5 SDO · 6 CSB · 7 INT · 8/9 VSS · 10 VDD.

## Basis rows

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
|---|---|---|---|---|---|---|
| U1 | BMP390 | pin decoupling | C1 100nF + C2 100nF at VDD/VDDIO | "recommended value for C1, C2 is 100 nF" | evidence/files/BMP390-datasheet.pdf §6.3 Fig 25 note | Match |
| — | +3V3 rail | bulk decoupling at board entry | **C3 10uF at J1** (added rev1, 2026-08-25) | 10uF (C5) + 0.1uF (C6) on the 3.3V net that feeds IC1.VDD/VDDIO | evidence/files/BMP390_Adafruit_20BMP390.sch (C5/C6 net `3.3V`); evidence/files/BMP390-datasheet.pdf p.7 Table 2 | Match in bulk-capacitance value/function, not in supply topology. C3 is retained to support the host-fed rail. The reference includes local regulation; our host/cable impedance differs. Neither this comparison nor the selected capacitance proves the 50mVpp condition is met; measurement at U1 remains required. |
| U1 | BMP390 | VDD / VDDIO | both on +3V3 (pads 1, 10) | both on 3.3V | evidence/files/BMP390_Adafruit_20BMP390.sch (IC1) | Match |
| U1 | BMP390 | CSB (interface select) | hard-tied +3V3 (pad 6) | 10K pull-up to 3.3V | evidence/files/BMP390-datasheet.pdf §6.3 Fig 25 (`VDDIO*`); evidence/files/BMP390_Adafruit_20BMP390.sch (R1) | Deviate: hard tie, accepting the datasheet's `*` caveat. Fig 25 shows CSB at VDDIO but notes a programmable pin driving VDDIO at POR is preferred. This board has no MCU — compute lives on the QT host — so there is no pin to drive it with. Adafruit reach the same conclusion via a 10K pull-up; a direct tie is equivalent for an I2C-only board and saves a part. |
| U1 | BMP390 | SDO (I2C address) | hard-tied +3V3 (pad 5) = 0x77 | 10K pull-up + SJ1 jumper to GND, 0x77/0x76 selectable | evidence/files/BMP390-datasheet.pdf §6.3 Fig 25; evidence/files/BMP390_Adafruit_20BMP390.sch (R4, SJ1) | Match to datasheet — Fig 25 offers exactly two options, "Connect to VDDIO, X='1'" or VSS; we took one. Deviate vs Adafruit, who make it jumper-selectable: single baro per bus in this stack, revisit if a second is ever added. |
| U1 | BMP390 | INT | broken out to TP1 | broken out to header | evidence/files/BMP390_Adafruit_20BMP390.sch (INT net) | Match |
| R1, R2 | 4.7k | I2C pull-ups | 4.7k | **"for R1, R2 is 4.7 kΩ"** (datasheet); 10K (Adafruit) | evidence/files/BMP390-datasheet.pdf §6.3 Fig 25 note | Match — to the datasheet, which is the higher authority. Previously logged as `Deviate` against Adafruit's 10K; that was reading the commentary over the specification. Adafruit is the deviation here, not us. |

## What this comparison actually caught

**1. A missing board-entry bulk capacitor relative to the reference's rail
decoupling strategy.** The archived schematic motivated adding C3, 10uF, at
the J1 rail entry. ERC, DRC and the geometric checker do not establish supply
ripple or sensor noise. No before/after measurement is recorded here, so this
is a documented design improvement, not proof of a former specification
violation or of current compliance.

**2. Two of this file's own verdicts were wrong**, caught only by opening the
datasheet instead of trusting the summary of it. The 4.7k pull-ups were logged
as a deviation from Adafruit's 10K when the datasheet *names 4.7 kΩ* — we were
matching the manufacturer and calling it a departure. The address tie was
logged the same way. Both are Tier-0 questions that had been answered from a
Tier-2 source.

The ordering rule this establishes: **datasheet first, reference design
second, and a reference is evidence of practice, not of correctness.** Where
they disagree, the datasheet wins and the disagreement itself gets a row.

**3. `EVALUATION.md` contradicted this file** on the bulk cap — it argued the
10uF was "for Adafruit's regulator, not applicable here." The Eagle netlist
says C5/C6 sit on the `3.3V` net alongside `IC1.VDD` and `IC1.VDDIO`, so they
decouple the rail the sensor actually runs on. A host-fed rail has a different
source/cable impedance from the regulated reference, so neither blanket
conclusion establishes the needed capacitance or achievable ripple. C3 remains
the current design choice, with bench verification open. `EVALUATION.md` is a
historical decision record, not evidence of measured supply performance.
