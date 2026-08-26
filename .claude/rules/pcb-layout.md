---
paths:
  - "projects/**/*.kicad_pcb"
---

# PCB Layout Rules (Triggered on .kicad_pcb files)

Full reference: `docs/pcb-design-rules.md`. This is the compressed version for in-context recall.

**First action of a fresh session touching PCB tooling: read `docs/pcb-design-workflow.md` Phase 0.** It's a health-check + gotcha list for the MCP servers/autorouter/validator that has already cost one full session to derive from scratch — don't re-derive it. Covers: MCP server registration (not `~/.claude/settings.json`), the `kicad-skip` compat patch required to load any board here, `autoroute_pcb` passes/timeout tuning, why `add_track`'s `net=` param doesn't work for stitching on these files, and the recurring `starved_thermal` zone-fill pattern.

## Non-negotiable gates
- **Every board must have routed traces.** Placement-only is not a deliverable — see Phase 4B in `docs/pcb-design-workflow.md`.
- **Zero unconnected nets** before calling layout done. Verify with DRC.
- **Fiducials optional** — JLCPCB auto-adds its own for assembly if the board has none, so orders aren't rejected for missing them. Add 3 self-placed fiducials (L-pattern) for boards with fine-pitch (<0.5mm) parts, for tighter placement accuracy.
- Run `python3 docs/validate_pcb.py <board>.kicad_pcb` before declaring the board ready for export.

## Before choosing any placement coordinate
Fetch the real footprint first and check its courtyard size with `docs/pcb_layout_helpers.py` — a placeholder-era coordinate does not survive a real footprint (recurring defect: TMS V3's relay/24-pin header, IMU's header anchor point, barometer's 3×-oversized STEMMA QT connector all trace to this). Use `PlacementTracker.place()` for every component as you place it — it raises immediately on a courtyard collision with the exact overlap, instead of a DRC violation discovered after the whole board is built. See `pcb-design-rules.md` §15.7.

## Fast checks while editing
- Decoupling caps ≤2mm from IC power pins, no via between cap and pin (§2)
- Single solid ground plane — never split AGND/DGND (§3)
- Crystal ≤5mm from IC, no ground pour under crystal body (§5)
- Ground stitching via within 2mm of every signal layer-change via (§8)
- Trace widths sized for actual current — IPC-2221 table (§4.2)
- No traces within 3mm of board edge (§14)

## Before declaring layout complete
Run the 7+1 pass Layout Review Protocol (`docs/pcb-design-rules.md` §17), starting with Pass 0 (pre-layout completeness) if this is a fresh layout, ending with Pass 7 (post-route verification).

## Before saying this board is done

```bash
python3 docs/pipeline.py projects/<board> --check   # gates only
python3 docs/pipeline.py projects/<board>           # full rebuild + gates
```

Exits non-zero unless every gate passes. **Paste its output** — a completion
claim without this table is not evidence. New/legacy board missing the gate
artifacts: `python3 docs/run_gates.py --init projects/<board>`.

DRC answers *"can JLCPCB build this?"*, never *"is this a good layout?"*.
`check_design_rules.py` (inside the gate runner) answers the second — TMS V3
passed DRC while breaking 23 numbered rules in `pcb-design-rules.md`.

Three traps that cost the most time here, all invisible to DRC:

- **Coordinate frames.** design / MCP / KiCad-Y-down. Convert *only* through
  `design_to_mcp()` / `design_to_kicad()` / `kicad_to_design()`. The same sign
  error appeared three separate times when they were done inline.
- **Anchors.** A `1xN` header anchors on **pin 1**, not its centre. An anchor
  comfortably mid-board can put pads 16mm off the edge.
- **Placement, not the router.** Moving the Teensy 6mm took unconnected from
  8 to 5; extra router passes did nothing. Sweep placement before blaming
  Freerouting. Stitching presupposes **two** pours — on a single-pour board
  every stitching via dangles (90 vias → 112 `via_dangling`).
