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

## Assisted layout proposal — 2026-09-20

`layout-intent.yaml` transcribes native accepted 34x40mm outline and exact
footprint IDs, SHA-256
`352b9a918f92f160d7f18d93cd791287db3cac9aefea57a5609d18c9455650af`.
Shared bottom-left/y-up conversion of native (10,160)-(44,200) differs from
the generator's legacy y-down coordinates: holes at legacy y4 become y36;
U.FL J2=(31,29), interface J3=(17,4), rotation 90. Connector/hole/fiducial,
battery and switch anchors preserve current mechanical/access choices.
U1/U2 retain current anchors as provisional power/receiver seeds, not source
layout copies or owner-approved constraints.

The proposed bands are interface/backup y0–12 and receiver/power/RF y12–40.
An initial split at y30 intersected fixed J1/J2 envelopes, so those functions
share a region; near-pad relationships express their electrical grouping.
Movable bypass parts target actual supply pads:
C1→U1.3/C2→U1.2 within a proposed 5mm; C3→U2.23 within 2mm;
C4 bulk→U2.23 within 5mm; C5→U2.9 and C6→U2.22 within 3mm.
D1→J2.1 has a proposed 5mm maximum to keep protection at the connector.
These are search bounds informed by existing bypass/entry functions and house
rules, not proof of effective decoupling or vendor-required numerical distances.

The manufacturer RF grounding/VCC examples and limited SparkFun copper views
recorded in REFERENCE_REVIEW inform review priorities. SparkFun's USB,
ANT_VCC bias branch, rechargeable backup path and 2.2k pull-ups differ from
our unused USB, no-bias antenna feed, CR1220 and 4.7k pull-ups. No coordinates,
fill, RF width or stackup are adopted from that source. Exact source -00B
variant and suitability remain unresolved.

All 15 named native nets retain effective classes: Power VCC/VIN/V_BCKP
width/clearance 0.3/0.15mm, RF_IN historical RF_50ohm 0.3/0.2mm, others
Default 0.2/0.127mm; vias 0.6/0.3mm. The RF class name is not impedance proof.
Critical-net calculations are empty because manufacturer stackup/dielectric
height, er and copper thickness are unknown.

Current GND_TOP/GND_BOTTOM occupy F.Cu/B.Cu with 0.2mm clearance and an RF
notch. Schema v1 cannot represent their polygon. The proposal intentionally
has no zones, so the isolated draft removes accepted copper and requires
manual source-backed notch/return-plane reconstruction before routing or
approval. It does not replace the notch with a full-board rectangle or
assert that the historic notch is electrically correct. Antenna type/siting/
ground plane, D1 ordered-package mapping, VIN dropout, cell/environment and
RF return/impedance review remain pending. Accepted CAD and signoff are untouched.

## Routing repair — 2026-09-23

Moved FID3 to native (41.8, 191.7) mm and relocated nearby ground stitching.
Connected formerly ineffective ground vias to existing bottom ground copper;
the isolated ground via now lies inside connected ground copper. Refreshed J2
from the installed KiCad Hirose U.FL footprint with the same pads and sourcing
identity. Its embedded copper keepout had been stored at the wrong location;
it now follows the connector. Moved the affected ground via/escape outside
that keepout. Restored the headers' library-relative pad angles and moved
silkscreen clear of pads/edges. Existing RESET_N and RF_IN signal routes,
component values, net assignments and ground-zone polygons are retained.

Working assumption for the requested basic configuration: a passive external
GNSS antenna and regulated 5 V at VIN. The user has not selected a specific
antenna or fabrication stackup. This is not confirmation of 50-ohm impedance,
antenna performance, D1 package suitability, or the former 3.3 V VIN claim.
Those items remain in the review profile; no RF sign-off has been recorded.

The repaired board passed the current review pipeline's automated checks,
including exact schematic/PCB parity and two zone-refilled DRC runs with
zero errors, zero warnings and zero unconnected items. Human decisions remain
unsigned; lifecycle remains DRAFT. No fabrication release was produced.

The earlier layout intent remains an unapproved placement proposal. Its
conservative envelope/near-pad checks are separate from native DRC and still
require work; these routing repairs do not establish that proposal as accepted
or waive its constraints. Mechanical, assembly and bench review remain open.
