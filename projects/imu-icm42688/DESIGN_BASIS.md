# Design Basis — imu-icm42688

Every key part's circuit names what it was learned from. A departure nobody
wrote down is indistinguishable from an oversight. Verdicts are `Match` or
`Deviate: <reason>`.

## Sources archived for this board

| File | What it is | Trust tier |
|---|---|---|
| `evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf` | TDK InvenSense DS-000347 **rev 1.6** — §4.2 Figure 6 is the manufacturer's own SPI application schematic | Tier 0 (the part's specification; outranks everything below) |
| `evidence/files/ICM-42688-P_ICM-42688-P_Datasheet.pdf` | DS-000347 **rev 1.2**, SparkFun CDN copy — kept as an independent cross-check | Tier 0 (older revision) |
| `evidence/files/ICM-42688-P_ICM-42688.kicad_sch` | anyshake ICM-42688 breakout, **KiCad source** — exact values, not a summary | Tier 2 (open hardware) |

**Revision note, stated because it matters:** TDK lists v1.9 as current. Their
own host returns **HTTP 403 to curl** (verified, not "couldn't fetch"), so the
newest revision obtainable here is 1.6, taken from a third-party mirror. Both
1.2 and 1.6 were checked and **agree** on every value used below, which is why
they are both on disk. Re-check against v1.9 before fabricating.

Datasheet ground truth (read from Figure 6 rendered to an image, because it is
a vector diagram that text extraction scrambles — `fetch_reference_doc.py pdf`):

- `VDD` (pin 8) — **C1 = 0.1 µF *and* C2 = 2.2 µF**
- `VDDIO` (pin 5) — **C3 = 10 nF**
- Table 9: pin 7 `RESV` — **"Connect to GND"** (no "No Connect or" prefix,
  unlike pins 2/3/10/11)
- Table 9: pin 9 `INT2/FSYNC/CLKIN` — **"Connect to GND if FSYNC not used"**
- §3.3.2 — **`Power Supply Noise ... 10 mV peak-peak`**

Reference ground truth (values read out of the KiCad source): `C3 2.2uF`,
`C7 0.01uF`, `C2/C5/C6/C8/C9 0.1uF`. The reference follows the datasheet
exactly on all three decoupling values.

## Basis rows

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
|---|---|---|---|---|---|---|
| C1 | 100nF | VDD HF decoupling | 0.1 µF at 0.96mm from pin 8 | "C1, 0.1 µF" on VDD | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 6 | Match |
| C2 | 2.2uF | VDD bulk | **2.2 µF (added rev1, 2026-08-25)** | "C2, 2.2 µF" on VDD; anyshake `C3 2.2uF` | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 6 | Match. **Was missing entirely.** The board carried 100nF only, described in a comment as "per TDK app circuit" — which is not what the TDK app circuit says. §3.3.2's 10 mVpp supply-noise limit is not meetable without it. |
| C3 | 10nF | VDDIO decoupling | **10 nF (corrected rev1)** | "C3, 10 nF" on VDDIO; anyshake `C7 0.01uF` | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 6 | Match. Was **100 nF, ten times the specified value**. |
| U1.7 | ICM-42688-P | RESV pin 7 | **tied to GND (corrected rev1)** | Table 9: "Connect to GND" | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.1 Table 9; Fig 6 draws it grounded | Match. Was `no_connect`, under a comment claiming "datasheet says leave unconnected". Table 9 draws the distinction explicitly and pin 7 is the one that has no NC option. |
| U1.9 | ICM-42688-P | INT2 / FSYNC / CLKIN | **tied to GND (corrected rev1)**, with a pre-route escape via | Table 9: "Connect to GND if FSYNC not used" | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.1 Table 9 | Match. Was `no_connect` — a floating CMOS **input** on a vibration sensor. |
| U1.2/3/10/11 | ICM-42688-P | RESV pins | no-connect | Table 9: "No Connect or Connect to GND"; Fig 6 grounds 11 | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.1 Table 9 | Deviate: left as NC. The datasheet explicitly permits either. Grounding them would be marginally better for EMI but there is no room to escape four more pads on a 0.5mm-pitch LGA on 2 layers, and U1.9's escape already had to be hand-placed. |
| U1 | ICM-42688-P | interface | 4-wire SPI, CS on pin 12 | Fig 6 (SPI) is one of the two circuits offered | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 6 | Match |
| U1.1 | ICM-42688-P | AP_SDO | broken out to header | Fig 6 breaks it out | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 6 | Match |
| U1.4 | ICM-42688-P | INT1 | broken out to TP3 | Fig 6 breaks it out | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 6 | Match |
| — | rail | I2C pull-ups | none fitted | "I2C lines are open drain and pull-up resistors (e.g. 10 kΩ) are required" | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 note under Fig 5 | Deviate: correctly omitted. That note applies to Figure 5 (I2C/I3C). This board is SPI (Figure 6), where SCLK/SDI/SDO/CS are push-pull and pull-ups are not wanted. Recorded because the note is easy to apply to the wrong figure. |

## What this comparison actually caught

Five defects, all invisible to ERC and DRC, all found by reading Tier 0:

1. **No 2.2 µF bulk cap** on VDD — the datasheet names it explicitly.
2. **VDDIO cap 10x too large** — 100 nF where 10 nF is specified.
3. **Pin 7 floating** where the datasheet says "Connect to GND", mandatory.
4. **Pin 9 (FSYNC input) floating** where the datasheet says to ground it.
5. A code comment asserting **"per TDK app circuit"** for values that were
   not the TDK app circuit's — the most dangerous kind, because it reads as
   evidence the check was already done.

Item 5 is the general lesson: a comment citing a source is not a citation.
`DESIGN_BASIS.md` exists so the claim and the source sit in the same row
where they can be compared.
