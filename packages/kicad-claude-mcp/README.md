# KiCad support adapters

This local dependency retains the CAD parsing, schematic editing, geometry,
project rules and routing code used by PCB Copilot. Its Python import name is
`kicad_claude`. The original MCP server, provider integrations and unrelated
simulation tools have been removed. The root workspace installs this package.

The adapters originated in kicad-claude-mcp by Grigory Filimonov (MIT).
PCB Copilot's schematic/layout tests exercise these APIs; the package tests
cover the shared routing pipeline. Native operations require KiCad. Optional
autorouting additionally requires Java and `FREEROUTING_JAR`.

## Retained runtime surface

| Files | Used for |
| --- | --- |
| `adapters/sch_io.py`, `adapters/sch_editor.py`, `templates/blank.py` | Native parsing and optional schematic intent rendering, including hierarchy and real pin geometry |
| `utils/geometry.py`, `utils/kicad_paths.py` | Coordinate conversion and discovery of the installed KiCad tools/libraries |
| `adapters/project_settings.py` | Candidate-only design constraints and net classes |
| `adapters/dsn_keepouts.py`, `adapters/freerouting.py`, `adapters/route_pipeline.py` | Optional routing candidate generation with keepouts and connectivity classification |
| `adapters/kicad_python.py`, `adapters/kicad_cli.py` | Native DSN/SES, fill/bond operations and DRC for that routing backend |

The old independent PCB tree editor, length-tuning/stackup generators, blank
PCB/project creation and duplicate export wrappers had no pipeline callers and
were removed. PCB construction uses the native renderer in
`src/pcb_copilot/layout/render.py`; review and release use the shared pipeline's
checked exporters. Fabricator rules come from the project intent and cited
design basis, not unused vendor presets in this dependency. The repository
history retains the original implementations.
