## Architect Final Position — Pokemon Champions Format Integration

**Revised recommendation:** `FormatConfig` gains two independent discriminators (`stat_system` and `calc_backend`) as the single source of routing truth; Oracle's separate tool modules (`calculate_champions_damage`, `calculate_champions_stats`) are the correct MCP surface, and those tools should read `FormatConfig` to route internally — these two positions are not in conflict. All Champions database tables are fully separate from Gen 9 tables. Transaction safety on the pokedex pipeline ships before any Champions table work.

**Concessions made:**

- **`game` column → separate tables (deferred to Skeptic + Scout):** The schema isolation argument is correct given the unfixed transaction safety on `fetcher/pokedex.py`. `champions_dex_pokemon`, `champions_dex_moves`, `champions_dex_abilities`, `champions_dex_items`, `champions_dex_learnsets` are new tables, not columns on existing ones. Likewise `champions_teams`, `champions_team_pokemon` — because Scout correctly notes `team_pokemon` can't represent SP values in its current schema. The Gen 9 tables are untouched.

- **Build order (deferred to Strategist):** I originally led with schema design. Strategist's phasing is correct: data source must be confirmed before building a pipeline. Phase 0 is Reg I registration + `FormatConfig` `stat_system`/`calc_backend` fields + prompt guardrails that distinguish Gen 9 from Champions context. Nothing else ships in Phase 0.

- **Separate tool modules (concede to Oracle):** Input schemas are structurally incompatible — `calculate_damage` expects `tera_type`, EVs (0-252, 508 total), IVs; Champions accepts SP (0-32, 66 total), no Tera, presumably no natures. Passing a `format` parameter that silently changes which fields are valid is a footgun. Separate tool modules with distinct input schemas are the right call. `calculate_champions_stats` and `calculate_champions_damage` are first-class MCP tools.

**Non-negotiables:**

1. **`FormatConfig` is the routing authority.** `stat_system: Literal["gen9_ev_iv", "champions_sp"]` and `calc_backend: Literal["smogon_calc_gen9", "python_native"]` must be declared on the config, not inferred at call sites. The separate Champions tool modules read these fields; they do not hardcode their own routing logic.

2. **Transaction safety before Champions schema work.** `fetch_and_store_pokedex_all` must wrap all DELETE+insert operations in a single `BEGIN`/`COMMIT` with rollback on any fetch failure before any Champions table migration runs. Non-negotiable ordering.

3. **Champions calc ships with a test suite.** The stat formula Scout confirmed — `floor((2*Base) * Level/100) + Level + 10 + SP` — is simple enough to verify against manual in-game values before shipping. A `tests/test_champions_calc.py` with at least 10 known-good (pokemon, SP, expected_stat) fixtures is a prerequisite, not a follow-up.

4. **Champions tool responses carry an uncertainty label until validated.** The `calculate_champions_damage` tool output must include a `"verified": false` field until community diffing against in-game results confirms accuracy. This is surfaced to the LLM caller, not hidden.

**Implementation notes:**

```python
# FormatConfig additions
@dataclass
class FormatConfig:
    ...
    generation: int = 9                           # game generation number
    stat_system: Literal["gen9_ev_iv", "champions_sp"] = "gen9_ev_iv"
    calc_backend: Literal["smogon_calc_gen9", "python_native"] = "smogon_calc_gen9"
```

Champions stat formula (Scout-confirmed):
```python
def calculate_stat_champions(base: int, sp: int, level: int = 50) -> int:
    """Champions SP formula. No IVs, no natures. SP range: 0-32, total cap: 66."""
    return math.floor((2 * base) * level / 100) + level + 10 + sp
```

HP uses the same formula — unlike Gen 9 where HP has a different formula, Champions unifies stat calculation. This needs confirmation before shipping.

Schema additions (Phase 1, after data source confirmed):
```sql
CREATE TABLE IF NOT EXISTS champions_dex_pokemon (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    type1 TEXT NOT NULL,
    type2 TEXT,
    hp INTEGER, atk INTEGER, def INTEGER,
    spa INTEGER, spd INTEGER, spe INTEGER,
    ability1 TEXT, ability2 TEXT, ability_hidden TEXT,
    height_m REAL, weight_kg REAL
);

CREATE TABLE IF NOT EXISTS champions_team_pokemon (
    id INTEGER PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    slot INTEGER NOT NULL,
    pokemon TEXT NOT NULL,
    item TEXT,
    ability TEXT,
    -- SP values: 0-32 each, total max 66
    hp_sp INTEGER DEFAULT 0,
    atk_sp INTEGER DEFAULT 0,
    def_sp INTEGER DEFAULT 0,
    spa_sp INTEGER DEFAULT 0,
    spd_sp INTEGER DEFAULT 0,
    spe_sp INTEGER DEFAULT 0,
    move1 TEXT, move2 TEXT, move3 TEXT, move4 TEXT,
    UNIQUE(team_id, slot)
);
```

The `teams` table itself can be reused with `format` column distinguishing Champions formats — only the per-pokemon slot table needs Champions-specific columns.
