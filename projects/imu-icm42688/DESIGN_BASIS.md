# Design Basis — imu-icm42688

Every key part's circuit names what it was learned from. A departure nobody
wrote down is indistinguishable from an oversight. Verdicts are `Match` or
`Deviate: <reason>`.

## Sources archived for this board

| File | What it is | Trust tier |
|---|---|---|
| `evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf` | TDK InvenSense DS-000347 **rev 1.6** — §4.2 Figure 7 is the manufacturer's own SPI application schematic | Tier 0 (the part's specification; outranks everything below) |
| `evidence/files/ICM-42688-P_ICM-42688-P_Datasheet.pdf` | DS-000347 **rev 1.2**, SparkFun CDN copy — kept as an independent cross-check | Tier 0 (older revision) |
| `evidence/files/ICM-42688-P_DOC056673507_44e5201b843b.pdf` | TDK AN-000493 rev 1.0, ChipDip mirror: schematic p.12 and placement views p.14; no routed-copper proof | Tier 1 (manufacturer EVM) |
| `evidence/files/ICM-42688-P_ICM-42688.kicad_sch` | anyshake ICM-42688 breakout, **KiCad source** — exact values, not a summary | Tier 2 (open hardware) |

**Revision scope:** these rows cite the archived rev 1.6, not a claim about
the latest manufacturer revision. The historical retrieval noted rev 1.9 and
an HTTP 403; current revision/access status must be rechecked before release.
The older rev 1.2 is retained as a cross-check. See `REFERENCE_REVIEW.md` for
source identity, retrieval limitations and the pinned reference schematic/PCB.

Datasheet ground truth (read from Figure 7 rendered to an image, because it is
a vector diagram that text extraction scrambles — `fetch_reference_doc.py pdf`):

- `VDD` (pin 8) — **C1 = 0.1 µF *and* C2 = 2.2 µF**
- `VDDIO` (pin 5) — **C3 = 10 nF**
- Table 10: pin 7 `RESV` — **"Connect to GND"** (no "No Connect or" prefix,
  unlike pins 2/3/10/11)
- Table 10: pin 9 `INT2/FSYNC/CLKIN` — **"Connect to GND if FSYNC not used"**
- §3.3.2 — **`Power Supply Noise ... 10 mV peak-peak`**

Reference ground truth (values read out of the KiCad source): `C3 2.2uF`,
`C7 0.01uF`, `C2/C5/C6/C8/C9 0.1uF`. The reference follows the datasheet
exactly on all three decoupling values.

## Basis rows

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
|---|---|---|---|---|---|---|
| C1 | 100nF | VDD HF decoupling | 0.1 µF at 0.96mm from pin 8 | "C1, 0.1 µF" on VDD | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 7 | Match |
| C2 | 2.2uF | VDD bulk | **2.2 µF (added rev1, 2026-08-25)** | "C2, 2.2 µF" on VDD; anyshake `C3 2.2uF` | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 7 | Match. **Was missing entirely.** The board carried 100nF only, described in a comment as "per TDK app circuit" — which is not what the TDK app circuit says. Matching the recommended capacitance does not prove the 10 mVpp supply-noise limit; verify the actual rail by measurement. |
| C3 | 10nF | VDDIO decoupling | **10 nF (corrected rev1)** | "C3, 10 nF" on VDDIO; anyshake `C7 0.01uF` | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 7 | Match. Was **100 nF, ten times the specified value**. |
| U1.7 | ICM-42688-P | RESV pin 7 | **tied to GND (corrected rev1)** | Table 10: "Connect to GND" | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.1 Table 10; Fig 7 draws it grounded | Match. Was `no_connect`, under a comment claiming "datasheet says leave unconnected". Table 10 draws the distinction explicitly and pin 7 is the one that has no NC option. |
| U1.9 | ICM-42688-P | INT2 / FSYNC / CLKIN | **tied to GND (corrected rev1)**, with a pre-route escape via | Table 10: "Connect to GND if FSYNC not used" | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.1 Table 10 | Match. Was `no_connect` — a floating CMOS **input** on a vibration sensor. |
| U1.2/3/10/11 | ICM-42688-P | RESV pins | no-connect | Table 10: "No Connect or Connect to GND"; Fig 7 grounds 11 | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.1 Table 10 | Deviate: left as NC. The datasheet explicitly permits either. Grounding them would be marginally better for EMI but there is no room to escape four more pads on a 0.5mm-pitch LGA on 2 layers, and U1.9's escape already had to be hand-placed. |
| U1 | ICM-42688-P | interface | 4-wire SPI, CS on pin 12 | Fig 7 (SPI) is one of the two circuits offered | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 7 | Match |
| U1.1 | ICM-42688-P | AP_SDO | broken out to header | Fig 7 breaks it out | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 7 | Match |
| U1.4 | ICM-42688-P | INT1 | broken out to TP3 | Fig 7 breaks it out | evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf §4.2 Fig 7 | Match |
| — | rail | Interface pull-ups | none fitted | The I2C pull-up note belongs to Figure 6, not SPI Figure 7; the selectable-interface EVM includes pull-ups | DS-000347 rev 1.6 §4.2 p.21; AN-000493 rev 1.0 p.12 Fig 4 (archives above) | Deviate: fixed SPI rather than the EVM's selectable interface. Absence of I2C does not prove every pull-up is unwanted; review CS startup and configured interrupt output mode with the host. No resistor change is made here. |

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

## Assisted layout proposal — 2026-09-20

The unapproved `layout-intent.yaml` uses native accepted 24x19mm outline and
footprint IDs, SHA-256
`a70dda20452db6712b75275eff32f4f56b6767a2e21048ba0ce9f483d1ad855e`.
Shared bottom-left conversion subtracts native outline origin: the generator's
absolute MCP hole (6,18) becomes H1=(3,15); H2=(21,10), J1=(5,5), rotation
90 degrees. Anchors are not footprint centres. Holes and connector retain
existing mechanics. PCB-only FID1–3 are manufacturing features, not fixed
owner mating interfaces. Historical FID1=(1.5,9), FID3=(2,1.5) fail the
measured envelope/edge constraint; the draft proposes FID1=(2.1,9.8),
FID3=(21.8,2.1), keeping FID2=(21.5,15) and an asymmetric three-point pattern.
The new positions clear the fixed header and mounting-hole envelopes; physical
inspection remains pending. Accepted fiducials are unchanged.
U1=(13,11), rotation 0 is a provisional
existing seed only; owner airframe orientation and mounting rigidity are open.

Proposed host-entry y0–7 and sensor y7–19 regions follow the existing functional
placement. C3/test points remain movable. C1.1→U1.8 and C3.1→U1.5
target 2mm pad distance; VDD bulk C2.1→U1.8 allows 4mm as a proposed search
limit, not a manufacturer numerical requirement. The greedy search repeatedly
placed VDD capacitors in VDDIO's required space. Two new proposed anchors,
C1=(16.1,10.25) and C2=(16.3,8.4), both rotation 0, keep VDD bypass on the
east side and bulk below it, leaving space for C3 at actual VDDIO pin5.
These are proposed relocations, not frozen historical capacitor positions;
the unchanged 2mm/4mm pad-distance and geometry checks must pass.
TDK SPI Fig 7 supplies
bypass values/functions; AN-000493 Fig 5 and the AnyShake copper views supply
local-placement context. AnyShake's regulator/translator/power selection and
exposed INT2 are not adopted. The later native pair comparison in
REFERENCE_REVIEW establishes only ref/footprint/named-net consistency.

Seven native named nets retain Default width/clearance 0.254/0.2mm and
via diameter/drill 0.6/0.3mm. GND F.Cu/B.Cu zones retain net/layers/0.2mm
clearance; generated rectangles and default thermal/fill settings are not
native zone equivalence. Review the existing J1 solid-connection deviation,
return paths, ground escapes, access and silkscreen after placement.
No current/stackup calculation is fabricated. Host ramp, rail noise, high-g
coverage and mechanical axes remain unresolved; nominal capacitance alone
does not establish the 10mVpp condition despite historical REQUIREMENTS prose.
Any existing edge/envelope violation remains a blocking measured finding,
not a reason to silently move fixed mechanics or waive geometry.
