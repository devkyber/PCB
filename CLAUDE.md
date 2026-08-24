# PCB Design Workspace

## Owner
Mechanical engineering student. Not EE major. Has EasyEDA experience, new to KiCad.
Takes electronics/controls roles in team projects (rocketry avionics, GNC systems).
Wants fast iteration with minimal EE friction.

## Fabrication Target
- **Primary:** JLCPCB (2-layer default, 4-layer when needed)
- **Assembly:** JLCPCB SMT assembly when needed (BOM + pick-and-place format)
- **Design rules:** JLCPCB 2-layer minimums: 0.127mm trace, 0.127mm clearance, 0.3mm via drill, 0.6mm via pad

## Tools Installed

### kicad-claude-mcp (Generator)
- Location: `tools/kicad-claude-mcp/`
- MCP server registered in `~/.claude/settings.json`
- 105 tools: schematic capture, PCB layout, autorouting (Freerouting), DRC/ERC, Gerber export, signal integrity, SPICE
- Reload Claude Code after changes to pick up the MCP server

### kicad-jlcpcb (JLCPCB/EasyEDA Bridge)
- Location: `tools/kicad-jlcpcb/`
- MCP server registered in `~/.claude/settings.json`
- 13 tools: LCSC part sourcing (basic-tier preferred), EasyEDA pin-map fetching, wired .kicad_pcb generation, EasyEDA handoff for cloud autorouting, Gerber/BOM/CPL packaging
- `fetch_part_library` produces **real** libraries via easyeda2kicad: pin-accurate `.kicad_sym`, per-package `.kicad_mod`, and `.step`/`.wrl` 3D models. All land in `<project>/libs/` as one library named `jlcpcb`, auto-registered in the project's `sym-lib-table`/`fp-lib-table`.
- Check `fidelity` in the result: `"real"` = actual part geometry; `"placeholder"` = conversion failed, generic outline substituted — **must** be reviewed in KiCad before fabricating.
- LCSC metadata lookup (`lcsc_search`, `lcsc_resolve_bom`) uses the jlcparts v4 sharded JSONL format (`manifest.json` + `attributes-lut.json.gz` + `components-*.jsonl.gz`). Library fetching is unaffected (it goes straight to EasyEDA).
- Slash commands: `/pcb-new` (from description), `/pcb-from-bom` (from CSV)
- Flow: Claude sources LCSC parts → generates wired PCB → you import into EasyEDA → autoroute → order at JLCPCB

### kicad-happy (Reviewer)
- Location: `tools/kicad-happy/`
- Skills symlinked to `~/.claude/skills/`: kicad, spice, emc, datasheets, bom, digikey, mouser, lcsc, element14, jlcpcb, pcbway
- Use for design reviews, datasheet extraction, component sourcing, EMC checks

### KiCad 10.0.5
- Installed at `/Applications/KiCad/`
- kipython symlink at `~/.local/bin/kipython`
- CLI: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`

### Freerouting Autorouter
- JAR at `tools/kicad-claude-mcp/third_party/freerouting.jar`
- Requires Java 21 (Temurin JDK 21 installed at `~/Library/Java/JavaVirtualMachines/`)

## Project Structure
```
PCB/
├── projects/           # Each board gets its own subfolder
│   └── <board-name>/
│       ├── *.kicad_pro, *.kicad_sch, *.kicad_pcb
│       ├── fabrication/    # Gerbers, drill, BOM, PnP
│       ├── datasheets/     # Auto-downloaded PDFs
│       └── 3d-models/      # STEP exports
├── tools/              # Don't edit - cloned repos
│   ├── kicad-claude-mcp/
│   └── kicad-happy/
└── docs/               # Workspace-level docs
```

## Workflow
1. Describe the board spec in plain English with mechanical constraints
2. Claude generates schematic + PCB via kicad-claude-mcp
3. Run DRC/ERC validation
4. Run kicad-happy design review (power tree, signals, DFM, EMC)
5. Open in KiCad for visual review and manual fixes
6. Export 3D STEP model → check fit in CAD tool
7. Export Gerbers + BOM → order at JLCPCB

Full workflow: `docs/pcb-design-workflow.md` (6-phase process with gate checklists)

## PCB Design Rules (MANDATORY)
**Always consult `docs/pcb-design-rules.md` during layout and review.**

This is the expert knowledge base covering component placement, decoupling strategy, ground plane rules, trace routing, crystal layout, thermal management, via design, EMC, and JLCPCB DFM. It includes a 25-item beginner mistake checklist and a 7+1 pass layout review protocol.

Key rules to never violate:
- Decoupling caps ≤2 mm from IC power pins, no via between cap and pin
- Single solid ground plane (never split AGND/DGND)
- Crystal within 5 mm of IC, no ground pour under crystal body
- Analog/digital physical separation by placement, not ground plane cuts
- Ground stitching via within 2 mm of every signal layer-change via
- Trace widths sized for actual current (IPC-2221 table in the doc)
- Run Pass 0 (pre-layout completeness) before starting layout (§15)
- Run the 7-pass Layout Review Protocol before declaring layout complete (§17)
- **Every board must have routed traces** — placement-only is not a PCB
- **Every PCBA board needs ≥3 fiducials** — JLCPCB rejects without them
- Run `python3 docs/validate_pcb.py <board>.kicad_pcb` before export

## Conventions
- Always include board dimensions and mounting hole positions in the spec
- Prefer through-hole for prototypes when hand-soldering
- Use LCSC part numbers for JLCPCB assembly compatibility
- Save datasheets in the project's datasheets/ folder
- Name revisions: rev1, rev2, etc.
- Put your name and rev on the silkscreen
