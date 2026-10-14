# TMS project protocol

Follow the root AGENTS.md, CLAUDE.md and shared workflow. This is fresh CAD
captured from design-bases/tms on 2026-10-13. A1 presentation was followed by the owner-approved A2 schematic-stage
installation on 2026-10-14. A2 includes reviewed circuit/library/value changes;
97 retained physical component UUIDs are preserved, 23 parts added, C9 removed.
PCB/project/rule files remain unchanged. This exception is not release approval.
Do not restore or develop the frozen TMS fixture.

Root KiCad files are the editable design. Future edits start from their saved
native hierarchy, through update-schematic --candidate and the normal preview /
--apply gates. No one-time capture script or historical BOM is an authority to
redraw owner edits. Inspect every affected rendered sheet.

Read docs/design/CAPTURE.md, docs/design/COMPONENT_VERIFICATION.md and
docs/design/FIRMWARE_CONTRACT_A2.md and docs/review/ELECTRICAL_REVIEW_A2.md
alongside the
requirements and design basis. The empty PCB is a project placeholder; it has
no selected outline, placement or routing. No fabrication approval exists.

Owner-confirmed radio: XB3-24AST-J with A24-HASM-450 antenna. The USB adapter is
assumed to be at the ground station; confirm its installation before a harness
or enclosure is finalized. Never connect two 3.3 V supply outputs together.
