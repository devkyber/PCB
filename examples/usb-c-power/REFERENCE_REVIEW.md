# Reference review

The USB-C attachment follows the passive sink pull-down arrangement in the
archived USB Type-C Cable and Connector Specification R2.0 (August 2019),
sections 4.5 and 4.6. This dated primary reference informs Rd selection and
the distinction between attachment and source-advertised current. It is not
a current USB compliance assessment. The selected GCT drawing independently
supplies the connector pin allocation and recommended land pattern.

Bourns MF-MSMF pp1,5,7,13 supply the selected PPTC row, style-1 package/lands,
and assembly limits. Vishay 88390 pp1–2 supply polarity and the SMAJ6.0A
electrical row. The series LED circuit uses Kingbright WP710A10ID polarity/
ratings (pp1–2) and Yageo MFR ordering/dimensions (pp2–3). Samtec's TSW/HTSW
family sheet supplies the HTSW output header identity, pitch and assembly
distinction. Exact documents are archived with hashes in evidence/index.yaml.

No vendor reference circuit is represented as protection coordination or bench
validation of this board. The TVS/PPTC combination requires application testing.

## Open-hardware comparison

The [Adafruit USB-C downstream breakout / product4090](https://github.com/adafruit/Adafruit-USB-C-Downstream-Breakout)
rev-B Eagle schematic and PCB are archived at commit
`1484ecb56b369e177848e69de4b7b7e513399590`, with the full original README,
MIT LICENSE and Attribution-ShareAlike3.0 license.txt. The source identifies
Limor Fried/Ladyada for Adafruit Industries. Original notices are retained
unchanged; this project makes no endorsement or blanket relicensing claim.

| Compared item | Actual source observation | Adopted choice / boundary |
| --- | --- | --- |
| CC1 / CC2 | Source X1 CC1 connects R2 pin2; CC2 connects R1 pin2. Each 5.1K resistor pin1 joins GND. | Same independent pull-down pattern. Our resistor references and pin1/2 orientation differ, with equivalent nonpolar function. |
| VBUS / GND | Source X1 VBUS/GND join a breakout header and common returns. | Common connector power/ground groups, with our fuse/TVS/LED output circuit added independently. |
| Reference connector | Source package is CUSB31-CFM2AX-01-X, rather than GCT USB4105-GF-A. | Do not adopt its footprint, mounting geometry or mechanical conclusion. Our exact GCT drawing controls. |
| Data / sideband | Source brings D+/D-/SBU and CC pins to its header. | Our power-only design intentionally leaves data/SBU unused and does not export CC. |
| Board/schematic comparison | Shared Eagle inspector compared24 numbered pad memberships with no mismatches; source board has84 routed wire records and4 vias on layers1/16. | Confirms the reference pair's explicit membership only. It does not run reference-board DRC, judge its copper, or validate this board. |
| Current claim | Source README gives a simplified higher-current description. | That marketing shorthand is not adopted. This board has no advertisement detector; the actual source must independently allow its stated budget. |

The exact [reference comparison result](output/reference-pair.json) binds the
archived source hashes. The pair is stored as evidence, never as an active
project or a template to redraw this board. No reference CAD, retained owner
design or frozen fixture was copied into the new native schematic/layout.
The GPIO example supplied folder/receipt conventions and unchanged common
upstream license notices only. Independent design work preceded this reference
comparison; similarity of the basic passive attachment pattern is not approval.
