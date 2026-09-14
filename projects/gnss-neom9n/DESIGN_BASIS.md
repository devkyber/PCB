# Design Basis — gnss-neom9n

Every key part's circuit names what it was learned from. Verdicts are `Match`
or `Deviate: <reason>`.

## Sources archived for this board

| File | What it is | Trust tier |
|---|---|---|
| `evidence/files/NEO-M9N-00B_NEO-M9N-00B_DataSheet_UBX-19014285.pdf` | u-blox NEO-M9N-00B data sheet | Tier 0 |
| `evidence/files/NEO-M9N-00B_NEO-M9N_Integrationmanual_UBX-19014286.pdf` | u-blox **Integration Manual R10** — §4.3 Figure 31 is the manufacturer's own minimal design, §4.9 is their design-in checklist | Tier 1 (the vendor's hardware design authority for this module) |
| `evidence/files/XC6206P332MR_8579707861620228096.pdf` | Torex XC6206P332MR-G LDO | Tier 0 |
| `evidence/files/RCLAMP0521P_8588899113072648192.pdf` | Semtech RCLAMP0521PATCT ESD | Tier 0 |
| `evidence/files/B3U-1000P_8588893394868953088.pdf` | Omron B3U-1000P switch | Tier 0 |
| `evidence/files/CR1220_CR1220_Datasheet_EN.pdf` | Panasonic CR1220 cell | Tier 0 |

**A note on tiering for modules.** For a module, the *Integration Manual* —
not the data sheet — is where the manufacturer states how to wire it. The data
sheet gives electrical limits; the manual gives the circuit. Every finding
below came from the manual, and none of them are in the data sheet. Reading
only "the datasheet" would have missed all three.

Ground truth (read from the archived PDFs; Figure 31 rendered to an image
with `fetch_reference_doc.py pdf`, because it is a vector diagram):

- §4.2.3 — *"If the USB interface is not used, the V_USB pin **must be
  connected to GND**."* Repeated in the §4.9.1 and §4.9.6 checklists, and
  Figure 31 draws pin 7 grounded.
- §4.9.1 — *"Is there a **1 uF** cap right next to the module VCC pin?"*
- §4.9.4 — *"**ESD protection on the RF input is mandatory**."*
- §4.2.1 — *"Do not add any series resistance greater than 0.2 Ω to the VCC
  supply"*; large short-duration current peaks leaving backup mode.
- Table 25 — D_SEL: *"open or VCC = UART + I2C; GND = SPI"*.

## Basis rows

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
|---|---|---|---|---|---|---|
| U2.7 | NEO-M9N | V_USB | **tied to GND (corrected rev1)** | "must be connected to GND"; Fig 31 grounds it | Integration manual §4.2.3, §4.9.1, §4.9.6, Fig 31 | Match. Was `no_connect`, under a comment reading "datasheet permits open". No u-blox document says that; three say the opposite. |
| U2.23 | NEO-M9N | VCC decoupling | **C3 = 1 µF at 0.78 mm from the pin (corrected rev1)** + C4 10 µF bulk | "Is there a 1 uF cap right next to the module VCC pin?" | Integration manual §4.9.1 | Match on the value and the proximity. **Deviate on the 100 nF**: there is no room for a third cap on that edge — see DEVIATIONS.md. |
| — | RF_IN | ESD protection | **D1, RCLAMP0521PATCT, 0.5 pF, at the U.FL connector (added rev1)** | "ESD protection on the RF input is mandatory" | Integration manual §4.9.4 | Match. Was **absent**. Part choice is the substance: a general-purpose ESD diode is 8–15 pF, which at L1 (1.575 GHz) is ~12 Ω to ground and would shunt the signal it protects. 0.5 pF is ~200 Ω. |
| U2.22 | NEO-M9N | V_BCKP | CR1220 solder-tab cell direct to pin 22 | "connect a backup battery to V_BCKP" for warm/hot starts; "avoid high resistance on the V_BCKP line" | Integration manual §4.2.2, §4.9.2, Fig 31 | Match. Direct connection, no series resistance. |
| U2.2 | NEO-M9N | D_SEL | 10k pull-up to VCC (R2) | "open or VCC = UART + I2C" | Integration manual Table 25 | Match — UART + I2C selected deliberately, not SPI. |
| U2.14 | NEO-M9N | LNA_EN | left open | Fig 31 leaves it open | Integration manual Fig 31 | Match — passive-antenna design. **See REQUIREMENTS.md [OWNER]**: an active antenna would need a bias-tee this board does not have. |
| U2.5/6 | NEO-M9N | USB_DM / USB_DP | no-connect | Fig 31 leaves both open; only V_USB is grounded | Integration manual Fig 31 | Match |
| U2.1 | NEO-M9N | SAFEBOOT_N | TP1 test point | Fig 31: "SAFEBOOT test point" | Integration manual Fig 31 | Match |
| U2.10/12/13/24 | NEO-M9N | grounds | all tied to GND | §4.9.5 "Ensure the ground pads of the module are connected to ground" | Integration manual §4.9.5 | Match |
| U1 | XC6206P332MR | LDO I/O caps | 1 µF in (C1), 1 µF out (C2) | Torex datasheet recommends 1 µF ceramic on both | evidence/files/XC6206P332MR_8579707861620228096.pdf | Match. **See REQUIREMENTS.md [OWNER]** on dropout: this regulator cannot make 3.3 V from a 3.3 V input, and the board's stated input range starts at 3.3 V. |
| R4, R5 | 4.7k | I2C pull-ups | 4.7k to VCC | manual notes I2C needs pull-ups; value not specified for the module | Integration manual §3.3.2 | Deviate: value is ours, not u-blox's. 4.7k is standard for 400 kHz over short traces and matches the other boards in this stack. |

## What this comparison actually caught

Three defects, none visible to ERC or DRC, all stated plainly in a document
that was on the internet and not on this disk until today:

1. **V_USB floating** where u-blox says three times it must be grounded —
   under a code comment claiming the datasheet permitted it.
2. **No 1 µF at VCC**, the one capacitor value u-blox names explicitly.
3. **No ESD protection on RF_IN**, which their checklist calls mandatory —
   on the one net that leaves the board through a connector a human handles.

And one process defect: **`SW1` was in the schematic and not on the board.**
That had been documented in the PCB generator's docstring and in
EVALUATION.md — Tier 3, where nothing reads it — while `validate_pcb.py`
reported "0 schematic-parity issue(s)" on every run because it read a
kicad-cli field the pipeline never asked to be populated. Fixed by a real
presence check, and by choosing a switch that fits (16.8 x 12.5 mm → 4.8 x
3.3 mm).
