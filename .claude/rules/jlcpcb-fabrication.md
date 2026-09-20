---
paths:
  - "projects/**/fabrication/**"
---

# Fabrication Export Rules (Triggered when working in fabrication/)

Full reference: `docs/DESIGN_RULES.md` §11 (DFM), `docs/WORKFLOW.md` Phase 6.

## Before exporting Gerbers
- `python3 scripts/validate_pcb.py <board>.kicad_pcb` must show zero FAIL
- DRC and ERC both zero violations
- Fiducials optional for JLCPCB PCBA (auto-added if absent); recommended for fine-pitch (<0.5mm) parts

## Export checklist
- Gerbers: F.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen, B.Silkscreen, Edge.Cuts
- Drill file (Excellon)
- BOM: Comment, Designator, Footprint, LCSC Part# — prefer JLCPCB basic parts
- CPL: Designator, Mid X, Mid Y, Rotation, Layer
- 3D STEP for mechanical fit records

## JLCPCB order defaults
2-layer, 1.6mm thickness, HASL lead-free, 1oz copper, green mask, white silkscreen.
