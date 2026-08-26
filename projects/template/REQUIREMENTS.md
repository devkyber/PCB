# Requirements — template

Phase 1 deliverable. Audited 2026-08-25: no board in this repo had one, so
every later "why is it like this?" had to be reconstructed from chat
scrollback. Replace every <angle bracket> — `check_research.py` fails on a
section left as a placeholder, because a half-filled spec reads as a
finished one.

## Purpose
<What the board does, in one paragraph, and what system it plugs into.>

## Electrical
- Supply: <voltage in, tolerance, max current>
- Rails generated: <e.g. 3V3 @ 500mA>
- Signal levels: <3.3V / 5V logic, any level shifting needed>
- Worst-case load / transient: <e.g. relay coil inrush, igniter current>

## Mechanical
- Board outline: <X x Y mm>
- Mounting holes: <count, diameter, positions>
- Height limit / connector-facing edges: <...>

## Interfaces
| Connector | Signal set | Mates with | Notes |
|---|---|---|---|
| <J1> | <...> | <...> | <...> |

## Environment
- Temperature: <range>
- Vibration / shock: <e.g. rocket flight loads>
- Conformal coating, potting, EMI environment: <...>

## Success criteria
- <Measurable. "Reads pressure at 50 Hz over I2C with <1 Pa noise", not "works".>
