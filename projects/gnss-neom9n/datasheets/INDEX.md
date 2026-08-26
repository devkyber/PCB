# Datasheet Provenance — gnss-neom9n

Every non-passive part needs a datasheet on file. This index maps parts to the
PDF that documents them, and records where each came from, so "verified"
can be told apart from "not verified" — the distinction that was missing when
eleven parts shipped with an empty datasheets/ folder and nothing noticed.

Format:  `<keys> -> <file>`  (keys = comma-separated part/value substrings)

SW1, RESET, B3U-1000P  ->  B3U-1000P_8588893394868953088.pdf  # https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8588893394868953088 | fetched 2026-08-25 | pdf 675KB | SW1's Value is "RESET", which no filename match can find — this is exactly the case INDEX keys exist for.

## Known gaps

_List any part with no obtainable datasheet, and say what you did instead._
NEO-M9N-00B  ->  NEO-M9N-00B_NEO-M9N-00B_DataSheet_UBX-19014285.pdf  # https://content.u-blox.com/sites/default/files/NEO-M9N-00B_DataSheet_UBX-19014285.pdf | fetched 2026-08-25 | pdf 638KB | u-blox official, UBX-19014285 — Tier 1
RCLAMP0521P  ->  RCLAMP0521P_8588899113072648192.pdf  # https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8588899113072648192 | fetched 2026-08-25 | pdf 146KB | Semtech RCLAMP0521PATCT, via JLCPCB part page for C117554
B3U-1000P  ->  B3U-1000P_8588893394868953088.pdf  # https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8588893394868953088 | fetched 2026-08-25 | pdf 675KB | Omron B3U-1000P tactile switch, via JLCPCB part page for C231329
XC6206P332MR  ->  XC6206P332MR_8579707861620228096.pdf  # https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8579707861620228096 | fetched 2026-08-25 | pdf 1024KB | Torex XC6206P332MR-G, via JLCPCB part page for C5446 (the part already on this board)

SW1, RESET, B3U-1000P  ->  B3U-1000P_8588893394868953088.pdf  # https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8588893394868953088 | fetched 2026-08-25 | pdf 675KB | SW1's Value is "RESET", which no filename match can find — this is exactly the case INDEX keys exist for.

## Known gaps

BT1 — resolved, but read the correction. This entry first said "no datasheet,
the holder part is undecided". That was based on misreading the footprint name:
`Battery_Panasonic_CR1220-VCN_Vertical_CircularHoles` is not a holder land
pattern at all. Panasonic's `-VCN` suffix denotes the CR1220 CELL WITH SOLDER
TABS — the battery is soldered to the board, not socketed. So the correct
document is the Panasonic cell datasheet, now archived above, and the LCSC
holder search that produced no footprint match was looking for the wrong kind
of part entirely.

That distinction has a design consequence worth stating: a soldered cell
cannot be replaced in the field, which is a real limitation, but it also
cannot shake loose — which for a rocketry board is the better trade. See
DEVIATIONS.md and REQUIREMENTS.md.
CR1220  ->  CR1220_CR1220_Datasheet_EN.pdf  # https://energy.panasonic.com/dam/master/pdf/en/datasheet/lithium/CR1220_Datasheet_EN.pdf | fetched 2026-08-25 | pdf 498KB | Panasonic Energy official CR1220 datasheet; the VCN variant is the solder-tab version this footprint targets
