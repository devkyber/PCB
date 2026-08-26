# Datasheet Provenance — imu-icm42688

Every non-passive part needs a datasheet on file. This index maps parts to the
PDF that documents them, and records where each came from, so "verified"
can be told apart from "not verified" — the distinction that was missing when
eleven parts shipped with an empty datasheets/ folder and nothing noticed.

Format:  `<keys> -> <file>`  (keys = comma-separated part/value substrings)

## Known gaps

_List any part with no obtainable datasheet, and say what you did instead._
ICM-42688-P  ->  ICM-42688-P_ICM-42688-P_Datasheet.pdf  # https://cdn.sparkfun.com/assets/f/e/4/5/a/ICM-42688-P_Datasheet.pdf | fetched 2026-08-25 | pdf 1347KB | SparkFun CDN mirror of TDK DS-000347; TDK's own host returns 403 to curl
ICM-42688-P  ->  ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf  # https://raw.githubusercontent.com/anyshake/icm-42688-breakout/HEAD/hardware/datasheet/ds-000347-icm-42688-p-v1.6.pdf | fetched 2026-08-25 | pdf 1786KB | DS-000347 rev 1.6 — newer than the 1.2 reachable elsewhere; TDK's own host 403s to curl
