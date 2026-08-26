# Datasheet Provenance — baro-bmp390

Every non-passive part needs a datasheet on file. This index maps parts to the
PDF that documents them, and records where each came from, so "verified"
can be told apart from "not verified" — the distinction that was missing when
eleven parts shipped with an empty datasheets/ folder and nothing noticed.

Format:  `<keys> -> <file>`  (keys = comma-separated part/value substrings)

## Archive

U1, BMP390, C5124834  ->  BMP390-datasheet.pdf  # https://www.lcsc.com/datasheet/lcsc_datasheet_2410121912_Bosch-Sensortec-BMP390_C5124834.pdf | fetched 2026-08-25 | pdf 1885KB | BST-BMP390-DS002-07 Rev 1.7, March 2021, 59pp. Revision confirmed by reading page 1 of the file on disk, not from the link text.

## Known gaps

_List any part with no obtainable datasheet, and say what you did instead._

Bosch's own canonical URL,
`https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp390-ds002.pdf`,
is the authoritative home of this document but does not respond to curl from
this machine (status `000` — connection refused/blocked, *not* a 404; the page
exists in search results). The LCSC mirror above is byte-identical in revision
(DS002-07 Rev 1.7) and is the distributor copy for the exact part number this
board buys, C5124834, so it is the provenance of record. Re-check the Bosch URL
before trusting a future revision bump.
