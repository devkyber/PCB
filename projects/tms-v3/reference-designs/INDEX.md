# Reference Design Archive — tms-v3

Provenance record for reference designs, EVM schematics, app notes and
vendor source files. `docs/check_research.py` reads the `->` rows.

Format:  PART[, PART...]  ->  filename  # source-url | fetched YYYY-MM-DD | note

Nothing counts as a reference until it is a FILE ON THIS DISK with a live
source URL beside it. A link read once and not saved cannot be re-checked,
and a summary of a schematic is not a schematic.

Add entries with:
    python3 docs/collect_references.py add projects/tms-v3 <PART> <URL>
J7, J8, TEENSY, TEENSY-L, TEENSY-R  ->  TEENSY_card11a_rev4_web.pdf  # https://www.pjrc.com/teensy/card11a_rev4_web.pdf | fetched 2026-08-25 | pdf 368KB | PJRC Teensy 4.1 pinout card rev4 (front). For a MODULE SOCKET the vendor pinout card IS the reference design — it is the only authority on which net belongs on which pin.
J9, XBee, XBee_THT_20pin  ->  XBee_90001543.pdf  # https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf | fetched 2026-08-25 | pdf 9084KB | Digi XBee 3 Hardware Reference 90001543 — TH pin table and mechanical drawing; the reference for the J9 socket wiring.
U3, ADS1220, ADS1220IPWR  ->  U3__ADS1220__ADS1220IPWR_sbau203.pdf  # https://www.ti.com/lit/pdf/sbau203 | fetched 2026-08-26 | pdf 831KB | TI ADS1x20EVM User's Guide SBAU203 — the manufacturer's own evaluation-module schematic and BOM for the ADS1220 (Tier 1)
U2, ADS1256, ADS1256IDBR  ->  U2__ADS1256__ADS1256IDBR_sbau090e.pdf  # https://www.ti.com/lit/ug/sbau090e/sbau090e.pdf | fetched 2026-08-26 | pdf 3154KB | TI ADS1256EVM User's Guide SBAU090E — manufacturer evaluation-module schematic for the ADS1256 (Tier 1)
