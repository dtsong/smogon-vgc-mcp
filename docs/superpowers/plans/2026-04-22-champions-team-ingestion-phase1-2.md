# Champions Team Ingestion — Phase 1+2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working Champions team ingestion pipeline for Tier-1 (pokepaste) URLs, seeded by the Champions Google Sheet tab, with deterministic validator + normalizer foundation that Tiers 2/3 will build on.

**Architecture:** Parallel `champions_teams` / `champions_team_pokemon` tables with Stat Points (SP) storage. Classifier routes URLs to tier handlers; handlers produce `ChampionsTeamDraft` objects; normalizer + validator decide auto-write vs. queue-for-review. Sheet extension branches on URL shape so pokepaste rows auto-land while X/blog rows get queued as `parse_failed` until later phases.

**Tech Stack:** Python 3.11+, aiosqlite, existing `fetch_text_resilient`, pytest-asyncio, ruff. No new external deps this phase.

**Spec:** `docs/superpowers/specs/2026-04-22-champions-team-ingestion-design.md`

**Scope:** Phases 1 (foundation) + 2 (Tier 1 + sheet + reactive CLI) from the spec. Phases 3 (Tier 2), 4 (Tier 3 + X + blog), 5 (audit), 6 (labeler queue) will each get their own plan after this ships.

---

## File Map

**New files:**
- `src/smogon_vgc_mcp/database/champions_team_queries.py` — CRUD + write-or-queue routing
- `src/smogon_vgc_mcp/fetcher/ingestion/__init__.py` — package marker (empty)
- `src/smogon_vgc_mcp/fetcher/ingestion/normalizer.py` — alias + fuzzy-match pass
- `src/smogon_vgc_mcp/fetcher/ingestion/validator.py` — ValidationReport + checks
- `src/smogon_vgc_mcp/fetcher/ingestion/classifier.py` — URL → Tier enum
- `src/smogon_vgc_mcp/fetcher/ingestion/tier1_pokepaste.py` — Tier 1 handler
- `src/smogon_vgc_mcp/fetcher/ingestion/pipeline.py` — orchestrator
- `src/smogon_vgc_mcp/entry/ingest_cli.py` — `vgc-ingest <url>` CLI
- `tests/test_champions_team_schema.py`
- `tests/test_ingestion_normalizer.py`
- `tests/test_ingestion_validator.py`
- `tests/test_ingestion_classifier.py`
- `tests/test_ingestion_tier1.py`
- `tests/test_ingestion_pipeline.py`
- `tests/test_champions_team_queries.py`
- `tests/test_ingestion_cli.py`
- `tests/fixtures/champions_pokepaste_sample.txt`

**Modified files:**
- `src/smogon_vgc_mcp/database/schema.py` — add migration function + tables + register in `init_database`
- `src/smogon_vgc_mcp/database/models.py` — add `ChampionsTeam` + `ChampionsTeamPokemon`
- `src/smogon_vgc_mcp/formats.py` — set `champions_ma.sheet_gid = "791705272"`
- `src/smogon_vgc_mcp/fetcher/sheets.py` — add `ingest_champions_sheet` that branches by URL shape
- `pyproject.toml` — add `vgc-ingest` console script entry

---

## Task 1: Schema + migration for `champions_teams` / `champions_team_pokemon`

**Files:**
- Modify: `src/smogon_vgc_mcp/database/schema.py`
- Create: `tests/test_champions_team_schema.py`

- [ ] **Step 1: Write the failing schema test**

Create `tests/test_champions_team_schema.py`:

```python
from pathlib import Path

import pytest
from smogon_vgc_mcp.database.schema import get_connection, init_database


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    await init_database(db_path)
    async with get_connection(db_path) as conn:
        yield conn


async def test_champions_teams_table_created(db):
    async with db.execute("PRAGMA table_info(champions_teams)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    assert {
        "id", "format", "team_id", "description", "owner",
        "source_type", "source_url", "ingestion_status",
        "confidence_score", "review_reasons", "normalizations", "ingested_at",
    } <= cols


async def test_champions_team_pokemon_table_created(db):
    async with db.execute("PRAGMA table_info(champions_team_pokemon)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    assert {
        "id", "team_id", "slot", "pokemon", "item", "ability", "nature",
        "tera_type", "level",
        "sp_hp", "sp_atk", "sp_def", "sp_spa", "sp_spd", "sp_spe",
        "move1", "move2", "move3", "move4",
    } <= cols


async def test_sp_constraints_enforced(db):
    await db.execute(
        "INSERT INTO champions_teams(format, team_id, source_type, source_url, "
        "ingestion_status, confidence_score) VALUES "
        "('champions_ma', 't1', 'pokepaste', 'https://x', 'auto', 1.0)"
    )
    # Per-stat > 32 must fail
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO champions_team_pokemon(team_id, slot, pokemon, sp_hp) "
            "VALUES (1, 1, 'Flutter Mane', 33)"
        )


async def test_sp_total_constraint_enforced(db):
    await db.execute(
        "INSERT INTO champions_teams(format, team_id, source_type, source_url, "
        "ingestion_status, confidence_score) VALUES "
        "('champions_ma', 't2', 'pokepaste', 'https://x', 'auto', 1.0)"
    )
    # Sum > 66 must fail: 32 + 32 + 10 = 74
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO champions_team_pokemon(team_id, slot, pokemon, "
            "sp_hp, sp_atk, sp_def) VALUES (1, 1, 'Koraidon', 32, 32, 10)"
        )
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_champions_team_schema.py -v
```
Expected: FAIL — tables don't exist.

- [ ] **Step 3: Add schema DDL + migration**

Append to `src/smogon_vgc_mcp/database/schema.py` (before `async def init_database`):

```python
CHAMPIONS_TEAMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS champions_teams (
    id INTEGER PRIMARY KEY,
    format TEXT NOT NULL DEFAULT 'champions_ma',
    team_id TEXT NOT NULL,
    description TEXT,
    owner TEXT,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    ingestion_status TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    review_reasons TEXT,
    normalizations TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(format, team_id)
);

CREATE TABLE IF NOT EXISTS champions_team_pokemon (
    id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES champions_teams(id) ON DELETE CASCADE,
    slot INTEGER NOT NULL,
    pokemon TEXT NOT NULL,
    item TEXT,
    ability TEXT,
    nature TEXT,
    tera_type TEXT,
    level INTEGER DEFAULT 50,
    sp_hp INTEGER DEFAULT 0,
    sp_atk INTEGER DEFAULT 0,
    sp_def INTEGER DEFAULT 0,
    sp_spa INTEGER DEFAULT 0,
    sp_spd INTEGER DEFAULT 0,
    sp_spe INTEGER DEFAULT 0,
    move1 TEXT,
    move2 TEXT,
    move3 TEXT,
    move4 TEXT,
    UNIQUE(team_id, slot),
    CHECK(sp_hp BETWEEN 0 AND 32),
    CHECK(sp_atk BETWEEN 0 AND 32),
    CHECK(sp_def BETWEEN 0 AND 32),
    CHECK(sp_spa BETWEEN 0 AND 32),
    CHECK(sp_spd BETWEEN 0 AND 32),
    CHECK(sp_spe BETWEEN 0 AND 32),
    CHECK(sp_hp + sp_atk + sp_def + sp_spa + sp_spd + sp_spe <= 66),
    CHECK(slot BETWEEN 1 AND 6)
);

CREATE INDEX IF NOT EXISTS idx_champions_teams_format ON champions_teams(format);
CREATE INDEX IF NOT EXISTS idx_champions_teams_source ON champions_teams(source_type);
CREATE INDEX IF NOT EXISTS idx_champions_teams_status ON champions_teams(ingestion_status);
CREATE INDEX IF NOT EXISTS idx_champions_team_pokemon_pokemon ON champions_team_pokemon(pokemon);
CREATE INDEX IF NOT EXISTS idx_champions_team_pokemon_team_id ON champions_team_pokemon(team_id);
"""


async def migrate_add_champions_teams_tables(db: aiosqlite.Connection) -> None:
    """Create champions_teams + champions_team_pokemon. Safe on every startup."""
    await db.executescript(CHAMPIONS_TEAMS_SCHEMA)
    await db.commit()
```

Then inside `init_database(...)`, after the existing migration calls, add:

```python
    await migrate_add_champions_teams_tables(db)
```

Also at the top of `init_database` where foreign keys are enabled, ensure `PRAGMA foreign_keys = ON` is set (it already is for aiosqlite default — verify and leave).

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_champions_team_schema.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/database/schema.py tests/test_champions_team_schema.py
git commit -m "feat(db): champions_teams + champions_team_pokemon tables with SP constraints"
```

---

## Task 2: Data models — `ChampionsTeam`, `ChampionsTeamPokemon`, `ChampionsTeamDraft`

**Files:**
- Modify: `src/smogon_vgc_mcp/database/models.py`
- Test: inline type check via the query tests in Task 8

- [ ] **Step 1: Add dataclasses**

Append to `src/smogon_vgc_mcp/database/models.py`:

```python
@dataclass
class ChampionsTeamPokemon:
    """A Pokemon on a Champions team (Stat Points, not EVs/IVs)."""

    slot: int
    pokemon: str
    item: str | None = None
    ability: str | None = None
    nature: str | None = None
    tera_type: str | None = None
    level: int = 50
    sp_hp: int = 0
    sp_atk: int = 0
    sp_def: int = 0
    sp_spa: int = 0
    sp_spd: int = 0
    sp_spe: int = 0
    move1: str | None = None
    move2: str | None = None
    move3: str | None = None
    move4: str | None = None


@dataclass
class ChampionsTeam:
    """A Champions team as stored in champions_teams."""

    team_id: str
    source_type: str              # 'sheet' | 'pokepaste' | 'x' | 'blog'
    source_url: str
    ingestion_status: str         # 'auto' | 'review_pending' | 'labeled' | 'fetch_failed' | 'parse_failed'
    confidence_score: float
    format: str = "champions_ma"
    description: str | None = None
    owner: str | None = None
    review_reasons: list[str] | None = None
    normalizations: list[str] | None = None
    pokemon: list[ChampionsTeamPokemon] = field(default_factory=list)


@dataclass
class ChampionsTeamDraft:
    """In-flight team from an extractor before validation/write."""

    source_type: str
    source_url: str
    tier_baseline_confidence: float
    description: str | None = None
    owner: str | None = None
    pokemon: list[ChampionsTeamPokemon] = field(default_factory=list)
```

Ensure `from dataclasses import dataclass, field` is in the imports.

- [ ] **Step 2: Run existing model tests**

```bash
uv run pytest tests/ -q --ignore=tests/integration -k "model"
```
Expected: PASS (no regressions).

- [ ] **Step 3: Commit**

```bash
git add src/smogon_vgc_mcp/database/models.py
git commit -m "feat(models): ChampionsTeam/ChampionsTeamPokemon/ChampionsTeamDraft dataclasses"
```

---

## Task 3: `ValidationReport` + SP numeric checks

**Files:**
- Create: `src/smogon_vgc_mcp/fetcher/ingestion/__init__.py` (empty)
- Create: `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`
- Create: `tests/test_ingestion_validator.py`

- [ ] **Step 1: Write failing tests for SP checks**

Create `tests/test_ingestion_validator.py`:

```python
from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon
from smogon_vgc_mcp.fetcher.ingestion.validator import validate


def _draft(*pokes: ChampionsTeamPokemon) -> ChampionsTeamDraft:
    return ChampionsTeamDraft(
        source_type="pokepaste",
        source_url="https://pokepast.es/x",
        tier_baseline_confidence=1.0,
        pokemon=list(pokes),
    )


def test_valid_team_passes():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="Koraidon", sp_atk=32, sp_spe=32)))
    assert rep.passed
    assert rep.hard_failures == []


def test_sp_over_per_stat_flagged():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="X", sp_atk=33)))
    assert not rep.passed
    assert "sp_over_per_stat" in rep.hard_failures


def test_sp_over_total_flagged():
    rep = validate(_draft(ChampionsTeamPokemon(
        slot=1, pokemon="X", sp_hp=32, sp_atk=32, sp_def=10,
    )))
    assert not rep.passed
    assert "sp_over_total" in rep.hard_failures


def test_sp_negative_flagged():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="X", sp_atk=-1)))
    assert not rep.passed
    assert "sp_negative" in rep.hard_failures


def test_boundary_32_ok():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="X", sp_atk=32)))
    assert "sp_over_per_stat" not in rep.hard_failures


def test_boundary_66_total_ok():
    # 11 each across 6 stats = 66
    rep = validate(_draft(ChampionsTeamPokemon(
        slot=1, pokemon="X",
        sp_hp=11, sp_atk=11, sp_def=11, sp_spa=11, sp_spd=11, sp_spe=11,
    )))
    assert "sp_over_total" not in rep.hard_failures
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: FAIL (`ModuleNotFoundError: smogon_vgc_mcp.fetcher.ingestion`).

- [ ] **Step 3: Implement validator module**

Create `src/smogon_vgc_mcp/fetcher/ingestion/__init__.py` (empty file).

Create `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`:

```python
"""Deterministic validator for Champions team drafts.

Runs on every extracted team. Pure functions — no network, no LLM.
Emits a ValidationReport with hard/soft failure reason codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon

SP_PER_STAT_MAX = 32
SP_TOTAL_MAX = 66


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    hard_failures: list[str] = field(default_factory=list)
    soft_failures: list[str] = field(default_factory=list)
    normalizations: list[str] = field(default_factory=list)


def _check_sp_numeric(poke: ChampionsTeamPokemon) -> list[str]:
    """Return list of reason codes for this Pokemon's SP values."""
    sp_values = [poke.sp_hp, poke.sp_atk, poke.sp_def, poke.sp_spa, poke.sp_spd, poke.sp_spe]
    reasons: list[str] = []
    if any(v < 0 for v in sp_values):
        reasons.append("sp_negative")
    if any(v > SP_PER_STAT_MAX for v in sp_values):
        reasons.append("sp_over_per_stat")
    if sum(sp_values) > SP_TOTAL_MAX:
        reasons.append("sp_over_total")
    return reasons


def validate(draft: ChampionsTeamDraft) -> ValidationReport:
    """Validate a team draft. Returns a ValidationReport."""
    hard: list[str] = []
    soft: list[str] = []

    for poke in draft.pokemon:
        for code in _check_sp_numeric(poke):
            if code not in hard:
                hard.append(code)

    return ValidationReport(
        passed=not hard,
        hard_failures=hard,
        soft_failures=soft,
    )
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/__init__.py src/smogon_vgc_mcp/fetcher/ingestion/validator.py tests/test_ingestion_validator.py
git commit -m "feat(validator): ValidationReport + SP numeric checks (per-stat, total, negative)"
```

---

## Task 4: Team-level checks (slot_count, duplicate_species)

**Files:**
- Modify: `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`
- Modify: `tests/test_ingestion_validator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ingestion_validator.py`:

```python
def test_empty_team_flagged():
    rep = validate(_draft())
    assert "slot_count" in rep.hard_failures


def test_seven_slots_flagged():
    pokes = [ChampionsTeamPokemon(slot=i, pokemon=f"P{i}") for i in range(1, 8)]
    rep = validate(_draft(*pokes))
    assert "slot_count" in rep.hard_failures


def test_six_slots_ok():
    pokes = [ChampionsTeamPokemon(slot=i, pokemon=f"P{i}") for i in range(1, 7)]
    rep = validate(_draft(*pokes))
    assert "slot_count" not in rep.hard_failures


def test_duplicate_species_flagged():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"),
        ChampionsTeamPokemon(slot=2, pokemon="Flutter Mane"),
    ))
    assert "duplicate_species" in rep.hard_failures


def test_species_clause_case_insensitive():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"),
        ChampionsTeamPokemon(slot=2, pokemon="flutter mane"),
    ))
    assert "duplicate_species" in rep.hard_failures
```

- [ ] **Step 2: Run — expect fail**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: new tests FAIL.

- [ ] **Step 3: Implement team-level checks**

Modify `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`. Replace the `validate` function with:

```python
def _check_team_shape(pokes: list[ChampionsTeamPokemon]) -> list[str]:
    reasons: list[str] = []
    if not (1 <= len(pokes) <= 6):
        reasons.append("slot_count")
    names_cf = [p.pokemon.casefold() for p in pokes]
    if len(set(names_cf)) != len(names_cf):
        reasons.append("duplicate_species")
    return reasons


def validate(draft: ChampionsTeamDraft) -> ValidationReport:
    """Validate a team draft. Returns a ValidationReport."""
    hard: list[str] = []
    soft: list[str] = []

    for code in _check_team_shape(draft.pokemon):
        if code not in hard:
            hard.append(code)

    for poke in draft.pokemon:
        for code in _check_sp_numeric(poke):
            if code not in hard:
                hard.append(code)

    return ValidationReport(
        passed=not hard,
        hard_failures=hard,
        soft_failures=soft,
    )
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/validator.py tests/test_ingestion_validator.py
git commit -m "feat(validator): slot_count + duplicate_species team-level checks"
```

---

## Task 5: Dex-dependent checks (pokemon_unknown, ability_illegal, move_illegal)

**Files:**
- Modify: `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`
- Modify: `tests/test_ingestion_validator.py`

- [ ] **Step 1: Write failing tests with fake dex lookup**

Append to `tests/test_ingestion_validator.py`:

```python
FAKE_DEX = {
    "flutter mane": {
        "abilities": ["Protosynthesis"],
        "moves": ["Moonblast", "Shadow Ball", "Protect", "Dazzling Gleam", "Icy Wind"],
    },
    "koraidon": {
        "abilities": ["Orichalcum Pulse"],
        "moves": ["Flare Blitz", "Collision Course", "Protect", "Dragon Claw"],
    },
}


def test_pokemon_unknown_flagged():
    rep = validate(
        _draft(ChampionsTeamPokemon(slot=1, pokemon="Fake Pokemon")),
        dex_lookup=FAKE_DEX,
    )
    assert "pokemon_unknown" in rep.hard_failures


def test_ability_illegal_flagged_as_soft():
    rep = validate(
        _draft(ChampionsTeamPokemon(
            slot=1, pokemon="Flutter Mane", ability="Levitate",
        )),
        dex_lookup=FAKE_DEX,
    )
    assert "ability_illegal" in rep.soft_failures
    assert rep.passed  # soft failures don't fail the report


def test_move_illegal_flagged_as_soft():
    rep = validate(
        _draft(ChampionsTeamPokemon(
            slot=1, pokemon="Flutter Mane",
            move1="Flare Blitz",  # not in Flutter Mane learnset
        )),
        dex_lookup=FAKE_DEX,
    )
    assert "move_illegal" in rep.soft_failures


def test_legal_ability_and_moves_ok():
    rep = validate(
        _draft(ChampionsTeamPokemon(
            slot=1, pokemon="Flutter Mane",
            ability="Protosynthesis",
            move1="Moonblast", move2="Shadow Ball", move3="Protect", move4="Icy Wind",
        )),
        dex_lookup=FAKE_DEX,
    )
    assert "ability_illegal" not in rep.soft_failures
    assert "move_illegal" not in rep.soft_failures
```

- [ ] **Step 2: Run — expect fail**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: new tests FAIL (`dex_lookup` kwarg unknown).

- [ ] **Step 3: Implement dex-dependent checks**

Modify `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`. Extend `validate` and add helpers:

```python
DexLookup = dict[str, dict[str, list[str]]]  # name_casefold -> {"abilities": [...], "moves": [...]}


def _check_pokemon_identity(poke: ChampionsTeamPokemon, dex: DexLookup | None) -> list[str]:
    if dex is None:
        return []
    if poke.pokemon.casefold() not in dex:
        return ["pokemon_unknown"]
    return []


def _check_ability_and_moves(
    poke: ChampionsTeamPokemon, dex: DexLookup | None
) -> list[str]:
    if dex is None:
        return []
    entry = dex.get(poke.pokemon.casefold())
    if entry is None:
        return []
    soft: list[str] = []
    if poke.ability and poke.ability not in entry["abilities"]:
        soft.append("ability_illegal")
    moves = [poke.move1, poke.move2, poke.move3, poke.move4]
    for move in moves:
        if move and move not in entry["moves"]:
            soft.append("move_illegal")
            break
    return soft


def validate(
    draft: ChampionsTeamDraft,
    *,
    dex_lookup: DexLookup | None = None,
) -> ValidationReport:
    hard: list[str] = []
    soft: list[str] = []

    for code in _check_team_shape(draft.pokemon):
        if code not in hard:
            hard.append(code)

    for poke in draft.pokemon:
        for code in _check_sp_numeric(poke):
            if code not in hard:
                hard.append(code)
        for code in _check_pokemon_identity(poke, dex_lookup):
            if code not in hard:
                hard.append(code)
        for code in _check_ability_and_moves(poke, dex_lookup):
            if code not in soft:
                soft.append(code)

    return ValidationReport(
        passed=not hard,
        hard_failures=hard,
        soft_failures=soft,
    )
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/validator.py tests/test_ingestion_validator.py
git commit -m "feat(validator): dex-dependent checks (pokemon_unknown, ability_illegal, move_illegal)"
```

---

## Task 6: Vocabulary + move count checks

**Files:**
- Modify: `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`
- Modify: `tests/test_ingestion_validator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ingestion_validator.py`:

```python
def test_nature_unknown_soft():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="X", nature="Weird"),
    ))
    assert "nature_unknown" in rep.soft_failures


def test_nature_known_ok():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="X", nature="Timid"),
    ))
    assert "nature_unknown" not in rep.soft_failures


def test_tera_type_unknown_soft():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="X", tera_type="Banana"),
    ))
    assert "tera_type_unknown" in rep.soft_failures


def test_tera_type_none_ok():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="X", tera_type=None),
    ))
    assert "tera_type_unknown" not in rep.soft_failures


def test_move_count_zero_soft():
    # no moves at all
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="X")))
    assert "move_count" in rep.soft_failures


def test_move_count_four_ok():
    rep = validate(_draft(ChampionsTeamPokemon(
        slot=1, pokemon="X",
        move1="a", move2="b", move3="c", move4="d",
    )))
    assert "move_count" not in rep.soft_failures
```

- [ ] **Step 2: Run — expect fail**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: new tests FAIL.

- [ ] **Step 3: Implement vocabulary + move count checks**

Append constants and extend `validate` in `src/smogon_vgc_mcp/fetcher/ingestion/validator.py`:

```python
NATURES = frozenset({
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
})

TYPES = frozenset({
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
})


def _check_vocab_and_moves(poke: ChampionsTeamPokemon) -> list[str]:
    soft: list[str] = []
    if poke.nature is not None and poke.nature not in NATURES:
        soft.append("nature_unknown")
    if poke.tera_type is not None and poke.tera_type not in TYPES:
        soft.append("tera_type_unknown")
    moves = [m for m in (poke.move1, poke.move2, poke.move3, poke.move4) if m]
    if not (1 <= len(moves) <= 4):
        soft.append("move_count")
    return soft
```

Then in `validate`, add after the existing per-poke loop body:

```python
        for code in _check_vocab_and_moves(poke):
            if code not in soft:
                soft.append(code)
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_validator.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/validator.py tests/test_ingestion_validator.py
git commit -m "feat(validator): vocabulary + move_count soft checks"
```

---

## Task 7: Normalizer (Pokemon aliases, move fuzzy, nature/tera title-case)

**Files:**
- Create: `src/smogon_vgc_mcp/fetcher/ingestion/normalizer.py`
- Create: `tests/test_ingestion_normalizer.py`

- [ ] **Step 1: Write failing normalizer tests**

Create `tests/test_ingestion_normalizer.py`:

```python
from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon
from smogon_vgc_mcp.fetcher.ingestion.normalizer import normalize


def _draft(*pokes: ChampionsTeamPokemon) -> ChampionsTeamDraft:
    return ChampionsTeamDraft(
        source_type="pokepaste",
        source_url="https://x",
        tier_baseline_confidence=1.0,
        pokemon=list(pokes),
    )


def test_pokemon_alias_expanded():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="urshifu-s"))
    normed, log = normalize(d)
    assert normed.pokemon[0].pokemon == "Urshifu-Single-Strike"
    assert any("pokemon_alias" in entry for entry in log)


def test_move_fuzzy_match_distance_2():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", move1="Close Combatt"))
    known_moves = {"Close Combat", "Moonblast", "Protect"}
    normed, log = normalize(d, known_moves=known_moves)
    assert normed.pokemon[0].move1 == "Close Combat"
    assert any("move_fuzzy" in entry for entry in log)


def test_move_fuzzy_no_match_left_alone():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", move1="Completely Unknown"))
    normed, log = normalize(d, known_moves={"Close Combat"})
    assert normed.pokemon[0].move1 == "Completely Unknown"


def test_nature_title_case():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", nature="timid"))
    normed, log = normalize(d)
    assert normed.pokemon[0].nature == "Timid"


def test_tera_title_case():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", tera_type="fairy"))
    normed, log = normalize(d)
    assert normed.pokemon[0].tera_type == "Fairy"


def test_item_strip_consumed():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", item="Focus Sash (consumed)"))
    normed, log = normalize(d)
    assert normed.pokemon[0].item == "Focus Sash"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_ingestion_normalizer.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement normalizer**

Create `src/smogon_vgc_mcp/fetcher/ingestion/normalizer.py`:

```python
"""Deterministic normalizer for Champions team drafts.

Runs before the validator. Fixes common surface-level issues (case,
aliases, whitespace, fuzzy move spelling) and logs every change so
the audit trail can detect LLM drift.
"""

from __future__ import annotations

from dataclasses import replace

from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon

# Minimal alias table — extend as real data exposes gaps. Keys are
# casefolded inputs; values are canonical Pokemon names in the dex.
POKEMON_ALIASES: dict[str, str] = {
    "urshifu-s": "Urshifu-Single-Strike",
    "urshifu-r": "Urshifu-Rapid-Strike",
    "ogerpon-w": "Ogerpon-Wellspring",
    "ogerpon-h": "Ogerpon-Hearthflame",
    "ogerpon-c": "Ogerpon-Cornerstone",
    "landorus-t": "Landorus-Therian",
    "landorus-i": "Landorus-Incarnate",
}


def _levenshtein(a: str, b: str) -> int:
    """Classic iterative Levenshtein distance."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            ins = curr[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]


def _closest_move(name: str, known: set[str]) -> str | None:
    """Return the closest known move within distance 2, else None."""
    best: tuple[int, str] | None = None
    for known_name in known:
        d = _levenshtein(name.casefold(), known_name.casefold())
        if d <= 2 and (best is None or d < best[0]):
            best = (d, known_name)
    return best[1] if best else None


def _normalize_pokemon(
    poke: ChampionsTeamPokemon,
    *,
    known_moves: set[str] | None,
    log: list[str],
) -> ChampionsTeamPokemon:
    updates: dict[str, object] = {}

    alias = POKEMON_ALIASES.get(poke.pokemon.casefold())
    if alias and alias != poke.pokemon:
        log.append(f"pokemon_alias:{poke.pokemon}->{alias}")
        updates["pokemon"] = alias

    if poke.nature:
        title = poke.nature.strip().title()
        if title != poke.nature:
            log.append(f"nature_case:{poke.nature}->{title}")
            updates["nature"] = title

    if poke.tera_type:
        title = poke.tera_type.strip().title()
        if title != poke.tera_type:
            log.append(f"tera_case:{poke.tera_type}->{title}")
            updates["tera_type"] = title

    if poke.item and "(consumed)" in poke.item.casefold():
        stripped = poke.item.replace("(consumed)", "").replace("(Consumed)", "").strip()
        log.append(f"item_strip_consumed:{poke.item}->{stripped}")
        updates["item"] = stripped

    if known_moves:
        for attr in ("move1", "move2", "move3", "move4"):
            current = getattr(poke, attr)
            if not current or current in known_moves:
                continue
            fixed = _closest_move(current, known_moves)
            if fixed and fixed != current:
                log.append(f"move_fuzzy:{current}->{fixed}")
                updates[attr] = fixed

    if not updates:
        return poke
    return replace(poke, **updates)


def normalize(
    draft: ChampionsTeamDraft,
    *,
    known_moves: set[str] | None = None,
) -> tuple[ChampionsTeamDraft, list[str]]:
    """Return a normalized copy of the draft plus a list of change entries."""
    log: list[str] = []
    new_pokes = [
        _normalize_pokemon(p, known_moves=known_moves, log=log) for p in draft.pokemon
    ]
    return replace(draft, pokemon=new_pokes), log
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_normalizer.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/normalizer.py tests/test_ingestion_normalizer.py
git commit -m "feat(normalizer): pokemon aliases + move fuzzy + case-fold normalization"
```

---

## Task 8: Champions team queries (insert, write-or-queue, fingerprint)

**Files:**
- Create: `src/smogon_vgc_mcp/database/champions_team_queries.py`
- Create: `tests/test_champions_team_queries.py`

- [ ] **Step 1: Write failing query tests**

Create `tests/test_champions_team_queries.py`:

```python
import json
from pathlib import Path

import pytest
from smogon_vgc_mcp.database.champions_team_queries import (
    compute_team_fingerprint,
    get_champions_team,
    write_or_queue_team,
)
from smogon_vgc_mcp.database.models import ChampionsTeam, ChampionsTeamPokemon
from smogon_vgc_mcp.database.schema import get_connection, init_database


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


def _team(
    *pokes: ChampionsTeamPokemon,
    status: str = "auto",
    conf: float = 1.0,
    fingerprint: str = "abc123",
) -> ChampionsTeam:
    return ChampionsTeam(
        team_id=fingerprint,
        source_type="pokepaste",
        source_url="https://pokepast.es/abc",
        ingestion_status=status,
        confidence_score=conf,
        pokemon=list(pokes),
    )


async def test_write_auto_team(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="Koraidon", sp_atk=32, sp_spe=32),
        fingerprint="fp1",
    )
    async with get_connection(db_path) as db:
        row_id = await write_or_queue_team(db, team)
        assert row_id > 0
        out = await get_champions_team(db, row_id)
    assert out is not None
    assert out.ingestion_status == "auto"
    assert len(out.pokemon) == 1
    assert out.pokemon[0].pokemon == "Koraidon"


async def test_write_queue_team(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"),
        status="review_pending",
        conf=0.5,
        fingerprint="fp2",
    )
    async with get_connection(db_path) as db:
        row_id = await write_or_queue_team(db, team)
        out = await get_champions_team(db, row_id)
    assert out.ingestion_status == "review_pending"
    assert out.confidence_score == pytest.approx(0.5)


async def test_duplicate_fingerprint_returns_existing(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="Koraidon"),
        fingerprint="dup",
    )
    async with get_connection(db_path) as db:
        id1 = await write_or_queue_team(db, team)
        id2 = await write_or_queue_team(db, team)
    assert id1 == id2


async def test_review_reasons_persisted(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="X"),
        fingerprint="rr",
    )
    team.review_reasons = ["sp_over_total"]
    team.normalizations = ["move_fuzzy:Close Combatt->Close Combat"]
    async with get_connection(db_path) as db:
        row_id = await write_or_queue_team(db, team)
        out = await get_champions_team(db, row_id)
    assert out.review_reasons == ["sp_over_total"]
    assert out.normalizations == ["move_fuzzy:Close Combatt->Close Combat"]


def test_fingerprint_stable_for_same_team():
    team_a = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon", move1="Flare Blitz"))
    team_b = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon", move1="Flare Blitz"))
    assert compute_team_fingerprint(team_a.pokemon) == compute_team_fingerprint(team_b.pokemon)


def test_fingerprint_move_order_insensitive():
    team_a = _team(ChampionsTeamPokemon(
        slot=1, pokemon="X", move1="A", move2="B", move3="C", move4="D"))
    team_b = _team(ChampionsTeamPokemon(
        slot=1, pokemon="X", move1="D", move2="C", move3="B", move4="A"))
    assert compute_team_fingerprint(team_a.pokemon) == compute_team_fingerprint(team_b.pokemon)


def test_fingerprint_different_when_sets_differ():
    team_a = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon"))
    team_b = _team(ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"))
    assert compute_team_fingerprint(team_a.pokemon) != compute_team_fingerprint(team_b.pokemon)
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_champions_team_queries.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement queries**

Create `src/smogon_vgc_mcp/database/champions_team_queries.py`:

```python
"""CRUD + routing for Champions teams."""

from __future__ import annotations

import hashlib
import json

import aiosqlite

from smogon_vgc_mcp.database.models import ChampionsTeam, ChampionsTeamPokemon


def compute_team_fingerprint(pokemon: list[ChampionsTeamPokemon]) -> str:
    """Stable SHA256 of the team's structural content.

    Move order within a set is normalized (sorted) so a team that
    reorders moves doesn't produce a different fingerprint.
    """
    canonical = []
    for p in sorted(pokemon, key=lambda x: (x.slot, x.pokemon.casefold())):
        moves = tuple(sorted(m for m in (p.move1, p.move2, p.move3, p.move4) if m))
        canonical.append(
            (
                p.pokemon.casefold(),
                (p.ability or "").casefold(),
                (p.item or "").casefold(),
                (p.nature or "").casefold(),
                (p.tera_type or "").casefold(),
                p.level,
                p.sp_hp, p.sp_atk, p.sp_def, p.sp_spa, p.sp_spd, p.sp_spe,
                moves,
            )
        )
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    return digest[:16]


async def write_or_queue_team(db: aiosqlite.Connection, team: ChampionsTeam) -> int:
    """Insert the team. Returns the row id. Duplicate (format, team_id) returns existing id."""
    db.row_factory = aiosqlite.Row

    existing = await db.execute_fetchall(
        "SELECT id FROM champions_teams WHERE format = ? AND team_id = ?",
        (team.format, team.team_id),
    )
    if existing:
        return int(existing[0]["id"])

    cursor = await db.execute(
        """
        INSERT INTO champions_teams(
            format, team_id, description, owner, source_type, source_url,
            ingestion_status, confidence_score, review_reasons, normalizations
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            team.format,
            team.team_id,
            team.description,
            team.owner,
            team.source_type,
            team.source_url,
            team.ingestion_status,
            team.confidence_score,
            json.dumps(team.review_reasons) if team.review_reasons else None,
            json.dumps(team.normalizations) if team.normalizations else None,
        ),
    )
    team_row_id = cursor.lastrowid

    for poke in team.pokemon:
        await db.execute(
            """
            INSERT INTO champions_team_pokemon(
                team_id, slot, pokemon, item, ability, nature, tera_type, level,
                sp_hp, sp_atk, sp_def, sp_spa, sp_spd, sp_spe,
                move1, move2, move3, move4
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team_row_id, poke.slot, poke.pokemon, poke.item, poke.ability,
                poke.nature, poke.tera_type, poke.level,
                poke.sp_hp, poke.sp_atk, poke.sp_def, poke.sp_spa, poke.sp_spd, poke.sp_spe,
                poke.move1, poke.move2, poke.move3, poke.move4,
            ),
        )

    await db.commit()
    return int(team_row_id)


async def get_champions_team(db: aiosqlite.Connection, row_id: int) -> ChampionsTeam | None:
    db.row_factory = aiosqlite.Row
    team_row = await db.execute_fetchall(
        "SELECT * FROM champions_teams WHERE id = ?", (row_id,)
    )
    if not team_row:
        return None
    t = team_row[0]

    poke_rows = await db.execute_fetchall(
        "SELECT * FROM champions_team_pokemon WHERE team_id = ? ORDER BY slot",
        (row_id,),
    )
    pokemon = [
        ChampionsTeamPokemon(
            slot=p["slot"], pokemon=p["pokemon"], item=p["item"], ability=p["ability"],
            nature=p["nature"], tera_type=p["tera_type"], level=p["level"],
            sp_hp=p["sp_hp"], sp_atk=p["sp_atk"], sp_def=p["sp_def"],
            sp_spa=p["sp_spa"], sp_spd=p["sp_spd"], sp_spe=p["sp_spe"],
            move1=p["move1"], move2=p["move2"], move3=p["move3"], move4=p["move4"],
        )
        for p in poke_rows
    ]

    return ChampionsTeam(
        team_id=t["team_id"],
        format=t["format"],
        description=t["description"],
        owner=t["owner"],
        source_type=t["source_type"],
        source_url=t["source_url"],
        ingestion_status=t["ingestion_status"],
        confidence_score=t["confidence_score"],
        review_reasons=json.loads(t["review_reasons"]) if t["review_reasons"] else None,
        normalizations=json.loads(t["normalizations"]) if t["normalizations"] else None,
        pokemon=pokemon,
    )
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_champions_team_queries.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/database/champions_team_queries.py tests/test_champions_team_queries.py
git commit -m "feat(db): champions_team_queries with fingerprint dedup"
```

---

## Task 9: URL classifier + Tier enum

**Files:**
- Create: `src/smogon_vgc_mcp/fetcher/ingestion/classifier.py`
- Create: `tests/test_ingestion_classifier.py`

- [ ] **Step 1: Write failing classifier tests**

Create `tests/test_ingestion_classifier.py`:

```python
import pytest
from smogon_vgc_mcp.fetcher.ingestion.classifier import Tier, classify_url


@pytest.mark.parametrize("url, tier", [
    ("https://pokepast.es/abc123", Tier.POKEPASTE),
    ("http://pokepast.es/abc123", Tier.POKEPASTE),
    ("https://pokepast.es/abc123/raw", Tier.POKEPASTE),
    ("https://twitter.com/user/status/12345", Tier.X),
    ("https://x.com/user/status/12345", Tier.X),
    ("https://mobile.twitter.com/user/status/12345", Tier.X),
    ("https://nuggetbridge.com/2016/01/foo", Tier.BLOG),
    ("https://smogon.com/forums/threads/x.12345/", Tier.BLOG),
    ("https://medium.com/@user/my-team", Tier.BLOG),
    ("", Tier.UNKNOWN),
    ("not-a-url", Tier.UNKNOWN),
    ("ftp://example.com/file", Tier.UNKNOWN),
])
def test_classify_url(url: str, tier: Tier):
    assert classify_url(url) == tier
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_ingestion_classifier.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement classifier**

Create `src/smogon_vgc_mcp/fetcher/ingestion/classifier.py`:

```python
"""URL shape classifier for the ingestion pipeline."""

from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse


class Tier(Enum):
    POKEPASTE = "pokepaste"
    X = "x"
    BLOG = "blog"
    UNKNOWN = "unknown"


_POKEPASTE_HOSTS = frozenset({"pokepast.es", "www.pokepast.es"})
_X_HOSTS = frozenset({
    "twitter.com", "www.twitter.com", "mobile.twitter.com",
    "x.com", "www.x.com",
})


def classify_url(url: str) -> Tier:
    """Return the Tier enum for a raw URL string."""
    if not url:
        return Tier.UNKNOWN
    try:
        parsed = urlparse(url)
    except ValueError:
        return Tier.UNKNOWN
    if parsed.scheme not in ("http", "https"):
        return Tier.UNKNOWN
    host = (parsed.netloc or "").casefold()
    if host in _POKEPASTE_HOSTS:
        return Tier.POKEPASTE
    if host in _X_HOSTS:
        return Tier.X
    if host:  # any other http(s) host counts as a generic blog URL
        return Tier.BLOG
    return Tier.UNKNOWN
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_classifier.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/classifier.py tests/test_ingestion_classifier.py
git commit -m "feat(ingestion): URL classifier with Tier enum"
```

---

## Task 10: Tier 1 pokepaste handler

**Files:**
- Create: `src/smogon_vgc_mcp/fetcher/ingestion/tier1_pokepaste.py`
- Create: `tests/fixtures/champions_pokepaste_sample.txt`
- Create: `tests/test_ingestion_tier1.py`

- [ ] **Step 1: Write failing Tier 1 tests**

Create `tests/fixtures/champions_pokepaste_sample.txt`:

```
Koraidon @ Life Orb
Ability: Orichalcum Pulse
Level: 50
Tera Type: Fire
EVs: 32 Atk / 32 Spe
Adamant Nature
- Flare Blitz
- Collision Course
- Protect
- Dragon Claw

Flutter Mane @ Focus Sash
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 32 SpA / 32 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Protect
- Dazzling Gleam
```

Note: EVs lines here are used because existing `parse_pokepaste` expects EV syntax. The Tier 1 handler translates EV numbers directly into SP fields — a pokepaste authored for Champions uses the same `32 Atk / 32 Spe` text shape as Gen 9 but the numbers now mean SP.

Create `tests/test_ingestion_tier1.py`:

```python
from pathlib import Path

import pytest
from smogon_vgc_mcp.fetcher.ingestion.tier1_pokepaste import (
    parse_pokepaste_to_champions_draft,
)


FIXTURE = Path(__file__).parent / "fixtures" / "champions_pokepaste_sample.txt"


def test_tier1_parses_two_pokemon():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(
        text, source_url="https://pokepast.es/fixt"
    )
    assert len(draft.pokemon) == 2
    assert draft.pokemon[0].pokemon == "Koraidon"
    assert draft.pokemon[1].pokemon == "Flutter Mane"


def test_tier1_maps_evs_to_sp():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(
        text, source_url="https://pokepast.es/fixt"
    )
    kor = draft.pokemon[0]
    assert kor.sp_atk == 32
    assert kor.sp_spe == 32
    assert kor.sp_hp == 0


def test_tier1_captures_item_ability_nature_tera():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(
        text, source_url="https://pokepast.es/fixt"
    )
    kor = draft.pokemon[0]
    assert kor.item == "Life Orb"
    assert kor.ability == "Orichalcum Pulse"
    assert kor.nature == "Adamant"
    assert kor.tera_type == "Fire"


def test_tier1_captures_moves():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(
        text, source_url="https://pokepast.es/fixt"
    )
    kor = draft.pokemon[0]
    assert kor.move1 == "Flare Blitz"
    assert kor.move4 == "Dragon Claw"


def test_tier1_sets_source_type_and_baseline_confidence():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(
        text, source_url="https://pokepast.es/fixt"
    )
    assert draft.source_type == "pokepaste"
    assert draft.tier_baseline_confidence == 1.0
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_ingestion_tier1.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement Tier 1 handler**

Create `src/smogon_vgc_mcp/fetcher/ingestion/tier1_pokepaste.py`:

```python
"""Tier 1 pokepaste handler for Champions ingestion.

Reuses the existing pokepaste parser and translates its Gen 9 EV
output directly into Champions SP fields (same numeric values — a
pokepaste authored for Champions uses identical text syntax but the
numbers now represent Stat Points).
"""

from __future__ import annotations

from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon
from smogon_vgc_mcp.fetcher.pokepaste import fetch_pokepaste, parse_pokepaste
from smogon_vgc_mcp.resilience import FetchResult


def parse_pokepaste_to_champions_draft(
    text: str, *, source_url: str,
) -> ChampionsTeamDraft:
    """Parse raw pokepaste text into a ChampionsTeamDraft."""
    parsed = parse_pokepaste(text)
    pokemon = [
        ChampionsTeamPokemon(
            slot=tp.slot,
            pokemon=tp.pokemon,
            item=tp.item,
            ability=tp.ability,
            nature=tp.nature,
            tera_type=tp.tera_type,
            level=50,
            sp_hp=tp.hp_ev,
            sp_atk=tp.atk_ev,
            sp_def=tp.def_ev,
            sp_spa=tp.spa_ev,
            sp_spd=tp.spd_ev,
            sp_spe=tp.spe_ev,
            move1=tp.move1,
            move2=tp.move2,
            move3=tp.move3,
            move4=tp.move4,
        )
        for tp in parsed
    ]
    return ChampionsTeamDraft(
        source_type="pokepaste",
        source_url=source_url,
        tier_baseline_confidence=1.0,
        pokemon=pokemon,
    )


async def fetch_and_parse_pokepaste(url: str) -> FetchResult[ChampionsTeamDraft]:
    """Fetch a pokepaste URL and return a ChampionsTeamDraft."""
    fetched = await fetch_pokepaste(url)
    if not fetched.success or not fetched.data:
        return FetchResult.fail(fetched.error) if fetched.error else FetchResult.ok(None)
    draft = parse_pokepaste_to_champions_draft(fetched.data, source_url=url)
    return FetchResult.ok(draft)
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_tier1.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/tier1_pokepaste.py tests/fixtures/champions_pokepaste_sample.txt tests/test_ingestion_tier1.py
git commit -m "feat(ingestion): Tier 1 pokepaste handler mapping EV syntax to SP"
```

---

## Task 11: Pipeline orchestrator (classify → fetch → normalize → validate → write-or-queue)

**Files:**
- Create: `src/smogon_vgc_mcp/fetcher/ingestion/pipeline.py`
- Create: `tests/test_ingestion_pipeline.py`

- [ ] **Step 1: Write failing orchestrator tests**

Create `tests/test_ingestion_pipeline.py`:

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from smogon_vgc_mcp.database.champions_team_queries import get_champions_team
from smogon_vgc_mcp.database.schema import get_connection, init_database
from smogon_vgc_mcp.fetcher.ingestion.pipeline import IngestResult, ingest_url
from smogon_vgc_mcp.resilience import FetchResult

FIXTURE = Path(__file__).parent / "fixtures" / "champions_pokepaste_sample.txt"


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


async def test_ingest_unknown_url_returns_rejected(db_path: Path):
    result = await ingest_url("not-a-url", db_path=db_path)
    assert result.status == "rejected"
    assert result.reason == "classifier_unknown_tier"
    assert result.team_row_id is None


async def test_ingest_pokepaste_auto_writes(db_path: Path):
    text = FIXTURE.read_text()
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(text)),
    ):
        result = await ingest_url(
            "https://pokepast.es/abc", db_path=db_path
        )
    assert result.status == "auto"
    assert result.team_row_id is not None
    async with get_connection(db_path) as db:
        stored = await get_champions_team(db, result.team_row_id)
    assert stored.ingestion_status == "auto"
    assert stored.confidence_score == pytest.approx(1.0)
    assert len(stored.pokemon) == 2


async def test_ingest_fetch_failure_returns_fetch_failed(db_path: Path):
    from smogon_vgc_mcp.resilience import ErrorCategory, ServiceError

    err = ServiceError(
        category=ErrorCategory.HTTP_CLIENT_ERROR,
        service="pokepaste",
        message="404",
        is_recoverable=False,
    )
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.fail(err)),
    ):
        result = await ingest_url(
            "https://pokepast.es/missing", db_path=db_path
        )
    assert result.status == "fetch_failed"
    assert result.team_row_id is None


async def test_ingest_x_and_blog_not_implemented_yet(db_path: Path):
    result = await ingest_url("https://x.com/u/status/1", db_path=db_path)
    assert result.status == "rejected"
    assert result.reason == "tier_not_implemented"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_ingestion_pipeline.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement pipeline**

Create `src/smogon_vgc_mcp/fetcher/ingestion/pipeline.py`:

```python
"""Top-level ingestion orchestrator.

Routes a URL through the classifier to the appropriate tier handler,
then normalizes, validates, and writes (or queues) the result.

Phases 3-6 will register additional tier handlers by extending
``_TIER_HANDLERS``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from smogon_vgc_mcp.database.champions_team_queries import (
    compute_team_fingerprint,
    write_or_queue_team,
)
from smogon_vgc_mcp.database.models import ChampionsTeam, ChampionsTeamDraft
from smogon_vgc_mcp.database.schema import get_connection
from smogon_vgc_mcp.fetcher.ingestion.classifier import Tier, classify_url
from smogon_vgc_mcp.fetcher.ingestion.normalizer import normalize
from smogon_vgc_mcp.fetcher.ingestion.tier1_pokepaste import (
    parse_pokepaste_to_champions_draft,
)
from smogon_vgc_mcp.fetcher.ingestion.validator import validate
from smogon_vgc_mcp.fetcher.pokepaste import fetch_pokepaste  # re-imported for patchability
from smogon_vgc_mcp.resilience import FetchResult

AUTO_WRITE_THRESHOLD = 0.85


@dataclass(frozen=True)
class IngestResult:
    status: str                    # 'auto' | 'review_pending' | 'fetch_failed' | 'parse_failed' | 'rejected'
    team_row_id: int | None = None
    confidence: float | None = None
    reason: str | None = None


async def _fetch_tier1(url: str) -> FetchResult[ChampionsTeamDraft]:
    fetched = await fetch_pokepaste(url)
    if not fetched.success or not fetched.data:
        return FetchResult.fail(fetched.error) if fetched.error else FetchResult.ok(None)
    draft = parse_pokepaste_to_champions_draft(fetched.data, source_url=url)
    return FetchResult.ok(draft)


def _score(draft: ChampionsTeamDraft, soft_count: int) -> float:
    return max(0.0, draft.tier_baseline_confidence - 0.1 * soft_count)


async def ingest_url(url: str, *, db_path: Path | None = None) -> IngestResult:
    tier = classify_url(url)

    if tier == Tier.UNKNOWN:
        return IngestResult(status="rejected", reason="classifier_unknown_tier")
    if tier in (Tier.X, Tier.BLOG):
        return IngestResult(status="rejected", reason="tier_not_implemented")

    if tier == Tier.POKEPASTE:
        fetched = await _fetch_tier1(url)
    else:
        return IngestResult(status="rejected", reason="tier_not_implemented")

    if not fetched.success:
        return IngestResult(status="fetch_failed", reason=str(fetched.error))
    if fetched.data is None:
        return IngestResult(status="parse_failed", reason="empty_parse")

    draft = fetched.data
    normalized, norm_log = normalize(draft)
    report = validate(normalized)

    if report.hard_failures:
        confidence = 0.0
    else:
        confidence = _score(normalized, len(report.soft_failures))

    status = "auto" if confidence >= AUTO_WRITE_THRESHOLD else "review_pending"

    team = ChampionsTeam(
        team_id=compute_team_fingerprint(normalized.pokemon),
        source_type=normalized.source_type,
        source_url=normalized.source_url,
        ingestion_status=status,
        confidence_score=confidence,
        review_reasons=report.hard_failures + report.soft_failures or None,
        normalizations=norm_log or None,
        pokemon=normalized.pokemon,
    )

    async with get_connection(db_path) as db:
        row_id = await write_or_queue_team(db, team)

    return IngestResult(status=status, team_row_id=row_id, confidence=confidence)
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_pipeline.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/ingestion/pipeline.py tests/test_ingestion_pipeline.py
git commit -m "feat(ingestion): pipeline orchestrator with confidence gate"
```

---

## Task 12: Champions sheet extension + format config

**Files:**
- Modify: `src/smogon_vgc_mcp/formats.py`
- Modify: `src/smogon_vgc_mcp/fetcher/sheets.py`
- Create: `tests/test_sheets_champions.py`

- [ ] **Step 1: Write failing sheet extension test**

Create `tests/test_sheets_champions.py`:

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from smogon_vgc_mcp.database.schema import get_connection, init_database
from smogon_vgc_mcp.fetcher.sheets import ingest_champions_sheet
from smogon_vgc_mcp.resilience import FetchResult


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


MIXED_SHEET_CSV = """Owner,Tournament,Rank,URL
Alice,Regional A,Top 8,https://pokepast.es/abc123
Bob,Regional B,Winner,https://x.com/bob/status/42
Carol,Regional C,Top 4,https://someblog.example/post
"""


async def test_ingest_champions_sheet_routes_by_url_shape(db_path: Path):
    pokepaste_text = "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\nEVs: 32 Atk\nAdamant Nature\n- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"

    with (
        patch(
            "smogon_vgc_mcp.fetcher.sheets.fetch_text_resilient",
            new=AsyncMock(return_value=FetchResult.ok(MIXED_SHEET_CSV)),
        ),
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
            new=AsyncMock(return_value=FetchResult.ok(pokepaste_text)),
        ),
    ):
        report = await ingest_champions_sheet(db_path=db_path)

    # 3 rows: 1 pokepaste (auto), 2 rejected as tier_not_implemented
    assert report["auto"] == 1
    assert report["rejected"] == 2
    assert report["fetch_failed"] == 0
```

- [ ] **Step 2: Run — expect fail**

```bash
uv run pytest tests/test_sheets_champions.py -v
```
Expected: FAIL (`ingest_champions_sheet` missing).

- [ ] **Step 3: Set champions_ma sheet_gid + implement sheet ingestion**

In `src/smogon_vgc_mcp/formats.py`, update `champions_ma` FormatConfig entry to set:

```python
        sheet_gid="791705272",
```

(Leave the rest of the entry as-is.)

Append to `src/smogon_vgc_mcp/fetcher/sheets.py`:

```python
from pathlib import Path

from smogon_vgc_mcp.fetcher.ingestion.pipeline import ingest_url
from smogon_vgc_mcp.formats import get_sheet_csv_url


async def ingest_champions_sheet(db_path: Path | None = None) -> dict[str, int]:
    """Read the Champions Google Sheet tab and ingest each row's URL.

    Returns a counter dict of status -> count.
    """
    sheet_url = get_sheet_csv_url("champions_ma")
    if not sheet_url:
        return {"auto": 0, "review_pending": 0, "rejected": 0, "fetch_failed": 0, "parse_failed": 0}

    fetched = await fetch_text_resilient(sheet_url, service="sheets")
    if not fetched.success or not fetched.data:
        return {"auto": 0, "review_pending": 0, "rejected": 0, "fetch_failed": 1, "parse_failed": 0}

    reader = csv.reader(io.StringIO(fetched.data))
    rows = list(reader)

    counts: dict[str, int] = {
        "auto": 0, "review_pending": 0, "rejected": 0,
        "fetch_failed": 0, "parse_failed": 0,
    }

    for row in rows[1:]:  # skip header
        url = next((c for c in row if c.startswith(("http://", "https://"))), "")
        if not url:
            continue
        result = await ingest_url(url, db_path=db_path)
        counts[result.status] = counts.get(result.status, 0) + 1

    return counts
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_sheets_champions.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/formats.py src/smogon_vgc_mcp/fetcher/sheets.py tests/test_sheets_champions.py
git commit -m "feat(sheets): champions sheet ingestion routing rows through pipeline"
```

---

## Task 13: Reactive `vgc-ingest <url>` CLI

**Files:**
- Create: `src/smogon_vgc_mcp/entry/ingest_cli.py`
- Modify: `pyproject.toml`
- Create: `tests/test_ingestion_cli.py`

- [ ] **Step 1: Write failing CLI test**

Create `tests/test_ingestion_cli.py`:

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from smogon_vgc_mcp.database.schema import init_database
from smogon_vgc_mcp.entry.ingest_cli import main_async
from smogon_vgc_mcp.resilience import FetchResult


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


async def test_cli_auto_write_exit_zero(db_path: Path, capsys):
    pokepaste_text = "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\nEVs: 32 Atk\nAdamant Nature\n- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(pokepaste_text)),
    ):
        exit_code = await main_async(["https://pokepast.es/abc"], db_path=db_path)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "auto" in captured.out.lower()


async def test_cli_rejected_exit_nonzero(db_path: Path, capsys):
    exit_code = await main_async(["not-a-url"], db_path=db_path)
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "rejected" in captured.out.lower()


async def test_cli_missing_url_exit_usage(db_path: Path, capsys):
    exit_code = await main_async([], db_path=db_path)
    assert exit_code == 1
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_ingestion_cli.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement CLI**

Create `src/smogon_vgc_mcp/entry/ingest_cli.py`:

```python
"""vgc-ingest CLI: ingest a single URL into champions_teams."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from smogon_vgc_mcp.fetcher.ingestion.pipeline import ingest_url


async def main_async(argv: list[str], *, db_path: Path | None = None) -> int:
    if not argv:
        print("Usage: vgc-ingest <url>", file=sys.stderr)
        return 1
    url = argv[0]
    result = await ingest_url(url, db_path=db_path)
    print(f"status: {result.status}")
    if result.team_row_id is not None:
        print(f"team_row_id: {result.team_row_id}")
    if result.confidence is not None:
        print(f"confidence: {result.confidence:.2f}")
    if result.reason:
        print(f"reason: {result.reason}")

    if result.status in ("auto", "review_pending"):
        return 0
    if result.status in ("fetch_failed", "parse_failed"):
        return 3
    return 2  # rejected


def main() -> None:
    sys.exit(asyncio.run(main_async(sys.argv[1:])))


if __name__ == "__main__":
    main()
```

In `pyproject.toml`, add to `[project.scripts]` (locate the existing block — similar to `smogon-vgc-mcp` or `vgc-build`):

```toml
vgc-ingest = "smogon_vgc_mcp.entry.ingest_cli:main"
```

Then regenerate the lock:

```bash
uv sync
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_ingestion_cli.py -v
```
Expected: PASS.

- [ ] **Step 5: Run full suite + lint**

```bash
uv run pytest --ignore=tests/integration -q
uv run ruff check src/smogon_vgc_mcp/fetcher/ingestion/ src/smogon_vgc_mcp/database/champions_team_queries.py src/smogon_vgc_mcp/entry/ingest_cli.py tests/test_ingestion_*.py tests/test_champions_team_queries.py tests/test_champions_team_schema.py tests/test_sheets_champions.py
uv run ruff format --check src/smogon_vgc_mcp/fetcher/ingestion/ src/smogon_vgc_mcp/database/champions_team_queries.py src/smogon_vgc_mcp/entry/ingest_cli.py tests/test_ingestion_*.py tests/test_champions_team_queries.py tests/test_champions_team_schema.py tests/test_sheets_champions.py
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/smogon_vgc_mcp/entry/ingest_cli.py pyproject.toml uv.lock tests/test_ingestion_cli.py
git commit -m "feat(cli): vgc-ingest reactive ingestion for single URL"
```

---

## Self-Review

- **Spec coverage**: Schema (T1), models (T2), validator §all (T3-T6), normalizer (T7), queries + fingerprint (T8), classifier (T9), Tier 1 (T10), pipeline (T11), sheet extension + Champions format config (T12), reactive CLI (T13). Phases 3-6 explicitly deferred.
- **Placeholders**: none. Every step includes actual code or exact commands.
- **Type consistency**: `ChampionsTeam`, `ChampionsTeamPokemon`, `ChampionsTeamDraft`, `ValidationReport`, `Tier`, `IngestResult` match across tasks. `write_or_queue_team` / `ingest_url` / `classify_url` / `normalize` / `validate` signatures consistent with test call sites.
- **Not in this plan (intentional)**: Tier 2 embedded Showdown (next plan), Tier 3 LLM + X/blog adapters (next plan), audit layer + MCP tool (next plan), labeler queue source (next plan), OCR (deferred indefinitely), proactive scheduler (deferred).

---

## Done When

- All 13 tasks' checkboxes complete
- `uv run pytest --ignore=tests/integration -q` fully green
- `uv run ruff check` clean on new files
- `vgc-ingest https://pokepast.es/<real-champions-team>` lands a row in `champions_teams` with `ingestion_status='auto'`
- `ingest_champions_sheet()` called against the real Champions sheet tab produces a mix of `auto` (pokepaste rows) and `rejected:tier_not_implemented` (X + blog rows), with no crashes

Next plan will pick up at Phase 3 (Tier 2 + Tier 3 + X/blog adapters).
