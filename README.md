# Smogon VGC MCP Server

MCP server providing VGC competitive Pokemon stats, damage calculations, and teambuilding tools to LLMs like Claude.

## Features

- **Usage Statistics** - Pokemon usage rates, common items, moves, abilities, EV spreads, and Tera types from Smogon ladder
- **Tournament Teams** - Search 500+ tournament teams from the VGC Pastes Repository with full details
- **Damage Calculator** - Full damage calculations using @smogon/calc with support for items, abilities, weather, terrain, and more
- **Stat Calculator** - Calculate actual stats at Level 50, compare speeds, find speed tier benchmarks
- **Type Analysis** - Type weaknesses/resistances, team type coverage analysis, offensive coverage
- **Pokedex** - Pokemon stats, moves, abilities, items, learnsets from Pokemon Showdown

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for damage calculator)
- **uv** (recommended) - Install from [astral.sh](https://astral.sh)

## Installation

### Option 1: Install from GitHub (Recommended)

```bash
# Clone the repository
git clone https://github.com/dtsong/smogon-vgc-mcp.git
cd smogon-vgc-mcp

# Install dependencies
uv sync

# Install Node.js dependencies for damage calculator
npm install
```

### Option 2: Install with uvx (No Clone Required)

```bash
uvx --from git+https://github.com/dtsong/smogon-vgc-mcp smogon-vgc-mcp
```

## Claude Code Configuration

Add the MCP server to your Claude Code settings file.

### Find your settings file

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Or for Claude Code CLI, use `~/.claude/settings.json`.

### Add the server configuration

```json
{
  "mcpServers": {
    "smogon-vgc": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/smogon-vgc-mcp",
        "smogon-vgc-mcp"
      ]
    }
  }
}
```

Replace `/path/to/smogon-vgc-mcp` with the actual path where you cloned the repository.

### Alternative: Using uvx

```json
{
  "mcpServers": {
    "smogon-vgc": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/dtsong/smogon-vgc-mcp",
        "smogon-vgc-mcp"
      ]
    }
  }
}
```

## Initial Data Setup

After configuring the server, you'll need to fetch the data. Ask Claude to run these commands:

```
"Please refresh the VGC data"
```

This will trigger:
1. `refresh_data` - Fetches Smogon ladder usage stats
2. `refresh_moveset_data` - Fetches Tera types and checks/counters data
3. `refresh_pokepaste_data` - Fetches tournament teams
4. `refresh_pokedex_data` - Fetches Pokedex data from Pokemon Showdown

Data is cached locally in a SQLite database, so you only need to refresh periodically.

## Example Queries

Once configured, you can ask Claude things like:

### Usage Stats
- "What are the top 20 Pokemon in VGC right now?"
- "Show me Incineroar's usage stats, common items, and EV spreads"
- "What are Flutter Mane's most common teammates?"

### Teambuilding
- "Find Pokemon that commonly use Assault Vest"
- "What counters Urshifu?"
- "Find teams that use Incineroar + Flutter Mane core"

### Damage Calculations
- "Calculate damage from 252 Atk Jolly Urshifu Close Combat into 252 HP / 84 Def Careful Incineroar"
- "How much damage does Flutter Mane do to Kingambit after Intimidate?"
- "What's the minimum Attack EVs needed for Dragonite to OHKO Amoonguss with Tera Normal Extreme Speed?"

### Speed Tiers
- "Compare speed between max speed Kingambit and min speed Torkoal"
- "What does 252 Speed Jolly Flutter Mane outspeed?"

### Type Analysis
- "What are Kingambit's type weaknesses?"
- "Analyze type coverage for my team: Incineroar, Flutter Mane, Urshifu, Rillaboom, Farigiraf, Archaludon"

### Pokedex
- "What moves can Incineroar learn?"
- "What's the base power of Moonblast?"
- "Show me all Fairy-type Pokemon"

## Available Tools

### Usage Stats
- `get_pokemon` - Comprehensive stats for a Pokemon
- `find_pokemon` - Search Pokemon by name
- `get_top_pokemon` - Usage rankings
- `compare_pokemon_usage` - Compare across months
- `compare_elo_brackets` - Compare across skill levels

### Teambuilding
- `get_pokemon_teammates` - Common teammates
- `find_pokemon_by_item` - Find users of an item
- `find_pokemon_by_move` - Find users of a move
- `find_pokemon_by_tera` - Find users of a Tera type
- `get_pokemon_counters` - Find counters

### Tournament Teams
- `get_tournament_team` - Full team details
- `search_tournament_teams` - Search by Pokemon/player/tournament
- `get_pokemon_tournament_spreads` - EV spreads from tournaments
- `find_teams_with_pokemon_core` - Find teams with specific Pokemon

### Calculators
- `calc_damage` - Damage calculation with all modifiers
- `analyze_matchup` - Full matchup analysis
- `calculate_pokemon_stats` - Stat calculation
- `compare_pokemon_speeds` - Speed comparison
- `get_speed_benchmarks` - Speed tier analysis

### Type Analysis
- `get_type_weaknesses` - Pokemon type matchups
- `analyze_team_type_coverage` - Team weakness analysis
- `analyze_move_coverage` - Offensive coverage

### Pokedex
- `dex_pokemon` - Pokemon info
- `dex_move` - Move info
- `dex_ability` - Ability info
- `dex_item` - Item info
- `dex_learnset` - Pokemon learnset

## Multi-Format Support

The server supports multiple VGC formats. Most tools accept a `format` parameter:
- `regf` - Regulation F (default)

Use `list_available_formats` to see all supported formats.

## Development

```bash
# Run tests
uv run pytest

# Lint and format
uv run ruff check --fix .
uv run ruff format .

# Type check
uv run ty check

# Test with MCP Inspector
npx @modelcontextprotocol/inspector uv run smogon-vgc-mcp
```

## License

MIT
