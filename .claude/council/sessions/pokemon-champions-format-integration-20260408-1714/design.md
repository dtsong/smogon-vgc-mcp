# Design Document: Pokemon Champions Format Integration

## Overview

Pokemon Champions launched April 8, 2026 as a standalone battle game replacing Scarlet/Violet for VGC. It introduces a fundamentally different stat system (Stat Points instead of EVs/IVs), a curated 169-Pokemon dex, no Tera types, and Mega Evolutions. The MCP server must evolve to support Champions as the primary VGC platform while maintaining Gen 9 support for Regulation I.

The council unanimously agreed: Champions is not a "new format" — it's a **separate game** requiring isolated data stores, separate tool modules, and a new stat calculation engine. A `game` parameter bolted onto existing Gen 9 tools is the wrong abstraction because input schemas are structurally incompatible.

## Architecture

### FormatConfig Evolution

`FormatConfig` gains three new fields as the single routing authority:

```python
generation: int = 9
stat_system: Literal["gen9_ev_iv", "champions_sp"] = "gen9_ev_iv"
calc_backend: Literal["smogon_calc_gen9", "python_native"] = "smogon_calc_gen9"
```

`stat_system` is an enum with exhaustive branching — new stat systems produce type errors, not silent Gen 9 fallthrough. `smogon_stats_url` becomes `str | None` (None for Champions until Showdown support lands).

### Database: Separate Champions Tables

Champions data lives in fully separate tables — no shared tables with `game` column:

- `champions_dex_pokemon` — same shape as `dex_pokemon` minus unused fields
- `champions_dex_moves`, `champions_dex_abilities`, `champions_dex_items`, `champions_dex_learnsets`
- `champions_team_pokemon` — replaces `hp_ev/atk_ev/...` with `hp_sp/atk_sp/...` (0-32 each, 66 total cap)
- `teams` table is reusable with `format` column distinguishing Champions formats

Rationale: separate tables guarantee Champions data can never corrupt Gen 9 data. Migration is simpler (`CREATE TABLE IF NOT EXISTS`, no `ALTER TABLE`). The EV-based spread columns physically cannot represent Stat Points.

### Damage Calculator: Dual Backend Protocol

`calc_backend` on FormatConfig routes to the appropriate engine:
- Gen 9: existing `@smogon/calc` Node.js subprocess (unchanged)
- Champions: new Python-native calculator module

Champions stat formula (Scout-confirmed):
```python
def calculate_stat_champions(base: int, sp: int, level: int = 50) -> int:
    return math.floor((2 * base) * level / 100) + level + 10 + sp
```

Nature multiplier behavior must be verified against Porygon Labs before shipping.

### MCP Tools: Separate Champions Modules

New tool modules with Champions-native schemas:
- `tools/champions_calculator.py` — `calculate_champions_stats`, `calculate_champions_damage`
- `tools/champions_pokedex.py` — Champions dex lookups
- Input schemas use `stat_points` (0-32), no `tera_type`, no `iv` fields

Existing Gen 9 tools remain untouched. No `game` parameter on Gen 9 tools.

### Agent System Prompts

Multi-agent teambuilder prompts updated for Champions:
- Sparse-data operating mode: fall back to pokedex/base stats when usage stats unavailable
- Explicit "no Champions data yet" responses rather than Gen 9 fallback
- Guardrails rewritten to handle empty `get_top_pokemon` gracefully

## Risk Assessment

### Mitigated Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Data collision (Champions overwrites Gen 9) | Critical | Separate table sets — disjoint by design |
| Calculator fragility (@smogon/calc on Champions data) | Critical | `calc_backend` routing, separate tools |
| Agent hallucination (Gen 9 data for Champions queries) | High | Game scoping + prompt guardrails in Phase 0 |
| Silent data loss (pokedex DELETE+reinsert) | High | Transactional wrapper prerequisite |
| Sparse launch-window stats as valid data | Critical | `min_battles` threshold gate |

### Accepted Risks

| Risk | Severity | Acceptance Rationale |
|------|----------|---------------------|
| Python calc accuracy without @smogon/calc verification | Medium | Formula is simpler than Gen 9; hardcoded test suite + Porygon Labs cross-validation sufficient |
| No Smogon chaos JSON for Champions (unknown timeline) | Medium | Plan for Pikalytics as primary source; Smogon support is bonus, not dependency |
| Third-party data source instability | Medium | No API integrations — all sources are fetch-and-store with circuit breakers |

## Data Source Strategy

### Confirmed Sources (Scout research)
- **Pikalytics** (`pikalytics.com/champions`) — Primary target for ladder usage stats. Expected late April/early May 2026.
- **Pokemon-Zone** (`pokemon-zone.com/champions`) — Tournament-sourced usage data, available now for Reg M-A.

### Validation References Only (no API integration)
- **Porygon Labs** (`porygonlabs.com`) — Champions damage calc, use to verify Python calc accuracy
- **Champions Lab** (`championslab.xyz`) — Simulation data, no public API

### Not Available
- **Smogon chaos JSON** — Showdown doesn't implement Champions. No timeline.
- **@smogon/calc** — No Champions support in 0.11.0. No roadmap entry.
- **Official TPC API** — Does not exist. In-game ladder data not externally accessible.

## Quality Strategy

### Prerequisites (ship before Champions work)
1. **Transactional pokedex refresh** — wrap `fetch_and_store_pokedex_all` DELETE+inserts in single BEGIN/COMMIT with rollback
2. **`min_battles` threshold** — configurable per FormatConfig, gate in `store_snapshot_data`

### Champions Calc Requirements
- Test suite with hardcoded expected outputs for boundary SP values (0, 32, 66 total)
- Cross-validation against Porygon Labs for representative damage matchups
- `"verified": false` field on tool responses until community validation
- Remove `@smogon/calc` Node dependency in same PR that adds Champions test suite

## Tension Resolutions

| Tension | Agents | Resolution | Reasoning |
|---------|--------|------------|-----------|
| Shared tables vs separate tables | Architect ↔ Skeptic | Separate tables | Unfixed DELETE+reinsert makes shared tables dangerous; SP columns incompatible with EV schema |
| `game` param on tools vs separate modules | Oracle ↔ Architect | Separate modules reading FormatConfig | Structurally incompatible input schemas (SP vs EVs, no Tera) make shared tools a footgun for LLMs |
| Build architecture now vs wait for data | Strategist ↔ Oracle | Phase 0 = scaffolding only | Game scoping + prompt guardrails are zero-data work; calc/pipeline defer until data source confirmed |
| Python calc risk without verification oracle | Skeptic ↔ All | Accept with test suite gate | Champions formula is simpler than Gen 9; hardcoded fixtures + Porygon Labs cross-check sufficient |

## Decision Log

| Decision | Options Considered | Chosen | Reasoning |
|----------|-------------------|--------|-----------|
| Champions data isolation | `game` column on shared tables, separate table sets, separate database file | Separate table sets | Zero corruption risk, simpler migration, EV columns can't represent SP |
| MCP tool surface | `game` param on existing tools, separate tool modules | Separate tool modules | Incompatible input schemas, cleaner LLM experience |
| Damage calculator | Wait for @smogon/calc, integrate Porygon Labs API, build Python calc | Build Python calc | No @smogon/calc roadmap, no public Porygon API, formula is simple |
| Phasing strategy | Big bang, incremental 4-phase | 4-phase (Reg I → Pokedex → Calc → Meta) | Each phase has a clear gate; Phase 1 blocked on data source confirmation |
| Third-party data source | Smogon-only, Pikalytics, multi-source | Pikalytics primary, Pokemon-Zone secondary | Only sources with Champions commitment; Smogon has no timeline |
