# TMS A2 local libraries

Fresh functional symbols and module footprints, 2026-10-13. No retired CAD or
fixture library was copied. Exact source bytes are in ../evidence/index.yaml.

| Device | Pin/function source |
| --- | --- |
| ADS1256IDBR | TI SBAS288K p5; AVDD1, DVDD16, RESET15 |
| ADS1220IPWR | TI SBAS501D PW table p4; AVDD12, DVDD13 |
| OPA2388IDR | TI SBOS777D dual D-package table p5 |
| OPA350UA | TI D-package pinout; +IN3, -IN2, OUT6, V+7, V-4 |
| LMR51430YFDDCR | TI DDC6 table: GND1, SW2, VIN3, FB4, EN5, CB6 |
| TXU0204PWR | TI SCES936A PW14 table; A1/A2 to B1Y/B2Y, B3/B4 to A3Y/A4Y |
| OPA388IDBVR | TI DBV5 table: OUT1, V-2, +IN3, -IN4, V+5 |
| TLV75533PDBVR | TI SBVS320D DBV table p3; NC4, OUT5 |
| AO3400A | AOS Rev3.1 SOT23 drawing; gate1, source2, drain3 |
| BAV199 | Nexperia 2023-04-01 p1; A1=1, K2=2, midpoint=3 |
| TPD2E2U06DCKR | TI DCK table p3; IO1=1, IO2=2, GND3; SC70-3 |
| Teensy41_Socket | PJRC archived front/back cards |
| XBee3_RPSMA_Socket | Digi p37 RP-SMA drawing and p45-46 pin table |
| HF46F_Type1 | Hongfa type1 bottom-view outline/layout/wiring drawings |
| L_SRP1038A | Bourns p1 lands: overall13.6 mm, pads3.5 x5.4 mm |

Teensy orientation is USB left. At y=+7.62 mm the 24 contacts, left to right,
are GNDL, D0-D12, 3V3L, D24-D32. At y=-7.62 mm they are VIN, GNDR, 3V3R,
D23-D13, GNDA, D41-D33. Pitch2.54 mm. Pad IDs are an explicit local signal
convention, not invented manufacturer package numbers. Verify a 1:1 print.

XBee pad1 is upper left, pad10 lower left, pad20 upper right, pad11 lower right,
with 2 mm pitch and 22 mm row spacing. Courtyard includes RP-SMA projection.
Actual socket, standoffs and enclosure/antenna fit are not qualified by CAD.

Hongfa drawings show topology/geometry without terminal numbers. The local
convention retains coil1/6 and contact2/3; it is not claimed as manufacturer
numbering. The coil/contact pairs are unpolarized. The footprint reflects the
bottom view into a top PCB view: coil6 y=-4.7 mm, contacts x=11.5/18.5 mm.
Verify the physical variant. The NO graphic is adapted from Relay_SPST-NO.

KiCad contributors' library geometry is used under the
[KiCad library license](https://www.kicad.org/libraries/license/), CC BY-SA4.0
with the library exception. Manufacturer/source identities are retained.
lcsc_C8465 is freshly imported supplier CAD/model with archived JSON provenance;
it is not manufacturer geometry approval. No qualified local module3D models
are included. Native pin/pad consistency is separate from actual physical fit.

## A2 source-bound derivations

`footprint-provenance.yaml` binds all five hand-authored footprints to exact
CAD hashes, manufacturer evidence IDs, every pad function and derivation notes.
The normal shared resolver validates the receipts and source hashes. This is
lineage/pad coverage, not physical fit or owner sign-off. Changed bytes invalidate
the receipt. Imported lcsc_C8465 CAD/model remains preserved supplier evidence;
A2 J5 uses the corrected TMS drawing-derived footprint with1.50mm holes.

A2 adds LMR51430YFDDCR, TXU0204PWR and OPA388IDBVR functional symbols.
Teensy application pins use Serial3 TX14/RX15/CTS19/RTS18. Physical socket
pad names/positions retain the PJRC card mapping.

AMASS J1/J4 XT30PW-F and J6 XT60PW-F assigned footprints mark pad 1
negative and pad 2 positive. A2 symbols match these markings; the independent
contract checks actual footprint polarity as well as pad coverage. Verify the
purchased molded part, exact revision and mating harness before assembly.
