# Quick Start — New Board Project

## 1. Start a new project
Tell Claude Code (in the PCB/ directory):
```
Create a new KiCad project called "my-board" in projects/my-board/
```

## 2. Describe your board
Be specific about constraints. Example:
```
Design a sensor breakout board with:
- MCU: ESP32-S3-WROOM-1 module
- Inputs: 3 analog channels (0-3.3V) with ESD protection
- Communication: I2C header (4-pin), USB-C for power + programming
- Power: USB 5V → 3.3V LDO (AMS1117-3.3)
- LEDs: 1 power LED, 1 user LED
- Mechanical: 50x35mm, M3 mounting holes at corners, 2-layer
- Fabrication: JLCPCB compatible
```

## 3. Review the design
```
Run a full design review on projects/my-board/ — check power tree,
signal integrity, DFM for JLCPCB, and download datasheets for all components
```

## 4. Check in KiCad
Open the .kicad_pro file in KiCad. Visually inspect:
- Component placement makes mechanical sense
- Connectors on accessible edges
- Silkscreen readable
- Board outline matches your enclosure

## 5. Export and order
```
Export fabrication files for projects/my-board/ in JLCPCB format:
Gerbers, drill files, BOM with LCSC part numbers, and pick-and-place file
```

Upload the zip to jlcpcb.com → Instant Quote → check the Gerber viewer → order.

## Useful Commands
| What you want | What to tell Claude |
|---|---|
| Design review | "Analyze my project at projects/X/" |
| Download datasheets | "Download datasheets for all components in projects/X/" |
| Check JLCPCB compatibility | "Validate DFM rules for JLCPCB on projects/X/" |
| Export 3D model | "Export STEP file for projects/X/ so I can check fit in Fusion 360" |
| Run DRC/ERC | "Run design rule check and electrical rule check on projects/X/" |
| Source components | "Find LCSC/JLCPCB part numbers for all components in projects/X/" |
| EMC check | "Run EMC pre-compliance analysis on projects/X/" |

## EasyEDA Transition Notes
| EasyEDA concept | KiCad equivalent |
|---|---|
| Schematic editor | Schematic Editor (same idea) |
| PCB editor | PCB Editor (same idea) |
| Component library | Symbol + Footprint libraries (separate in KiCad) |
| LCSC part picker | Use kicad-happy's `lcsc` skill or BOM sourcing |
| Design rules | Board Setup → Design Rules (or .kicad_dru file) |
| Gerber export | File → Fabrication Outputs → Gerbers |
| 3D viewer | View → 3D Viewer |
| EasyEDA's autorouter | Freerouting (via kicad-claude-mcp) |
