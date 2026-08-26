# TMS V3 — datasheet provenance

Every part on the board that is not a passive, an LED, or a plain field
connector must appear here with the document it was verified against.
`docs/check_datasheets.py` reads the `->` lines; the rest is for humans.

    <ref or value>, ...  ->  <file>   # where it came from

J7, J8, TEENSY-L, TEENSY-R  ->  card11a_rev4_web.pdf   # PJRC Teensy 4.1 pinout card rev4, pjrc.com/teensy/card11a_rev4_web.pdf  |  https://www.pjrc.com/teensy/card11a_rev4_web.pdf (verified live 2026-08-25)
J9, XBEE3                   ->  xbee3_hardware_ref.pdf # Digi 90001543 XBee 3 Hardware Reference; TH pin table p.45-46, mechanical p.36  |  https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf (verified live 2026-08-25)
U2, ADS1256IDBR             ->  ADS1256_ti.pdf         # TI SBAS288K, ti.com/lit/ds/symlink/ads1256.pdf  |  https://www.ti.com/lit/ds/symlink/ads1256.pdf (verified live 2026-08-25)
U3, ADS1220IPWR             ->  ADS1220_ti.pdf         # TI, ti.com/lit/ds/symlink/ads1220.pdf  |  https://www.ti.com/lit/ds/symlink/ads1220.pdf (verified live 2026-08-25)
U4, LM7805                  ->  LM7805_C22467097.pdf   # via LCSC C22467097 (YONGYUTAI TO-263)  |  https://www.lcsc.com/product-detail/C22467097.html (verified live 2026-08-25)
D3, SS54                    ->  SS54_C22452.pdf        # via LCSC C22452 (MDD, SMA/DO-214AC)  |  https://www.lcsc.com/product-detail/C22452.html (verified live 2026-08-25)
D2, PESD5V0S2BT             ->  PESD5V0S2BT_C49338.pdf # Nexperia, via LCSC C49338  |  https://www.lcsc.com/product-detail/C49338.html (verified live 2026-08-25)
D1, 1N4148WS                ->  1N4148WS_C57759.pdf    # via LCSC C57759  |  https://www.lcsc.com/product-detail/C57759.html (verified live 2026-08-25)
Q1, MMBT3904                ->  MMBT3904_C20526.pdf    # via LCSC C20526  |  https://www.lcsc.com/product-detail/C20526.html (verified live 2026-08-25)
K1, HF46F-G/5-HS1T          ->  HF46F_C5274026.pdf     # the LCSC listing for the relay actually ordered  |  https://www.lcsc.com/product-detail/C5274026.html (verified live 2026-08-25)
J7, J8, TEENSY-BACK         ->  card11b_rev4_web.pdf   # PJRC Teensy 4.1 pinout card rev4, BACK side — the underside pads and power pins the front card does not show  |  https://www.pjrc.com/teensy/card11b_rev4_web.pdf (verified live 2026-08-25)
K1, HF46F-G/5-HS1T          ->  HF46F_hongfa_en.pdf    # Hongfa; coil pin1/pin6, COM pin2, NO pin3 read from the wiring diagram  |  http://www.hongfaamerica.com/hq/PDF/HF46F_en.pdf (verified live 2026-08-25)

## Known gap

**RESOLVED 2026-08-25 — and the 22pF was wrong.** This entry read: "Y1
(7.68MHz crystal) has no datasheet on file... the load-capacitance figure
behind C8/C9 = 22pF is UNVERIFIED."

Resolved by searching for 7.68MHz parts in the board's actual footprint
(HC-49S-SMD, 11.4 x 4.7mm) rather than by chasing the unresolvable LCSC code
C891749. Every candidate specifies **CL = 20pF** (Huiyuan C5265772, archived
above; Changjing CJ03-076802020B20 agrees; ECS is 18pF).

C_L = (C8*C9)/(C8+C9) + C_stray. At 22pF that is 11 + C_stray, roughly 15pF
against a 20pF requirement — the crystal was under-loaded and would run fast.
On the ADS1256 the crystal is the conversion clock, so that is a sample-rate
error in every measurement, and it fails silently: the board works, the
numbers are wrong. C8/C9 are now 33pF. See gen_tms_v3_sch.py for the
arithmetic and the [OWNER] note on stray capacitance.

Historical note, kept because it is the lesson: this was a
tooling artefact — see DEVIATIONS.md.

## Provenance note

These twelve documents were fetched during the original TMS V3 work with no
source recorded. The URLs above were located and **HTTP-verified on
2026-08-25**, then written beside the files that were already on disk. That
is a reconstruction, not the original provenance chain: it establishes where
each document can be re-fetched and re-checked for a newer revision, which is
the point of the record, but it does not prove the byte-identical file came
from that URL. Anything fetched from now on goes through
`collect_references.py add`, which verifies and records in one step.
7.68MHz  ->  7.68MHz_8590903324206051328.pdf  # https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8590903324206051328 | fetched 2026-08-25 | pdf 240KB | Huiyuan HY7680M49SSMDOB2R20, LCSC C5265772 — 7.68MHz HC-49S-SMD, CL=20pF, +-20ppm, 9447 stock. Package matches the board's CRYSTAL-SMD_L11.4-W4.7 footprint.
XT60  ->  XT60_XT60.pdf  # https://www.handsontec.com/dataspecs/connector/XT60.pdf | fetched 2026-08-26 | pdf 682KB | AMASS XT60 connector specification — 30A continuous / 60A instantaneous, DC500V, -20..+120C, 12AWG recommended
