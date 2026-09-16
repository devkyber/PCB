---
paths:
  - "projects/**/*.kicad_sch"
---

# Schematic Capture Rules (Triggered on .kicad_sch files)

Full reference: `docs/WORKFLOW.md` Phase 3, `docs/DESIGN_RULES.md` §15.

## Before adding any component
- Fetch its real footprint via `fetch_part_library` — check `fidelity == "real"`, not `"placeholder"`.
- Verify the `jlcpcb` library actually landed in `sym-lib-table`/`fp-lib-table` — the fetch step doesn't guarantee registration (§15.7).
- Extract the real pin map from the fetched `.kicad_sym` — never reuse a placeholder-era pin-map comment. For relay COM/NO, TVS common, or any other unlabeled multi-function pin, confirm against the manufacturer datasheet before wiring, especially for safety-critical circuits (§15.7).
- Cross-check every passive value against the IC's datasheet application circuit (§15.1). Don't guess cap values.

## While wiring (script-based generation)
- Attach every net to the symbol's real pin coordinate (e.g. `get_pin_position`) — never a hand-guessed `(x, y)`. A label near a pin looks connected but ERC will show it dangling; this was the largest defect class found integrating real parts into TMS V3.
- **Never call `add_label` or `add_symbol` at bare coordinates. Route everything through `docs/schematic_layout_helpers.py`.** ERC only checks connectivity, never geometry, so every defect below is 100% ERC-clean and invisible until a human renders the sheet. The module handles them all; a generator script should contain circuit intent and coordinates, nothing else.

  Two objects, wired up once per script:

  ```python
  from schematic_layout_helpers import LabelPlacer, SymbolPlacer

  symbols = SymbolPlacer(ed, tree)              # placement geometry
  labels  = LabelPlacer(ed, tree, symbols=symbols)
  labels.place_symbol = place                   # after place() is defined

  def place(...):
      ed.add_symbol(...)
      # register() may RELOCATE to clear an overlap; it returns the final
      # centre, so record that, not the requested (x, y).
      symbol_origin[ref] = symbols.register(ref) or (snap(x), snap(y))

  def pin_label(ref, pin, net):
      return labels.auto(ref, pin, net, *symbol_origin[ref])
  ```

  What that buys, all automatic:
  - `.auto()` sends standard global rails (`GND`, `+3V3`, `+5V`) to a **graphical power symbol** and everything else to a text label. Rail text was ~45% of all label text on these boards (tms-v3: 78 of 172 labels, including 38 separate "GND" strings). Exact name match only — a power symbol's net name comes from its pin name, so substituting a differently-spelled symbol *renames the net* and silently desyncs the PCB.
  - `SymbolPlacer.register()` refuses/relocates overlapping symbols (schematic twin of the PCB courtyard check), pulls off-sheet placements back inside the frame, and positions Reference/Value text on whichever side the pins don't use.
  - Stub wires are auto-sized to clear the pin's own name, staggered across pin columns, re-routed to another side when a flank is congested, and checked for cross-net crossings (a crossing silently bridges two nets — it once merged an entire board into one net with ERC still passing).

- **Grid: snap in KiCad's coordinate space, not the helper's.** `y_kicad = page_h - y_mcp`, and `page_h` is never a multiple of the 1.27mm grid (A4 is 210mm; 210/1.27 = 165.35), so a Y that looks grid-aligned in generator coordinates lands off-grid in the file. This produced 521 `endpoint_off_grid` warnings across the four boards, and off-grid endpoints are a real hazard — they are what makes a wire fail to connect when someone later edits the sheet by hand. `SymbolPlacer.register()` now snaps via `snap_mcp_y_to_kicad_grid()`; all 521 are gone. Don't reintroduce a bare `round(y/1.27)*1.27` on a Y coordinate.

- **Page size is a design decision.** ~25 components is about the limit for A4. tms-v3 (69 components) is on A3 and still dense; past that, split into hierarchical sheets rather than shrinking spacing.

- Run ERC after each section, not just at the end — catches net-naming bugs immediately.
- Every genuinely unused pin gets an explicit no-connect flag, not silence.

## Before finishing a schematic
- Every IC power pin has a decoupling cap
- Every address/config/mode pin is tied per datasheet — nothing floating (§15.2)
- Every inter-IC connection has matching voltage levels, or a level shifter if not (§15.3)
- Reference-design comparison table (`docs/WORKFLOW.md` Phase 2.3) has every row filled — this is a hard gate, not optional. When fetching the reference source, use `docs/fetch_reference_doc.py` for anything you need an exact value from (GitHub Eagle `.sch`/`.brd`, PDFs) — WebFetch summarizes and will silently lose pin-level detail; a dead link goes through `verify_url()` first, never reported as just "unavailable."
- Run ERC — zero **errors**. `endpoint_off_grid`/`pin_to_pin` warnings on real fetched parts are an expected easyeda2kicad artifact; a `power_pin_not_driven` error gets a `power:PWR_FLAG` symbol on that net.


## Before any wire: the reference must be on disk

Audited 2026-08-25 — this file already called the Phase 2.3 comparison "a
hard gate, not optional", and four boards had zero archived references. The
rule was true and unenforced, which is the same as absent.

```bash
python3 docs/collect_references.py suggest <PARTNO>
uv run pcb-copilot research <project> --add <PART> <URL> --role <ROLE>
uv run pcb-copilot research <project> --extract <PART>
uv run pcb-copilot research <project> --verify
python3 docs/check_research.py <board.kicad_pcb>
```

- Search order is Tier 1 manufacturer EVM/app note → Tier 2 open hardware
  source (Adafruit/SparkFun Eagle or KiCad files: **exact** values and nets)
  → Tier 3 teaching sources (Phil's Lab, Altium Academy) for rationale.
- Archive it before you cite it. `add` verifies the URL is alive, rejects an
  HTML error/login page saved as a document, and records provenance.
- Then fill a `DESIGN_BASIS.md` row per key part: our value, what the
  reference does, the source file, and `Match` / `Deviate: <reason>`.
- Advisory while you design, blocking at `run_gates.py`. Escape hatch is one
  line in `DEVIATIONS.md` naming the part.
