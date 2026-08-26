# PCB Workspace Setup

## What's Installed

| Tool | Version | Path | Purpose |
|------|---------|------|---------|
| KiCad | 10.0.5 | `/Applications/KiCad/` | PCB design GUI |
| kicad-cli | 10.0.5 | On PATH via .zshrc | Headless ERC/DRC, Gerber export |
| kipython | Python 3.9.13 | `~/.local/bin/kipython` | KiCad's Python with pcbnew |
| uv | 0.12.5 | `~/.local/bin/uv` | Python package manager |
| Node.js | v24.19.0 | via fnm | JS runtime for MCP servers |
| Java (Temurin) | **25.0.4** and 21.0.12 | `~/Library/Java/JavaVirtualMachines/` | Freerouting autorouter |
| Freerouting | **2.3.0** (2.1.0 kept as fallback) | `tools/kicad-claude-mcp/third_party/` | Autorouter JAR |
| kicad-claude-mcp | latest | `tools/kicad-claude-mcp/` | 105-tool MCP server (generate) |
| kicad-jlcpcb | latest | `tools/kicad-jlcpcb/` | 13-tool MCP server (LCSC + EasyEDA + JLCPCB) |
| kicad-happy | latest | `tools/kicad-happy/` | 12 Claude Code review skills |

## Claude Code Integration

### MCP registration — read this before debugging a missing server

`~/.claude/settings.json` **contains an `mcpServers` block, and this
installation does not read it.** Confirmed 2026-08-25. The block is inert: it
looks authoritative, it is the first place anyone looks, and editing it changes
nothing. Registration actually lives in the CLI's own store:

```bash
claude mcp list                    # what is really registered
claude mcp add <name> -- <command> # how to register
```

Leaving the stale block in place is a trap; it is documented here rather than
removed because deleting someone's settings file is not this document's call.

### The servers

| Server | Tools | Purpose |
|---|---|---|
| `kicad` (kicad-claude-mcp) | 105 | schematic → PCB → routing → fabrication |
| `kicad-jlcpcb` | 13 | LCSC sourcing, EasyEDA pin maps, JLCPCB packaging |

Slash commands: `/pcb-new` (from a description), `/pcb-from-bom` (from CSV).

**Before using either in a fresh session**, run the Phase 0 checklist in
`docs/pcb-design-workflow.md` — venv / Freerouting / registration / compat-patch
health check.

### Freerouting version, and why it matters

The adapter picks the newest JAR whose JVM is actually present, so a missing
JDK **degrades silently to the old router** rather than failing. Run
`routing_status` to see which one you are on. 2.1.0's route optimiser is
multi-threaded, upstream-broken, and cannot be disabled — `-mt 1` and the env
override were both measured not to reach it.

Never call the JAR directly. `autoroute_pcb` (MCP) and `docs/route_and_fill.py`
(CLI) run one shared pipeline — DSN export → route → SES import → **zone fill**
→ **ground bonding** → DRC. Raw `java -jar` skips the fill and the bonding, and
an unfilled board reports every pour-connected pad as unconnected.

### Skills (kicad-happy + kicad-jlcpcb)
12 skills symlinked to `~/.claude/skills/`:
`kicad`, `spice`, `emc`, `datasheets`, `bom`, `digikey`, `mouser`, `lcsc`, `element14`, `jlcpcb`, `pcbway`, `kicad-jlcpcb-workflow`

## Shell Environment (.zshrc additions)
```bash
. "$HOME/.local/bin/env"           # uv
eval "$(fnm env 2>/dev/null)"      # Node.js via fnm
export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"  # kicad-cli
export JAVA_HOME="$HOME/Library/Java/JavaVirtualMachines/jdk-21.0.12.1+1/Contents/Home"
# Freerouting 2.2+ needs JDK 25: jdk-25.0.4.1+1 is installed alongside.
```

## Verification Commands
```bash
kicad-cli version                                     # 10.0.5
kipython -c "import pcbnew; print(pcbnew.Version())"  # 10.0.5
uv --version                                          # 0.12.x
node --version                                        # v24.x
$JAVA_HOME/bin/java --version                         # 21.x
```

Then the check that actually matters — whether the enforcement machinery is
wired and firing, not merely present:

```bash
python3 docs/selftest_enforcement.py
```

It runs at session start and as the first thing in the pipeline's `env` stage.
It exists because a hook advertised as automatic had never once fired: it read
`tool_input.file_path`, which `Bash` does not have. Reviewing a rule is not
running it.

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
