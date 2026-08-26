# Reference Design Archive — imu-icm42688

Provenance record for reference designs, EVM schematics, app notes and
vendor source files. `docs/check_research.py` reads the `->` rows.

Format:  PART[, PART...]  ->  filename  # source-url | fetched YYYY-MM-DD | note

Nothing counts as a reference until it is a FILE ON THIS DISK with a live
source URL beside it. A link read once and not saved cannot be re-checked,
and a summary of a schematic is not a schematic.

Add entries with:
    python3 docs/collect_references.py add projects/imu-icm42688 <PART> <URL>
ICM-42688-P  ->  ICM-42688-P_ICM-42688.kicad_sch  # https://raw.githubusercontent.com/anyshake/icm-42688-breakout/HEAD/hardware/ICM-42688.kicad_sch | fetched 2026-08-25 | kicad 132KB | anyshake ICM-42688 breakout, KiCad source — exact values and pin-level nets (Tier 2)
