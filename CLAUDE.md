# Smogon VGC MCP Server

MCP server providing VGC competitive Pokemon stats, damage calculations, and teambuilding tools to LLMs.

## Toolchain

Uses [Astral](https://astral.sh/) tools: **uv** (packages), **ruff** (lint/format), **ty** (types)

```bash
uv sync                 # Install dependencies
uv run pytest           # Run tests
uv run ruff check --fix . && uv run ruff format .  # Lint
uv run ty check         # Type check
uv run smogon-vgc-mcp   # Run MCP server
```

## Project Structure

```
src/smogon_vgc_mcp/
├── formats.py        # Format config (regf, regg, etc.)
├── calculator/       # Stat, speed, type, damage calculators
├── database/         # SQLite schema and queries
├── fetcher/          # Smogon/Showdown data fetchers
├── tools/            # MCP tool implementations
└── entry/            # Entry points

src/vgc_agent/        # Multi-agent teambuilder
├── agents/           # Architect, Calculator, Critic, Refiner
├── orchestrator.py   # Pipeline coordination
└── cli.py            # CLI interface

calc/                 # @smogon/calc JS damage calculator (Node subprocess)
data/                 # SQLite database (generated)
```

## Multi-Format Support

Supports multiple VGC formats via `format` parameter. Each format has its own Smogon stats URL, tournament teams sheet tab, and team ID prefix. Format config in `src/smogon_vgc_mcp/formats.py`.

## Data Sources

- **Smogon Stats**: `smogon.com/stats/{month}/chaos/{format}-{elo}.json`
- **Tournament Teams**: Google Sheet `1axlwmzPA49rYkqXh7zHvAtSP-TKbM0ijGYBPRflLSWw`
- **Pokedex**: Pokemon Showdown data files

## VGC Multi-Agent Teambuilder

Four agents collaborate: Architect → Calculator → Critic → Refiner

```bash
export ANTHROPIC_API_KEY="your-key"
uv run vgc-build "Build a sun team with Koraidon"
uv run vgc-build "Counter Flutter Mane" --verbose
```

See `src/vgc_agent/` for Python API and event types.
