# KiCad support adapters

This local dependency retains the CAD parsing, schematic editing, geometry,
project rules and routing code used by PCB Copilot. Its Python import name is
`kicad_claude`. The original MCP server, provider integrations and unrelated
simulation tools have been removed. The root workspace installs this package.

The adapters originated in kicad-claude-mcp by Grigory Filimonov (MIT).
PCB Copilot's schematic/layout tests exercise these APIs; the package tests
cover the shared routing pipeline. Native operations require KiCad. Optional
autorouting additionally requires Java and `FREEROUTING_JAR`.
