# Smogon VGC MCP Server - Project Conventions

## Overview

MCP server providing VGC competitive Pokemon stats, damage calculations, and teambuilding tools to LLMs. Supports multiple VGC formats (Regulation F, G, H, etc.) with data coexisting in the database.

## Multi-Format Support

The server supports multiple VGC formats via a `format` parameter on most tools. Each format has its own:
- Smogon stats URL pattern
- Available months and ELO brackets
- Google Sheet tab for tournament teams
- Team ID prefix (e.g., "F" for Reg F, "G" for Reg G)

**Current Formats:**
- `regf` - Regulation F (default, current format)

**Format Parameter:**
- Most tools accept an optional `format` parameter (default: `"regf"`)
- Use `list_available_formats()` to see all supported formats
- Format configuration is in `src/smogon_vgc_mcp/formats.py`

## Toolchain (Astral)

This project uses tools from https://astral.sh/:

- **uv** - Package/project management
- **ruff** - Linting and formatting
- **ty** - Type checking

## Common Commands

```bash
# Install dependencies
uv sync

# Run the MCP server
uv run smogon-vgc-mcp

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

## Data Sources

### Smogon Ladder Stats
- URL pattern: `https://www.smogon.com/stats/{month}/chaos/{smogon_format_id}-{elo}.json`
- Format-specific (see `formats.py` for smogon_format_id per format)
- ELO brackets: 0, 1500, 1630, 1760

### VGC Pastes Repository (Tournament Teams)
- Google Sheet: `1axlwmzPA49rYkqXh7zHvAtSP-TKbM0ijGYBPRflLSWw`
- Each format has its own tab (gid configured in `formats.py`)
- Contains: Tournament teams with pokepaste links, rental codes
- Parsed data: Full team details (EVs, IVs, moves, abilities, items, tera types)

### Pokemon Showdown Pokedex
- Species, moves, abilities, items, learnsets, type chart
- Source: Pokemon Showdown data files

## MCP Tools

### Usage Stats
- `get_pokemon` - Get comprehensive stats (usage, abilities, items, moves, teammates, spreads, tera types, counters)
- `find_pokemon` - Search for Pokemon by partial name
- `get_top_pokemon` - Get top Pokemon by usage rate
- `compare_pokemon_usage` - Compare usage across months
- `compare_elo_brackets` - Compare usage across ELO brackets

### Teambuilding
- `get_pokemon_teammates` - Get most common teammates
- `find_pokemon_by_item` - Find Pokemon using a specific item
- `find_pokemon_by_move` - Find Pokemon using a specific move
- `find_pokemon_by_tera` - Find Pokemon using a specific Tera Type
- `get_pokemon_counters` - Get Pokemon that counter a specific Pokemon (from checks/counters data)

### Tournament Teams
- `get_tournament_team` - Get full team details by ID
- `search_tournament_teams` - Search teams by Pokemon/tournament/owner
- `get_pokemon_tournament_spreads` - Get EV spreads from tournament teams
- `find_teams_with_pokemon_core` - Find teams using a specific Pokemon core
- `get_team_database_stats` - Get team database statistics

### Stat Calculator
- `calculate_pokemon_stats` - Calculate actual stat values at Level 50
- `get_pokemon_base_stats` - Get base stats and BST
- `compare_pokemon_speeds` - Compare speed between two Pokemon
- `get_speed_benchmarks` - Find what notable Pokemon a speed stat outspeeds/underspeeds

### Type Analysis
- `get_type_weaknesses` - Get type matchups for a Pokemon (4x weak, 2x weak, resists, immunities)
- `analyze_team_type_coverage` - Analyze shared weaknesses/resistances for a team
- `analyze_move_coverage` - Analyze offensive type coverage of a moveset

### Damage Calculator
- `calc_damage` - Calculate damage with full modifiers (items, abilities, tera, weather, terrain, stat boosts, screens, Helping Hand)
- `analyze_matchup` - Analyze full matchup between two Pokemon (damage calcs for all moves both ways)
- `check_ohko` - Check minimum Attack/SpA EVs needed to OHKO a target
- `calc_damage_after_intimidate` - Compare damage before/after Intimidate

### Pokedex
- `dex_pokemon` - Get Pokedex info (stats, types, abilities)
- `dex_move` - Get move info (type, power, effect)
- `dex_ability` - Get ability info
- `dex_item` - Get item info
- `dex_learnset` - Get all moves a Pokemon can learn
- `dex_type_effectiveness` - Calculate type effectiveness
- `dex_pokemon_weaknesses` - Get Pokemon type weaknesses/resistances
- `search_dex` - Search Pokedex by name (pokemon, moves, abilities, items)
- `dex_pokemon_by_type` - Get Pokemon of a specific type
- `dex_moves_by_type` - Get moves of a specific type

### Admin/Data Refresh
- `list_available_formats` - List all supported VGC formats
- `refresh_data` - Fetch Smogon usage stats (accepts format parameter)
- `refresh_moveset_data` - Fetch moveset data (tera types, checks/counters)
- `refresh_pokepaste_data` - Fetch tournament teams from VGC Pastes Repository
- `refresh_pokedex_data` - Fetch Pokedex data from Pokemon Showdown
- `get_data_status` - Get usage data cache status (can filter by format)
- `get_pokepaste_data_status` - Get team data cache status (can filter by format)
- `get_pokedex_data_status` - Get Pokedex data cache status

## Project Structure

- `src/smogon_vgc_mcp/formats.py` - Format configuration registry (FormatConfig dataclass)
- `src/smogon_vgc_mcp/calculator/` - Stat, speed, type, and damage calculators
- `src/smogon_vgc_mcp/data/` - Pokemon data (base stats, types)
- `src/smogon_vgc_mcp/database/` - SQLite schema and queries
- `src/smogon_vgc_mcp/fetcher/` - Smogon/Showdown data fetchers
- `src/smogon_vgc_mcp/tools/` - MCP tool implementations
- `src/smogon_vgc_mcp/resources/` - MCP resource implementations
- `src/smogon_vgc_mcp/entry/` - Entry points
- `calc/` - @smogon/calc JavaScript damage calculator (via Node.js subprocess)
- `data/` - SQLite database (generated)

## Code Style

- Use type hints for all function signatures
- Async functions for I/O operations (database, HTTP)
- Docstrings for all public functions
- Follow PEP 8 (enforced by ruff)
