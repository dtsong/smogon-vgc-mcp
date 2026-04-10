# Champions Pokedex Data Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Serebii-backed data pipeline that scrapes Champions Pokedex data (201 base Pokemon + 58 Mega forms) into separate SQLite tables, following the existing fetcher/store patterns.

**Architecture:** New `fetcher/champions_dex.py` scrapes Serebii HTML pages using positional parsing, stores into `champions_dex_*` tables via transactional refresh. New `ChampionsDexPokemon` and `ChampionsDexMove` models in `database/models.py`. HTML parsing tested against saved fixtures.

**Tech Stack:** Python 3.12, httpx (async HTTP), aiosqlite, BeautifulSoup4 (HTML parsing), pytest + pytest-asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/smogon_vgc_mcp/database/schema.py` | Modify | Add `champions_dex_*` table DDL |
| `src/smogon_vgc_mcp/database/models.py` | Modify | Add `ChampionsDexPokemon`, `ChampionsDexMove` dataclasses |
| `src/smogon_vgc_mcp/database/queries.py` | Modify | Add Champions Pokedex query functions |
| `src/smogon_vgc_mcp/fetcher/champions_dex.py` | Create | Serebii scraper + store orchestrator |
| `src/smogon_vgc_mcp/fetcher/champions_pokemon_list.py` | Create | Static list of 201 Champions Pokemon names |
| `src/smogon_vgc_mcp/formats.py` | Modify | Uncomment `champions_ma` FormatConfig entry |
| `tests/test_fetcher_champions_dex.py` | Create | HTML parsing tests with fixtures |
| `tests/test_champions_dex_queries.py` | Create | Query function tests |
| `tests/fixtures/` | Create dir | Saved Serebii HTML fixtures for parser tests |
| `tests/fixtures/serebii_charizard.html` | Create | Sample Pokemon page fixture |
| `tests/fixtures/serebii_charizard_mega_x.html` | Create | Sample Mega form page fixture |

---

### Task 1: Add BeautifulSoup4 dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add bs4 to project dependencies**

```toml
# In [project.dependencies], add:
"beautifulsoup4>=4.12",
```

- [ ] **Step 2: Install and verify**

Run: `uv sync`
Expected: Successful install, no errors

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add beautifulsoup4 dependency for HTML parsing"
```

---

### Task 2: Champions database schema — tables and indexes

**Files:**
- Modify: `src/smogon_vgc_mcp/database/schema.py`
- Test: `tests/test_champions_dex_queries.py`

- [ ] **Step 1: Write failing test that Champions tables exist after init**

Create `tests/test_champions_dex_queries.py`:

```python
"""Tests for Champions Pokedex database schema and queries."""

import pytest
import aiosqlite

from smogon_vgc_mcp.database.schema import init_database


@pytest.mark.asyncio
async def test_champions_tables_created(tmp_path):
    """Champions dex tables should exist after database init."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    async with aiosqlite.connect(db_path) as db:
        # Check champions_dex_pokemon exists
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='champions_dex_pokemon'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None, "champions_dex_pokemon table not created"

        # Check champions_dex_moves exists
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='champions_dex_moves'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None, "champions_dex_moves table not created"

        # Check champions_dex_abilities exists
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='champions_dex_abilities'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None, "champions_dex_abilities table not created"

        # Check champions_dex_learnsets exists
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='champions_dex_learnsets'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None, "champions_dex_learnsets table not created"


@pytest.mark.asyncio
async def test_champions_pokemon_columns(tmp_path):
    """champions_dex_pokemon should have Mega form columns."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("PRAGMA table_info(champions_dex_pokemon)") as cursor:
            columns = {row[1] async for row in cursor}

        assert "base_form_id" in columns
        assert "is_mega" in columns
        assert "mega_stone" in columns
        assert "hp" in columns
        assert "type1" in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_champions_dex_queries.py::test_champions_tables_created -v`
Expected: FAIL — tables don't exist yet

- [ ] **Step 3: Add Champions table DDL to SCHEMA**

In `src/smogon_vgc_mcp/database/schema.py`, append to the `SCHEMA` string (before the closing `"""`):

```sql
-- =============================================================================
-- Champions Pokedex data (from Serebii)
-- =============================================================================

-- Champions Pokemon species data (rebalanced stats, Mega forms)
CREATE TABLE IF NOT EXISTS champions_dex_pokemon (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    type1 TEXT NOT NULL,
    type2 TEXT,
    hp INTEGER NOT NULL,
    atk INTEGER NOT NULL,
    def INTEGER NOT NULL,
    spa INTEGER NOT NULL,
    spd INTEGER NOT NULL,
    spe INTEGER NOT NULL,
    ability1 TEXT,
    ability2 TEXT,
    ability_hidden TEXT,
    base_form_id TEXT,
    is_mega INTEGER NOT NULL DEFAULT 0,
    mega_stone TEXT,
    height_m REAL,
    weight_kg REAL
);

-- Champions move data (includes rebalanced moves)
CREATE TABLE IF NOT EXISTS champions_dex_moves (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    category TEXT NOT NULL,
    base_power INTEGER,
    accuracy INTEGER,
    pp INTEGER,
    priority INTEGER DEFAULT 0,
    target TEXT,
    description TEXT,
    short_desc TEXT
);

-- Champions ability data
CREATE TABLE IF NOT EXISTS champions_dex_abilities (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    short_desc TEXT
);

-- Champions learnsets (Pokemon -> Move mapping)
CREATE TABLE IF NOT EXISTS champions_dex_learnsets (
    pokemon_id TEXT,
    move_id TEXT,
    method TEXT,
    PRIMARY KEY (pokemon_id, move_id)
);

-- Indexes for Champions Pokedex queries
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_name ON champions_dex_pokemon(name);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_type1 ON champions_dex_pokemon(type1);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_type2 ON champions_dex_pokemon(type2);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_base_form ON champions_dex_pokemon(base_form_id);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_is_mega ON champions_dex_pokemon(is_mega);
CREATE INDEX IF NOT EXISTS idx_champ_moves_type ON champions_dex_moves(type);
CREATE INDEX IF NOT EXISTS idx_champ_moves_category ON champions_dex_moves(category);
CREATE INDEX IF NOT EXISTS idx_champ_abilities_name ON champions_dex_abilities(name);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_champions_dex_queries.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/database/schema.py tests/test_champions_dex_queries.py
git commit -m "feat: add Champions Pokedex database tables and indexes (#6)"
```

---

### Task 3: Champions data models

**Files:**
- Modify: `src/smogon_vgc_mcp/database/models.py`
- Test: `tests/test_database_models.py`

- [ ] **Step 1: Write failing test for ChampionsDexPokemon model**

Append to `tests/test_database_models.py`:

```python
class TestChampionsDexPokemon:
    """Tests for ChampionsDexPokemon dataclass."""

    def test_base_form(self):
        from smogon_vgc_mcp.database.models import ChampionsDexPokemon

        pkmn = ChampionsDexPokemon(
            id="charizard",
            num=6,
            name="Charizard",
            types=["Fire", "Flying"],
            base_stats={"hp": 78, "atk": 104, "def": 98, "spa": 159, "spd": 115, "spe": 100},
            abilities=["Blaze"],
        )
        assert pkmn.name == "Charizard"
        assert pkmn.base_stats["spa"] == 159
        assert pkmn.is_mega is False
        assert pkmn.base_form_id is None

    def test_mega_form(self):
        from smogon_vgc_mcp.database.models import ChampionsDexPokemon

        mega = ChampionsDexPokemon(
            id="charizard-mega-x",
            num=6,
            name="Mega Charizard X",
            types=["Fire", "Dragon"],
            base_stats={"hp": 78, "atk": 170, "def": 131, "spa": 170, "spd": 115, "spe": 100},
            abilities=["Tough Claws"],
            is_mega=True,
            base_form_id="charizard",
            mega_stone="Charizardite X",
        )
        assert mega.is_mega is True
        assert mega.base_form_id == "charizard"
        assert mega.mega_stone == "Charizardite X"


class TestChampionsDexMove:
    """Tests for ChampionsDexMove dataclass."""

    def test_rebalanced_move(self):
        from smogon_vgc_mcp.database.models import ChampionsDexMove

        move = ChampionsDexMove(
            id="flamethrower",
            num=53,
            name="Flamethrower",
            type="Fire",
            category="Special",
            base_power=90,
            accuracy=100,
            pp=15,
        )
        assert move.base_power == 90
        assert move.category == "Special"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_database_models.py::TestChampionsDexPokemon -v`
Expected: FAIL — `ChampionsDexPokemon` does not exist

- [ ] **Step 3: Add dataclasses to models.py**

Append to `src/smogon_vgc_mcp/database/models.py`:

```python
# =============================================================================
# Champions Pokedex data models (from Serebii)
# =============================================================================


@dataclass
class ChampionsDexPokemon:
    """Champions Pokemon species data (rebalanced stats, Mega forms)."""

    id: str
    num: int
    name: str
    types: list[str]
    base_stats: dict[str, int]  # hp, atk, def, spa, spd, spe
    abilities: list[str]
    ability_hidden: str | None = None
    height_m: float = 0.0
    weight_kg: float = 0.0
    is_mega: bool = False
    base_form_id: str | None = None  # FK to base form for Megas
    mega_stone: str | None = None


@dataclass
class ChampionsDexMove:
    """Champions move data (includes rebalanced moves)."""

    id: str
    num: int
    name: str
    type: str
    category: str
    base_power: int | None
    accuracy: int | None
    pp: int
    priority: int = 0
    target: str | None = None
    description: str | None = None
    short_desc: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_database_models.py::TestChampionsDexPokemon tests/test_database_models.py::TestChampionsDexMove -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/database/models.py tests/test_database_models.py
git commit -m "feat: add ChampionsDexPokemon and ChampionsDexMove models (#6)"
```

---

### Task 4: Champions Pokemon name list

**Files:**
- Create: `src/smogon_vgc_mcp/fetcher/champions_pokemon_list.py`
- Test: `tests/test_fetcher_champions_dex.py`

This is the static list of all 201 Champions Pokemon. The scraper iterates over this list to fetch individual Serebii pages. Serebii uses lowercased, hyphenated names in URLs (e.g., `/pokedex-champions/charizard/`).

- [ ] **Step 1: Write failing test for the Pokemon list**

Create `tests/test_fetcher_champions_dex.py`:

```python
"""Tests for Champions Pokedex fetcher."""


class TestChampionsPokemonList:
    """Tests for the static Champions Pokemon roster."""

    def test_list_has_expected_count(self):
        from smogon_vgc_mcp.fetcher.champions_pokemon_list import CHAMPIONS_POKEMON

        # 201 base forms in the Champions roster
        assert len(CHAMPIONS_POKEMON) == 201

    def test_contains_key_pokemon(self):
        from smogon_vgc_mcp.fetcher.champions_pokemon_list import CHAMPIONS_POKEMON

        # Starters and iconic Pokemon must be present
        for name in ["charizard", "pikachu", "mewtwo", "gardevoir", "dragonite", "greninja"]:
            assert name in CHAMPIONS_POKEMON, f"{name} missing from Champions roster"

    def test_names_are_lowercase(self):
        from smogon_vgc_mcp.fetcher.champions_pokemon_list import CHAMPIONS_POKEMON

        for name in CHAMPIONS_POKEMON:
            assert name == name.lower(), f"{name} should be lowercase"
            assert " " not in name, f"{name} should not contain spaces"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fetcher_champions_dex.py::TestChampionsPokemonList -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Create the Pokemon list module**

Create `src/smogon_vgc_mcp/fetcher/champions_pokemon_list.py`:

```python
"""Static list of all 201 Pokemon in Pokemon Champions.

Used to drive the Serebii page scraper — each name maps to
a Serebii URL at /pokedex-champions/{name}/.

Source: Serebii.net Champions Pokedex (April 2026 launch roster).
"""

# fmt: off
CHAMPIONS_POKEMON: list[str] = [
    "venusaur", "charizard", "blastoise", "pikachu", "raichu",
    "nidoqueen", "nidoking", "clefable", "ninetales", "arcanine",
    "alakazam", "machamp", "golem", "gengar", "kingler",
    "exeggutor", "marowak", "hitmonlee", "hitmonchan", "chansey",
    "kangaskhan", "mr-mime", "scyther", "jynx", "pinsir",
    "gyarados", "lapras", "ditto", "eevee", "vaporeon",
    "jolteon", "flareon", "snorlax", "dragonite", "mewtwo",
    "mew", "typhlosion", "feraligatr", "ampharos", "espeon",
    "umbreon", "slowking", "steelix", "scizor", "heracross",
    "kingdra", "hitmontop", "blissey", "tyranitar", "blaziken",
    "swampert", "gardevoir", "breloom", "slaking", "sableye",
    "mawile", "aggron", "medicham", "sharpedo", "camerupt",
    "altaria", "zangoose", "seviper", "lunatone", "solrock",
    "milotic", "banette", "absol", "salamence", "metagross",
    "latias", "latios", "rayquaza", "jirachi", "infernape",
    "empoleon", "luxray", "roserade", "garchomp", "lucario",
    "hippowdon", "drapion", "toxicroak", "leafeon", "glaceon",
    "gallade", "dusknoir", "rotom", "darkrai", "arceus",
    "samurott", "excadrill", "audino", "conkeldurr", "scolipede",
    "krookodile", "darmanitan", "zoroark", "reuniclus", "chandelure",
    "haxorus", "mienshao", "hydreigon", "volcarona", "greninja",
    "talonflame", "vivillon", "aegislash", "sylveon", "goodra",
    "trevenant", "noivern", "decidueye", "incineroar", "primarina",
    "lycanroc", "toxapex", "mudsdale", "araquanid", "lurantis",
    "bewear", "tsareena", "comfey", "mimikyu", "kommo-o",
    "cinderace", "rillaboom", "inteleon", "corviknight", "orbeetle",
    "drednaw", "coalossal", "appletun", "sandaconda", "cramorant",
    "barraskewda", "toxtricity", "centiskorch", "polteageist",
    "hatterene", "grimmsnarl", "obstagoon", "perrserker", "cursola",
    "sirfetchd", "mr-rime", "runerigus", "alcremie", "falinks",
    "pincurchin", "frosmoth", "stonjourner", "eiscue", "copperajah",
    "dracozolt", "arctozolt", "dracovish", "arctovish", "duraludon",
    "dragapult", "urshifu", "zarude", "glastrier", "spectrier",
    "wyrdeer", "kleavor", "ursaluna", "basculegion", "sneasler",
    "overqwil", "enamorus", "meowscarada", "skeledirge", "quaquaval",
    "spidops", "lokix", "pawmot", "maushold", "dachsbun",
    "arboliva", "squawkabilly", "nacli", "garganacl", "armarouge",
    "ceruledge", "palafin", "flamigo", "cetitan", "veluza",
    "dondozo", "tatsugiri", "annihilape", "clodsire", "farigiraf",
    "dudunsparce", "kingambit", "great-tusk", "iron-treads",
    "iron-hands", "iron-jugulis", "iron-thorns", "iron-bundle",
    "iron-valiant", "roaring-moon", "iron-leaves", "bloodmoon-ursaluna",
    "ogerpon", "terapagos",
]
# fmt: on

# Mega forms are discovered during scraping — the base form page links to them.
# This dict maps base_form_id -> list of (mega_id, mega_stone) tuples.
# Populated at scrape time, but known Megas listed here for reference/validation.
KNOWN_MEGA_POKEMON: dict[str, list[tuple[str, str]]] = {
    "charizard": [("charizard-mega-x", "Charizardite X"), ("charizard-mega-y", "Charizardite Y")],
    "mewtwo": [("mewtwo-mega-x", "Mewtwonite X"), ("mewtwo-mega-y", "Mewtwonite Y")],
    "venusaur": [("venusaur-mega", "Venusaurite")],
    "blastoise": [("blastoise-mega", "Blastoisinite")],
    "alakazam": [("alakazam-mega", "Alakazite")],
    "gengar": [("gengar-mega", "Gengarite")],
    "kangaskhan": [("kangaskhan-mega", "Kangaskhanite")],
    "pinsir": [("pinsir-mega", "Pinsirite")],
    "gyarados": [("gyarados-mega", "Gyaradosite")],
    "scizor": [("scizor-mega", "Scizorite")],
    "heracross": [("heracross-mega", "Heracrossite")],
    "tyranitar": [("tyranitar-mega", "Tyranitarite")],
    "blaziken": [("blaziken-mega", "Blazikenite")],
    "swampert": [("swampert-mega", "Swampertite")],
    "gardevoir": [("gardevoir-mega", "Gardevoirite")],
    "mawile": [("mawile-mega", "Mawilite")],
    "aggron": [("aggron-mega", "Aggronite")],
    "medicham": [("medicham-mega", "Medichamite")],
    "sharpedo": [("sharpedo-mega", "Sharpedonite")],
    "camerupt": [("camerupt-mega", "Cameruptite")],
    "altaria": [("altaria-mega", "Altarianite")],
    "banette": [("banette-mega", "Banettite")],
    "absol": [("absol-mega", "Absolite")],
    "salamence": [("salamence-mega", "Salamencite")],
    "metagross": [("metagross-mega", "Metagrossite")],
    "latias": [("latias-mega", "Latiasite")],
    "latios": [("latios-mega", "Latiosite")],
    "rayquaza": [("rayquaza-mega", "N/A")],
    "garchomp": [("garchomp-mega", "Garchompite")],
    "lucario": [("lucario-mega", "Lucarionite")],
    "gallade": [("gallade-mega", "Galladite")],
    "audino": [("audino-mega", "Audinite")],
    "diancie": [("diancie-mega", "Diancite")],
    "sableye": [("sableye-mega", "Sablenite")],
    # Champions-exclusive new Megas:
    "dragonite": [("dragonite-mega", "Dragonitite")],
    "greninja": [("greninja-mega", "Greninjaite")],
    "clefable": [("clefable-mega", "Clefablite")],
    "arcanine": [("arcanine-mega", "Arcaninite")],
    "machamp": [("machamp-mega", "Machampite")],
    "snorlax": [("snorlax-mega", "Snorlaxite")],
    "kingdra": [("kingdra-mega", "Kingdranite")],
    "milotic": [("milotic-mega", "Milotite")],
    "infernape": [("infernape-mega", "Infernapite")],
    "darkrai": [("darkrai-mega", "Darkrainite")],
    "volcarona": [("volcarona-mega", "Volcaronite")],
    "hydreigon": [("hydreigon-mega", "Hydreigonite")],
    "aegislash": [("aegislash-mega", "Aegislashite")],
    "goodra": [("goodra-mega", "Goodranite")],
    "mimikyu": [("mimikyu-mega", "Mimikyunite")],
    "dragapult": [("dragapult-mega", "Dragapultite")],
    "hatterene": [("hatterene-mega", "Hatterenite")],
    "grimmsnarl": [("grimmsnarl-mega", "Grimmsnarlite")],
    "toxtricity": [("toxtricity-mega", "Toxtricitite")],
    "kommo-o": [("kommo-o-mega", "Kommonite")],
    "annihilape": [("annihilape-mega", "Annihilapite")],
    "kingambit": [("kingambit-mega", "Kingambitite")],
    "incineroar": [("incineroar-mega", "Incineroarenite")],
}
```

> **Note:** This list will need validation against the actual Serebii roster page. The exact 201 names and 58 Mega forms should be verified during a dry-run scrape (Task 7). Some names/stones are best-effort from research and may need correction.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetcher_champions_dex.py::TestChampionsPokemonList -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/champions_pokemon_list.py tests/test_fetcher_champions_dex.py
git commit -m "feat: add Champions Pokemon roster list (201 base forms + known Megas) (#6)"
```

---

### Task 5: Serebii HTML parser — Pokemon page

**Files:**
- Create: `tests/fixtures/` directory
- Create: `tests/fixtures/serebii_charizard.html` (saved fixture)
- Create: `tests/fixtures/serebii_charizard_mega_x.html` (saved fixture)
- Create: `src/smogon_vgc_mcp/fetcher/champions_dex.py`
- Modify: `tests/test_fetcher_champions_dex.py`

The parser extracts from Serebii's `/pokedex-champions/{name}/` pages: name, types, base stats (HP/Atk/Def/SpA/SpD/Spe), abilities, height, weight, and Mega form links. Serebii HTML has **no CSS class names** on data cells — parse by table structure and text patterns.

- [ ] **Step 1: Fetch and save HTML fixtures**

Run these manually to create test fixtures (do NOT commit to automated scraping without fixtures):

```bash
mkdir -p tests/fixtures
curl -s "https://www.serebii.net/pokedex-champions/charizard/" -o tests/fixtures/serebii_charizard.html
curl -s "https://www.serebii.net/pokedex-champions/mewtwo/" -o tests/fixtures/serebii_mewtwo.html
```

If Serebii returns 403, use a browser User-Agent:
```bash
curl -s -H "User-Agent: Mozilla/5.0" "https://www.serebii.net/pokedex-champions/charizard/" -o tests/fixtures/serebii_charizard.html
```

Inspect the HTML structure to identify:
- The table containing base stats (look for "HP", "Attack", "Defense" header cells)
- The table/section containing type information
- The table/section containing abilities
- Links to Mega Evolution pages (if present on base form page)

> **IMPORTANT:** Before writing the parser, you MUST read the actual downloaded HTML and adapt the parsing logic to match the real structure. The code below is a template based on typical Serebii layout — adjust selectors after inspecting fixtures.

- [ ] **Step 2: Write failing tests for the parser**

Add to `tests/test_fetcher_champions_dex.py`:

```python
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseSerebiiPokemonPage:
    """Tests for parsing Serebii Champions Pokemon pages."""

    def test_parse_base_form_stats(self):
        from smogon_vgc_mcp.fetcher.champions_dex import parse_serebii_pokemon_page

        html = (FIXTURES_DIR / "serebii_charizard.html").read_text()
        result = parse_serebii_pokemon_page(html, "charizard")

        assert result is not None
        assert result["name"] == "Charizard"
        assert "Fire" in result["types"]
        assert len(result["base_stats"]) == 6
        assert all(stat in result["base_stats"] for stat in ["hp", "atk", "def", "spa", "spd", "spe"])
        # Champions Charizard has rebalanced stats (SpA 159, not 109)
        assert result["base_stats"]["spa"] > 100
        assert len(result["abilities"]) >= 1

    def test_parse_detects_mega_forms(self):
        from smogon_vgc_mcp.fetcher.champions_dex import parse_serebii_pokemon_page

        html = (FIXTURES_DIR / "serebii_charizard.html").read_text()
        result = parse_serebii_pokemon_page(html, "charizard")

        assert result is not None
        # Charizard has Mega X and Mega Y
        assert len(result.get("mega_forms", [])) >= 1

    def test_parse_returns_none_for_empty_html(self):
        from smogon_vgc_mcp.fetcher.champions_dex import parse_serebii_pokemon_page

        result = parse_serebii_pokemon_page("", "charizard")
        assert result is None

    def test_parse_returns_none_for_404_page(self):
        from smogon_vgc_mcp.fetcher.champions_dex import parse_serebii_pokemon_page

        result = parse_serebii_pokemon_page("<html><body>404 Not Found</body></html>", "fakemon")
        assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_fetcher_champions_dex.py::TestParseSerebiiPokemonPage -v`
Expected: FAIL — `parse_serebii_pokemon_page` does not exist

- [ ] **Step 4: Implement the parser**

Create `src/smogon_vgc_mcp/fetcher/champions_dex.py`:

```python
"""Fetch and parse Champions Pokedex data from Serebii.

Serebii HTML has no CSS class names on data cells. Parsing relies on
table structure and text patterns. All parsing logic is tested against
saved HTML fixtures to catch breakage from layout changes.

Data source: serebii.net/pokedex-champions/
Attribution: Pokemon data from Serebii.net.
"""

import asyncio
import re

from bs4 import BeautifulSoup, Tag

from smogon_vgc_mcp.utils import fetch_text_resilient

SEREBII_BASE_URL = "https://www.serebii.net/pokedex-champions"
SEREBII_SERVICE = "serebii"
# Polite delay between requests (seconds)
REQUEST_DELAY = 1.0


def parse_serebii_pokemon_page(html: str, pokemon_id: str) -> dict | None:
    """Parse a Serebii Champions Pokemon page into structured data.

    Args:
        html: Raw HTML content from serebii.net/pokedex-champions/{name}/
        pokemon_id: Lowercase Pokemon identifier (e.g., "charizard")

    Returns:
        Dict with keys: name, types, base_stats, abilities, ability_hidden,
        height_m, weight_kg, mega_forms. Returns None if parsing fails.
    """
    if not html or len(html) < 100:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Detect 404/error pages
    title = soup.find("title")
    if title and "404" in title.get_text():
        return None

    result: dict = {
        "pokemon_id": pokemon_id,
        "name": "",
        "types": [],
        "base_stats": {},
        "abilities": [],
        "ability_hidden": None,
        "height_m": 0.0,
        "weight_kg": 0.0,
        "mega_forms": [],
    }

    # --- Parse name ---
    # Serebii typically has the Pokemon name in a large header or title
    name = _extract_name(soup, pokemon_id)
    if not name:
        return None
    result["name"] = name

    # --- Parse types ---
    result["types"] = _extract_types(soup)

    # --- Parse base stats ---
    result["base_stats"] = _extract_base_stats(soup)
    if not result["base_stats"]:
        return None

    # --- Parse abilities ---
    abilities, hidden = _extract_abilities(soup)
    result["abilities"] = abilities
    result["ability_hidden"] = hidden

    # --- Parse physical data ---
    result["height_m"], result["weight_kg"] = _extract_physical_data(soup)

    # --- Detect Mega forms ---
    result["mega_forms"] = _extract_mega_links(soup, pokemon_id)

    return result


def _extract_name(soup: BeautifulSoup, pokemon_id: str) -> str:
    """Extract Pokemon name from page. Adapt after inspecting fixture HTML."""
    # Strategy 1: Look for the main header with Pokemon name
    # Serebii often uses a table cell with the name prominently
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        # Match pattern like "Charizard" or "#006 Charizard"
        if pokemon_id.replace("-", "").lower() in text.replace(" ", "").lower():
            # Extract just the name part
            name_match = re.search(r"#?\d*\s*([A-Z][a-zA-Z\s\-':.]+)", text)
            if name_match:
                return name_match.group(1).strip()

    # Fallback: title tag
    title = soup.find("title")
    if title:
        title_text = title.get_text()
        # Serebii titles are like "Charizard - Pokemon Champions Pokedex"
        name_match = re.match(r"([^-]+)", title_text)
        if name_match:
            return name_match.group(1).strip()

    return pokemon_id.replace("-", " ").title()


def _extract_types(soup: BeautifulSoup) -> list[str]:
    """Extract Pokemon types from page.

    Serebii shows types as small images with alt text like 'Fire' or 'Flying'.
    Look for img tags with src containing '/type/' or alt matching known types.
    """
    known_types = {
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
        "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
        "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
    }
    types: list[str] = []

    # Look for type images — Serebii uses /type/fire.gif etc.
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        if "/type/" in src.lower():
            # Extract type name from src: /type/fire.gif -> Fire
            type_match = re.search(r"/type/(\w+)\.", src, re.IGNORECASE)
            if type_match:
                type_name = type_match.group(1).capitalize()
                if type_name in known_types and type_name not in types:
                    types.append(type_name)
        elif alt in known_types and alt not in types:
            types.append(alt)

    # Deduplicate while preserving order, take first two
    return types[:2]


def _extract_base_stats(soup: BeautifulSoup) -> dict[str, int]:
    """Extract base stats from the stats table.

    Looks for a table containing cells with text 'HP', 'Attack', 'Defense',
    'Sp. Attack', 'Sp. Defense', 'Speed' followed by numeric values.
    """
    stat_names = {
        "HP": "hp",
        "Attack": "atk",
        "Defense": "def",
        "Sp. Attack": "spa",
        "Sp. Atk": "spa",
        "Sp. Defense": "spd",
        "Sp. Def": "spd",
        "Speed": "spe",
    }
    stats: dict[str, int] = {}

    # Find all tables and look for one containing stat headers
    for table in soup.find_all("table"):
        table_text = table.get_text()
        if "HP" in table_text and "Attack" in table_text and "Speed" in table_text:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                for i, cell in enumerate(cells):
                    cell_text = cell.get_text(strip=True)
                    if cell_text in stat_names:
                        key = stat_names[cell_text]
                        # Look for the numeric value in the next cell
                        if i + 1 < len(cells):
                            val_text = cells[i + 1].get_text(strip=True)
                            val_match = re.search(r"(\d+)", val_text)
                            if val_match and key not in stats:
                                stats[key] = int(val_match.group(1))

            if len(stats) == 6:
                return stats

    # Fallback: search for stat pattern in any context
    # Some Serebii pages use a different layout
    all_text = soup.get_text()
    for display_name, key in stat_names.items():
        if key not in stats:
            pattern = rf"{re.escape(display_name)}\s*[:：]?\s*(\d+)"
            match = re.search(pattern, all_text)
            if match:
                stats[key] = int(match.group(1))

    return stats if len(stats) == 6 else {}


def _extract_abilities(soup: BeautifulSoup) -> tuple[list[str], str | None]:
    """Extract abilities from page. Returns (regular_abilities, hidden_ability)."""
    abilities: list[str] = []
    hidden: str | None = None

    # Serebii shows abilities in a section — look for "Abilities" header
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if "Abilities:" in text or "Ability:" in text:
            # Extract ability names from links within parent context
            parent = td.parent
            if parent:
                for a_tag in parent.find_all("a"):
                    ability_name = a_tag.get_text(strip=True)
                    if ability_name and len(ability_name) > 1:
                        abilities.append(ability_name)

    # Look for hidden ability marker
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if "Hidden Ability" in text or "Hidden:" in text:
            parent = td.parent
            if parent:
                for a_tag in parent.find_all("a"):
                    ability_name = a_tag.get_text(strip=True)
                    if ability_name and len(ability_name) > 1:
                        hidden = ability_name
                        break

    return abilities, hidden


def _extract_physical_data(soup: BeautifulSoup) -> tuple[float, float]:
    """Extract height (m) and weight (kg) from page."""
    height = 0.0
    weight = 0.0
    all_text = soup.get_text()

    height_match = re.search(r"Height\s*[:：]?\s*([\d.]+)\s*m", all_text)
    if height_match:
        height = float(height_match.group(1))

    weight_match = re.search(r"Weight\s*[:：]?\s*([\d.]+)\s*kg", all_text)
    if weight_match:
        weight = float(weight_match.group(1))

    return height, weight


def _extract_mega_links(soup: BeautifulSoup, pokemon_id: str) -> list[dict]:
    """Extract links to Mega Evolution pages from the base form page.

    Returns list of dicts: [{"id": "charizard-mega-x", "name": "Mega Charizard X", "url": "..."}]
    """
    megas: list[dict] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)
        # Look for links containing "mega" in the Pokemon context
        if "mega" in href.lower() and pokemon_id.replace("-", "") in href.lower().replace("-", ""):
            mega_id = href.strip("/").split("/")[-1] if "/" in href else href
            megas.append({
                "id": mega_id,
                "name": text or f"Mega {pokemon_id.title()}",
                "url": href,
            })

    return megas
```

- [ ] **Step 5: Run tests (some may need fixture adjustment)**

Run: `uv run pytest tests/test_fetcher_champions_dex.py::TestParseSerebiiPokemonPage -v`

If tests fail because the HTML structure doesn't match expectations, **read the fixture HTML** and adjust the parser functions. This is expected — the parser template above is best-effort and must be adapted to actual Serebii markup.

- [ ] **Step 6: Iterate until all parser tests pass**

Adjust `_extract_*` functions based on actual fixture HTML structure. Common fixes:
- Serebii may use `<th>` instead of `<td>` for stat headers
- Type images may be in a different parent element
- Abilities may be rendered differently than expected

- [ ] **Step 7: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/champions_dex.py tests/test_fetcher_champions_dex.py tests/fixtures/
git commit -m "feat: add Serebii HTML parser for Champions Pokemon pages (#6)"
```

---

### Task 6: Store functions — Champions Pokemon and moves to SQLite

**Files:**
- Modify: `src/smogon_vgc_mcp/fetcher/champions_dex.py`
- Modify: `tests/test_champions_dex_queries.py`

- [ ] **Step 1: Write failing test for store_champions_pokemon**

Add to `tests/test_champions_dex_queries.py`:

```python
@pytest.mark.asyncio
async def test_store_champions_pokemon(tmp_path):
    """Store and retrieve a Champions Pokemon."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    from smogon_vgc_mcp.fetcher.champions_dex import store_champions_pokemon_data

    pokemon_data = [
        {
            "pokemon_id": "charizard",
            "num": 6,
            "name": "Charizard",
            "types": ["Fire", "Flying"],
            "base_stats": {"hp": 78, "atk": 104, "def": 98, "spa": 159, "spd": 115, "spe": 100},
            "abilities": ["Blaze"],
            "ability_hidden": "Solar Power",
            "height_m": 1.7,
            "weight_kg": 90.5,
            "is_mega": False,
            "base_form_id": None,
            "mega_stone": None,
        },
        {
            "pokemon_id": "charizard-mega-x",
            "num": 6,
            "name": "Mega Charizard X",
            "types": ["Fire", "Dragon"],
            "base_stats": {"hp": 78, "atk": 170, "def": 131, "spa": 170, "spd": 115, "spe": 100},
            "abilities": ["Tough Claws"],
            "ability_hidden": None,
            "height_m": 1.7,
            "weight_kg": 110.5,
            "is_mega": True,
            "base_form_id": "charizard",
            "mega_stone": "Charizardite X",
        },
    ]

    async with aiosqlite.connect(db_path) as db:
        count = await store_champions_pokemon_data(db, pokemon_data)
        assert count == 2

        # Verify stored data
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM champions_dex_pokemon WHERE id = ?", ("charizard",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["name"] == "Charizard"
            assert row["type1"] == "Fire"
            assert row["type2"] == "Flying"
            assert row["spa"] == 159
            assert row["is_mega"] == 0

        async with db.execute(
            "SELECT * FROM champions_dex_pokemon WHERE id = ?", ("charizard-mega-x",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["is_mega"] == 1
            assert row["base_form_id"] == "charizard"
            assert row["mega_stone"] == "Charizardite X"


@pytest.mark.asyncio
async def test_store_champions_pokemon_transactional(tmp_path):
    """Store is atomic — partial failures leave no data."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    from smogon_vgc_mcp.fetcher.champions_dex import store_champions_pokemon_data

    # First store some valid data
    valid_data = [{
        "pokemon_id": "pikachu",
        "num": 25,
        "name": "Pikachu",
        "types": ["Electric"],
        "base_stats": {"hp": 55, "atk": 80, "def": 50, "spa": 75, "spd": 60, "spe": 110},
        "abilities": ["Static"],
        "ability_hidden": "Lightning Rod",
        "height_m": 0.4,
        "weight_kg": 6.0,
        "is_mega": False,
        "base_form_id": None,
        "mega_stone": None,
    }]

    async with aiosqlite.connect(db_path) as db:
        await store_champions_pokemon_data(db, valid_data)
        await db.commit()

    # Verify Pikachu exists
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM champions_dex_pokemon") as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_champions_dex_queries.py::test_store_champions_pokemon -v`
Expected: FAIL — `store_champions_pokemon_data` does not exist

- [ ] **Step 3: Implement store functions**

Add to `src/smogon_vgc_mcp/fetcher/champions_dex.py`:

```python
import aiosqlite


async def store_champions_pokemon_data(
    db: aiosqlite.Connection,
    pokemon_list: list[dict],
    *,
    _commit: bool = True,
) -> int:
    """Store Champions Pokemon data into champions_dex_pokemon table.

    Follows the same transactional pattern as pokedex.py — caller
    controls commit via _commit flag for atomic batch operations.

    Args:
        db: Database connection
        pokemon_list: List of parsed Pokemon dicts from parse_serebii_pokemon_page
        _commit: Whether to commit after storing (False for batch transactions)

    Returns:
        Number of Pokemon stored
    """
    await db.execute("DELETE FROM champions_dex_pokemon")

    count = 0
    for pkmn in pokemon_list:
        types = pkmn.get("types", [])
        stats = pkmn.get("base_stats", {})

        await db.execute(
            """INSERT OR REPLACE INTO champions_dex_pokemon
               (id, num, name, type1, type2,
                hp, atk, def, spa, spd, spe,
                ability1, ability2, ability_hidden,
                base_form_id, is_mega, mega_stone,
                height_m, weight_kg)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pkmn["pokemon_id"],
                pkmn.get("num"),
                pkmn["name"],
                types[0] if types else None,
                types[1] if len(types) > 1 else None,
                stats.get("hp"),
                stats.get("atk"),
                stats.get("def"),
                stats.get("spa"),
                stats.get("spd"),
                stats.get("spe"),
                pkmn["abilities"][0] if pkmn.get("abilities") else None,
                pkmn["abilities"][1] if len(pkmn.get("abilities", [])) > 1 else None,
                pkmn.get("ability_hidden"),
                pkmn.get("base_form_id"),
                1 if pkmn.get("is_mega") else 0,
                pkmn.get("mega_stone"),
                pkmn.get("height_m", 0.0),
                pkmn.get("weight_kg", 0.0),
            ),
        )
        count += 1

    if _commit:
        await db.commit()
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_champions_dex_queries.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/champions_dex.py tests/test_champions_dex_queries.py
git commit -m "feat: add store function for Champions Pokemon data (#6)"
```

---

### Task 7: Fetch orchestrator — scrape all Champions Pokemon from Serebii

**Files:**
- Modify: `src/smogon_vgc_mcp/fetcher/champions_dex.py`
- Modify: `tests/test_fetcher_champions_dex.py`

- [ ] **Step 1: Write failing test for the orchestrator**

Add to `tests/test_fetcher_champions_dex.py`:

```python
from unittest.mock import AsyncMock, patch


class TestFetchChampionsDex:
    """Tests for the fetch orchestrator."""

    @pytest.mark.asyncio
    async def test_fetch_single_pokemon(self):
        """Test fetching a single Pokemon page."""
        from smogon_vgc_mcp.fetcher.champions_dex import fetch_champions_pokemon_page
        from smogon_vgc_mcp.resilience import FetchResult

        # Mock the HTTP fetch to return fixture HTML
        fixture_html = (FIXTURES_DIR / "serebii_charizard.html").read_text()
        mock_result = FetchResult.ok(fixture_html)

        with patch(
            "smogon_vgc_mcp.fetcher.champions_dex.fetch_text_resilient",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await fetch_champions_pokemon_page("charizard")

        assert result is not None
        assert result["name"] == "Charizard"

    @pytest.mark.asyncio
    async def test_dry_run_validates_parsing(self):
        """Dry run should validate parsing on a small subset before full scrape."""
        from smogon_vgc_mcp.fetcher.champions_dex import fetch_and_store_champions_dex
        from smogon_vgc_mcp.resilience import FetchResult

        fixture_html = (FIXTURES_DIR / "serebii_charizard.html").read_text()
        mock_result = FetchResult.ok(fixture_html)

        with patch(
            "smogon_vgc_mcp.fetcher.champions_dex.fetch_text_resilient",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await fetch_and_store_champions_dex(
                dry_run=True,
                dry_run_names=["charizard"],
            )

        assert result["dry_run"] is True
        assert result["pokemon_parsed"] >= 1
        assert result["errors"] is None or len(result["errors"]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fetcher_champions_dex.py::TestFetchChampionsDex -v`
Expected: FAIL — functions don't exist

- [ ] **Step 3: Implement fetch orchestrator**

Add to `src/smogon_vgc_mcp/fetcher/champions_dex.py`:

```python
from pathlib import Path

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.fetcher.champions_pokemon_list import CHAMPIONS_POKEMON
from smogon_vgc_mcp.resilience import FetchResult, get_all_circuit_states


async def fetch_champions_pokemon_page(pokemon_id: str) -> dict | None:
    """Fetch and parse a single Champions Pokemon page from Serebii.

    Args:
        pokemon_id: Lowercase Pokemon identifier (e.g., "charizard")

    Returns:
        Parsed Pokemon dict, or None if fetch/parse failed
    """
    url = f"{SEREBII_BASE_URL}/{pokemon_id}/"
    result: FetchResult[str] = await fetch_text_resilient(url, service=SEREBII_SERVICE)

    if not result.success or not result.data:
        return None

    return parse_serebii_pokemon_page(result.data, pokemon_id)


async def fetch_and_store_champions_dex(
    db_path: Path | None = None,
    *,
    dry_run: bool = False,
    dry_run_names: list[str] | None = None,
    request_delay: float = REQUEST_DELAY,
) -> dict:
    """Fetch and store all Champions Pokedex data from Serebii.

    Follows the same two-phase pattern as pokedex.py:
    Phase 1 — Fetch all pages into memory (no DB writes)
    Phase 2 — Store atomically in a single transaction

    Args:
        db_path: Database file path (defaults to project data dir)
        dry_run: If True, parse a small subset and report results without storing
        dry_run_names: Pokemon to parse in dry_run mode (default: first 5)
        request_delay: Seconds to wait between HTTP requests (polite crawling)

    Returns:
        Dict with pokemon_parsed, pokemon_stored, mega_forms_found, errors, etc.
    """
    if db_path is None:
        db_path = get_db_path()

    names = dry_run_names or CHAMPIONS_POKEMON[:5] if dry_run else CHAMPIONS_POKEMON
    errors: list[dict] = []
    all_pokemon: list[dict] = []

    # Phase 1: Fetch all pages into memory
    for i, name in enumerate(names):
        if i > 0:
            await asyncio.sleep(request_delay)

        print(f"  [{i + 1}/{len(names)}] Fetching {name}...")
        parsed = await fetch_champions_pokemon_page(name)

        if parsed is None:
            errors.append({"pokemon": name, "error": "Failed to fetch or parse"})
            continue

        parsed["is_mega"] = False
        parsed["base_form_id"] = None
        parsed["mega_stone"] = None
        all_pokemon.append(parsed)

        # Fetch Mega forms if detected
        for mega in parsed.get("mega_forms", []):
            mega_id = mega["id"]
            await asyncio.sleep(request_delay)
            print(f"    Fetching Mega form: {mega_id}...")
            mega_parsed = await fetch_champions_pokemon_page(mega_id)
            if mega_parsed:
                mega_parsed["is_mega"] = True
                mega_parsed["base_form_id"] = name
                mega_parsed["mega_stone"] = mega.get("stone", None)
                all_pokemon.append(mega_parsed)
            else:
                errors.append({"pokemon": mega_id, "error": "Failed to fetch Mega form"})

    if dry_run:
        return {
            "dry_run": True,
            "pokemon_parsed": len(all_pokemon),
            "errors": errors if errors else None,
            "parsed_names": [p["name"] for p in all_pokemon],
            "circuit_states": get_all_circuit_states(),
        }

    # Phase 2: Store atomically
    await init_database(db_path)
    pokemon_count = 0

    async with get_connection(db_path) as db:
        try:
            pokemon_count = await store_champions_pokemon_data(
                db, all_pokemon, _commit=False
            )
            await db.commit()
            print(f"  Stored {pokemon_count} Champions Pokemon")
        except Exception:
            await db.rollback()
            raise

    return {
        "dry_run": False,
        "pokemon_parsed": len(all_pokemon),
        "pokemon_stored": pokemon_count,
        "mega_forms_found": sum(1 for p in all_pokemon if p.get("is_mega")),
        "errors": errors if errors else None,
        "circuit_states": get_all_circuit_states(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetcher_champions_dex.py::TestFetchChampionsDex -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/smogon_vgc_mcp/fetcher/champions_dex.py tests/test_fetcher_champions_dex.py
git commit -m "feat: add Champions Pokedex fetch orchestrator with dry-run mode (#6)"
```

---

### Task 8: Champions Pokedex query functions

**Files:**
- Modify: `src/smogon_vgc_mcp/database/queries.py`
- Modify: `tests/test_champions_dex_queries.py`

- [ ] **Step 1: Write failing tests for query functions**

Add to `tests/test_champions_dex_queries.py`:

```python
@pytest.mark.asyncio
async def test_get_champions_pokemon(tmp_path):
    """Query a Champions Pokemon by ID."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    from smogon_vgc_mcp.fetcher.champions_dex import store_champions_pokemon_data
    from smogon_vgc_mcp.database.queries import get_champions_pokemon

    pokemon_data = [{
        "pokemon_id": "charizard",
        "num": 6,
        "name": "Charizard",
        "types": ["Fire", "Flying"],
        "base_stats": {"hp": 78, "atk": 104, "def": 98, "spa": 159, "spd": 115, "spe": 100},
        "abilities": ["Blaze"],
        "ability_hidden": "Solar Power",
        "height_m": 1.7,
        "weight_kg": 90.5,
        "is_mega": False,
        "base_form_id": None,
        "mega_stone": None,
    }]

    async with aiosqlite.connect(db_path) as db:
        await store_champions_pokemon_data(db, pokemon_data)
        await db.commit()

    result = await get_champions_pokemon("charizard", db_path=db_path)
    assert result is not None
    assert result.name == "Charizard"
    assert result.base_stats["spa"] == 159
    assert result.is_mega is False


@pytest.mark.asyncio
async def test_get_champions_pokemon_with_megas(tmp_path):
    """Query a Pokemon and its Mega forms."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    from smogon_vgc_mcp.fetcher.champions_dex import store_champions_pokemon_data
    from smogon_vgc_mcp.database.queries import get_champions_pokemon_with_megas

    pokemon_data = [
        {
            "pokemon_id": "charizard",
            "num": 6, "name": "Charizard",
            "types": ["Fire", "Flying"],
            "base_stats": {"hp": 78, "atk": 104, "def": 98, "spa": 159, "spd": 115, "spe": 100},
            "abilities": ["Blaze"], "ability_hidden": "Solar Power",
            "height_m": 1.7, "weight_kg": 90.5,
            "is_mega": False, "base_form_id": None, "mega_stone": None,
        },
        {
            "pokemon_id": "charizard-mega-x",
            "num": 6, "name": "Mega Charizard X",
            "types": ["Fire", "Dragon"],
            "base_stats": {"hp": 78, "atk": 170, "def": 131, "spa": 170, "spd": 115, "spe": 100},
            "abilities": ["Tough Claws"], "ability_hidden": None,
            "height_m": 1.7, "weight_kg": 110.5,
            "is_mega": True, "base_form_id": "charizard", "mega_stone": "Charizardite X",
        },
    ]

    async with aiosqlite.connect(db_path) as db:
        await store_champions_pokemon_data(db, pokemon_data)
        await db.commit()

    base, megas = await get_champions_pokemon_with_megas("charizard", db_path=db_path)
    assert base is not None
    assert base.name == "Charizard"
    assert len(megas) == 1
    assert megas[0].name == "Mega Charizard X"
    assert megas[0].mega_stone == "Charizardite X"


@pytest.mark.asyncio
async def test_search_champions_pokemon_by_type(tmp_path):
    """Search Champions Pokemon by type."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    from smogon_vgc_mcp.fetcher.champions_dex import store_champions_pokemon_data
    from smogon_vgc_mcp.database.queries import search_champions_pokemon_by_type

    pokemon_data = [
        {
            "pokemon_id": "charizard", "num": 6, "name": "Charizard",
            "types": ["Fire", "Flying"],
            "base_stats": {"hp": 78, "atk": 104, "def": 98, "spa": 159, "spd": 115, "spe": 100},
            "abilities": ["Blaze"], "ability_hidden": None,
            "height_m": 1.7, "weight_kg": 90.5,
            "is_mega": False, "base_form_id": None, "mega_stone": None,
        },
        {
            "pokemon_id": "pikachu", "num": 25, "name": "Pikachu",
            "types": ["Electric"],
            "base_stats": {"hp": 55, "atk": 80, "def": 50, "spa": 75, "spd": 60, "spe": 110},
            "abilities": ["Static"], "ability_hidden": "Lightning Rod",
            "height_m": 0.4, "weight_kg": 6.0,
            "is_mega": False, "base_form_id": None, "mega_stone": None,
        },
    ]

    async with aiosqlite.connect(db_path) as db:
        await store_champions_pokemon_data(db, pokemon_data)
        await db.commit()

    results = await search_champions_pokemon_by_type("Fire", db_path=db_path)
    assert len(results) == 1
    assert results[0].name == "Charizard"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_champions_dex_queries.py::test_get_champions_pokemon -v`
Expected: FAIL — query functions don't exist

- [ ] **Step 3: Implement query functions**

Add to `src/smogon_vgc_mcp/database/queries.py`:

```python
from smogon_vgc_mcp.database.models import ChampionsDexPokemon


def _row_to_champions_pokemon(row) -> ChampionsDexPokemon:
    """Convert a database row to a ChampionsDexPokemon model."""
    types = [row["type1"]]
    if row["type2"]:
        types.append(row["type2"])

    abilities = []
    if row["ability1"]:
        abilities.append(row["ability1"])
    if row["ability2"]:
        abilities.append(row["ability2"])

    return ChampionsDexPokemon(
        id=row["id"],
        num=row["num"],
        name=row["name"],
        types=types,
        base_stats={
            "hp": row["hp"],
            "atk": row["atk"],
            "def": row["def"],
            "spa": row["spa"],
            "spd": row["spd"],
            "spe": row["spe"],
        },
        abilities=abilities,
        ability_hidden=row["ability_hidden"],
        height_m=row["height_m"] or 0.0,
        weight_kg=row["weight_kg"] or 0.0,
        is_mega=bool(row["is_mega"]),
        base_form_id=row["base_form_id"],
        mega_stone=row["mega_stone"],
    )


async def get_champions_pokemon(
    pokemon_id: str,
    db_path: Path | None = None,
) -> ChampionsDexPokemon | None:
    """Get a Champions Pokemon by ID."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM champions_dex_pokemon WHERE id = ?",
            (pokemon_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return _row_to_champions_pokemon(row)
    return None


async def get_champions_pokemon_with_megas(
    pokemon_id: str,
    db_path: Path | None = None,
) -> tuple[ChampionsDexPokemon | None, list[ChampionsDexPokemon]]:
    """Get a Champions Pokemon and all its Mega forms.

    Returns:
        Tuple of (base_form, [mega_forms])
    """
    base = await get_champions_pokemon(pokemon_id, db_path=db_path)
    megas: list[ChampionsDexPokemon] = []

    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM champions_dex_pokemon WHERE base_form_id = ?",
            (pokemon_id,),
        ) as cursor:
            async for row in cursor:
                megas.append(_row_to_champions_pokemon(row))

    return base, megas


async def search_champions_pokemon_by_type(
    type_name: str,
    db_path: Path | None = None,
) -> list[ChampionsDexPokemon]:
    """Search Champions Pokemon by type (primary or secondary)."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM champions_dex_pokemon WHERE type1 = ? OR type2 = ? ORDER BY name",
            (type_name, type_name),
        ) as cursor:
            return [_row_to_champions_pokemon(row) async for row in cursor]
```

- [ ] **Step 4: Add import for ChampionsDexPokemon to queries.py imports**

In the imports at the top of `queries.py`, add `ChampionsDexPokemon` to the import from `models`:

```python
from smogon_vgc_mcp.database.models import (
    ...,
    ChampionsDexPokemon,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_champions_dex_queries.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/smogon_vgc_mcp/database/queries.py tests/test_champions_dex_queries.py
git commit -m "feat: add Champions Pokedex query functions (#6)"
```

---

### Task 9: Uncomment Champions FormatConfig entry

**Files:**
- Modify: `src/smogon_vgc_mcp/formats.py`
- Modify: `tests/test_formats.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_formats.py`:

```python
def test_champions_format_exists():
    """Champions M-A format should be registered."""
    from smogon_vgc_mcp.formats import get_format

    fmt = get_format("champions_ma")
    assert fmt.generation == 10
    assert fmt.stat_system == "champions_sp"
    assert fmt.calc_backend == "python_native"
    assert fmt.smogon_stats_available is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_formats.py::test_champions_format_exists -v`
Expected: FAIL — `ValueError: Unknown format: champions_ma`

- [ ] **Step 3: Uncomment the Champions FormatConfig in formats.py**

In `src/smogon_vgc_mcp/formats.py`, replace the commented block with:

```python
    "champions_ma": FormatConfig(
        code="champions_ma",
        name="Champions Regulation M-A",
        smogon_format_id="",
        available_months=[],
        generation=10,
        stat_system="champions_sp",
        calc_backend="python_native",
        smogon_stats_available=False,
        is_current=False,
    ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_formats.py -v`
Expected: PASS

- [ ] **Step 5: Run full type check and lint**

Run: `uv run ruff check --fix . && uv run ruff format .`
Run: `uv run ty check`

- [ ] **Step 6: Commit**

```bash
git add src/smogon_vgc_mcp/formats.py tests/test_formats.py
git commit -m "feat: register Champions M-A format in FormatConfig (#6)"
```

---

### Task 10: Full test suite verification + lint

**Files:** None — verification only

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests PASS, including all new Champions tests

- [ ] **Step 2: Run linter**

Run: `uv run ruff check --fix . && uv run ruff format .`
Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `uv run ty check`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 4: Fix any issues found**

If any tests fail, lint errors, or type errors — fix them and commit:

```bash
git add -u
git commit -m "fix: resolve lint/type errors from Champions Pokedex pipeline (#6)"
```

- [ ] **Step 5: Close issue #5 (spike complete)**

The data source spike (#5) was completed last session. Close it:

```bash
gh issue close 5 --comment "Spike complete: Serebii confirmed as Champions Pokedex data source. Implemented in Phase 1 (#6)."
```
