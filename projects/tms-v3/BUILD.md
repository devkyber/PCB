# TMS V3 Build Guide — Full MCP Pipeline

**Status:** PDR Rev D approved, all findings resolved. Ready for generation.

## Prerequisites

- Claude Code CLI (interactive terminal) — MCP servers only load in CLI, not web app
- KiCad 10.0.5 installed at `/Applications/KiCad/`
- Java 21 (Temurin) for Freerouting

## Quick Start

```bash
cd /Users/leetaeho/CODE/PCB/projects/tms-v3
```

Then open Claude Code CLI and follow the phases below.

---

## Phase 1: Fetch LCSC Part Libraries

Use `kicad-jlcpcb` MCP tools to fetch real footprints from EasyEDA.

```
Fetch the following parts using fetch_part_library for project tms-v3:

1. ADS1256IDBR — LCSC C28186
2. ADS1220IPWR — LCSC C132290  
3. LM7805CT (D2PAK) — LCSC C22467097
4. MMBT3904 — LCSC C20526
5. 1N4148WS — LCSC C57759
6. PESD5V0S2BT — LCSC C356017
7. SS54 — LCSC C22452
8. HF46F-G/5-HS1T — LCSC C65122
9. NDK AT-41CD2-7.68MHZ — LCSC C891749
```

Check `fidelity` in each result — if "placeholder", the part needs manual review in KiCad.

## Phase 2: Generate Schematic

Option A — MCP tools:
```
Use kicad-claude-mcp to generate the TMS V3 schematic.
Follow the netlist in tms-v3-bom.md (Rev D).
All findings are resolved — see tms-v3-pdr.md Rev D.
```

Option B — Script (if ed API available):
```bash
python3 gen_tms_v3_sch.py
```

Then run ERC:
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc \
  --output erc-report.json --format json \
  tms-v3.kicad_sch
```

## Phase 3: Generate PCB

Option A — MCP `generate_pcb` tool:
```
Use kicad-jlcpcb generate_pcb with this spec:
- Board: 100mm × 80mm, 2-layer
- Components: all from BOM with LCSC parts fetched in Phase 1
- Nets: per netlist in tms-v3-bom.md
```

Option B — Script:
```bash
python3 gen_tms_v3_pcb.py
```

Then import netlist in KiCad: Schematic → Update PCB from Schematic.

## Phase 4: Route Traces

### Option A — Freerouting (autorouter)

Export DSN from KiCad:
```
File → Export → Specctra DSN
```

Run Freerouting:
```bash
java -jar /Users/leetaeho/CODE/PCB/tools/kicad-claude-mcp/third_party/freerouting.jar \
  -de tms-v3.dsn -do tms-v3.ses
```

Import SES back into KiCad:
```
File → Import → Specctra Session
```

### Option B — EasyEDA Handoff (kicad-jlcpcb)

```
Use easyeda_handoff to export the board for EasyEDA cloud autorouting.
After routing in EasyEDA, export Gerbers from there directly.
```

### Option C — Manual Routing in KiCad

Open in KiCad PCB editor, route manually. Follow design rules in
`docs/pcb-design-rules.md`:
- Power traces: 0.5mm minimum (IPC-2221 for current)
- Signal traces: 0.254mm
- Decoupling caps: verify ≤2mm from IC pins
- Crystal: verify ≤5mm from ADS1256, no pour under crystal body
- Analog/digital separation: analog left, digital right

## Phase 5: Validate

### DRC
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc \
  --output drc-report.json --format json \
  tms-v3.kicad_pcb
```

### Design Review (kicad-happy)
```
Run the 6-pass layout review protocol from docs/pcb-design-rules.md §16:
1. Power integrity pass
2. Decoupling pass  
3. Ground plane pass
4. Signal integrity pass
5. Thermal pass
6. DFM pass (JLCPCB minimums)
```

## Phase 6: Export Fabrication Files

```bash
# Gerbers
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers \
  --output fabrication/ tms-v3.kicad_pcb

# Drill files
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export drill \
  --output fabrication/ tms-v3.kicad_pcb

# BOM (JLCPCB format)
# Generate from tms-v3-bom.md → CSV with columns: Comment, Designator, Footprint, LCSC

# Pick-and-place (CPL)
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export pos \
  --output fabrication/tms-v3-cpl.csv --format csv --units mm \
  tms-v3.kicad_pcb
```

### 3D Model
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export step \
  --output 3d-models/tms-v3.step tms-v3.kicad_pcb
```

## File Inventory

| File | Purpose |
|------|---------|
| `tms-v3.kicad_pro` | Project file with design rules, net classes |
| `tms-v3.kicad_sch` | Schematic |
| `tms-v3.kicad_pcb` | PCB layout |
| `tms-v3-bom.md` | Full BOM with LCSC parts, netlist, pin assignments |
| `gen_tms_v3_sch.py` | Schematic generation script (ed API) |
| `gen_tms_v3_pcb.py` | PCB generation script (raw S-expressions) |
| `fabrication/` | Gerbers, drill, BOM CSV, CPL |
| `3d-models/` | STEP export |

## Key Design Decisions (Rev D)

| Decision | Resolution |
|----------|------------|
| Excitation reference (D-04) | LC filter (10µH + 10µF) on 5V rail |
| Igniter battery (D-06) | 2S LiPo (7.4V) |
| FIRE mechanism (D-07) | Remote only via XBee |
| Continuity check (D-10) | Skip for V3 |
| 5V tolerance (F-04) | 33Ω series on SPI lines |
| Input protection (F-06) | 100Ω + TVS on ADC inputs |
| Reverse polarity (F-14) | SS54 Schottky on VBAT |
