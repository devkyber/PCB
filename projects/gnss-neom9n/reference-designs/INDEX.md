# Reference Design Archive — gnss-neom9n

Provenance record for reference designs, EVM schematics, app notes and
vendor source files. `docs/check_research.py` reads the `->` rows.

Format:  PART[, PART...]  ->  filename  # source-url | fetched YYYY-MM-DD | note

Nothing counts as a reference until it is a FILE ON THIS DISK with a live
source URL beside it. A link read once and not saved cannot be re-checked,
and a summary of a schematic is not a schematic.

Add entries with:
    python3 docs/collect_references.py add projects/gnss-neom9n <PART> <URL>
NEO-M9N-00B  ->  NEO-M9N-00B_NEO-M9N_Integrationmanual_UBX-19014286.pdf  # https://content.u-blox.com/sites/default/files/NEO-M9N_Integrationmanual_UBX-19014286.pdf | fetched 2026-08-25 | pdf 3977KB | u-blox NEO-M9N Integration Manual UBX-19014286 — contains the manufacturer's reference design (Tier 1)
