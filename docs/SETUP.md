# PCB Workspace Setup

## What's Installed

| Tool | Version | Path | Purpose |
|------|---------|------|---------|
| KiCad | 10.0.5 | `/Applications/KiCad/` | PCB design GUI |
| kicad-cli | 10.0.5 | On PATH via .zshrc | Headless ERC/DRC, Gerber export |
| kipython | Python 3.9.13 | `~/.local/bin/kipython` | KiCad's Python with pcbnew |
| uv | 0.12.5 | `~/.local/bin/uv` | Python package manager |
| Node.js | v24.19.0 | via fnm | JS runtime for MCP servers |
| Java (Temurin) | 21.0.12 | `~/Library/Java/JavaVirtualMachines/` | Freerouting autorouter |
| Freerouting | 2.1.0 | `tools/kicad-claude-mcp/third_party/` | Autorouter JAR |
| kicad-claude-mcp | latest | `tools/kicad-claude-mcp/` | 105-tool MCP server (generate) |
| kicad-jlcpcb | latest | `tools/kicad-jlcpcb/` | 13-tool MCP server (LCSC + EasyEDA + JLCPCB) |
| kicad-happy | latest | `tools/kicad-happy/` | 12 Claude Code review skills |

## Claude Code Integration

### MCP Server (kicad-claude-mcp)
Registered in `~/.claude/settings.json` under `mcpServers.kicad`.
Provides 105 tools across 16 phases (schematic → PCB → routing → fabrication).

**To verify:** Restart Claude Code, then run `/mcp` — you should see the `kicad` server listed.

### MCP Server (kicad-jlcpcb)
Registered in `~/.claude/settings.json` under `mcpServers.kicad-jlcpcb`.
13 tools for LCSC part sourcing, EasyEDA pin maps, PCB generation, and JLCPCB packaging.
Slash commands: `/pcb-new` (from description), `/pcb-from-bom` (from CSV).

### Skills (kicad-happy + kicad-jlcpcb)
12 skills symlinked to `~/.claude/skills/`:
`kicad`, `spice`, `emc`, `datasheets`, `bom`, `digikey`, `mouser`, `lcsc`, `element14`, `jlcpcb`, `pcbway`, `kicad-jlcpcb-workflow`

## Shell Environment (.zshrc additions)
```bash
. "$HOME/.local/bin/env"           # uv
eval "$(fnm env 2>/dev/null)"      # Node.js via fnm
export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"  # kicad-cli
export JAVA_HOME="$HOME/Library/Java/JavaVirtualMachines/jdk-21.0.12.1+1/Contents/Home"
```

## Verification Commands
```bash
kicad-cli version                    # Should print 10.0.5
kipython -c "import pcbnew; print(pcbnew.Version())"  # Should print 10.0.5
uv --version                        # Should print 0.12.x
node --version                      # Should print v24.x
$JAVA_HOME/bin/java --version       # Should print 21.x
```

## Optional: API Keys (for component sourcing)
Edit `tools/kicad-claude-mcp/.env` to add:
- **DigiKey**: Get credentials at https://developer.digikey.com
- **Mouser**: Get API key at https://www.mouser.com/api-hub/

These are optional — component sourcing and datasheet lookup work without them
(kicad-happy uses free web scraping as fallback), but API access is faster and more reliable.

## Updating Tools
```bash
cd ~/CODE/PCB/tools/kicad-claude-mcp && git pull && uv sync
cd ~/CODE/PCB/tools/kicad-jlcpcb && git pull && uv pip install -e "."
cd ~/CODE/PCB/tools/kicad-happy && git pull
```
