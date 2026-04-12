# Champions Data Pipelines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two Champions-format data pipelines: a Serebii scraper for move changes (new/rebalanced moves) and a Pikalytics scraper for usage statistics (moves, items, abilities, teammates, spreads per Pokemon across ELO cutoffs).

**Architecture:** Follow the existing `fetcher/champions_dex.py` two-phase pattern (fetch-all → transactional store). Serebii move scraper reuses the existing `champions_dex_moves` schema/`ChampionsDexMove` model. Pikalytics needs a new `champions_usage` schema (snapshot + per-pokemon rows + distribution rows) modeled on the existing `pokemon_usage` tables but keyed on ELO cutoff ("0+", "1500+", "1630+", "1760+") instead of month. Parsers extract JSON-LD Dataset schema blocks from SSR HTML. Both pipelines wire into `fetch_text_resilient()` with the existing `serebii` / new `pikalytics` circuit breaker.

**Tech Stack:** Python 3.12, aiosqlite, BeautifulSoup4, stdlib `json`, `fetch_text_resilient`, pytest/pytest-asyncio, uv+ruff+ty.

---

## File Structure

### Phase 1 — Serebii Champions moves

- Create: `src/smogon_vgc_mcp/fetcher/champions_moves.py` — parser + fetch/store for `https://www.serebii.net/pokemonchampions/updatedattacks.shtml`
- Create: `tests/fixtures/serebii_champions_moves.html` — real HTML fixture for offline parser tests
- Create: `tests/test_fetcher_champions_moves.py` — parser + store tests
- Modify: `src/smogon_vgc_mcp/database/queries.py` — add `get_champions_move(move_id)` and `list_champions_moves()` helpers

### Phase 2 — Pikalytics Champions usage

- Modify: `src/smogon_vgc_mcp/database/schema.py` — add `champions_usage_snapshots`, `champions_pokemon_usage`, `champions_usage_moves`, `champions_usage_items`, `champions_usage_abilities`, `champions_usage_teammates`, `champions_usage_spreads` tables + indexes
- Modify: `src/smogon_vgc_mcp/database/models.py` — add `ChampionsUsageSnapshot`, `ChampionsPokemonUsage`, distribution row dataclasses
- Create: `src/smogon_vgc_mcp/fetcher/pikalytics_champions.py` — HTML + JSON-LD parser, fetch orchestrator, transactional store
- Create: `tests/fixtures/pikalytics_incineroar.html` — real fixture for parser tests
- Create: `tests/test_fetcher_pikalytics_champions.py` — parser + store tests
- Modify: `src/smogon_vgc_mcp/database/queries.py` — add `get_champions_usage(pokemon, elo)`, `list_champions_usage_snapshots()`
- Create: `src/smogon_vgc_mcp/tools/champions_usage.py` — MCP tool `get_champions_usage_stats(pokemon, elo="0+")`
- Modify: `src/smogon_vgc_mcp/tools/__init__.py` — export + register
- Modify: `src/smogon_vgc_mcp/server.py` — register tool
- Create: `tests/test_tools_champions_usage.py` — MCP tool tests

---

# Phase 1: Serebii Champions Moves Scraper

The Serebii page lists "Updated Attacks" — moves whose stats/behavior differ from mainline. Schema (`champions_dex_moves`) and model (`ChampionsDexMove`) already exist, so this phase is parser + fetch glue.

## Task 1: Capture Serebii moves fixture and write parser

**Files:**
- Create: `tests/fixtures/serebii_champions_moves.html`
- Create: `src/smogon_vgc_mcp/fetcher/champions_moves.py`
- Create: `tests/test_fetcher_champions_moves.py`

- [ ] **Step 1: Capture the HTML fixture**

Fetch the page once manually and save to the fixture path. From repo root:

```bash
curl -sSL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  "https://www.serebii.net/pokemonchampions/updatedattacks.shtml" \
  > tests/fixtures/serebii_champions_moves.html
```

Expected: file size >10KB, contains `<table class="dextable">` tags.
Sanity-check:

```bash
wc -c tests/fixtures/serebii_champions_moves.html
grep -c 'dextable' tests/fixtures/serebii_champions_moves.html
```

Expected: size > 10000, at least 1 dextable match.

- [ ] **Step 2: Write failing parser test (single move)**

Create `tests/test_fetcher_champions_moves.py`:

```python
"""Tests for Serebii Champions move changes scraper."""

from pathlib import Path

import pytest

from smogon_vgc_mcp.fetcher.champions_moves import parse_serebii_moves_page

FIXTURE = Path(__file__).parent / "fixtures" / "serebii_champions_moves.html"


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="latin-1")


def test_parse_returns_list_of_moves(fixture_html: str) -> None:
    moves = parse_serebii_moves_page(fixture_html)
    assert isinstance(moves, list)
    assert len(moves) > 0


def test_parsed_moves_have_required_fields(fixture_html: str) -> None:
    moves = parse_serebii_moves_page(fixture_html)
    for m in moves:
        assert m["id"]
        assert m["name"]
        assert m["type"]
        assert m["category"] in ("Physical", "Special", "Status")
        # base_power/accuracy may be None for status/variable moves
        assert "base_power" in m
        assert "accuracy" in m
        assert "pp" in m


def test_parse_handles_empty_html() -> None:
    assert parse_serebii_moves_page("") == []
    assert parse_serebii_moves_page("<html></html>") == []
```

- [ ] **Step 3: Run tests, expect import error**

```bash
uv run python -m pytest tests/test_fetcher_champions_moves.py -v
```

Expected: `ModuleNotFoundError: No module named 'smogon_vgc_mcp.fetcher.champions_moves'`.

- [ ] **Step 4: Implement minimal parser**

Create `src/smogon_vgc_mcp/fetcher/champions_moves.py`:

```python
"""Parse Pokemon Champions move changes from Serebii.

Source: https://www.serebii.net/pokemonchampions/updatedattacks.shtml
Each move is rendered in a dextable with columns for name, type, category,
power, accuracy, PP, and effect description.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

_CATEGORY_MAP = {
    "physical": "Physical",
    "special": "Special",
    "status": "Status",
    "other": "Status",
}


def _slugify_move(name: str) -> str:
    """Convert 'Dragon Claw' -> 'dragonclaw' (matches Showdown id convention)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _parse_int_or_none(text: str) -> int | None:
    text = text.strip()
    if not text or text in ("--", "—", "-"):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _extract_category_from_img(td: Tag) -> str | None:
    """Category is rendered as an icon img; read its src or alt."""
    img = td.find("img")
    if not img:
        text = td.get_text(strip=True).lower()
        return _CATEGORY_MAP.get(text)
    src = (img.get("src") or "").lower()
    alt = (img.get("alt") or "").lower()
    for key, val in _CATEGORY_MAP.items():
        if key in src or key in alt:
            return val
    return None


def _extract_type_from_img(td: Tag) -> str | None:
    img = td.find("img")
    if not img:
        return td.get_text(strip=True).capitalize() or None
    src = (img.get("src") or "").lower()
    m = re.search(r"/type/([a-z]+)\.(?:gif|png)", src)
    if m:
        return m.group(1).capitalize()
    alt = (img.get("alt") or "").strip()
    alt = re.sub(r"-type$", "", alt, flags=re.I)
    return alt.capitalize() or None


def parse_serebii_moves_page(html: str) -> list[dict]:
    """Parse the Serebii updated attacks page into a list of move dicts.

    Each dict has keys: id, name, type, category, base_power, accuracy, pp,
    priority, target, description, short_desc. Unknown fields are None.
    """
    if not html or len(html.strip()) < 100:
        return []

    soup = BeautifulSoup(html, "html.parser")
    moves: list[dict] = []

    for table in soup.find_all("table", class_="dextable"):
        move = _parse_move_table(table)
        if move is not None:
            moves.append(move)

    return moves


def _parse_move_table(table: Tag) -> dict | None:
    """Parse one dextable. Each move table has a header row with the name,
    followed by a stats row (type, category, power, accuracy, PP) and a
    description row."""
    # Name is typically in the first <td class="fooevo"> or <h3>
    name_td = table.find("td", class_="fooevo")
    if name_td is None:
        h3 = table.find("h3")
        name = h3.get_text(strip=True) if h3 else ""
    else:
        name = name_td.get_text(strip=True)

    if not name:
        return None

    # Stats row: look for a row of <td class="fooinfo"> cells
    stat_rows = [
        tr for tr in table.find_all("tr") if tr.find_all("td", class_="fooinfo")
    ]
    if not stat_rows:
        return None

    type_name: str | None = None
    category: str | None = None
    power: int | None = None
    accuracy: int | None = None
    pp: int | None = None

    # Expect one row with 5 fooinfo cells: type | category | power | accuracy | PP
    for row in stat_rows:
        cells = row.find_all("td", class_="fooinfo")
        if len(cells) >= 5:
            type_name = _extract_type_from_img(cells[0])
            category = _extract_category_from_img(cells[1])
            power = _parse_int_or_none(cells[2].get_text())
            accuracy = _parse_int_or_none(cells[3].get_text())
            pp = _parse_int_or_none(cells[4].get_text())
            break

    if type_name is None or category is None:
        return None

    # Description: last fooinfo row that spans full width
    description = ""
    for row in stat_rows:
        cells = row.find_all("td", class_="fooinfo")
        if len(cells) == 1:
            txt = cells[0].get_text(" ", strip=True)
            if len(txt) > len(description):
                description = txt

    return {
        "id": _slugify_move(name),
        "name": name,
        "type": type_name,
        "category": category,
        "base_power": power,
        "accuracy": accuracy,
        "pp": pp or 0,
        "priority": 0,
        "target": None,
        "description": description or None,
        "short_desc": description or None,
    }
```

- [ ] **Step 5: Run tests, expect some to pass**

```bash
uv run python -m pytest tests/test_fetcher_champions_moves.py -v
```

Expected: `test_parse_handles_empty_html` passes. `test_parse_returns_list_of_moves` and `test_parsed_moves_have_required_fields` should pass if the real HTML matches the assumed `dextable` / `fooinfo` layout. If they fail, inspect the fixture:

```bash
uv run python -c "
from pathlib import Path
from bs4 import BeautifulSoup
html = Path('tests/fixtures/serebii_champions_moves.html').read_text(encoding='latin-1')
soup = BeautifulSoup(html, 'html.parser')
tables = soup.find_all('table', class_='dextable')
print(f'dextables: {len(tables)}')
if tables:
    print(tables[0].prettify()[:2000])
"
```

Then adjust `_parse_move_table` to match the actual structure (column order, class names, wrapper tags). Re-run until both tests pass.

- [ ] **Step 6: Commit Phase 1 parser**

```bash
git add src/smogon_vgc_mcp/fetcher/champions_moves.py \
        tests/test_fetcher_champions_moves.py \
        tests/fixtures/serebii_champions_moves.html
git commit -m "feat(champions): add Serebii move changes parser"
```

---

## Task 2: Fetch + store orchestrator for Champions moves

**Files:**
- Modify: `src/smogon_vgc_mcp/fetcher/champions_moves.py`
- Modify: `tests/test_fetcher_champions_moves.py`
- Modify: `src/smogon_vgc_mcp/database/queries.py`

- [ ] **Step 1: Write failing store test**

Append to `tests/test_fetcher_champions_moves.py`:

```python
import aiosqlite

from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.champions_moves import store_champions_moves


@pytest.mark.asyncio
async def test_store_inserts_moves() -> None:
    moves = [
        {
            "id": "dragonclaw",
            "name": "Dragon Claw",
            "type": "Dragon",
            "category": "Physical",
            "base_power": 85,
            "accuracy": 100,
            "pp": 15,
            "priority": 0,
            "target": None,
            "description": "A slashing attack with sharp claws.",
            "short_desc": "A slashing attack with sharp claws.",
        }
    ]
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        count = await store_champions_moves(db, moves)
        assert count == 1
        async with db.execute(
            "SELECT name, type, base_power FROM champions_dex_moves WHERE id = ?",
            ("dragonclaw",),
        ) as cursor:
            row = await cursor.fetchone()
    assert row == ("Dragon Claw", "Dragon", 85)


@pytest.mark.asyncio
async def test_store_replaces_existing() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await store_champions_moves(
            db, [{"id": "x", "name": "X", "type": "Fire", "category": "Physical",
                  "base_power": 50, "accuracy": 100, "pp": 10, "priority": 0,
                  "target": None, "description": None, "short_desc": None}],
        )
        await store_champions_moves(
            db, [{"id": "x", "name": "X", "type": "Fire", "category": "Physical",
                  "base_power": 75, "accuracy": 100, "pp": 10, "priority": 0,
                  "target": None, "description": None, "short_desc": None}],
        )
        async with db.execute(
            "SELECT COUNT(*), MAX(base_power) FROM champions_dex_moves"
        ) as cursor:
            row = await cursor.fetchone()
    assert row == (1, 75)
```

- [ ] **Step 2: Run tests, expect failure**

```bash
uv run python -m pytest tests/test_fetcher_champions_moves.py::test_store_inserts_moves -v
```

Expected: `ImportError: cannot import name 'store_champions_moves'`.

- [ ] **Step 3: Implement store function**

Append to `src/smogon_vgc_mcp/fetcher/champions_moves.py`:

```python
import asyncio
from pathlib import Path

import aiosqlite

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.resilience import get_all_circuit_states
from smogon_vgc_mcp.utils import fetch_text_resilient

SEREBII_MOVES_URL = "https://www.serebii.net/pokemonchampions/updatedattacks.shtml"


async def store_champions_moves(
    db: aiosqlite.Connection,
    moves: list[dict],
    *,
    _commit: bool = True,
) -> int:
    """Replace all Champions moves with the provided list.

    DELETE + INSERT OR REPLACE pattern matching store_champions_pokemon_data.
    Returns count of stored rows.
    """
    await db.execute("DELETE FROM champions_dex_moves")
    count = 0
    for m in moves:
        await db.execute(
            """INSERT OR REPLACE INTO champions_dex_moves
               (id, num, name, type, category, base_power, accuracy, pp,
                priority, target, description, short_desc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m["id"],
                m.get("num"),
                m["name"],
                m["type"],
                m["category"],
                m.get("base_power"),
                m.get("accuracy"),
                m.get("pp", 0),
                m.get("priority", 0),
                m.get("target"),
                m.get("description"),
                m.get("short_desc"),
            ),
        )
        count += 1
    if _commit:
        await db.commit()
    return count


async def fetch_and_store_champions_moves(
    db_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict:
    """Fetch the Serebii updated attacks page and store parsed moves.

    Returns dict: {fetched, stored, errors, circuit_states, dry_run}.
    """
    if db_path is None:
        db_path = get_db_path()

    await init_database(db_path)

    result = await fetch_text_resilient(SEREBII_MOVES_URL, service="serebii")
    errors: list[dict] = []
    if not result.success or not result.data:
        errors.append({"url": SEREBII_MOVES_URL, "message": "Fetch failed"})
        return {
            "fetched": 0,
            "stored": 0,
            "errors": errors,
            "circuit_states": get_all_circuit_states(),
            "dry_run": dry_run,
        }

    moves = parse_serebii_moves_page(result.data)

    if dry_run:
        return {
            "fetched": len(moves),
            "stored": 0,
            "errors": errors,
            "circuit_states": get_all_circuit_states(),
            "dry_run": True,
            "results": moves,
        }

    stored = 0
    async with get_connection(db_path) as db:
        try:
            stored = await store_champions_moves(db, moves, _commit=False)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            errors.append({"url": "store", "message": str(exc)})

    return {
        "fetched": len(moves),
        "stored": stored,
        "errors": errors,
        "circuit_states": get_all_circuit_states(),
        "dry_run": False,
    }
```

- [ ] **Step 4: Run store tests**

```bash
uv run python -m pytest tests/test_fetcher_champions_moves.py -v
```

Expected: all tests pass. If not, inspect the error, re-read the fetcher file, and fix.

- [ ] **Step 5: Add query helpers**

In `src/smogon_vgc_mcp/database/queries.py`, find the existing Champions-related query functions (search for `champions_dex_pokemon`) and add alongside them:

```python
async def get_champions_move(move_id: str) -> ChampionsDexMove | None:
    """Look up a single Champions move by normalized id (e.g. 'dragonclaw')."""
    async with get_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT id, num, name, type, category, base_power, accuracy,
                      pp, priority, target, description, short_desc
               FROM champions_dex_moves WHERE id = ?""",
            (move_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return None
    return ChampionsDexMove(
        id=row["id"],
        num=row["num"] or 0,
        name=row["name"],
        type=row["type"],
        category=row["category"],
        base_power=row["base_power"],
        accuracy=row["accuracy"],
        pp=row["pp"] or 0,
        priority=row["priority"] or 0,
        target=row["target"],
        description=row["description"],
        short_desc=row["short_desc"],
    )


async def list_champions_moves() -> list[ChampionsDexMove]:
    """Return all Champions moves, ordered by name."""
    async with get_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT id, num, name, type, category, base_power, accuracy,
                      pp, priority, target, description, short_desc
               FROM champions_dex_moves ORDER BY name"""
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        ChampionsDexMove(
            id=r["id"],
            num=r["num"] or 0,
            name=r["name"],
            type=r["type"],
            category=r["category"],
            base_power=r["base_power"],
            accuracy=r["accuracy"],
            pp=r["pp"] or 0,
            priority=r["priority"] or 0,
            target=r["target"],
            description=r["description"],
            short_desc=r["short_desc"],
        )
        for r in rows
    ]
```

Ensure `ChampionsDexMove` is imported at the top of `queries.py` (check existing imports first — if only `ChampionsDexPokemon` is imported, add `ChampionsDexMove` to that line).

- [ ] **Step 6: Type-check and lint**

```bash
uv run ty check src/smogon_vgc_mcp/fetcher/champions_moves.py \
                src/smogon_vgc_mcp/database/queries.py
uv run ruff check --fix src/smogon_vgc_mcp/fetcher/champions_moves.py \
                       src/smogon_vgc_mcp/database/queries.py \
                       tests/test_fetcher_champions_moves.py
uv run ruff format src/smogon_vgc_mcp/fetcher/champions_moves.py \
                   src/smogon_vgc_mcp/database/queries.py \
                   tests/test_fetcher_champions_moves.py
```

Fix any reported errors. Re-run tests after.

- [ ] **Step 7: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/champions_moves.py \
        src/smogon_vgc_mcp/database/queries.py \
        tests/test_fetcher_champions_moves.py
git commit -m "feat(champions): store Serebii move changes + query helpers"
```

---

# Phase 2: Pikalytics Champions Usage Scraper

Pikalytics URL pattern: `https://www.pikalytics.com/pokedex/championspreview/<pokemon_slug>`. Each page is server-rendered HTML that includes a JSON-LD `Dataset` schema block alongside static sections listing usage %, moves, abilities, items, teammates, and spreads. ELO cutoffs are "0+", "1500+", "1630+", "1760+" and each cutoff is selectable on the page (we scrape each cutoff separately and tag rows with the cutoff).

## Task 3: Add Champions usage schema and models

**Files:**
- Modify: `src/smogon_vgc_mcp/database/schema.py`
- Modify: `src/smogon_vgc_mcp/database/models.py`
- Create: `tests/test_database_champions_usage_schema.py`

- [ ] **Step 1: Write failing schema test**

Create `tests/test_database_champions_usage_schema.py`:

```python
"""Tests that champions_usage tables exist with expected columns."""

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import SCHEMA

EXPECTED_TABLES = {
    "champions_usage_snapshots",
    "champions_pokemon_usage",
    "champions_usage_moves",
    "champions_usage_items",
    "champions_usage_abilities",
    "champions_usage_teammates",
    "champions_usage_spreads",
}


@pytest.mark.asyncio
async def test_champions_usage_tables_exist() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cursor:
            names = {row[0] async for row in cursor}
    assert EXPECTED_TABLES <= names


@pytest.mark.asyncio
async def test_champions_pokemon_usage_columns() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        async with db.execute(
            "PRAGMA table_info(champions_pokemon_usage)"
        ) as cursor:
            cols = {row[1] async for row in cursor}
    assert {"id", "snapshot_id", "pokemon", "usage_percent", "rank"} <= cols
```

- [ ] **Step 2: Run test, expect failure**

```bash
uv run python -m pytest tests/test_database_champions_usage_schema.py -v
```

Expected: assertion failures (tables missing).

- [ ] **Step 3: Extend schema**

In `src/smogon_vgc_mcp/database/schema.py`, append these CREATE TABLE statements to the `SCHEMA` string (before the closing `"""`):

```sql
-- =============================================================================
-- Champions usage data (from Pikalytics)
-- =============================================================================

CREATE TABLE IF NOT EXISTS champions_usage_snapshots (
    id INTEGER PRIMARY KEY,
    elo_cutoff TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'pikalytics',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, elo_cutoff)
);

CREATE TABLE IF NOT EXISTS champions_pokemon_usage (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER REFERENCES champions_usage_snapshots(id) ON DELETE CASCADE,
    pokemon TEXT NOT NULL,
    usage_percent REAL,
    rank INTEGER,
    raw_count INTEGER,
    UNIQUE(snapshot_id, pokemon)
);

CREATE TABLE IF NOT EXISTS champions_usage_moves (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES champions_pokemon_usage(id) ON DELETE CASCADE,
    move TEXT NOT NULL,
    percent REAL
);

CREATE TABLE IF NOT EXISTS champions_usage_items (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES champions_pokemon_usage(id) ON DELETE CASCADE,
    item TEXT NOT NULL,
    percent REAL
);

CREATE TABLE IF NOT EXISTS champions_usage_abilities (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES champions_pokemon_usage(id) ON DELETE CASCADE,
    ability TEXT NOT NULL,
    percent REAL
);

CREATE TABLE IF NOT EXISTS champions_usage_teammates (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES champions_pokemon_usage(id) ON DELETE CASCADE,
    teammate TEXT NOT NULL,
    percent REAL
);

CREATE TABLE IF NOT EXISTS champions_usage_spreads (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES champions_pokemon_usage(id) ON DELETE CASCADE,
    nature TEXT,
    hp INTEGER,
    atk INTEGER,
    def INTEGER,
    spa INTEGER,
    spd INTEGER,
    spe INTEGER,
    percent REAL
);

CREATE INDEX IF NOT EXISTS idx_champ_usage_snap_elo
    ON champions_usage_snapshots(elo_cutoff);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_usage_name
    ON champions_pokemon_usage(pokemon);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_usage_snap
    ON champions_pokemon_usage(snapshot_id);
```

- [ ] **Step 4: Run schema test, expect pass**

```bash
uv run python -m pytest tests/test_database_champions_usage_schema.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Add dataclass models**

In `src/smogon_vgc_mcp/database/models.py`, append after the existing `ChampionsDexMove` class:

```python
@dataclass
class ChampionsUsageSnapshot:
    """A single Pikalytics Champions usage snapshot for one ELO cutoff."""

    id: int
    elo_cutoff: str  # "0+", "1500+", "1630+", "1760+"
    source: str = "pikalytics"
    fetched_at: str | None = None


@dataclass
class ChampionsPokemonUsage:
    """Per-Pokemon usage row for a Champions snapshot."""

    pokemon: str
    usage_percent: float | None = None
    rank: int | None = None
    raw_count: int | None = None
    moves: list[tuple[str, float]] = field(default_factory=list)
    items: list[tuple[str, float]] = field(default_factory=list)
    abilities: list[tuple[str, float]] = field(default_factory=list)
    teammates: list[tuple[str, float]] = field(default_factory=list)
    spreads: list[dict] = field(default_factory=list)
```

If `field` is not yet imported from `dataclasses` at the top of the file, update the import to `from dataclasses import dataclass, field`.

- [ ] **Step 6: Type-check and commit**

```bash
uv run ty check src/smogon_vgc_mcp/database/
uv run ruff check --fix src/smogon_vgc_mcp/database/ tests/test_database_champions_usage_schema.py
uv run ruff format src/smogon_vgc_mcp/database/ tests/test_database_champions_usage_schema.py
uv run python -m pytest tests/test_database_champions_usage_schema.py -v
```

All green, then:

```bash
git add src/smogon_vgc_mcp/database/schema.py \
        src/smogon_vgc_mcp/database/models.py \
        tests/test_database_champions_usage_schema.py
git commit -m "feat(champions): add Pikalytics usage schema and models"
```

---

## Task 4: Capture Pikalytics fixture and write parser

**Files:**
- Create: `tests/fixtures/pikalytics_incineroar.html`
- Create: `src/smogon_vgc_mcp/fetcher/pikalytics_champions.py`
- Create: `tests/test_fetcher_pikalytics_champions.py`

- [ ] **Step 1: Capture the fixture**

```bash
curl -sSL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  "https://www.pikalytics.com/pokedex/championspreview/incineroar" \
  > tests/fixtures/pikalytics_incineroar.html
wc -c tests/fixtures/pikalytics_incineroar.html
grep -c 'application/ld+json' tests/fixtures/pikalytics_incineroar.html
```

Expected: size > 20000, at least one `application/ld+json` match.

- [ ] **Step 2: Write failing parser tests**

Create `tests/test_fetcher_pikalytics_champions.py`:

```python
"""Tests for Pikalytics Champions usage parser."""

from pathlib import Path

import pytest

from smogon_vgc_mcp.fetcher.pikalytics_champions import parse_pikalytics_page

FIXTURE = Path(__file__).parent / "fixtures" / "pikalytics_incineroar.html"


@pytest.fixture
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_returns_usage_dict(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert result["pokemon"] == "incineroar"
    assert "usage_percent" in result or "rank" in result


def test_parse_extracts_moves(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert isinstance(result["moves"], list)
    assert len(result["moves"]) > 0
    name, pct = result["moves"][0]
    assert isinstance(name, str) and name
    assert isinstance(pct, float)


def test_parse_extracts_items_abilities_teammates(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert isinstance(result["items"], list)
    assert isinstance(result["abilities"], list)
    assert isinstance(result["teammates"], list)


def test_parse_handles_404() -> None:
    assert parse_pikalytics_page("", pokemon_slug="missingno") is None
    assert parse_pikalytics_page("<html>Not Found</html>", pokemon_slug="missingno") is None
```

- [ ] **Step 3: Run tests, expect import error**

```bash
uv run python -m pytest tests/test_fetcher_pikalytics_champions.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement parser**

Create `src/smogon_vgc_mcp/fetcher/pikalytics_champions.py`:

```python
"""Parse Pokemon Champions usage data from Pikalytics.

URL pattern:
  https://www.pikalytics.com/pokedex/championspreview/<pokemon_slug>

Each page is server-rendered HTML and embeds a JSON-LD Dataset schema
(<script type="application/ld+json">). We prefer JSON-LD where fields
overlap, and fall back to parsing the visible percentage bars in the
dedicated sections for moves/items/abilities/teammates/spreads.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

_PERCENT_RE = re.compile(r"([\d.]+)\s*%")


def _extract_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Return the first JSON-LD block that looks like a Dataset."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("@type") == "Dataset":
                    return item
        elif isinstance(payload, dict) and payload.get("@type") == "Dataset":
            return payload
    return None


def _parse_percent(text: str) -> float | None:
    m = _PERCENT_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _section_rows(soup: BeautifulSoup, heading_keywords: list[str]) -> list[tuple[str, float]]:
    """Find a section header whose text matches one of the keywords, then
    return (label, percent) pairs from the immediately-following list items.

    Pikalytics renders each stat section with a heading followed by a
    <ul> or <div> of rows, each containing a label and a percent string.
    """
    results: list[tuple[str, float]] = []
    for heading in soup.find_all(["h2", "h3", "h4", "div"]):
        text = heading.get_text(" ", strip=True).lower()
        if not any(kw in text for kw in heading_keywords):
            continue

        # Walk forward siblings until we find row-bearing content
        container: Tag | None = None
        for sib in heading.find_all_next():
            if not isinstance(sib, Tag):
                continue
            if sib.name in ("ul", "ol"):
                container = sib
                break
            # Some Pikalytics sections use div.stat-row patterns
            if sib.name == "div" and sib.find(class_=re.compile(r"stat|row|bar", re.I)):
                container = sib
                break
        if container is None:
            continue

        for row in container.find_all(["li", "div"], recursive=True):
            row_text = row.get_text(" ", strip=True)
            pct = _parse_percent(row_text)
            if pct is None:
                continue
            label = _PERCENT_RE.sub("", row_text).strip(" -:")
            if label:
                results.append((label, pct))

        if results:
            break

    return results


def parse_pikalytics_page(html: str, pokemon_slug: str) -> dict[str, Any] | None:
    """Parse a Pikalytics championspreview page into a usage dict.

    Returns None for empty or 404-style pages. Returned dict has keys:
      pokemon, usage_percent, rank, raw_count,
      moves, items, abilities, teammates, spreads
    """
    if not html or len(html.strip()) < 200:
        return None
    if "Not Found" in html[:500] or "404" in html[:200]:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Prefer JSON-LD for high-confidence fields
    ld = _extract_json_ld(soup) or {}
    usage_percent: float | None = None
    rank: int | None = None

    # JSON-LD "variableMeasured" commonly holds summary stats
    for var in ld.get("variableMeasured", []) if isinstance(ld.get("variableMeasured"), list) else []:
        if not isinstance(var, dict):
            continue
        name = (var.get("name") or "").lower()
        value = var.get("value")
        if "usage" in name and value is not None:
            try:
                usage_percent = float(str(value).strip("%"))
            except ValueError:
                pass
        elif "rank" in name and value is not None:
            try:
                rank = int(float(str(value)))
            except ValueError:
                pass

    # Fallback: parse usage from headline like "Usage: 35.8%"
    if usage_percent is None:
        body = soup.get_text(" ", strip=True)
        m = re.search(r"usage[^0-9%]*([\d.]+)\s*%", body, re.I)
        if m:
            try:
                usage_percent = float(m.group(1))
            except ValueError:
                pass

    moves = _section_rows(soup, ["move"])
    items = _section_rows(soup, ["item"])
    abilities = _section_rows(soup, ["abilit"])
    teammates = _section_rows(soup, ["teammate", "partner"])

    # Sanity check: if no signal at all, treat as 404
    if usage_percent is None and not moves and not items and not abilities:
        return None

    return {
        "pokemon": pokemon_slug,
        "usage_percent": usage_percent,
        "rank": rank,
        "raw_count": None,
        "moves": moves,
        "items": items,
        "abilities": abilities,
        "teammates": teammates,
        "spreads": [],  # spreads are lower priority; leave empty for v1
    }
```

- [ ] **Step 5: Run parser tests and iterate**

```bash
uv run python -m pytest tests/test_fetcher_pikalytics_champions.py -v
```

Expected: `test_parse_handles_404` passes immediately. The three fixture-dependent tests may fail — if so, inspect the real HTML structure:

```bash
uv run python -c "
from pathlib import Path
from bs4 import BeautifulSoup
html = Path('tests/fixtures/pikalytics_incineroar.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')
for h in soup.find_all(['h2','h3','h4']):
    print(h.name, '|', h.get_text(strip=True)[:80])
" | head -40
```

Then refine `_section_rows` or `heading_keywords` until `moves`, `items`, `abilities`, and `teammates` each return non-empty lists for the Incineroar fixture. Re-run tests until all four pass.

- [ ] **Step 6: Commit parser**

```bash
git add src/smogon_vgc_mcp/fetcher/pikalytics_champions.py \
        tests/test_fetcher_pikalytics_champions.py \
        tests/fixtures/pikalytics_incineroar.html
git commit -m "feat(champions): add Pikalytics usage parser"
```

---

## Task 5: Fetch orchestrator and transactional store

**Files:**
- Modify: `src/smogon_vgc_mcp/fetcher/pikalytics_champions.py`
- Modify: `tests/test_fetcher_pikalytics_champions.py`

- [ ] **Step 1: Write failing store test**

Append to `tests/test_fetcher_pikalytics_champions.py`:

```python
import aiosqlite

from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.pikalytics_champions import store_champions_usage


@pytest.mark.asyncio
async def test_store_creates_snapshot_and_rows() -> None:
    payload = [
        {
            "pokemon": "incineroar",
            "usage_percent": 35.8,
            "rank": 1,
            "raw_count": None,
            "moves": [("Fake Out", 95.2), ("Flare Blitz", 78.1)],
            "items": [("Safety Goggles", 40.0)],
            "abilities": [("Intimidate", 100.0)],
            "teammates": [("Farigiraf", 22.0)],
            "spreads": [],
        }
    ]
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        snapshot_id, count = await store_champions_usage(
            db, elo_cutoff="0+", pokemon_data=payload
        )
        assert snapshot_id > 0
        assert count == 1
        async with db.execute(
            "SELECT COUNT(*) FROM champions_usage_moves"
        ) as cursor:
            (moves_count,) = await cursor.fetchone()
        async with db.execute(
            "SELECT COUNT(*) FROM champions_usage_abilities"
        ) as cursor:
            (ab_count,) = await cursor.fetchone()
    assert moves_count == 2
    assert ab_count == 1


@pytest.mark.asyncio
async def test_store_replaces_same_elo_snapshot() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        first = [{"pokemon": "incineroar", "usage_percent": 35.8, "rank": 1,
                  "raw_count": None, "moves": [("A", 10.0)], "items": [],
                  "abilities": [], "teammates": [], "spreads": []}]
        await store_champions_usage(db, elo_cutoff="0+", pokemon_data=first)
        second = [{"pokemon": "incineroar", "usage_percent": 40.0, "rank": 1,
                   "raw_count": None, "moves": [("B", 20.0)], "items": [],
                   "abilities": [], "teammates": [], "spreads": []}]
        await store_champions_usage(db, elo_cutoff="0+", pokemon_data=second)
        async with db.execute(
            "SELECT COUNT(*) FROM champions_usage_snapshots"
        ) as cursor:
            (snap_count,) = await cursor.fetchone()
        async with db.execute(
            "SELECT move, percent FROM champions_usage_moves"
        ) as cursor:
            rows = await cursor.fetchall()
    assert snap_count == 1
    assert rows == [("B", 20.0)]
```

- [ ] **Step 2: Run tests, expect failure**

```bash
uv run python -m pytest tests/test_fetcher_pikalytics_champions.py::test_store_creates_snapshot_and_rows -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement store + orchestrator**

Append to `src/smogon_vgc_mcp/fetcher/pikalytics_champions.py`:

```python
import asyncio
from pathlib import Path

import aiosqlite

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.resilience import get_all_circuit_states
from smogon_vgc_mcp.utils import fetch_text_resilient

PIKALYTICS_URL_TEMPLATE = "https://www.pikalytics.com/pokedex/championspreview/{slug}"

# Known Champions Pokemon with Pikalytics data (as of 2026-04-08)
PIKALYTICS_POKEMON_SLUGS = [
    "incineroar", "sneasler", "sinistcha", "archaludon", "whimsicott",
    "pelipper", "ursaluna", "garchomp", "farigiraf", "dragonite",
    "charizard", "basculegion", "tyranitar", "kingambit",
]

ELO_CUTOFFS = ["0+", "1500+", "1630+", "1760+"]


async def store_champions_usage(
    db: aiosqlite.Connection,
    elo_cutoff: str,
    pokemon_data: list[dict],
    *,
    _commit: bool = True,
) -> tuple[int, int]:
    """Upsert a Pikalytics snapshot for one ELO cutoff.

    If a snapshot already exists for (source, elo_cutoff), its rows are
    cleared (via ON DELETE CASCADE) by deleting the old snapshot row first,
    then a fresh snapshot + children are inserted.

    Returns (snapshot_id, pokemon_count).
    """
    # Remove any existing snapshot for this cutoff to get clean cascade
    await db.execute(
        "DELETE FROM champions_usage_snapshots WHERE source = 'pikalytics' AND elo_cutoff = ?",
        (elo_cutoff,),
    )

    cursor = await db.execute(
        "INSERT INTO champions_usage_snapshots (elo_cutoff, source) VALUES (?, 'pikalytics')",
        (elo_cutoff,),
    )
    snapshot_id = cursor.lastrowid
    assert snapshot_id is not None

    count = 0
    for entry in pokemon_data:
        poke_cursor = await db.execute(
            """INSERT INTO champions_pokemon_usage
               (snapshot_id, pokemon, usage_percent, rank, raw_count)
               VALUES (?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                entry["pokemon"],
                entry.get("usage_percent"),
                entry.get("rank"),
                entry.get("raw_count"),
            ),
        )
        pu_id = poke_cursor.lastrowid
        assert pu_id is not None

        for move, pct in entry.get("moves", []):
            await db.execute(
                "INSERT INTO champions_usage_moves (pokemon_usage_id, move, percent) VALUES (?, ?, ?)",
                (pu_id, move, pct),
            )
        for item, pct in entry.get("items", []):
            await db.execute(
                "INSERT INTO champions_usage_items (pokemon_usage_id, item, percent) VALUES (?, ?, ?)",
                (pu_id, item, pct),
            )
        for ability, pct in entry.get("abilities", []):
            await db.execute(
                "INSERT INTO champions_usage_abilities (pokemon_usage_id, ability, percent) VALUES (?, ?, ?)",
                (pu_id, ability, pct),
            )
        for teammate, pct in entry.get("teammates", []):
            await db.execute(
                "INSERT INTO champions_usage_teammates (pokemon_usage_id, teammate, percent) VALUES (?, ?, ?)",
                (pu_id, teammate, pct),
            )
        count += 1

    if _commit:
        await db.commit()
    return snapshot_id, count


async def fetch_pikalytics_pokemon(slug: str) -> dict | None:
    """Fetch a single Pokemon page from Pikalytics and parse it."""
    url = PIKALYTICS_URL_TEMPLATE.format(slug=slug)
    result = await fetch_text_resilient(url, service="pikalytics")
    if not result.success or not result.data:
        return None
    return parse_pikalytics_page(result.data, pokemon_slug=slug)


async def fetch_and_store_pikalytics_champions(
    db_path: Path | None = None,
    *,
    elo_cutoff: str = "0+",
    dry_run: bool = False,
    slugs: list[str] | None = None,
    request_delay: float = 1.0,
) -> dict:
    """Fetch all Pikalytics Champions pages and store atomically.

    One snapshot per ELO cutoff. Callers loop over cutoffs if they want
    the full matrix.
    """
    if db_path is None:
        db_path = get_db_path()
    await init_database(db_path)

    target_slugs = slugs if slugs is not None else PIKALYTICS_POKEMON_SLUGS
    errors: list[dict] = []
    results: list[dict] = []

    for slug in target_slugs:
        data = await fetch_pikalytics_pokemon(slug)
        if data is None:
            errors.append({"slug": slug, "message": "Failed to fetch or parse page"})
        else:
            results.append(data)
        if request_delay > 0:
            await asyncio.sleep(request_delay)

    if dry_run:
        return {
            "fetched": len(results),
            "stored": 0,
            "errors": errors,
            "circuit_states": get_all_circuit_states(),
            "dry_run": True,
            "results": results,
        }

    snapshot_id = 0
    stored = 0
    async with get_connection(db_path) as db:
        try:
            snapshot_id, stored = await store_champions_usage(
                db, elo_cutoff=elo_cutoff, pokemon_data=results, _commit=False
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            errors.append({"slug": "store", "message": str(exc)})

    return {
        "fetched": len(results),
        "stored": stored,
        "snapshot_id": snapshot_id,
        "elo_cutoff": elo_cutoff,
        "errors": errors,
        "circuit_states": get_all_circuit_states(),
        "dry_run": False,
    }
```

- [ ] **Step 4: Register `pikalytics` circuit breaker**

The `service="pikalytics"` arg to `fetch_text_resilient` must be registered. Check where services are registered:

```bash
uv run python -c "
from smogon_vgc_mcp import resilience
print(resilience.get_all_circuit_states())
"
```

If `pikalytics` is missing, find the service registry (grep for `serebii` in `src/smogon_vgc_mcp/resilience.py` and `src/smogon_vgc_mcp/utils.py`) and add a `pikalytics` entry alongside `serebii` with the same defaults. If services are implicitly created on first use, no change needed — confirm by reading the relevant code.

- [ ] **Step 5: Run store tests**

```bash
uv run python -m pytest tests/test_fetcher_pikalytics_champions.py -v
```

Expected: all 6 tests pass. Fix any issues.

- [ ] **Step 6: Type-check, lint, commit**

```bash
uv run ty check src/smogon_vgc_mcp/fetcher/pikalytics_champions.py
uv run ruff check --fix src/smogon_vgc_mcp/fetcher/pikalytics_champions.py \
                       tests/test_fetcher_pikalytics_champions.py
uv run ruff format src/smogon_vgc_mcp/fetcher/pikalytics_champions.py \
                   tests/test_fetcher_pikalytics_champions.py
uv run python -m pytest tests/test_fetcher_pikalytics_champions.py -v
```

All green:

```bash
git add src/smogon_vgc_mcp/fetcher/pikalytics_champions.py \
        tests/test_fetcher_pikalytics_champions.py
git commit -m "feat(champions): add Pikalytics fetch + store orchestrator"
```

---

## Task 6: Query helpers and MCP tool

**Files:**
- Modify: `src/smogon_vgc_mcp/database/queries.py`
- Create: `src/smogon_vgc_mcp/tools/champions_usage.py`
- Modify: `src/smogon_vgc_mcp/tools/__init__.py`
- Modify: `src/smogon_vgc_mcp/server.py`
- Create: `tests/test_tools_champions_usage.py`

- [ ] **Step 1: Write failing query test**

Create `tests/test_tools_champions_usage.py`:

```python
"""Tests for champions usage MCP tool and query helpers."""

import aiosqlite
import pytest

from smogon_vgc_mcp.database.queries import get_champions_usage
from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.pikalytics_champions import store_champions_usage


async def _seed(db: aiosqlite.Connection) -> None:
    await db.executescript(SCHEMA)
    await store_champions_usage(
        db,
        elo_cutoff="0+",
        pokemon_data=[
            {
                "pokemon": "incineroar",
                "usage_percent": 35.8,
                "rank": 1,
                "raw_count": None,
                "moves": [("Fake Out", 95.2)],
                "items": [("Safety Goggles", 40.0)],
                "abilities": [("Intimidate", 100.0)],
                "teammates": [("Farigiraf", 22.0)],
                "spreads": [],
            }
        ],
    )


@pytest.mark.asyncio
async def test_get_champions_usage_returns_full_payload(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await _seed(db)
    result = await get_champions_usage("incineroar", elo_cutoff="0+")
    assert result is not None
    assert result["pokemon"] == "incineroar"
    assert result["usage_percent"] == 35.8
    assert ("Fake Out", 95.2) in result["moves"]
    assert result["abilities"] == [("Intimidate", 100.0)]


@pytest.mark.asyncio
async def test_get_champions_usage_returns_none_for_missing(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
    result = await get_champions_usage("missingno", elo_cutoff="0+")
    assert result is None
```

- [ ] **Step 2: Run test, expect failure**

```bash
uv run python -m pytest tests/test_tools_champions_usage.py -v
```

Expected: `ImportError: cannot import name 'get_champions_usage'`.

- [ ] **Step 3: Implement query helper**

In `src/smogon_vgc_mcp/database/queries.py`, add (near the other Champions queries):

```python
async def get_champions_usage(
    pokemon: str, elo_cutoff: str = "0+"
) -> dict | None:
    """Return the latest Pikalytics usage payload for a Pokemon + ELO cutoff.

    Returns None if no snapshot exists or the Pokemon is absent.
    """
    async with get_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT pu.id, pu.pokemon, pu.usage_percent, pu.rank, pu.raw_count
               FROM champions_pokemon_usage pu
               JOIN champions_usage_snapshots s ON s.id = pu.snapshot_id
               WHERE s.source = 'pikalytics'
                 AND s.elo_cutoff = ?
                 AND pu.pokemon = ?
               ORDER BY s.fetched_at DESC
               LIMIT 1""",
            (elo_cutoff, pokemon),
        ) as cursor:
            header = await cursor.fetchone()
        if header is None:
            return None
        pu_id = header["id"]

        async def _rows(table: str, col: str) -> list[tuple[str, float]]:
            async with db.execute(
                f"SELECT {col}, percent FROM {table} WHERE pokemon_usage_id = ? ORDER BY percent DESC",
                (pu_id,),
            ) as c:
                return [(r[0], r[1]) async for r in c]

        moves = await _rows("champions_usage_moves", "move")
        items = await _rows("champions_usage_items", "item")
        abilities = await _rows("champions_usage_abilities", "ability")
        teammates = await _rows("champions_usage_teammates", "teammate")

    return {
        "pokemon": header["pokemon"],
        "elo_cutoff": elo_cutoff,
        "usage_percent": header["usage_percent"],
        "rank": header["rank"],
        "raw_count": header["raw_count"],
        "moves": moves,
        "items": items,
        "abilities": abilities,
        "teammates": teammates,
    }
```

- [ ] **Step 4: Run query tests**

```bash
uv run python -m pytest tests/test_tools_champions_usage.py -v
```

Expected: both query tests pass. Fix issues before moving on.

- [ ] **Step 5: Write failing MCP tool test**

Append to `tests/test_tools_champions_usage.py`:

```python
from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.tools.champions_usage import register_champions_usage_tools


@pytest.mark.asyncio
async def test_mcp_tool_returns_usage(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await _seed(db)

    mcp = FastMCP("test")
    register_champions_usage_tools(mcp)

    # Invoke the registered tool directly
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_champions_usage_stats" in tool_names

    result = await mcp.call_tool(
        "get_champions_usage_stats",
        {"pokemon": "Incineroar", "elo_cutoff": "0+"},
    )
    # FastMCP call_tool returns a list of content items; the JSON payload is in the first
    assert result  # non-empty


@pytest.mark.asyncio
async def test_mcp_tool_returns_error_for_missing(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)

    mcp = FastMCP("test")
    register_champions_usage_tools(mcp)

    result = await mcp.call_tool(
        "get_champions_usage_stats",
        {"pokemon": "Missingno", "elo_cutoff": "0+"},
    )
    assert result  # error response is still non-empty
```

- [ ] **Step 6: Run test, expect failure**

```bash
uv run python -m pytest tests/test_tools_champions_usage.py -v
```

Expected: `ModuleNotFoundError: smogon_vgc_mcp.tools.champions_usage`.

- [ ] **Step 7: Implement MCP tool**

Create `src/smogon_vgc_mcp/tools/champions_usage.py`:

```python
"""Champions usage MCP tool backed by Pikalytics data."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database.queries import get_champions_usage
from smogon_vgc_mcp.utils import make_error_response


def _normalize_pokemon_id(pokemon: str) -> str:
    return pokemon.lower().replace(" ", "").replace("-", "")


def register_champions_usage_tools(mcp: FastMCP) -> None:
    """Register Champions usage tools with the MCP server."""

    @mcp.tool()
    async def get_champions_usage_stats(
        pokemon: str,
        elo_cutoff: str = "0+",
    ) -> dict:
        """Get Pikalytics usage statistics for a Pokemon in Champions format.

        Returns usage %, rank, top moves, items, abilities, and teammates
        for the given ELO cutoff ("0+", "1500+", "1630+", "1760+").

        Examples:
        - "Incineroar usage stats in Champions"
        - "What moves does Garchomp run in Champions at 1760+?"

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Garchomp").
            elo_cutoff: ELO cutoff: "0+", "1500+", "1630+", or "1760+".
        """
        valid_cutoffs = {"0+", "1500+", "1630+", "1760+"}
        if elo_cutoff not in valid_cutoffs:
            return make_error_response(
                f"Invalid elo_cutoff '{elo_cutoff}'",
                hint=f"Must be one of: {sorted(valid_cutoffs)}",
            )

        pokemon_id = _normalize_pokemon_id(pokemon)
        result = await get_champions_usage(pokemon_id, elo_cutoff=elo_cutoff)
        if result is None:
            return make_error_response(
                f"No Champions usage data for '{pokemon}' at {elo_cutoff}",
                hint="Run the Pikalytics fetcher first, or try a different Pokemon/ELO",
            )
        return result
```

- [ ] **Step 8: Wire into tools/__init__.py and server.py**

In `src/smogon_vgc_mcp/tools/__init__.py`, add alongside the other registration imports:

```python
from smogon_vgc_mcp.tools.champions_usage import register_champions_usage_tools
```

and append `"register_champions_usage_tools"` to `__all__`.

In `src/smogon_vgc_mcp/server.py`, find the line `register_champions_calculator_tools(logged_mcp)` and add directly after it:

```python
register_champions_usage_tools(logged_mcp)
```

(import `register_champions_usage_tools` at the top of the file alongside the other tool imports).

- [ ] **Step 9: Run the full new test suite**

```bash
uv run python -m pytest tests/test_tools_champions_usage.py \
                        tests/test_fetcher_pikalytics_champions.py \
                        tests/test_fetcher_champions_moves.py \
                        tests/test_database_champions_usage_schema.py -v
```

Expected: all tests pass.

- [ ] **Step 10: Type-check, lint, commit**

```bash
uv run ty check src/smogon_vgc_mcp/tools/champions_usage.py \
                src/smogon_vgc_mcp/server.py \
                src/smogon_vgc_mcp/database/queries.py
uv run ruff check --fix src/smogon_vgc_mcp/tools/ \
                       src/smogon_vgc_mcp/database/queries.py \
                       tests/test_tools_champions_usage.py
uv run ruff format src/smogon_vgc_mcp/tools/ \
                   src/smogon_vgc_mcp/database/queries.py \
                   tests/test_tools_champions_usage.py
```

All green:

```bash
git add src/smogon_vgc_mcp/tools/champions_usage.py \
        src/smogon_vgc_mcp/tools/__init__.py \
        src/smogon_vgc_mcp/server.py \
        src/smogon_vgc_mcp/database/queries.py \
        tests/test_tools_champions_usage.py
git commit -m "feat(champions): expose Pikalytics usage via MCP tool"
```

---

## Task 7: End-to-end smoke (live network, optional)

**Files:** none — verification only.

- [ ] **Step 1: Run Serebii moves fetch live**

```bash
uv run python -c "
import asyncio
from smogon_vgc_mcp.fetcher.champions_moves import fetch_and_store_champions_moves
print(asyncio.run(fetch_and_store_champions_moves(dry_run=True)))
"
```

Expected: `fetched` > 0, `errors` empty (or only minor parse warnings). If 0 fetched, debug the parser against the live page.

- [ ] **Step 2: Run Pikalytics fetch live (dry run)**

```bash
uv run python -c "
import asyncio
from smogon_vgc_mcp.fetcher.pikalytics_champions import fetch_and_store_pikalytics_champions
print(asyncio.run(fetch_and_store_pikalytics_champions(dry_run=True, slugs=['incineroar'])))
"
```

Expected: `fetched: 1`, `errors: []`, one dict in `results` with non-empty moves/items/abilities.

- [ ] **Step 3: Run the full test suite to catch regressions**

```bash
uv run python -m pytest -x --ignore=tests/integration 2>&1 | tail -40
```

Expected: new tests pass, no regressions introduced in the existing 53 pre-existing failures (which are unrelated to this work). If new failures appear in Champions or fetcher tests, fix before closing out.

- [ ] **Step 4: Final commit (if any cleanup needed)**

If Steps 1–3 surfaced fixes, commit them:

```bash
git add -u
git commit -m "fix(champions): address smoke test findings"
```

---

## Self-Review Notes

- **Spec coverage:** Phase 1 delivers Serebii move changes (parser + store + queries). Phase 2 delivers Pikalytics usage data (schema + model + parser + store + query + MCP tool). Both follow the two-phase fetch/store pattern from `champions_dex.py`.
- **Open assumptions:** Serebii updatedattacks page layout and Pikalytics heading structure are validated against fixtures in Tasks 1 and 4; parsers may need minor tweaks after inspecting real HTML. The `pikalytics` circuit breaker registration (Task 5 Step 4) depends on how `fetch_text_resilient` manages services — confirm during implementation.
- **Out of scope (v1):** Pikalytics spread parsing is stubbed (empty list). Multi-ELO scraping in a single run is supported but the caller must loop over `ELO_CUTOFFS`.
