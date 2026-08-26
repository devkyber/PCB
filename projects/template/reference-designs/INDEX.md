# Reference Design Archive — template

Provenance record for reference designs, EVM schematics, app notes and
vendor source files. `docs/check_research.py` reads the `->` rows.

Format:  PART[, PART...]  ->  filename  # source-url | fetched YYYY-MM-DD | note

Nothing counts as a reference until it is a FILE ON THIS DISK with a live
source URL beside it. A link read once and not saved cannot be re-checked,
and a summary of a schematic is not a schematic.

Add entries with:
    python3 docs/collect_references.py add projects/template <PART> <URL>
