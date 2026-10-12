# Inductor cost and alternatives

Research date: 2026-10-01, Asia/Seoul. This is a purchasing/design comparison,
not an approved substitution. The schematic, PCB, BOM identities and selected
Bourns inductors are unchanged.

## Why the selected parts are large

The Bourns SRP1265A series is a shielded, carbonyl-powder power inductor with
AEC-Q200 qualification. It uses a 13.5 x 12.5 mm body and is rated through
150 C including self-heating. Its low winding resistance and substantial
current capability are useful, but the selected ratings are generous for the
rover's 3.0 A / 2.4 A / 3.5 A planning loads. This is an engineering explanation
for the conservative selection, not evidence of the manufacturer's cost structure.

| Ref / rail | Selected part | DCR maximum | Irms, 40 C rise | Isat, 20% inductance drop |
| --- | --- | ---: | ---: | ---: |
| L1 / 12 V | SRP1265A-6R8M, 6.8 uH | 11.5 mOhm | 11.5 A | 18 A |
| L2 / 5 V | SRP1265A-4R7M, 4.7 uH | 8.4 mOhm | 13.5 A | 28 A |
| L3 / motor | SRP1265A-3R3M, 3.3 uH | 6.8 mOhm | 18 A | 30 A |

Source: [Bourns SRP1265A datasheet](https://www.bourns.com/docs/product-datasheets/srp1265a.pdf),
page 1. Distributor DCR fields sometimes show typical rather than maximum
values: use the maximum column above for winding-loss calculations.

## Prices and availability observed

USD per piece, quantity 1; tax, shipping, PCB assembly and extended-part fees
are excluded. These are supplier observations, not reserved stock or a quote.
LCSC loose-component inventory and JLCPCB assembly inventory are separate.

Current selections, LCSC pages retrieved during this review:

| Part | Unit price | Displayed stock |
| --- | ---: | ---: |
| [SRP1265A-6R8M / C2041326](https://www.lcsc.com/product-detail/C2041326.html) | $1.1431 | 432 |
| [SRP1265A-4R7M / C780205](https://www.lcsc.com/product-detail/power-inductors_bourns-srp1265a-4r7m_C780205.html) | $1.0227 | 105 |
| [SRP1265A-3R3M / C1329348](https://www.lcsc.com/product-detail/C1329348.html) | $0.3551, reference only | Out of stock |

Preliminary alternatives, **live JLCPCB pages** inspected in the browser:

| Intended rail | Candidate | Unit price | In stock / available order quantity |
| --- | --- | ---: | ---: |
| 12 V | [Sunlord MWSA1205S-6R8MT / C408515](https://jlcpcb.com/partdetail/Sunlord-MWSA1205S6R8MT/C408515) | $0.5917 | 2,151 / 2,112 |
| 5 V | [Sunlord MWSA1004S-4R7MT / C408484](https://jlcpcb.com/partdetail/Sunlord-MWSA1004S4R7MT/C408484) | $0.2669 | 1,394 / 1,374 |
| Motor | [Sunlord MWSA1005S-3R3MT / C17700181](https://jlcpcb.com/partdetail/Sunlord-MWSA1005S3R3MT/C17700181) | $0.2811 | 186 / 184 |

The three alternative unit prices sum to **$1.1397 per board** before assembly
charges. All three pages identify Extended parts supporting Economic and Standard
SMT assembly. This total must not be presented as a final PCBA saving: the current
Bourns prices above come from a different purchasing channel, and L3's displayed
price is not an in-stock offer. Older search snippets showed different prices;
the live browser values are used for the alternative table.

## Electrical screening

The official [Sunlord MWSA-S datasheet](https://www.sunlordinc.com/uploads/files/20230303/MWSA-S%C2%A0series%C2%A0of%C2%A0SMD%C2%A0Power%C2%A0Inductor.pdf)
(revision 2022-10-12) was retrieved in full. PDF pages 8-10 give the part rows;
page 11 defines its unusual headings. Isat **Max.** means the 20% inductance-drop
criterion; Isat **Typ.** uses 30%. Irms **Max.** means 20 C rise; Irms **Typ.**
uses 40 C rise. Neither label should be silently converted into an all-temperature
guaranteed minimum. Tests reference 20 C ambient. Operating range is -40 to
125 C including self-heating; absolute maximum voltage is 30 V DC.

| Candidate | DCR max. | Isat at 20% / 30% drop | Irms at 20 C / 40 C rise |
| --- | ---: | ---: | ---: |
| MWSA1205S-6R8MT | 18 mOhm | 12.8 / 16 A | 10 / 12 A |
| MWSA1004S-4R7MT | 20 mOhm | 10.4 / 13 A | 7.5 / 9 A |
| MWSA1005S-3R3MT | 10 mOhm | 14 / 16 A | 11.5 / 13 A |

The TI LMR51450 [datasheet](https://www.ti.com/lit/ds/symlink/lmr51450.pdf),
section 9.2.2.3, requires saturation capability above the peak current limit.
Section 7.4 lists 9.6 A maximum high-side limit for the 5 A version; its footnote
says this open-loop test value can differ in a closed-loop application. Therefore
selecting only for the normal 3-5 A peak is insufficient. The candidates' 20%
drop figures exceed 9.6 A by 3.2 A, 0.8 A and 4.4 A respectively. The 5 V
candidate has the smallest fault-current margin and needs particular attention
to hot saturation behavior. This comparison is a screen, not a fault guarantee.

For 25.2 V input, nominal 500 kHz, ideal continuous conduction, the existing
inductances give the following calculated normal operating points. Replacement
with equal inductance preserves these first-order ripple calculations:

| Rail | Load | Ripple peak-to-peak | Peak | RMS | Bourns / Sunlord winding loss |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12 V | 3.0 A | 1.849 A | 3.924 A | 3.047 A | 0.107 / 0.167 W |
| 5 V | 2.4 A | 1.706 A | 3.253 A | 2.450 A | 0.050 / 0.120 W |
| 22.190 V motor | 3.5 A | 1.606 A | 4.303 A | 3.531 A | 0.085 / 0.125 W |

Equations: delta-I = Vout*(Vin-Vout)/(Vin*L*f), Ipeak = Iload + delta-I/2,
Irms = sqrt(Iload^2 + delta-I^2/12), Pcu = Irms^2*DCRmax. These exclude
hot resistance, inductance tolerance/bias, core loss, startup, dropout and
transients. All three candidates have ample normal RMS-current capacity under
the catalog test conditions. Their extra total cold winding loss is about
0.17 W at these three simultaneous loads. Actual 500 kHz core loss and
temperature still need evaluation; 100 kHz is the inductance measurement
frequency, not a claimed operating-frequency ceiling.

The 30 V inductor voltage rating exceeds the 25.2 V planned battery maximum,
but switch-node ringing and startup must stay within it. The shared battery
and motor-regeneration limitations already documented for the board remain.

## Footprints and decision

These are **not approved drop-in replacements**. Sunlord's page 2 drawing calls
for 3.25 x 5.5 mm lands with an 8.0 mm gap for the 1205S family, and 4.1 x
4.1 mm lands with a 5.4 mm gap for the 1004S/1005S families. Current Bourns
lands are 3.1 x 5.0 mm with an 8.0 mm gap. Body heights and courtyards also differ.

The 6.8 uH 1004S part was not shortlisted: its 20%-drop current is 9.6 A,
equal to the listed IC maximum limit. The larger 1205S is a more defensible
cost candidate. For the other two rails the smaller bodies can reduce occupied
area as well as price, at the cost of higher winding resistance and lower
temperature/current margins.

Recommendation: keep the accepted board unchanged for this request, and use
this shortlist for an explicit cost-reduction revision. A substitution revision
must update schematic sourcing/footprints, local power routing and courtyards,
check current-bias/temperature curves and voltage stress, then rerun native
parity/DRC and visual review. The current Bourns choice is conservative rather
than inherently necessary, but replacing it is more than changing a BOM string.

Retrieved official Sunlord PDF SHA-256:
`55a6f5de0d3424730210584c2a732f5209bba52cffa5c226885944f3d9e1be9a`.
The exact research copy is indexed at `../../evidence/files/Sunlord_MWSA-S_55a6f5de0d34.pdf`.
It has no adopted component references: no substitution was made.
