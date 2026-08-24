# PCB Design Workflow

**PSI Rocketry — Standard PCB Design Process**  
**Date:** 2026-08-24  
**Applies to:** All boards in this workspace

---

## Phases Overview

| Phase | Name | Gate |
|-------|------|------|
| 1 | Define | Requirements doc reviewed and signed off |
| 2 | Research | Reference designs collected, component BOM finalized, all datasheets on file |
| 3 | Schematic | ERC passes, design review against references complete |
| 4 | Layout | DRC passes, EMC review, thermal check |
| 5 | Validate | 3D STEP fit check in CAD, full design review (kicad-happy) |
| 6 | Fabricate | Gerbers + BOM + CPL exported, order placed at JLCPCB |

Each phase has a checklist. Don't move to the next phase until the gate passes.

---

## Phase 1 — Define

**Goal:** Lock down what the board does, what it connects to, and what box it fits in.

### Checklist

- [ ] System-level block diagram (sensors → ADC → MCU → comms → storage)
- [ ] Electrical requirements (voltage rails, current budgets, signal types)
- [ ] Mechanical constraints (board dimensions, mounting holes, connector positions, enclosure fit)
- [ ] Interface spec (which connectors, pin assignments, cable types)
- [ ] Safety requirements (isolation needs, inhibit chains, failure modes)
- [ ] Target fab house and layer count (default: JLCPCB 2-layer)
- [ ] Power budget table (every load, nominal and peak current)

### Deliverable

Requirements document or PDR (e.g., `tms-v3-pdr.md`).

---

## Phase 2 — Research

**Goal:** Before designing anything, collect every proven reference design, datasheet, and application note for each key component. Compare proven circuits against our architecture. Finalize the BOM with real part numbers.

This is the most important phase for reliability. Copying a proven TI EVM circuit with verified decoupling is more reliable than inventing one.

### Step 2.1 — Collect Datasheets

For every IC in the component register, download:

- **Datasheet** — pinout, absolute max ratings, recommended operating conditions, application circuit
- **Errata** — if the manufacturer publishes one, check it

Save to `projects/<board>/datasheets/`.

### Step 2.2 — Collect Reference Designs

For each key IC, search these sources **in order of trust**:

#### Tier 1 — Manufacturer Official (highest trust)

These are designed by the IC manufacturer's application engineers. Always start here.

| Source | What they publish | How to find | Format |
|--------|-------------------|-------------|--------|
| **TI (Texas Instruments)** | EVM user guides with full schematics, BOM, layout. Reference designs with Gerbers. | [ti.com/product/PARTNUMBER](https://www.ti.com) → "Design & development" tab → "Evaluation boards" or "Reference designs" | PDF schematic, Altium/Eagle, sometimes KiCad |
| **Analog Devices** | EVM schematics, CN (Circuit Note) app notes with tested circuits | [analog.com](https://www.analog.com) → product page → "Reference Circuits" | PDF, Altium |
| **STMicroelectronics** | Nucleo/Discovery board schematics, app notes | [st.com](https://www.st.com) → product page → "Tools & Software" | PDF, Altium |
| **Microchip / Atmel** | Dev board schematics, app notes | [microchip.com](https://www.microchip.com) → product page → "Documentation" | PDF, Eagle |
| **NXP** | EVK schematics, reference manuals | [nxp.com](https://www.nxp.com) → product page | PDF, Altium |
| **ON Semiconductor** | App notes (AND series), EVM schematics | [onsemi.com](https://www.onsemi.com) | PDF |
| **Infineon** | App notes, EVM designs | [infineon.com](https://www.infineon.com) | PDF |

**What to look for in EVM schematics:**
- Decoupling cap values and placement (type, value, proximity to pin)
- Crystal/oscillator circuit (load caps, trace length recommendations)
- Input/output protection networks
- Power supply filtering
- Pin strapping (unused pins, address selection, mode configuration)
- Reference voltage circuits

#### Tier 2 — Open-Source Hardware Vendors (high trust)

These companies publish production-quality schematics and PCB files for every product they sell. Their designs are peer-reviewed by the community and battle-tested in thousands of units.

| Source | GitHub Org | Format | How to use |
|--------|-----------|--------|------------|
| **[Adafruit](https://learn.adafruit.com/accessing-and-using-adafruit-pcb-design-files)** | [github.com/adafruit](https://github.com/adafruit) — every product has a `-PCB` repo | Eagle (.brd/.sch) | KiCad can import Eagle files natively (File → Import → Eagle) |
| **[SparkFun](https://www.sparkfun.com)** | [github.com/sparkfun](https://github.com/sparkfun) — every product has its own repo | Eagle (.brd/.sch) | Same — KiCad imports Eagle. Also has [SparkFun Eagle Libraries](https://github.com/sparkfun/SparkFun-Eagle-Libraries) |
| **[Arduino](https://www.arduino.cc)** | [github.com/arduino](https://github.com/arduino) — board schematics in hardware repos | Eagle, KiCad (newer boards) | Official Arduino board designs — great for MCU peripheral circuits |
| **[Seeed Studio](https://wiki.seeedstudio.com/open_source_topic/)** | [github.com/Seeed-Studio](https://github.com/Seeed-Studio) — HDKs and modules | Eagle, KiCad | Also has [Open Parts Library for KiCad](https://github.com/Seeed-Studio/OPL_Kicad_Library) with 10k+ sourced parts |
| **[Pololu](https://www.pololu.com)** | Schematics on product pages (PDF) | PDF schematics | Great for motor drivers, voltage regulators, sensor carriers |
| **[DFRobot](https://www.dfrobot.com)** | Wiki pages with schematics | PDF, Eagle | Sensor breakout boards, motor shields |
| **[PJRC (Teensy)](https://www.pjrc.com)** | Schematics on [product pages](https://www.pjrc.com/store/teensy41.html) | PDF | Official Teensy schematics — essential if using Teensy as MCU |
| **[Digi (XBee)](https://www.digi.com)** | Reference designs on product pages | PDF, Altium | XBee carrier board reference designs |

**How to search:** Go to the GitHub org, search for the IC part number or module name. Example: search "ADS1256" in github.com/adafruit, or "relay driver" in github.com/sparkfun.

#### Tier 3 — Community & Shared Projects (verify before trusting)

| Source | URL | What's there | Caution |
|--------|-----|-------------|---------|
| **EasyEDA Open Projects** | [oshwlab.com](https://oshwlab.com) | Thousands of community-shared schematics and PCBs, directly openable in EasyEDA | Quality varies wildly — cross-check against Tier 1/2 |
| **PCBWay Projects** | [pcbway.com/project](https://www.pcbway.com/project/) | Community PCB projects with Gerbers | Same — verify against datasheet |
| **OSHPark Shared Projects** | [oshpark.com/shared_projects](https://oshpark.com/shared_projects) | US-made shared PCB designs | Smaller community, curated |
| **OSHWA Certified** | [certification.oshwa.org](https://certification.oshwa.org) | Certified open-source hardware directory, searchable by type | Certification means open, not necessarily correct |
| **GitHub Topics** | Search `github.com/topics/<ic-name>` | Community projects using the same IC | Read the issues/stars to gauge quality |
| **Hackaday.io** | [hackaday.io/projects](https://hackaday.io/projects) | Project logs with schematics, sometimes full KiCad files | Hobby quality — good for ideas, verify details |

#### Tier 4 — Symbol/Footprint/3D Model Libraries

Not reference designs, but essential for schematic capture. Use these when our kicad-jlcpcb `fetch_part_library` doesn't cover a part.

| Source | URL | What it gives you | Notes |
|--------|-----|-------------------|-------|
| **SnapEDA / SnapMagic** | [snapeda.com/kicad](https://www.snapeda.com/kicad/) | KiCad symbols, footprints, 3D models | Free, millions of parts. Download ZIP → import. |
| **Ultra Librarian** | [ultralibrarian.com](https://www.ultralibrarian.com/cad-vendors/kicad/) | KiCad symbols, footprints | Free, large database |
| **SamacSys / Component Search Engine** | [componentsearchengine.com](https://componentsearchengine.com) | KiCad symbols, footprints, 3D | Free tier available. Has KiCad plugin. |
| **KiCad Import Plugin** | [github.com/Steffen-W/Import-LIB-KiCad-Plugin](https://github.com/Steffen-W/Import-LIB-KiCad-Plugin) | Auto-imports SnapEDA/SamacSys/UltraLibrarian ZIPs | Install via KiCad Plugin Manager |
| **KiCad Built-in Libraries** | Bundled with KiCad 10 | Standard parts (passives, connectors, common ICs) | Already installed |
| **kicad-jlcpcb `fetch_part_library`** | Our MCP tool | LCSC part → real KiCad symbol + footprint + 3D model via easyeda2kicad | Preferred for JLCPCB assembly parts. Check `fidelity` field. |

### Step 2.3 — Compare & Verify (HARD GATE — Do Not Skip)

For each key IC, create a **full-pin comparison table**. This is the single most important step for catching design omissions.

```markdown
| Aspect | Our Design | TI EVM | Adafruit/Community | Action |
|--------|-----------|--------|-------------------|--------|
| AVDD decoupling | 100nF + 10µF | 100nF + 10µF | 100nF + 22µF | Match EVM |
| Crystal load caps | 22 pF | 22 pF | 20 pF | Match datasheet rec (22 pF) |
| Input protection | none | 100Ω + TVS | 100Ω series only | Add TVS per EVM |
| Unused pins | floating | tied to DVDD | tied to DVDD | Fix — tie to DVDD |
| ADDR pin | — | GND (0x48) | jumper to GND/VDD | Add solder jumper |
| EXTINT pin | — | header | test point | Break out to TP |
| REGOUT cap | 1µF | 2.2µF | 2.2µF | Fix — use 2.2µF |
```

#### Mandatory columns to fill for every IC:

1. **Every power pin** — cap value, type (C0G/X7R), distance spec
2. **Every config/address pin** — how it's tied, whether jumper is needed
3. **Every unused pin** — datasheet recommendation for unused state
4. **Every debug/test pin** — whether to break out to header/TP
5. **Voltage level at every inter-IC connection** — flag mismatches

#### Gate criteria:
- Every row must have an Action that is either "Match" or "Intentional deviation (documented reason)"
- Any row with a blank Our Design column is a **blocker** — fill it before proceeding
- Any passive value mismatch vs. datasheet must be resolved with a documented reason

Any difference between our design and the EVM should be either:
- **Intentional** (we have a reason, document it in the PDR)
- **A bug** (fix it before moving to Phase 3)

### Step 2.4 — Finalize BOM

- Every IC has an LCSC part number (for JLCPCB assembly)
- Every passive has a value, package, and LCSC part number
- Prefer JLCPCB basic parts (lower assembly fee)
- Run `lcsc_search` or `lcsc_resolve_bom` to verify stock and pricing

### Deliverable

- `projects/<board>/datasheets/` folder with all PDFs
- Reference design comparison table in the PDR
- Finalized component register with LCSC part numbers
- Full passive BOM (decoupling caps, resistors, crystals, TVS diodes)

---

## Phase 3 — Schematic

**Goal:** Capture the circuit in KiCad. Every wire, every component, every net label.

### Checklist

- [ ] Create KiCad project in `projects/<board>/`
- [ ] Fetch real footprints for every IC via `fetch_part_library` — check `fidelity` field
- [ ] **Gate: every IC must have fidelity="real"** — if "placeholder", re-fetch or manually create the footprint before proceeding
- [ ] Place all components from BOM
- [ ] Wire power tree first (battery → regulators → rails → IC power pins)
- [ ] Wire analog signal chains (sensor → protection → ADC)
- [ ] Wire digital buses (SPI, UART, I2C) — check pin conflicts
- [ ] Wire control circuits (relay drivers, LED indicators, switches)
- [ ] Add all decoupling caps (one per IC power pin, placed near the symbol)
- [ ] Add test points
- [ ] Add mounting holes
- [ ] Net labels on all important signals
- [ ] Power flags on all power sources
- [ ] Run ERC — **zero errors, zero warnings**
- [ ] Compare schematic against reference designs (Phase 2.3 table — every row filled)
- [ ] Run pre-layout completeness checks (`pcb-design-rules.md` §15):
  - [ ] Every passive value matches datasheet app circuit (§15.1)
  - [ ] Every IC pin accounted for — address, config, debug pins (§15.2)
  - [ ] Voltage levels verified at every inter-IC connection (§15.3)
  - [ ] Level shifters added where needed (§15.3)
- [ ] Peer review — have someone else check the schematic

### Tools

- **kicad-claude-mcp** — automated schematic generation (105 tools)
- **kicad-jlcpcb** — `sch_generate` for wired schematic from component list
- **Manual** — KiCad schematic editor for visual review and fine-tuning

---

## Phase 4 — Layout (Placement + Routing)

**Goal:** Place components, route all traces, achieve zero unconnected nets.

Phase 4 has three sub-phases: **4A Placement**, **4B Routing**, **4C Verification**. All three must complete before moving to Phase 5.

### Design Rules (JLCPCB 2-Layer)

| Parameter | JLCPCB Minimum | Our Target |
|-----------|---------------|------------|
| Trace width | 0.127 mm | 0.254 mm signal, 0.5 mm power |
| Clearance | 0.127 mm | 0.2 mm |
| Via drill | 0.3 mm | 0.3 mm |
| Via pad | 0.6 mm | 0.6 mm |
| Board thickness | — | 1.6 mm |
| Copper weight | — | 1 oz (35 µm) |

### Phase 4A — Component Placement

Follow the placement order in **[`docs/pcb-design-rules.md`](pcb-design-rules.md)** §1:

1. **Board outline → mounting holes → connectors** — mechanically fixed
2. **Fiducials** — 3× fiducial marks (1mm pad, 2mm mask opening) if using JLCPCB PCBA
3. **Power supply chain** — regulator + caps along power flow
4. **Precision analog ICs** — near their input connectors, away from heat sources (≥15 mm)
5. **Digital ICs** — separate zone from analog
6. **Decoupling caps ≤2 mm** from IC power pins (no via between cap and pin)
7. **Crystal within 5 mm of IC** — no ground pour under crystal body
8. **Relay/power switching isolated** from analog section, separate ground return

#### Placement Checklist
- [ ] Board outline matches mechanical spec (dimensions, mounting holes)
- [ ] Board area justified — component density 40–60% (§15.4)
- [ ] Fiducials placed (3× minimum for PCBA)
- [ ] Component placement follows design rules (§1)
- [ ] Decoupling caps placed per rules (§2) — ≤2 mm, no via between cap and IC
- [ ] Crystal layout per rules (§5) — ≤5 mm, no ground pour under body
- [ ] Analog/digital physical separation verified
- [ ] Ground pour zones defined on F.Cu and B.Cu

### Phase 4B — Trace Routing (MANDATORY — Do Not Skip)

**Every net must be routed.** A board with unconnected nets is not a board — it's a parts list with coordinates. This phase is the difference between a fabrication-ready design and a decorative placement exercise.

#### Routing Priority Order
1. **Critical analog** — ADC differential inputs (matched length, guarded)
2. **Crystal traces** — XIN/XOUT, ≤10mm, no vias, no ground under body
3. **Power traces** — sized per IPC-2221 table (§4.2)
4. **SPI/I2C buses** — clock first, then data
5. **Everything else** — remaining signal traces

#### Routing Method (choose one, in preference order)

**Option 1 — Interactive KiCad routing (recommended for learning)**
Open in KiCad PCB editor. Route manually following `pcb-design-rules.md` §4. This gives you the most control and teaches you the most.

**Option 2 — Freerouting autorouter**
```bash
# Export DSN from KiCad: File → Export → Specctra DSN
java -jar tools/kicad-claude-mcp/third_party/freerouting.jar \
  -de <board>.dsn -do <board>.ses
# Import SES back: File → Import → Specctra Session
```
After autorouting: visually inspect every trace. Autorouters don't understand analog vs. digital separation — manually fix violations.

**Option 3 — EasyEDA handoff (kicad-jlcpcb)**
```
Use easyeda_handoff to export for EasyEDA cloud autorouting.
Route in EasyEDA, then export Gerbers from there.
```

**Option 4 — kicad-claude-mcp autoroute tool**
```
Use the autoroute MCP tool (wraps Freerouting).
```

#### Routing Gate (HARD — Cannot Proceed Without)
- [ ] **Zero unconnected nets** — run `kicad-cli pcb drc` and confirm 0 unconnected items
- [ ] Ground pour filled on both layers
- [ ] Ground stitching vias placed — perimeter every 5–10mm, within 2mm of every signal via

### Phase 4C — Post-Route Verification

- [ ] Trace widths verified against IPC-2221 table (§4.2)
- [ ] Thermal vias under regulator pad (§9)
- [ ] Silkscreen: board name, revision, author name, pin labels, test point labels
- [ ] Silkscreen does not overlap pads — run DRC to check
- [ ] No copper within 0.5mm of board edge, no components within 1mm
- [ ] Run the **7-pass Layout Review Protocol** (`pcb-design-rules.md` §17)
- [ ] Run DRC — **zero errors, zero warnings**
- [ ] Visual inspection in KiCad 3D viewer

### Tools

- **KiCad PCB Editor** — manual interactive routing (preferred for learning)
- **Freerouting** — `tools/kicad-claude-mcp/third_party/freerouting.jar` (Java 21)
- **kicad-claude-mcp** — PCB layout tools, autoroute, DRC
- **kicad-jlcpcb** — `easyeda_handoff` for EasyEDA cloud autorouting alternative

---

## Phase 5 — Validate

**Goal:** Catch mistakes before spending money.

### Step 5.1 — Automated Validation

Run the validation script on the PCB file:
```bash
python3 docs/validate_pcb.py projects/<board>/<board>.kicad_pcb
```

This checks: placeholder footprints, fiducials present, board dimensions, silkscreen content, edge clearance. Fix any FAIL items before proceeding.

Then run DRC/ERC:
```bash
kicad-cli pcb drc --output drc.json --format json <board>.kicad_pcb
kicad-cli sch erc --output erc.json --format json <board>.kicad_sch
```

### Step 5.2 — Design Review Checklist

- [ ] **DRC** — zero violations (from 5.1)
- [ ] **ERC** — zero violations (from 5.1)
- [ ] **validate_pcb.py** — all checks PASS (from 5.1)
- [ ] **Design review** — run kicad-happy skills (kicad, emc, spice, bom)
- [ ] **3D STEP export** — import into CAD tool, check fit with enclosure and mounting
- [ ] **Connector alignment** — verify connector positions match panel cutouts
- [ ] **Antenna clearance** — no ground pour or traces under antenna zone (if applicable)
- [ ] **Power dissipation** — check regulator thermal pad sizing
- [ ] **Signal integrity** — review critical trace impedances if needed (kicad-claude-mcp has SI tools)
- [ ] **Peer review** — have someone else look at the board

### Tools

- **kicad-happy** — design review skills (invoke via `/kicad`, `/emc`, `/spice`, `/bom`)
- **kicad-claude-mcp** — DRC, signal integrity analysis
- **KiCad 3D Viewer** — visual inspection
- **kicad-cli** — batch DRC/ERC from command line

---

## Phase 6 — Fabricate

**Goal:** Export manufacturing files, order the board.

### Export Checklist

- [ ] **Gerber files** — F.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen, B.Silkscreen, Edge.Cuts
- [ ] **Drill file** — Excellon format
- [ ] **BOM** — JLCPCB format: Comment, Designator, Footprint, LCSC Part#
- [ ] **CPL (Pick-and-Place)** — Designator, Mid X, Mid Y, Rotation, Layer
- [ ] **3D STEP** — for mechanical integration records

Save all to `projects/<board>/fabrication/`.

### JLCPCB Order Settings

| Setting | Default |
|---------|---------|
| Layers | 2 |
| PCB thickness | 1.6 mm |
| Surface finish | HASL (lead-free) |
| Copper weight | 1 oz |
| Solder mask | Green (or whatever you want) |
| Silkscreen | White |
| Remove order number | Yes (specify position or "Remove") |

### Tools

- **kicad-jlcpcb** — `package_for_jlcpcb` bundles Gerber/BOM/CPL
- **kicad-cli** — `kicad-cli pcb export gerbers`, `kicad-cli pcb export drill`
- **KiCad** — Plot dialog for manual export

### Post-Order

- [ ] Save order confirmation and tracking
- [ ] Note revision number in project folder
- [ ] When boards arrive: visual inspection, continuity check, power-on test
- [ ] Document any issues for next revision

---

## Toolchain Summary

| Tool | Purpose | Location |
|------|---------|----------|
| KiCad 10.0.5 | Schematic + PCB editor | `/Applications/KiCad/` |
| kicad-claude-mcp | MCP server — 105 tools for automated schematic/PCB/DRC/SI | `tools/kicad-claude-mcp/` |
| kicad-jlcpcb | MCP server — 13 tools for LCSC sourcing, JLCPCB packaging | `tools/kicad-jlcpcb/` |
| kicad-happy | Review skills — design review, EMC, SPICE, datasheet extraction | `tools/kicad-happy/` |
| Freerouting | Autorouter (Java 21) | `tools/kicad-claude-mcp/third_party/freerouting.jar` |
| kicad-cli | Command-line DRC/ERC/export | `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` |

---

*PSI Rocketry · PCB Design Workflow · 2026-08-24*
