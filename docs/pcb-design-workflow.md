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

## Phase 0 — Environment & Tooling Health Check (Run First, Every Fresh Session)

Before touching any board, verify the toolchain actually works. On 2026-08-25 a session lost significant time rediscovering five environment bugs from scratch that a 30-second check would have caught. Run this checklist first:

1. **MCP servers have dependencies installed.** `tools/kicad-claude-mcp/.venv/` and `tools/kicad-jlcpcb/.venv/` must exist. If not: `cd <tool-dir> && uv sync`.
2. **MCP servers are registered where this CLI actually reads them.** `claude mcp list` must show `kicad` and `kicad-jlcpcb`. **`~/.claude/settings.json`'s `mcpServers` key is not read by this installation** — that was a dead end that cost real time. Register with `claude mcp add -s local kicad <venv-python> -- <absolute-path-to-server.py>` (absolute paths only — the server's cwd is not guaranteed to be its own directory).
3. **Freerouting + a JVM it can run on.** Call `mcp__kicad__routing_status` — it reports every JAR in `tools/kicad-claude-mcp/third_party/`, which one was selected, and on which JVM. Expect `freerouting-2.3.0.jar` on Java 25 (`/usr/libexec/java_home -v 25`, installed at `~/Library/Java/JavaVirtualMachines/jdk-25.x`). **Freerouting 2.2 and newer are compiled for Java 25** and will not start on Java 21 (`UnsupportedClassVersionError: class file version 69.0`). The adapter falls back to the older `freerouting.jar` (2.1.0, Java 21) rather than failing, so if `routing_status` reports `optimizer_is_broken: true` you are silently on the old router — fix the JVM, don't work around it.
4. **`mcp__kicad__ping` returns `"pong"`.** If the server errors on `set_project`/`get_project_state` with `AttributeError: 'Symbol' object has no attribute '_base_coords'` or `'NoneType' object has no attribute 'value'`, the `kicad-skip` 0.2.5 compat patch (`tools/kicad-claude-mcp/src/kicad_claude/_skip_compat.py`) isn't loading — check it's imported in `server.py` before the tool-module imports. This patch is required for **every** board in this workspace (real fetched footprints + mounting holes both trigger it) — it is not optional or board-specific. Do not re-diagnose this from scratch; the patch and its docstring already explain the two upstream bugs it works around.
5. **`docs/validate_pcb.py` actually detects routed traces.** This was silently broken (matched `"(segment "` with a literal trailing space; KiCad's real pretty-printer emits `(segment\n\t...)`, no space) and reported FAIL on fully-routed boards. Fixed 2026-08-25 with a regex (`\(segment\s`). If it's reporting FAIL on a board you just routed, check this didn't regress before assuming the board is actually broken.

None of the above should need re-fixing — they're already fixed in this repo. This section exists so a future session (or a fresh clone) checks state instead of re-deriving it. If any check fails, something changed (a `uv sync` wiped a patch, a dependency updated); fix the specific thing, don't re-architect.

### Known MCP-tool gotchas (save yourself the debugging time)

- **`autoroute_pcb` passes count vs. timeout**: for small boards (≤25 footprints) actual routing finishes in under a second — almost all wall-clock time is JVM startup + KiCad save, so `passes=20-50` is enough and finishes in seconds. For dense boards (tms-v3: 69 footprints, 48 nets), Freerouting's marginal improvement per pass drops fast after ~30-80 passes; a `passes=200` call is likely to hit the timeout without meaningfully improving the route (confirmed: passes=80 vs passes=30 improved unrouted count by only 2/37 on tms-v3). Start at `passes=50, timeout_seconds=900`. On 2.2+ this costs nothing: the router detects its own stagnation ("score has not improved by more than 0.5 points in the last 10 passes") and stops, so a high pass count is an upper bound rather than a duration.
- **Freerouting 2.1.0's multi-threaded route optimizer is broken and cannot be disabled** (its own log: "known to generate clearance violations"). Measured against tms-v3 on 2026-08-25: `-mt 1` does *not* reach the optimizer (the log still says "Starting optimization on 7 threads"), and neither does `FREEROUTING__ROUTER__MAX_THREADS=1`. Earlier notes here and in `route_and_fill.py` claimed `-mt 1` forced single-threaded optimization; that was wrong. **The only real fix is the 2.3.0 JAR on Java 25**, where `--feature_flags.multi_threading=false` works and the warning disappears. `autoroute_pcb` sets this automatically. If `routing_status` shows a 2.1.x JAR selected, expect the warning and re-run DRC.
- **These generated `.kicad_pcb` files have no numeric net-ID table** — pads carry `(net "NAME")` with no `(net N "NAME")` dictionary and no per-pad net number. `run_drc`/`kicad-cli` tolerate this fine (KiCad's loader derives connectivity from names), but **`add_track`'s `net` parameter is a net *number*, and passing an arbitrary one (e.g. `0`) creates a track that LOOKS placed but isn't actually part of that net** — DRC will flag it as `track_dangling` and it does nothing to fix connectivity. Don't use `add_track` to manually stitch a specific net on these boards; fix zone/thermal-relief connectivity in KiCad's GUI instead (see next point).
- **Unconnected GND after autorouting is a *bonding* failure, not a routing failure.** Seen on
  imu-icm42688, baro-bmp390, gnss-neom9n and tms-v3. The autorouter treats a pour as an obstacle, not as a
  net it owns: it carves traces through the copper and leaves islands behind, and any island no via reaches
  is floating copper that DRC reports as unconnected. On tms-v3 this measured as 13 filled islands on
  `GND_TOP` and 6 on `GND_BOTTOM`, producing 11 unconnected items with **zero unrouted signal nets**.
  Diagnose before reaching for a fix: all-GND unconnected items with `Zone ↔ Zone` or `Pad ↔ Zone` pairs are
  bonding work; only `Pad ↔ Pad` on a signal net is the router's fault. `autoroute_pcb` now bonds
  automatically (`bond_ground=True`) and the standalone `bond_ground` tool does it on demand. Thermal relief
  was investigated as the cause and ruled out — setting `ZONE_CONNECTION_FULL` + island removal on tms-v3
  changed the count by zero. Lowering zone min-thickness from 0.25mm to 0.13mm recovers roughly one item and
  buys thin copper slivers; not worth it by default.
- **What bonding cannot fix, it reports.** Pads in congested areas with no clearance-legal via site within
  `max_escape_mm` (default 2.0) come back in `unescapable` with coordinates. Route those by hand in KiCad —
  a longer auto-stub is worse than an honest report.

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

#### How to actually fetch a reference source (mandatory — do not use WebFetch alone)

Three reference fetches failed in one evaluation round, each silently and for a different reason: a dead official link reported as "just unavailable," a GitHub-hosted Eagle `.sch` truncated by WebFetch's markdown/summary layer before the pin-level detail survived, and a vector-graphic PDF that WebFetch's text extraction returned empty for. **WebFetch summarizes — it is fine for "what does this page say" and actively wrong for "what exact value is on this exact pin."** Use `docs/fetch_reference_doc.py` instead for anything you need exact ground truth from:

| Source type | Tool | Why |
|---|---|---|
| Any link you're about to cite as a reference | `verify_url(url)` | HEAD-checks it first — report "verified dead, HTTP 404" instead of "couldn't fetch, unknown reason." A dead link should never be silently treated as "checked, nothing found." |
| GitHub-hosted Eagle `.sch`/`.brd` (Adafruit, SparkFun, etc.) | `fetch_raw()` + `parse_eagle_schematic()` | Downloads the exact XML via `curl` (bypasses GitHub's blob-view HTML and WebFetch's summarizer entirely) and parses real part values **and pin-level net connections** with `xml.etree.ElementTree` — not a description of them. Validated this round: recovered Adafruit's exact BMP390 decoupling (C6 = 0.1µF, tied to both VDD and VDDIO) and caught that their I2C pull-ups are a 10kΩ 4-pack, not the 4.7kΩ a prior pass assumed. |
| Manufacturer PDF where text extraction fails (wiring diagrams, pinout tables, mechanical drawings) | `render_pdf_pages()` | Renders specific pages to PNG via PyMuPDF, then read the PNG with the Read tool — same method that recovered the HF46F relay's real coil/COM/NO pinout this session after WebFetch's PDF text extraction came back garbled. No system `poppler`/`pdftoppm` dependency (that's a separate, heavier install) — PyMuPDF is a pure wheel: `pip3 install pymupdf`. |
| A `github.com/.../blob/...` URL with spaces or a large file | `github_raw_url(owner_repo, path)` | Builds the correctly-encoded `raw.githubusercontent.com` URL — the blob-view HTML page renders through GitHub's UI chrome and WebFetch frequently truncates large files fetched that way. |

Run it directly, or import the functions: `python3 docs/fetch_reference_doc.py eagle <path.sch> [PartName]` prints every net a specific component touches, with real pin numbers.

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

### Step 2.3b — Module Socket Pinout Gate (HARD GATE — Do Not Skip)

Step 2.3 covers ICs. It does **not** cover plug-in modules (Teensy, XBee,
ESP32 dev boards, Feather, Pi HAT headers). Those fail differently and worse:
a module socket's pin order is fixed by the vendor's board, and a netlist that
assigns nets sequentially down a 1×N header will pass ERC, pass DRC, route
cleanly, fabricate, and then put a power rail into a 3.3V GPIO the first time
the module is plugged in. **No automated check in this workspace can catch
this.** `validate_pcb.py` flags every ≥8-pin connector for sign-off; clearing
that flag is a human action.

For every module socket, before writing a single `pin_label()`:

1. Fetch the **vendor pinout card** (not a summary, not from memory) —
   `python3 docs/fetch_reference_doc.py <url>` renders PDF pages for reading.
2. Write out the physical pin table, header position by header position,
   in a file next to the schematic script. Positions, not function names.
3. Mark pin 1 and the header's orientation relative to the board outline.
4. Check the **connector pitch** against the module. It is not always 2.54mm
   — an XBee 2×10 socket is 2.0mm pitch, and a 2.54mm header footprint will
   silently accept the netlist and physically not fit.
5. Confirm no power rail (`+5V`, `VBAT`, `Vin`) lands on a position that is a
   signal pin on the module, and that logic levels match (a Teensy 4.x is
   **not** 5V tolerant).

#### Gate criteria
- [ ] Vendor pinout card fetched and stored in `datasheets/`
- [ ] Physical position→function table written down and diffed against the
      `pin_label()` / `*_nets` list actually used by the generator
- [ ] Connector pitch verified against the module
- [ ] Pin-1 orientation verified against the placement rotation
- [ ] Every power rail's landing position confirmed safe

Any header net list built by "the order I wanted the signals in" rather than
copied from the vendor table is a **blocker**.

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
- [ ] Verify the `jlcpcb` library is registered in `sym-lib-table`/`fp-lib-table` — not guaranteed by the fetch step (`pcb-design-rules.md` §15.7)
- [ ] Extract the real pin map from each fetched `.kicad_sym` before wiring — never reuse a placeholder-era pin-map assumption (§15.7)
- [ ] For any multi-function pin without a descriptive name (relay COM/NO, TVS common, etc.), confirm against the manufacturer datasheet before connecting — especially for safety-critical circuits (§15.7)
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
- [ ] Run ERC — **zero errors**. Warnings from `endpoint_off_grid`/`pin_to_pin` on real fetched parts are an expected easyeda2kicad conversion artifact (§15.7) and don't need chasing; any `power_pin_not_driven` **error** gets a `power:PWR_FLAG` symbol on that net instead of investigation
- [ ] **Gate: schematic is visually readable — no overlapping text.** ERC passing is necessary but not sufficient; ERC only checks connectivity, never text layout, so a schematic can be 100% electrically correct and completely illegible (confirmed on imu-icm42688: net labels landed exactly on top of pin names and power-symbol value text — 0 ERC errors throughout). If schematic generation used a script, it must use `docs/schematic_layout_helpers.py`'s `LabelPlacer` (see below) — don't hand-place labels at bare pin coordinates. Verify by rendering, not by reading the generator code: `kicad-cli sch export svg <sch> -o /tmp/check && qlmanage -t -s 1800 -o /tmp/check /tmp/check/<board>.svg`, then look at the PNG. Read the render yourself before calling the schematic done.
- [ ] Compare schematic against reference designs (Phase 2.3 table — every row filled)
- [ ] Run pre-layout completeness checks (`pcb-design-rules.md` §15):
  - [ ] Every passive value matches datasheet app circuit (§15.1)
  - [ ] Every IC pin accounted for — address, config, debug pins (§15.2)
  - [ ] Voltage levels verified at every inter-IC connection (§15.3)
  - [ ] Level shifters added where needed (§15.3)
  - [ ] Real-part symbol verification complete — library registered, pin maps extracted from fetched `.kicad_sym`, multi-function pins datasheet-confirmed (§15.7)
- [ ] Peer review — have someone else check the schematic

### Tools

- **kicad-claude-mcp** — automated schematic generation (105 tools)
- **kicad-jlcpcb** — `sch_generate` for wired schematic from component list

### Script-Based Generation (When Writing a Python Generator)

If generating the schematic via a script rather than the MCP tools directly, the tooling almost always exposes a pin-position lookup (e.g. `get_pin_position(tree, ref, pin_number)` in kicad-claude-mcp's `sch_editor` adapter) — **use it for every single net connection.** A label dropped at a hand-computed `(x, y)` looks wired in a screenshot but ERC will show it dangling; this was the single largest defect class found integrating real parts into TMS V3 (184 of 368 ERC violations). Snap every component's placed center to the 1.27mm schematic grid too, since real fetched pins are grid-aligned and a misaligned center pushes every pin off-grid. Run ERC after each schematic section during generation, not just at the end — it catches naming bugs (two different nets accidentally sharing a label) while the section is still fresh.

**Text layout is a separate concern from connectivity — handle both, don't assume ERC-clean means readable.** Placing a label at the exact pin coordinate (correct, per above) puts it exactly where KiCad also auto-draws that pin's own name, and a symbol's Reference/Value property text both default to the *symbol's own placement origin* with no offset from each other — so a script that only calls the raw `add_label`/`add_symbol` primitives produces a schematic that's ERC-clean and visually unreadable (confirmed on imu-icm42688: 0 ERC errors, but doubled/merged text everywhere). Use `docs/schematic_layout_helpers.py` instead of the raw primitives:

```python
import sys
sys.path.insert(0, '/Users/leetaeho/CODE/PCB/docs')
from schematic_layout_helpers import LabelPlacer, SymbolPlacer

symbols = SymbolPlacer(ed, tree)                    # placement geometry
labels  = LabelPlacer(ed, tree, symbols=symbols)    # wiring + terminators
labels.place_symbol = place                         # bind after place() exists


def place(lib, sym, ref, value, x, y, rot=0, fp='', desc=''):
    ed.add_symbol(...)
    # register() may RELOCATE the symbol to clear an overlap and returns
    # the final centre — record THAT, or pin-exit directions are computed
    # against a stale origin.
    symbol_origin[ref] = symbols.register(ref) or (snap(x), snap(y))


def pin_label(ref, pin, net):
    return labels.auto(ref, pin, net, *symbol_origin[ref])
```

### What the two helpers do (and why each exists)

Every defect below is **100% ERC-clean**. ERC checks connectivity and
nothing else, so none of these are visible until a human renders the
sheet — which is why they must be prevented at generation time rather
than found by inspection.

`LabelPlacer.auto()` — picks the terminator per net:
- **Standard global rails get a graphical power symbol**, not text. Rail
  labels were ~45% of all label text (tms-v3: 78 of 172, including 38
  separate "GND" strings). After conversion: 0 rail text labels on all
  four boards. Matching is **exact-name only** — a power symbol's net
  name comes from its *pin name*, so drawing `VBAT` with the `+BATT`
  symbol does not decorate the net, it **renames** it and silently
  desyncs an already-generated `.kicad_pcb`.
- Everything else gets a text label, always drawn **horizontally** even
  on a vertical stub (KiCad otherwise rotates the text down through the
  component body).
- Stub wires are sized to clear the pin's own auto-drawn name, staggered
  across a pin column so terminators don't stack, re-routed out another
  side when a flank is congested, and checked for cross-net crossings —
  a crossing silently bridges two nets, and once merged an entire board
  into a single net with ERC still reporting zero errors.

`SymbolPlacer.register()` — owns placement geometry:
- **Refuses or relocates overlapping symbols.** This is the schematic
  twin of the PCB courtyard check and exists for the same reason: a
  hand-picked coordinate does not survive the symbol changing size. On
  imu-icm42688, C1 and C2 were being drawn *inside* U1's body.
- **Pulls off-sheet placements back inside the frame** (parts were
  landing under the title block).
- **Positions Reference and Value text** on whichever side the pins
  don't use. Programmatically injected symbols stamp both properties at
  the placement origin with zero offset — i.e. printed on top of each
  other, in the middle of the symbol's graphics.
- **Snaps pins to the grid in KiCad's coordinate space.** `y_kicad =
  page_h - y_mcp`, and `page_h` is never a grid multiple (A4 is 210mm;
  210/1.27 = 165.35), so a Y that is grid-aligned in generator
  coordinates lands off-grid in the file. This caused 521
  `endpoint_off_grid` warnings across the four boards; snapping in the
  wrong space is a guaranteed no-op, which is how it went unnoticed.
  All 521 are now gone.

### Scope: what this does NOT do

The output is a **clean, correct, readable pre-schematic for human
polish** — not a finished hand-drawn sheet. Specifically absent:
functional-block rectangles (`sch_editor` has no graphics primitive),
hierarchical sheets with a block-diagram overview, and wire-crossing
minimisation (a graph-planarisation problem; automated orthogonal
routing will always produce a messier result than a human). Assume a
polish pass in the KiCad schematic editor — dragging is cheap once the
netlist is right and parts are grouped.

**Page size is a design decision.** ~25 components is about the A4
limit. tms-v3 (69 components) needed A3 and is still dense; beyond that,
split into hierarchical sheets rather than shrinking spacing.

All four boards (`gen_imu_sch.py`, `gen_baro_sch.py`, `gen_gnss_sch.py`,
`gen_tms_v3_sch.py`) are converted and contain **zero** manual text-nudge
calls. If you find yourself adding one, fix the helper instead.
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

**Before choosing a single (x, y) coordinate, fetch every real footprint you'll place and check its courtyard size.** Coordinates chosen by eye before a real footprint exists don't survive contact with one — a relay, connector, or header can be several times larger than a placeholder-era guess assumed, and the collision doesn't surface until DRC runs on the finished board. This was the single largest recurring defect class across TMS V3, the IMU board, and the barometer board.

Use `docs/pcb_layout_helpers.py`, in script-based generation:
```python
from pcb_layout_helpers import PlacementTracker
tracker = PlacementTracker()
# call tracker.place(ref, fp_def_node, x, y, rot) for every component as you
# place it — it raises CourtyardCollisionError immediately, with the two
# overlapping refs and the exact overlap in mm, instead of surfacing as one
# of 40 DRC violations after the whole board is built and it's your problem
# to untangle which placement decision caused which error.
```
Run `python3 docs/pcb_layout_helpers.py <path-to.pretty-dir>` on a library directory any time to print every footprint's real courtyard size before you start deciding coordinates — turns "check real footprint courtyard sizes" from an easy-to-skip checklist line into a five-second command.

Follow the placement order in **[`docs/pcb-design-rules.md`](pcb-design-rules.md)** §1:

1. **Board outline → mounting holes → connectors** — mechanically fixed
2. **Fiducials (optional)** — 3× fiducial marks (1mm pad, 2mm mask opening), recommended for fine-pitch (<0.5mm) JLCPCB PCBA parts; JLCPCB auto-adds its own if omitted, so this is not required for order acceptance
3. **Power supply chain** — regulator + caps along power flow
4. **Precision analog ICs** — near their input connectors, away from heat sources (≥15 mm)
5. **Digital ICs** — separate zone from analog
6. **Decoupling caps ≤2 mm** from IC power pins (no via between cap and pin)
7. **Crystal within 5 mm of IC** — no ground pour under crystal body
8. **Relay/power switching isolated** from analog section, separate ground return

#### Placement Checklist
- [ ] Every real footprint's courtyard size checked (`pcb_layout_helpers.py`) **before** coordinates were chosen, not after
- [ ] `PlacementTracker` used during generation — zero courtyard collisions at generation time, not discovered later via DRC
- [ ] Board outline matches mechanical spec (dimensions, mounting holes)
- [ ] Board area justified — component density 40–60% (§15.4)
- [ ] Fiducials placed if fine-pitch PCBA (optional otherwise — JLCPCB auto-adds its own)
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

**Option 2 — Freerouting autorouter (scripted, verified)**
```bash
docs/route_and_fill.py projects/<board>/<board>.kicad_pcb 50
```
Runs the same pipeline as the MCP tool — DSN export → route → SES import → zone fill → ground bonding → DRC —
and **exits non-zero unless DRC reports zero unconnected items**. Writes `<board>.route-report.json`.
After autorouting: visually inspect every trace. Autorouters don't understand analog vs. digital separation —
manually fix violations.

**Option 3 — EasyEDA handoff (kicad-jlcpcb)**
```
Use easyeda_handoff to export for EasyEDA cloud autorouting.
Route in EasyEDA, then export Gerbers from there.
```

**Option 4 — kicad-claude-mcp autoroute tool**
```
Use autoroute_pcb (wraps Freerouting, bonds the ground pour, then verifies with DRC).
```
Returns `passed` (zero unconnected items) plus the leftovers split into `remaining_signal_items` (reroute
these) and `remaining_pour_items` (bond these), each with coordinates. A `.ses` file is not evidence of a
routed board and this tool no longer treats it as such.

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

This checks: placeholder footprints, fiducials, board dimensions, silkscreen,
edge clearance, **pads vs. the real board outline** (pad geometry, not the
footprint anchor), **courtyard collisions**, **module sockets needing pinout
sign-off**, and the **DRC report**. Fix any FAIL items before proceeding.

Note two deliberate design choices in the validator:
- A **missing or stale DRC report is a FAIL**, not a skip. Absence of evidence
  is never a pass here — TMS V3 reported "ALL PASS" while a 54-violation,
  97-unconnected DRC report sat unread in the same directory.
- The trace-routing check reports **INFO, not PASS**. Counting segments proves
  copper exists, never that routing is complete. Completeness comes only from
  the DRC report's `unconnected_items`.

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

---

## The Gate Rule

**Every step in this document must be checkable and non-missable.**

A step described only in prose is not a gate — it is a hope. This is the
governing rule of the workflow, and it exists because every failure this
workspace has shipped was a documented step that nothing checked:

| Documented instruction | Where it says so | What actually happened |
|---|---|---|
| "Download the datasheet for every IC, save to `datasheets/`" | Step 2.1 | Folder empty. Eleven parts. Nothing noticed. |
| "Always consult `pcb-design-rules.md`" | CLAUDE.md | Nothing checked it. The board broke **23** of its numbered rules while passing DRC. |
| "Every net must be routed" | Phase 4B | The validator counted trace *segments* — satisfied by any partly-routed board. |
| "Use `PlacementTracker` before choosing coordinates" | Phase 4A | The generator never imported it. `docs/` was not even on its `sys.path`. |
| "Compare against a reference design" | Step 2.3 | Applied to LCSC parts only; plug-in modules fell off the path entirely. |

So: **one command runs every gate.**

```bash
python3 docs/run_gates.py projects/<board>/<board>.kicad_pcb
```

It exits non-zero unless all of them pass, and it is the last step of
`projects/<board>/build.sh`. Gates it cannot automate are marked `[HUMAN]`
and are satisfied by a signed line in the board's `SIGNOFF.md`. That records
the step was **performed**, not that it was performed *correctly* — a real
limit, stated rather than hidden.

### Failure Mode Zero — where a lesson gets written decides whether it survives

On 2026-08-25 this workspace built a full set of gates to stop documented
steps from being skipped — and then wrote them down in a place nothing loads.
An audit the same day found `run_gates.py`, `check_design_rules.py`,
`check_datasheets.py`, `SIGNOFF.md` and `DEVIATIONS.md` referenced **nowhere**
in `CLAUDE.md`, `.claude/rules/`, `QUICKSTART.md`, or either slash command.
Three of the four boards had none of the artifacts. The fix had reproduced the
bug it was written to fix.

Same audit, same day: the `PostToolUse` hook matched only `Write|Edit` and read
`tool_input.file_path`. Every board in this repo is written by a Python
generator invoked through **Bash**, which has no `file_path`. So the hook
CLAUDE.md advertised as running "automatically after every edit to a
`.kicad_pcb`" had **never fired on a single board**. Both are now fixed.

The generalisation, and the rule that follows from it:

**Documentation has tiers, and the tier decides whether a lesson is enforced.**

| Tier | Where | When it reaches Claude | Use for |
|---|---|---|---|
| **0** | a gate in `run_gates.py` | always — exits non-zero | anything mechanically checkable |
| **1** | `CLAUDE.md` | every session, always loaded | the few rules that govern all work |
| **2** | `.claude/rules/*.md` | auto-loaded on matching file | rules specific to a file type |
| **3** | `docs/*.md` | only if someone chooses to read it | reference, derivations, rationale |
| **4** | a hook | only on tool patterns it actually matches | fast feedback — verify the matcher |

> **A lesson recorded only at Tier 3 is not enforced. It is a hope.**

And one tier above all of them: **the enforcement needs its own test.**
`docs/selftest_enforcement.py` verifies hook matchers, fires each hook with a
synthetic event, and confirms every entry point ends at the gate. It is
fault-injection tested — re-introducing the historical `Write|Edit` matcher
bug makes it fail with that exact message. It runs first in the pipeline's
`env` stage, so a board cannot be built on undone wiring.

So when a new lesson is learned, it is not "documented" until:

1. **Tier 0 if it can be checked at all.** Add a gate. A five-line check that
   runs beats a paragraph that persuades.
2. **Tier 2 (or Tier 1 if it governs everything) in one or two sentences**, so
   it is in context at the moment the mistake would be made — not in a
   698-line document that must be sought out.
3. **Tier 3 for the reasoning**, linked from above. This is the right home for
   *why*; it is the wrong home for *must*.
4. **Verify the enforcement actually fires.** Run the gate on a board that
   should fail it. Feed the hook a synthetic payload. The hook above passed
   review for months because nobody ever tested it with a `Bash` event.

The recurring shape of every failure in the table below is the same: **the
check lived at a lower tier than the mistake.** Fix the tier, not the prose.

### Lessons → the check that now catches them

Every row below is a defect that actually shipped or was hit during
development. None of them were caught by DRC.

| # | Lesson | Now enforced by |
|---|---|---|
| 1 | A `1xN` header's footprint anchor is **pin 1**, not its centre. An anchor comfortably mid-board can have pads 16mm off the edge. | `validate_pcb.py` *Pads inside board outline*; `PlacementTracker` raises `OffBoardError` at generation time |
| 2 | EasyEDA-converted footprints ship courtyards **smaller than their own land pattern**, so courtyard-only collision checks place caps inside an IC's pins. | `get_extents_from_text()` unions courtyard **and** pads |
| 3 | Three coordinate frames (design / MCP / KiCad-Y-down) caused the **same sign bug three times**: overlaps read as clear, keepouts queried in the wrong half of the board, caps placed on the mirror image of their pin. | `design_to_mcp()` / `design_to_kicad()` / `kicad_to_design()` — convert only through these; derivation written down and verified against `pcbnew` |
| 4 | Part verification was bound to the **LCSC fetch path**. Anything not on LCSC (Teensy, XBee) got a generic header and an invented pin map. | Step 2.3b + `check_datasheets.py` + `datasheets/INDEX.md` provenance |
| 5 | DRC answers *"can JLCPCB build this?"*, never *"is this a good layout?"* | `check_design_rules.py` — `pcb-design-rules.md` made executable |
| 6 | Placing parts on a tidy arithmetic grid has no relationship to which **pin** each serves. Rule 2.2 measures from the power pin. | `place_near_pin()` — placement relative to real pad positions |
| 7 | Placing the **bulk** cap first lets it take the near slot and pushes the 100nF out — the inverse of the cap-hierarchy rule. | All 100nF placed before any bulk; comment states why |
| 8 | A stitching via placed **before** routing is an obstacle. An 8mm grid took unrouted nets from 1 to 8. | Stitching moved after routing (`stitch_vias.py`, `bond_ground`) |
| 9 | A uniform via grid was cargo-cult: the fastest signal here is 7.68MHz, so λ/20 asks for stitching every ~75mm. | Perimeter ring + targeted analog-return vias, with the arithmetic in the comment |
| 10 | On a dense 2-layer board a **top ground pour fragments into islands**; KiCad deletes them, stranding any GND pad that was on one. An inner pin of a 0.65mm-pitch SSOP has no clear path out to a via. | Top pour omitted; GND routes as an ordinary net to the bottom plane (rule 3.2's primary instruction) |
| 11 | 69 reference designators is noise — but 0.7mm text is **below JLCPCB's 0.8mm minimum**. "Smaller looks tidier" is not a licence to go under a fab limit. | Passives/mechanical → `F.Fab`; survivors set to 0.8mm; `text_height` DRC |
| 12 | `pe.add_footprint(reference=...)` **silently fails** for footprints carrying `fp_text reference`. The XBee socket shipped as `J**` — no BOM line, no pick-and-place row. | Post-placement assertion in `_place()`; repairs and reports |
| 13 | Deriving the netlist by **regex over the schematic script's source text** meant any change to how nets were assigned produced a stale netlist instead of an error. | `netmap.json` — explicit handoff, missing file is a hard stop |
| 14 | A hand-written keepout list is a **second copy of the placement coordinates** and goes stale the moment a part moves. | `tracker.hits()` — anything generated after placement asks the tracker |
| 15 | `(connect_pads ...)` is a child of `(zone ...)`, **not** of `(zone (fill ...))`. Editing the wrong node fails silently; the only symptom is `starved_thermal` returning. | Comment at the edit site; `starved_thermal` in the DRC gate |
| 16 | ~~Freerouting is not deterministic~~ **— MEASURED FALSE for 2.3.0 on 2026-08-25.** Three runs from an identical unrouted board gave identical passes (6), identical score (999.98) and identical unconnected (6). The variance originally blamed on the router came from *different placements* being compared. A wrong lesson is worse than none: this one justified best-of-N churn that could not have helped. | `pipeline.py --verify-repeatable`; re-measure before blaming the router. `route_best_of.py` is retained only for 2.1.0, whose optimizer is genuinely multi-threaded and unfixable |
| 17 | A pad→via stub drawn as a straight line **crosses whatever is already in the gap** — 3 clearance violations, 2 shorts, 1 crossing pair. | Path is sampled and rejected before the stub is drawn |
| 18 | A rule you cannot meet is an engineering decision. Decisions get written down with a reason; they do not get quietly dropped from the report. | `DEVIATIONS.md` — unlisted violations are hard failures |
| 19 | Several Claude sessions can edit this repo at once and clobber each other. | Check `ListAgents` and file mtimes before editing shared files |
| 20 | **Stitching presupposes two pours.** With a pour on only one layer, every "stitching" via connects to the plane at one end and nothing at the other — 90 vias produced 112 `via_dangling` violations. This applies to `bond_ground`'s island stitches too. | `stitch_vias.py` counts GND pour layers and skips the grid pass below two, saying why |
| 21 | Freerouting picks its own via padstack from the DSN, not the netclass — it emitted 0.10mm annular rings against a 0.15mm board rule. Autorouter output is not automatically rule-compliant. | `annular_width` in the DRC gate; check the DSN's padstack when it fires |
| 22 | Routing quality is a **placement** result, not a router setting. Moving the Teensy 6mm took unconnected from 8 to 5; extra router passes did nothing, because 2.3.0 stops on stagnation after 1 pass. | Sweep placement before blaming the router; `route_best_of.py` for the residual variance |
| 23 | The gates built to stop skipped steps were referenced **nowhere** that loads automatically — not `CLAUDE.md`, not `.claude/rules/`, not the slash commands. Three of four boards had none of the artifacts. The fix reproduced the bug. | Gate Rule section in `CLAUDE.md` (Tier 1) + `.claude/rules/pcb-layout.md` (Tier 2); `run_gates.py --init` scaffolds any board |
| 24 | The `PostToolUse` hook matched only `Write\|Edit` and read `tool_input.file_path`. Boards are written by generators through **Bash**, which has no `file_path` — so the "automatic" validator had never fired on any board. | Hook matches `Bash` too and validates any `.kicad_pcb` newer than 120s; tested with a synthetic Bash payload |
| 25 | A gate whose input file nobody creates fails for a boring reason, and boring failures get ignored. `SIGNOFF.md` was simply absent on 3 of 4 boards. | `run_gates.py --init` creates `SIGNOFF.md` / `DEVIATIONS.md` / `datasheets/INDEX.md`, never overwriting |
| 26 | The generator was assumed deterministic and never checked. It is — but only *modulo UUIDs*: two identical runs differ on 83 regenerated `(uuid ...)` lines. A raw file hash therefore marks every board permanently "stale", which trains you to ignore the field. | `pipeline.py` hashes a **canonical** form with UUIDs masked; `--verify-repeatable` rebuilds twice and proves it |
| 27 | The first pipeline stopped the run on a failing stage *before* the gates, so the run that went worst produced the report with the least evidence — exactly backwards. | Gates **always** run and always land in `STATUS.md`, even after a stage fails; building further is still forbidden |
| 28 | A gate summary line can read healthy next to the word FAIL ("11 parts require a datasheet; 12 PDFs on file") while hiding which part is missing. A table you cannot act on teaches you to distrust the table. | Gate details name the offending refs (`— missing: Y1 (7.68MHz)`) |
| 29 | Fixing a hook *script* to handle `Bash` does nothing while the settings **matcher** still reads `Write\|Edit`. Enforcement has two halves and both must be checked. | Matcher is `Write\|Edit\|Bash`; verified by feeding the hook a synthetic Bash event |
| 30 | The whole RESEARCH half of this workflow (Phase 1, Steps 2.2/2.3/2.4) had **no gate at all**. Four boards, **zero** archived reference designs — on a step this document and `.claude/rules/pcb-schematic.md` both label a "HARD GATE". The back half got gates; the front half stayed prose. | `check_research.py`, wired into `run_gates.GATES` and a `research` pipeline stage |
| 31 | `fetch_reference_doc.py` was written to fetch reference designs correctly and was invoked by **nothing** — it appeared only in prose. A tool that exists and is never called is prose with a shebang. | `collect_references.py` archives; self-test asserts the research gate is *registered*, not merely defined |
| 32 | A reference "read once" leaves no evidence and cannot be re-checked. Worse, a vendor login wall saved as `.pdf` still satisfies a gate that only counts files. | `collect_references.py add` verifies the URL, sniffs the payload, **rejects HTML**, and records provenance; `check_research.py` re-verifies every archived file |
| 33 | The waiver escape hatch matched part *values* as bare substrings, so `bmp390` in the DEVIATIONS.md **title** silently waived that board's main IC. An escape hatch nobody opened was open. | Waivers must name the reference designator, word-boundary matched |
| 34 | A basis/spec check that a **blank scaffold satisfies** is worse than no check — it certifies the thing it was written to catch. The first version passed on the template's own `<U1>` placeholder. | Placeholder regex widened; a basis row counts only with a source *and* a `Match`/`Deviate` verdict |
| 35 | First real use of the reference archive found a **missing bulk capacitor** on `baro-bmp390` (Adafruit's BMP390 uses 10µF + 0.1µF; ours had 2×100nF). ERC, DRC and `check_design_rules.py` are all structurally blind to it. | `DESIGN_BASIS.md` comparison rows, sourced from archived Eagle files |
| 36 | "The datasheet is the bible" was enforced by **counting filenames ending in `.pdf`**. A 60-byte HTML login wall renamed `BMP390-datasheet.pdf` passed `check_datasheets.py` *and* archive integrity, and the gate printed "every part accounted for". Every downstream "verified against the datasheet" then rested on a file nobody could open. | `check_datasheets.py` sniffs the payload; self-test fault-injects that exact file |
| 37 | Archive integrity walked **INDEX.md rows only**, so a document on disk with no row was invisible: baro-bmp390's datasheet had no recorded origin at all. "Which revision, from where?" — the first question in any datasheet dispute — had no answer. | Integrity now enumerates *files on disk* in `datasheets/` and `reference-designs/` and demands a source URL for each |
| 38 | Two documents on one board reached **opposite verdicts on the same question** (`EVALUATION.md` said the 100nF-only decoupling "matches Bosch exactly"; `DESIGN_BASIS.md` called the missing bulk cap a real gap) and nothing noticed. Reading the datasheet settled it — and revealed a spec neither had used: **`VDD ripple max. 50 mVpp`**. | Datasheet is Tier 0 in `DESIGN_BASIS.md`, above any reference design; disagreements get a row |
| 39 | Two of `DESIGN_BASIS.md`'s own verdicts were **wrong in the safe-looking direction**: the 4.7k I2C pull-ups were logged as a deviation from Adafruit's 10K when the *datasheet names 4.7 kΩ*. We were matching the manufacturer and calling it a departure, from a Tier-2 source. | Ordering rule: datasheet first, reference design second; a reference is evidence of *practice*, not of correctness |
| 40 | A VSS pad (`U1.3`) was left **electrically floating** on a finished, zero-DRC-error board: no track, no via, alone on a 1.24 mm² fragment of top pour. It survived because of how DRC *phrases* it — `Zone 'GND_TOP' ↔ Zone 'GND_TOP'`, which reads like a cosmetic fill complaint. The post-route bonding pass builds escape targets only from items naming a **pad**, so it found nothing to do and reported "0 pad escapes". | Only the **zero-unconnected** gate catches this class. Pre-route ground escapes for pads that provably cannot be escaped afterwards |
| 41 | `stitch_vias.py` hardcoded `clearance = 0.4mm` and was wrong **in both directions on one board**: too small against a fiducial's 1.1mm local pad clearance (clearance error + mask bridge), and too large against the board's 0.127mm netclass rule, which sealed off `U1.3`'s only escape and silently placed *nothing*. The second failure produces no error — just an ungrounded pad. | Clearance is read from the board's design settings, with per-pad `GetOwnClearance()` overrides |
| 42 | Crowding bought nothing and cost a ground connection: R1/R2 sat 2.8mm from U1 on a board at **31% density**, pinching the pour that had to reach `U1.3`. Rule 4 again — routing quality is a placement result. | Moved clear; the pour then reached the pad unaided, and three `+3V3` clearance errors disappeared with it |
| 43 | A code comment claimed the decoupling was **"per TDK app circuit"** when the app circuit specifies 0.1 µF + 2.2 µF on VDD and 10 nF on VDDIO, and the board had 100 nF + 100 nF. The 2.2 µF was **absent** and VDDIO's cap was **10× oversized**. A comment citing a source reads as evidence the check was done. | `DESIGN_BASIS.md` puts the claim and the source in the same row; datasheet is Tier 0 |
| 44 | Two ICM-42688-P pins were `no_connect` under a comment reading *"datasheet says leave unconnected"*. Table 9 distinguishes **"No Connect or Connect to GND"** (pins 2/3/10/11) from **"Connect to GND"** (pin 7, mandatory), and says pin 9 FSYNC must be grounded when unused — a floating CMOS **input** on a vibration sensor. | Read the pin table row by row; both now grounded with pre-route escapes |
| 45 | `read_index`'s "extension within the last 6 characters" filter silently rejected `ICM-42688.kicad_sch` — a 10-character extension — so a correctly archived reference read as *"not archived"* and the gate demanded a file already on disk. A too-clever filter is its own false negative. | Full filename regex instead of a character-count heuristic |
| 46 | `collect_references.py` appended `.pdf` before the bytes arrived, archiving a KiCad schematic as `ICM-42688.kicad_sch.pdf` — creating exactly the filename/content mismatch `check_datasheets.py` was just taught to reject. | The file is renamed to match its **sniffed** format after download |
| 47 | A ground-escape stub drawn as a straight diagonal between two individually-clear points came within **0.0403mm** of a neighbouring pad. Pads were 0.675 × 0.280mm on 0.5mm pitch; only a stub along the pad's own centre line fits. A straight line between two clear points is not itself clear. | Stub routed axially; geometry measured from the board, never estimated |
| 48 | **`SW1` was in gnss-neom9n's schematic and had no footprint on the board** — wired to RESET_N, never fabricated. It *was* documented, in the PCB generator's docstring and EVALUATION.md (Tier 3), never in `DEVIATIONS.md`. Meanwhile `validate_pcb.py` printed "0 schematic-parity issue(s)" every run because it read a kicad-cli field the pipeline never asked to be filled. A check that cannot fail is worse than none: it reads like a pass. | New `check_symbol_footprint_parity` in `validate_pcb.py` — schematic refs vs board refs, mechanical prefixes exempt |
| 49 | Switching on `--schematic-parity` wholesale was *not* the fix: kicad-cli returns 72 parity items for that board, all cosmetic (`Description` field text, `/NET` vs `NET`). A gate that cries 72 times about nothing is one people learn to skip. | Gate the one thing that is always a defect and never a matter of taste: **presence** |
| 50 | The reason SW1 was skipped was real and the conclusion was wrong: its footprint (`SW_Push_1P1T_NO_CK_PTS125Sx43SMTR`) has a **16.8 × 12.5 mm courtyard** on a 34 × 40 mm board. The answer was a different switch (Omron B3U-1000P, 4.8 × 3.3 mm), not no switch. | Measure the courtyard with `pcb_layout_helpers.py` *before* committing to a part |
| 51 | **A comment citing a source that says the opposite** — `# V_USB — USB interface unused, datasheet permits open`, where u-blox states in three places that V_USB *must* be tied to GND, and Figure 31 draws it grounded. Second instance this session (the first: "per TDK app circuit"). | Claim and source belong in the same `DESIGN_BASIS.md` row, where they can be compared |
| 52 | **For a MODULE, the Integration Manual outranks the data sheet.** All three NEO-M9N defects (floating V_USB, missing 1 µF at VCC, no RF ESD) are stated in UBX-19014286 and appear in *no* data sheet. Reading only "the datasheet" would have found none of them. | Archive the integration manual as the Tier-1 reference for any module |
| 53 | "Add an ESD diode" is not a specification. A general-purpose ESD part is 8–15 pF; at GPS L1 that is ~12 Ω to ground, so the protection would shunt the signal it guards. **0.5 pF** (RCLAMP0521PATCT) is ~200 Ω. | Part *class* is a design decision, not a BOM lookup |
| 54 | Fourth and fifth false-waiver bugs, same family: a reason paragraph reading *"U2's pads extend…"* waived U2, and then the **scaffolded template's own `Example:` line** (`U2.3 \| 2.2 \| …`) waived U2 on a board with no real deviations at all. A template that waives things by existing. | Waivers parse **field one of lines under `## Declared`** only — no prose, no lookarounds. Template example changed to `U99` |
| 55 | The fix for (54) first used `^#+\s*Declared\b` — which matched the files' own **title**, `# Declared Deviations — <board>`, cut at line 1, and changed nothing. Two heading-shaped strings, one a trap. | `^#{2,}\s*Declared\s*$` — exact section heading |
| 56 | `BT1`'s footprint `Battery_Panasonic_CR1220-VCN_...` was read as a *holder* land pattern; a long LCSC holder search found no match and nearly produced a documented "unsourceable" waiver. `-VCN` is Panasonic's **solder-tab cell** — the battery mounts directly. The search had been for the wrong class of part. | Read the suffix; footprint names encode the variant |
| 57 | **Four connectors on tms-v3's battery and IGNITER path declared a type they did not have**: `J1`/`J2` valued `XT60-*` and `J5`/`J6` described as "screw terminal", all footprinted `PinHeader_1x02_P2.54mm`. An XT60 is 60 A; a 2.54 mm header pin is ~3 A with no retention — on a board that fires pyrotechnic igniters. Every other check passed: ERC saw two pins, DRC saw two pads, the netlist was right, the courtyard fit. The claim lived in Value/Description and the reality in the footprint, and nothing compared them. | New `check_connector_class` in `validate_pcb.py` |
| 58 | Two vias out of 100 on tms-v3 came off the router with a Default-class **diameter** on a Power-class **drill** — annular 0.100 mm against the board's own 0.150 mm minimum. Two vias is exactly the size of defect that gets waived "for now" and ships; a thin annular ring is a plating-reliability problem. | `docs/fix_via_annular.py`, wired into the pipeline's route stage, widening the **pad** (never shrinking the drill, which would change current capacity silently) and re-running DRC afterwards |
| 59 | tms-v3's `Y1` crystal had **no datasheet and C8/C9 = 22 pF unverified** — recorded as a "known gap" and left. Every 7.68 MHz part in the board's footprint specifies **C_L = 20 pF**; 22 pF gives `(22·22)/44 + C_stray ≈ 15 pF`, so the crystal was under-loaded and would run fast. On the ADS1256 the crystal **is** the conversion clock, so that is a sample-rate error in every thrust and pressure reading — a board that works and quietly produces wrong numbers. | Datasheet archived, C8/C9 → 33 pF with the arithmetic recorded; a "known gap" is a defect with a note on it |
| 60 | tms-v3's `U3` (ADS1220) had **C10 and C11 both decoupling AVDD (pin 12) and nothing on DVDD (pin 13)**. TI SBAS501 §9.3.3: *"AVDD, AVSS … and DVDD **must** be decoupled with at least a 0.1 µF capacitor … as close to the power-supply pins as possible."* The gap had been logged as a rule-2.2 *distance* deviation — which explained away the symptom and stopped anyone looking for the cause. | A deviation must name a cause, not a measurement; C11 moved to +3V3 at pin 13 and the deviation was **withdrawn** |
| 61 | `docs/stitch_vias.py` carried a comment saying it "happens after routing, called from build.sh" — and `build.sh` had since been reduced to a shim that execs `pipeline.py`. So **nothing called it**, and tms-v3's ground design (which deliberately places no stitching vias itself) silently lost its bonding when the build path was unified. A comment naming the caller is not a caller. | `stitch_vias.py` and `fix_via_annular.py` now run in `pipeline.py`'s route stage |
| 62 | The first version of that wiring **re-ran the router** after stitching, regenerating the DSN from the just-stitched board — undoing and redoing the work it was verifying, and reporting on a different board than the one on disk. | Post-route passes now **re-verify** with a fresh DRC, never re-route |
| 63 | `check_design_basis` matched the whole Ref cell verbatim, so a row for `U3.13` did not count as covering `U3` and a row listing `J7, J8` covered neither. Four boards with correct, sourced rows for every key part still reported them all missing. Third instance of an over-literal matcher (after `read_index`'s extension filter and the waiver parser). | Ref cells are split into designators with the pin suffix dropped |
| 64 | `audit_workflow.py` re-implemented ERC and placement instead of calling the gates, and **contradicted them on both** — counting waived ERC violations, and treating a sub-0.1 mm WARN as a failure. An audit that disagrees with the gate is worse than no audit. | It calls `run_gates.gate_erc` directly; the self-test asserts audit and gate agree |
| 65 | Two 0603 decoupling caps **cannot** both sit within 2 mm of adjacent 0.65 mm-pitch TSSOP supply pins; auto-placement put one at 2.86 mm. Two 0402s can (1.4 mm each) and have lower ESL. Package choice is part of meeting a placement rule, not a separate decision. | Explicit placement, measured from the built board |
| 66 | **`docs/route_best_of.py` — the THIRD orphaned tool**, invoked by nothing, on a router whose own docstring says it is non-deterministic. Routing once and keeping whatever came out makes "ships / does not ship" a matter of luck. | Wired into `pipeline.py`'s route stage as best-of-4 |
| 67 | Best-of-N is also a **measurement instrument**: 8 attempts all returning the same count is how you tell a *structural* block from router noise. tms-v3 returned 2 every time, so U3 pin 15's blocked escape channel was real. A later 0.5mm "fix" then returned 5 every time — proving it made the board worse, and it was reverted. | A local placement fix must be measured globally, over N runs |
| 68 | `check_research.inventory()` and `validate_pcb._fp_ref()` read only `(property "Reference" ...)`. tms-v3's XBee socket uses the legacy `(fp_text reference "J9")` form, so **J9 was invisible to every gate** — the sourcing check reported "every part sourced" while J9 had no part number, and the parity check could not have seen it either. A part the gates cannot see is worse than one they fail on. | Both readers accept either spelling |
| 69 | The BOM must carry LCSC numbers and `kicad-cli sch export bom` reads the **schematic**, while this workspace stamps part numbers onto **PCB footprints** — producing a BOM that looks complete with an empty LCSC column. | `docs/export_fab.py` builds the BOM from the `.kicad_pcb` |
| 70 | `kicad-cli pcb export pos` emits positions against the page origin: `Mid Y ≈ -188` for a 26mm board. That CPL uploads without complaint and places every part off the panel. | `export_fab.py` re-origins to the board's own bottom-left corner |
| 71 | A fabrication package is the one artifact that can be uploaded and charged for, so generating one for a board whose gates failed manufactures the exact false confidence the pipeline exists to prevent — a folder of Gerbers looks finished whatever DRC said. | The `fab` stage runs **only** when the gates pass |
| 72 | The TMS V3 **PDR existed in `docs/tms-v3-pdr.md`** — 504 lines, a full component register and signal-chain analysis — and the requirements were reconstructed from the as-built board without finding it. Phase 1 is not always "write a spec"; sometimes it is "find the spec that already exists". | `REQUIREMENTS.md` now cites the PDR as its source |
| 73 | **The escape hatch was wider than the thing it excused.** `DEVIATIONS.md` lines are `<ref>.<pin> \| <scope> \| <reason>`, and the scope field was parsed and then discarded. `U1.5 \| 2.2 \| Pad 5 is SDO, not a supply pin` — a narrow, correct waiver of one decoupling rule on one pin — silently excused baro-bmp390's only IC from needing an archived reference design *and* a design-basis row. Every reference file deleted, and the gate still said *"every key part has an archived reference"*. | `docs/deviations.py` matches scope; `reference`/`basis`/`datasheet` are the only non-rule scopes |
| 74 | **The containment fix was opt-in.** Waivers count only under a `## Declared` heading — but a file *without* that heading fell back to parsing the whole file, the mode behind four earlier false-waiver bugs. Two of five projects were in that state (`tms-v3` had no such heading; `template` was a stale pre-fix copy) and nothing said so. | No `## Declared` = waives nothing, reported as a BLOCK gate |
| 75 | **A `~~struck-out~~` waiver came back to life.** The new parser stripped `~` as decoration, re-activating tms-v3's withdrawn `U3.13` deviation — caught within minutes of writing it, in the same session that wrote the rule about narrow escape hatches. | Any line containing `~~` waives nothing |
| 76 | **`REQUIREMENTS.md` checked for placeholders, not for content.** Deleting an entire section's body passed as *"6 sections present and filled"*, while leaving the template text failed — the opposite of the intent. | A section under `MIN_BODY` characters of real text fails Phase 1 |
| 77 | **The last gate was the weakest.** `gate_signoff` counted `- [x]`, so `sed -i '' 's/- \[ \]/- [x]/'` — one line, no board opened — turned NOT READY into all-pass and would have armed the `fab` stage on three boards. The template had always said "add your initials + date"; that instruction was prose. | A ticked item needs a `YYYY-MM-DD` date on it |
| 78 | **`gate_drc` returned PASS for a file that was not a board.** It ignored `kicad-cli`'s exit code and read whatever `drc-report.json` was lying in the directory — a stale clean report from another board. The gate that answers "can JLCPCB build this?" was answering from last run's evidence. | Report deleted before the run; its absence is a hard failure |
| 79 | **`gate_drc` was non-deterministic.** Without `--refill-zones` it judged whatever fill state was cached: three consecutive runs of an unchanged `tms-v3.kicad_pcb` gave 1, 1 and 2 errors, and the optimistic answer was the usual one. Even refilled, tms-v3 alternates 1↔2. A result that does not reproduce is not evidence. | Refilled, run **twice**, worse result reported, disagreement stated |
| 80 | **The audit drifted back into re-implementing the gates.** `audit_workflow.py` exists on the rule that it must call gate functions, never copy them — and its DRC row read `drc-report.json` directly (reporting 1 error where the gate said 2) while its sign-off row counted unticked boxes, missing the signature requirement entirely. The rule was written down; nothing checked it. | Both rows call the gate; the self-test asserts agreement on ERC, placement, DRC **and** sign-off |
| 81 | **68/68 green while six gates could not fail.** The self-test measured *wiring* — matchers, entry points, artifacts present — and read as total coverage. Wiring is not strength. | The self-test now fault-injects each gate and requires the failure |

### What a human must do after Claude's initial generation

Claude can get a board to *"every automated gate passes."* It cannot get it
to *"correct."* These are the steps that need a person, in priority order:

1. **Verify every module socket pinout against the vendor card, with the
   module physically in hand.** This is the highest-stakes item and the one
   no tool here can check. A sequentially-assigned header netlist passes ERC,
   passes DRC, routes cleanly, fabricates — and then puts a power rail into a
   3.3V GPIO. Both of TMS V3's module sockets were wrong in exactly this way.
2. **Check any hand-authored footprint against the real part.** Print at 1:1
   and offer the component to it.
3. **Confirm passive values against the specific part bought**, not the
   generic value — crystal load caps especially.
4. **Review `DEVIATIONS.md`.** Agree with each declared deviation or reject it.
5. **Open the board in KiCad and look at it.** 3D view for mechanical fit,
   silkscreen legibility, pin-1 markers.
6. **Check connectors are the real connector.** A part labelled "XT60" that
   is a 2.54mm header will pass every gate in this document.
7. **Sign `SIGNOFF.md`.** Until then the human gate fails and the board is
   not fabrication-ready.


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
