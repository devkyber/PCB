# JLCPCB workflow and L3 stock substitution

Current workflow, 2026-10-06. Run commands from the PCB workspace root.

The assembly corrections and manual steps are documented in
[the workspace assembly workflow](../../../../docs/JLCPCB_ASSEMBLY.md) and
[the per-component orientation audit](../review/JLCPCB_ORIENTATION_AUDIT.md).

## One pipeline

```powershell
uv run pcb-copilot review projects/rover-pdb
uv run pcb-copilot release projects/rover-pdb --preview --quantity 5
```

Replace `5` with the number of boards to assemble. The default is one board.
Preview publishes a complete upload/quotation package under
`output/jlcpcb-preview/`, even when engineering approval or stock findings
remain open. Exit code 1 means findings remain; read `PREVIEW.txt` and the reports.
After the responsible human completes the existing hash-bound review process,
the same command without `--preview` publishes `fabrication/`. A failure leaves
the previous fabrication package intact. Neither command places an order.

| File | Use |
| --- | --- |
| `gerbers.zip` | Upload to JLCPCB's PCB/Gerber slot; includes copper, mask, silk, paste, outline and PTH/NPTH Excellon drills |
| `bom.csv` | Grouped assembly BOM with exact MPN/LCSC identity; quantities per board |
| `cpl.csv` | Matching assembly coordinates/rotation; upload to the CPL slot |
| `positions.csv` | Original KiCad position export for diagnosis |
| `ASSEMBLY.md`, `assembly.json` | Manual-fit exclusions, centroid corrections and placement limitations |
| `rotation-audit.csv`, `assembly-audit.json` | Every native/vendor angle, exact-part rule evidence, local models and wire-pad label checks |
| `assembly-F.svg`, `assembly-B.svg` | Assembly drawings with pad numbers; bottom drawing retains top-view coordinates |
| `assembly.step`, `assembly-top.png`, `model-export.json` | KiCad mechanical preview and exporter diagnostics, when local checks pass |
| `jlcpcb-dfm.json` | Dated independent factory geometry baseline and results |
| `stock.csv`, `stock.json`, `stock-sources/` | Fresh retail quantities, exact C-number/MPN matching, timestamps and hashed source responses |
| `review.json`, `SOURCE.json` | Engineering findings and source/output hashes |

Every export checks native CAD parity and BOM/CPL designators. The JLCPCB check
uses a disposable copy with the workspace baseline, removing DRC exclusions and
overriding ignored manufacturing severities. Project DRC separately checks the
project's own rules. It does not modify saved copper or silently waive a failure.
The supplier baseline is dated, not automatically downloaded manufacturing policy.

Stock is fetched afresh for each package. Missing data, failed requests, identity
mismatch or insufficient quantity blocks release. Demand is BOM count times board
quantity, with **no assembly attrition allowance**. LCSC retail stock is not JLCPCB
assembly stock or a reservation. Verify JLCPCB eligibility, preordering, spare-part
allowances and actual assembly inventory in the order. Stock can change afterward.

The 2026-10-05 whole-BOM check found **SW1 / C226259 / OS102011MA1QN1 at zero
retail stock**. The other 24 exact part numbers, including the replacement L3,
were available for the one-board check. SW1 is retained because its replacement
and actuator/mechanical choice are explicitly deferred in the current design.
This shortage and the five unsigned engineering decisions prevent release.

SW1 alternatives researched at the owner's request (2026-10-05; **not applied**):

| LCSC / MPN | Live retail count | Minimum purchase | Assessment |
| --- | --- | --- | --- |
| [C221530 / OS102011MA1QS1](https://www.lcsc.com/product-detail/C221530.html) | 233 | 1 | Preferred same-family mounting pattern: 2 mm contact pitch, 8.2 mm support pitch; same right-angle actuator |
| [C2930976 / SK-12D02-G040](https://www.lcsc.com/product-detail/C2930976.html) | 870 | 5 | Lower-cost candidate; nominal 2 mm / 8.2 mm pattern, but compare body, terminal tolerances and actuator before substitution |
| [C393937 / SK12D07VG4](https://www.lcsc.com/product-detail/C393937.html) | 106040 | 20 | Large stock; drawing has 8.3 mm support pitch versus the current 8.2 mm, so do not assume exact footprint equivalence |

The [C&K family drawing](https://www.littelfuse.com/assetdocs/littelfuse-ck-slide-os-series-datasheet?assetguid=f8954ac2-65ba-431f-af55-b0493370575e)
gives QS1 the same mechanical drawing and 0.1 A / 12 V rating as QN1, but
**make-before-break** contact timing rather than break-before-make. In Rover,
pin 3 is intentionally unconnected and pin 2 has R15 to ground. Consequently
the overlapping contact interval does not connect two supplies; the same final
ON/OFF states are expected. This is a circuit inference, not a measured switch test.
[JLCPCB lists C221530](https://jlcpcb.com/partdetail/CK-OS102011MA1QS1/C221530)
for **Standard PCBA / wave soldering**. Its public purchasable/preorder quantities
can differ from LCSC retail stock; check the actual assembly order.

## Current board and checkout

Use **77.5 x 100 mm, two layers, FR4, 1.6 mm, 1 oz per face, green mask, white silk**.
Vias are tented. Surface finish is currently `User defined` in native CAD: choose
and confirm the finish at checkout; a Gerber ZIP does not configure the order.
The Pico socket assembly is explicitly manual-fit and J9 is DNP. Other leaded
parts require the selected JLCPCB service to support their through-hole assembly.
Inspect matched part numbers, pin 1, LED/electrolytic polarity and every rotation
in JLCPCB's placement preview. Confirm support rails/panel handling with the service.

## Applied geometry rules, in beginner terms

Values below are conservative workspace settings for this stackup, not a claim
that every value is the factory's absolute minimum. Power-track width still needs
current/temperature engineering.

| Check | Setting (mm) | What it means |
| --- | --- | --- |
| Copper spacing | 0.15 floor; 0.20 normal netclass | Gap between different electrical nets |
| Track width | 0.15 floor | Smallest permitted copper line; power paths are much wider |
| Copper to board edge | 0.50 | Keep copper away from the routed cut edge |
| Via diameter / drill / ring | 0.60 / 0.30 / 0.15 | Copper circle / hole / copper left around hole |
| General hole spacing / clearance | 0.25 / 0.25 | Separation between holes, and holes from other copper |
| Component PTH spacing / ring | 0.45 / 0.25 | Additional drilled-pad rules, separate from vias |
| PTH hole to other-net copper | 0.28 | Protect plated component holes from nearby nets |
| Round NPTH / NPTH slot / plated slot | 0.50 / 1.00 / 0.50 | Minimum hole or slot width |
| Mask expansion / web / copper separation | 0 / 0.10 / 0.09 | Opening enlargement / remaining green strip / protection of nearby copper |
| Silk text height / stroke / pad gap | 1.00 / 0.15 / 0.15 | Keep printed labels legible and away from exposed pads |

Source: [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities),
checked 2026-10-05. The native template is
[`templates/jlcpcb-2layer-1oz`](../../../../templates/jlcpcb-2layer-1oz/meta/info.html).
Geometry checks do not certify current capacity, component fit, loop stability,
motor braking-energy handling or the physical assembly process.

## L3 replacement

The original Bourns SRP1265A-3R3M / C1329348 had zero LCSC stock when checked.
The selected [Coilank APS1365M3R3DW / C54431777](https://www.lcsc.com/product-detail/C54431777.html)
had 987 pieces in the exact product record. Use the latest package's stock report
for the current observation. JLCPCB lists this identity, but public overseas or
purchasable counts do not establish ready assembly allocation.

The archived [manufacturer drawing](../../evidence/files/APS1365M3R3DW_68d4a03c5920925210785d7848183ed4_a794e72576cd.pdf)
specifies 3.3 uH +/-20%, maximum 6 mOhm DCR, typical 18.3 A Irms and typical
28.75 A Isat. The sheet does not specify the current-rating test thresholds.
Planning current remains 3.531 A RMS / 4.303 A peak, with a 4.96 A screening peak;
the regulator's maximum listed current limit is 9.6 A. The ratings provide selection
margin, but temperature, bias, startup and saturation behavior still need validation.
Room-temperature winding loss is approximately 0.075 W at the planning RMS current;
core loss and hot DCR are additional. Inductance, RT setting and capacitor values stay unchanged.

Its recommended lands differ from the Bourns part: **3.2 x 5 mm at +/-5.75 mm**
(11.5 mm pitch). The local `rover:APS1365DW_13.8x12.6_P11.5` footprint follows
that drawing, with a courtyard around maximum body/land dimensions. L3 moves
0.15 mm left and TP4 0.35 mm left to remove courtyard overlap. Tracks are retained.
A locally authored maximum-envelope STEP model was added on 2026-10-06;
see `libs/Coilank_APS1365DW.3dshapes/README.md` for dimensions and simplifications.
It does not alter JLCPCB's separate model library. The four mounting holes receive unique H1-H4
references without moving, net ties are excluded from placement export, and
undersized silkscreen graphics become 0.15 mm.

## Do it manually in KiCad

1. Save a backup. In PCB Editor open **File > Board Setup**. Rules belong to the
   project, not global Preferences. Use **Import Settings from Another Board**,
   select the template PCB and import only the intended constraints/custom rules.
   Preserve your existing netclasses and any stricter project rules.
2. Check **Design Rules > Constraints**, **Custom Rules**, **Net Classes** and
   **Board Stackup**. Check mask settings and text/graphic defaults too. Imported
   defaults do not resize existing copper, text or footprint graphics. Run DRC
   and fix each affected object instead of ignoring violations.
3. Before changing a part, compare exact inductance/tolerance, saturation and RMS
   current, DCR, size, pin/pad mapping and datasheet land pattern. Stock alone does
   not make an equivalent component.
4. In Schematic Editor hover over L3 and press **E**. Set Value, MPN, LCSC Part,
   Datasheet and Footprint together. This part uses the local footprint named above.
   Save; use **Tools > Update PCB from Schematic (F8)** and inspect the proposed
   footprint replacement. Preserve placement, then repair nearby spacing as needed.
5. In PCB Editor press **B** to refill zones and run **Inspect > Design Rules Checker**.
   Run schematic ERC too. Inspect the board and all affected schematic sheets, then
   regenerate the entire upload package with the command above. Never mix an old
   Gerber ZIP with a new BOM/CPL.

For future boards, KiCad Manager **File > New Project from Template** offers the
installed **JLCPCB 2-layer 1oz** template. Workspace instructions also make this
the starting point for future assisted designs with the same stackup.

Author visual review, 2026-10-05: all seven rendered sheets inspected: overview,
battery/INA226, 12 V, 5 V, motor, Pico/servos and DYNAMIXEL. The new motor value and
note are readable; unchanged owner sheets remain intact. The upward GND glyph on
the DYNAMIXEL sheet and older revision notes are preexisting presentation issues.
This author inspection is not the required owner's engineering/fabrication sign-off.
