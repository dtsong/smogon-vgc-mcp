# Champions Stat Calculator & Speed Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Champions-specific stat calculator using the Stat Points (SP) system, SP optimizer for optimal allocation, and speed tier tools using Champions benchmark data.

**Architecture:** Separate calculator modules (`champions_stats.py`, `champions_speed.py`, `champions_sp_optimizer.py`) that mirror the Gen 9 calculator structure but use the Champions SP formula instead of EVs/IVs. MCP tools registered in a new `tools/champions_calculator.py`. Base stats looked up from Phase 1's `champions_dex_pokemon` SQLite table via existing query functions.

**Tech Stack:** Python 3.12, math (stdlib), aiosqlite (base stats lookup), pytest, mcp.server.fastmcp

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/smogon_vgc_mcp/calculator/champions_stats.py` | Champions stat formulas (HP + other stats with SP and nature) |
| `src/smogon_vgc_mcp/calculator/champions_speed.py` | Speed tier benchmarks, comparisons, and EV-finding for Champions |
| `src/smogon_vgc_mcp/calculator/champions_sp_optimizer.py` | SP allocation optimizer (speed benchmarks, HP thresholds, bulk) |
| `src/smogon_vgc_mcp/tools/champions_calculator.py` | MCP tool registrations for Champions calculator tools |
| `tests/test_champions_stats.py` | Unit tests for stat calculator |
| `tests/test_champions_speed.py` | Unit tests for speed tier tools |
| `tests/test_champions_sp_optimizer.py` | Unit tests for SP optimizer |
| `tests/test_champions_calculator_tools.py` | Integration tests for MCP tools |

---

## Context: Champions Stat System

**Stat Points (SP):** Each Pokemon gets 66 total SP, max 32 per stat. No IVs. Replaces EVs/IVs from Gen 9.

**Non-HP formula:** `floor(floor((2 * base) * level / 100) + 5) * nature_multiplier) + sp`
- Nature multiplier: 1.1 (boosted), 0.9 (reduced), 1.0 (neutral)
- SP added AFTER nature multiplier (confirmed from game data)
- At level 50: `floor((base + 5) * nature) + sp`

**HP formula:** `floor((2 * base) * level / 100) + level + 10 + sp`
- No nature multiplier on HP (same as mainline games)
- At level 50: `base + 60 + sp`

**Nature system:** Same 25 natures as mainline (Adamant, Jolly, etc.) with same stat modifiers (1.1/0.9). Reuses existing `get_nature_multiplier()` from `data/pokemon_data.py`.

**Speed tier data:** Pre-computed benchmarks stored in `memory/reference_champions_speed_tiers.md`. Key tiers: Excadrill Sand Rush 280, Venusaur Chlorophyll 264, Dragapult 213, uninvested Incineroar 112.

---

### Task 1: Champions Stat Calculator — Core Formulas

**Files:**
- Create: `src/smogon_vgc_mcp/calculator/champions_stats.py`
- Create: `tests/test_champions_stats.py`

- [ ] **Step 1: Write failing tests for `calculate_champions_hp()`**

```python
"""Tests for Champions stat calculator."""

import pytest

from smogon_vgc_mcp.calculator.champions_stats import (
    calculate_champions_hp,
    calculate_champions_stat,
    calculate_all_champions_stats,
    format_champions_stats,
)


class TestCalculateChampionsHp:
    """Tests for calculate_champions_hp()."""

    def test_base_100_no_sp(self):
        # floor((2*100)*50/100) + 50 + 10 + 0 = 100 + 60 = 160
        assert calculate_champions_hp(base=100, sp=0, level=50) == 160

    def test_base_100_max_sp(self):
        # 100 + 60 + 32 = 192
        assert calculate_champions_hp(base=100, sp=32, level=50) == 192

    def test_base_80_incineroar(self):
        # floor((2*80)*50/100) + 50 + 10 + 0 = 80 + 60 = 140
        assert calculate_champions_hp(base=80, sp=0, level=50) == 140

    def test_base_80_max_sp(self):
        # 80 + 60 + 32 = 172
        assert calculate_champions_hp(base=80, sp=32, level=50) == 172

    def test_shedinja_1_hp(self):
        # Shedinja always has 1 HP regardless of anything
        assert calculate_champions_hp(base=1, sp=0, level=50) == 62
        # Note: Shedinja's 1 HP is enforced at a higher level, not in the formula

    def test_level_100(self):
        # floor((2*100)*100/100) + 100 + 10 + 0 = 200 + 110 = 310
        assert calculate_champions_hp(base=100, sp=0, level=100) == 310

    def test_sp_must_be_0_to_32(self):
        with pytest.raises(ValueError, match="SP must be between 0 and 32"):
            calculate_champions_hp(base=100, sp=33, level=50)

    def test_sp_negative_raises(self):
        with pytest.raises(ValueError, match="SP must be between 0 and 32"):
            calculate_champions_hp(base=100, sp=-1, level=50)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_champions_stats.py::TestCalculateChampionsHp -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement `calculate_champions_hp()`**

```python
"""Champions stat calculator using Stat Points (SP) system.

Champions uses 66 total SP (max 32/stat) instead of EVs/IVs.
HP formula: floor((2 * base) * level / 100) + level + 10 + sp
Non-HP formula: floor((floor((2 * base) * level / 100) + 5) * nature) + sp
"""

import math

MAX_SP_PER_STAT = 32
MAX_TOTAL_SP = 66


def calculate_champions_hp(base: int, sp: int = 0, level: int = 50) -> int:
    """Calculate Champions HP stat.

    Formula: floor((2 * base) * level / 100) + level + 10 + sp
    """
    if not 0 <= sp <= MAX_SP_PER_STAT:
        raise ValueError(
            f"SP must be between 0 and {MAX_SP_PER_STAT}, got {sp}"
        )
    return math.floor((2 * base) * level / 100) + level + 10 + sp
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_champions_stats.py::TestCalculateChampionsHp -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for `calculate_champions_stat()`**

Add to `tests/test_champions_stats.py`:

```python
class TestCalculateChampionsStat:
    """Tests for calculate_champions_stat() (non-HP stats)."""

    def test_base_100_neutral_no_sp(self):
        # floor((floor((2*100)*50/100) + 5) * 1.0) + 0 = 105
        assert calculate_champions_stat(base=100, sp=0, level=50) == 105

    def test_base_100_neutral_max_sp(self):
        # floor((floor((2*100)*50/100) + 5) * 1.0) + 32 = 137
        assert calculate_champions_stat(
            base=100, sp=32, level=50
        ) == 137

    def test_base_100_boosted_nature(self):
        # floor((floor((2*100)*50/100) + 5) * 1.1) + 0 = floor(115.5) = 115
        assert calculate_champions_stat(
            base=100, sp=0, nature_multiplier=1.1, level=50
        ) == 115

    def test_base_100_reduced_nature(self):
        # floor((floor((2*100)*50/100) + 5) * 0.9) + 0 = floor(94.5) = 94
        assert calculate_champions_stat(
            base=100, sp=0, nature_multiplier=0.9, level=50
        ) == 94

    def test_base_80_boosted_max_sp(self):
        # floor((floor((2*80)*50/100) + 5) * 1.1) + 32
        # = floor(85 * 1.1) + 32 = floor(93.5) + 32 = 93 + 32 = 125
        assert calculate_champions_stat(
            base=80, sp=32, nature_multiplier=1.1, level=50
        ) == 125

    def test_sp_added_after_nature(self):
        # Verify SP is added after nature multiplier, not before
        # base=100, sp=10, boosted:
        # floor((105) * 1.1) + 10 = floor(115.5) + 10 = 125
        result = calculate_champions_stat(
            base=100, sp=10, nature_multiplier=1.1, level=50
        )
        assert result == 125

    def test_sp_validation(self):
        with pytest.raises(ValueError, match="SP must be between 0 and 32"):
            calculate_champions_stat(base=100, sp=33, level=50)

    def test_incineroar_speed_base_60_neutral(self):
        # floor((floor((2*60)*50/100) + 5) * 1.0) + 0 = 65
        assert calculate_champions_stat(base=60, sp=0, level=50) == 65

    def test_incineroar_speed_max_sp_neutral(self):
        # 65 + 32 = 97
        assert calculate_champions_stat(base=60, sp=32, level=50) == 97
```

- [ ] **Step 6: Implement `calculate_champions_stat()`**

Add to `champions_stats.py`:

```python
def calculate_champions_stat(
    base: int,
    sp: int = 0,
    nature_multiplier: float = 1.0,
    level: int = 50,
) -> int:
    """Calculate a Champions non-HP stat (Atk, Def, SpA, SpD, Spe).

    Formula: floor((floor((2 * base) * level / 100) + 5) * nature) + sp
    SP is added AFTER the nature multiplier.
    """
    if not 0 <= sp <= MAX_SP_PER_STAT:
        raise ValueError(
            f"SP must be between 0 and {MAX_SP_PER_STAT}, got {sp}"
        )
    raw = math.floor((2 * base) * level / 100) + 5
    return math.floor(raw * nature_multiplier) + sp
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_champions_stats.py::TestCalculateChampionsStat -v`
Expected: PASS

- [ ] **Step 8: Write failing tests for `calculate_all_champions_stats()`**

Add to `tests/test_champions_stats.py`:

```python
class TestCalculateAllChampionsStats:
    """Tests for calculate_all_champions_stats()."""

    def test_all_zero_sp_neutral(self):
        base_stats = {
            "hp": 80, "atk": 82, "def": 83,
            "spa": 100, "spd": 100, "spe": 80,
        }
        sp_spread = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        result = calculate_all_champions_stats(base_stats, sp_spread, "Hardy")
        assert result["hp"] == 140  # 80 + 60
        assert result["spe"] == 85  # 80 + 5

    def test_max_sp_modest(self):
        base_stats = {
            "hp": 80, "atk": 82, "def": 83,
            "spa": 100, "spd": 100, "spe": 80,
        }
        sp_spread = {
            "hp": 32, "atk": 0, "def": 0,
            "spa": 32, "spd": 0, "spe": 2,
        }
        result = calculate_all_champions_stats(base_stats, sp_spread, "Modest")
        assert result["hp"] == 172  # 140 + 32
        # spa: floor(105 * 1.1) + 32 = 115 + 32 = 147
        assert result["spa"] == 147
        # atk: floor(87 * 0.9) + 0 = floor(78.3) = 78
        assert result["atk"] == 78
        assert result["spe"] == 87  # 85 + 2

    def test_sp_total_validation(self):
        base_stats = {
            "hp": 100, "atk": 100, "def": 100,
            "spa": 100, "spd": 100, "spe": 100,
        }
        # 32 * 3 = 96 > 66
        sp_spread = {
            "hp": 32, "atk": 32, "def": 32,
            "spa": 0, "spd": 0, "spe": 0,
        }
        with pytest.raises(ValueError, match="Total SP must not exceed 66"):
            calculate_all_champions_stats(base_stats, sp_spread, "Hardy")

    def test_returns_none_for_invalid_nature(self):
        base_stats = {
            "hp": 100, "atk": 100, "def": 100,
            "spa": 100, "spd": 100, "spe": 100,
        }
        sp_spread = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        result = calculate_all_champions_stats(
            base_stats, sp_spread, "NotANature"
        )
        assert result is None
```

- [ ] **Step 9: Implement `calculate_all_champions_stats()` and `format_champions_stats()`**

Add to `champions_stats.py`:

```python
from smogon_vgc_mcp.data.pokemon_data import get_nature_multiplier

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
STAT_NAMES = {
    "hp": "HP", "atk": "Atk", "def": "Def",
    "spa": "SpA", "spd": "SpD", "spe": "Spe",
}


def calculate_all_champions_stats(
    base_stats: dict[str, int],
    sp_spread: dict[str, int],
    nature: str,
    level: int = 50,
) -> dict[str, int] | None:
    """Calculate all 6 stats for a Champions Pokemon.

    Args:
        base_stats: Dict with hp, atk, def, spa, spd, spe base values.
        sp_spread: Dict with hp, atk, def, spa, spd, spe SP values (0-32 each).
        nature: Nature name (e.g., "Adamant", "Modest", "Hardy").
        level: Pokemon level (default 50).

    Returns:
        Dict of calculated stats, or None if nature is invalid.
    """
    total_sp = sum(sp_spread.get(s, 0) for s in STAT_ORDER)
    if total_sp > MAX_TOTAL_SP:
        raise ValueError(
            f"Total SP must not exceed {MAX_TOTAL_SP}, got {total_sp}"
        )

    # Validate nature exists by checking if it returns a valid multiplier
    # Neutral natures return 1.0 for all stats, which is fine
    from smogon_vgc_mcp.data.pokemon_data import get_nature_modifiers
    if nature.lower() not in [
        "hardy", "lonely", "brave", "adamant", "naughty",
        "bold", "docile", "relaxed", "impish", "lax",
        "timid", "hasty", "serious", "jolly", "naive",
        "modest", "mild", "quiet", "bashful", "rash",
        "calm", "gentle", "sassy", "careful", "quirky",
    ]:
        return None

    stats = {}
    for stat in STAT_ORDER:
        base = base_stats[stat]
        sp = sp_spread.get(stat, 0)
        if stat == "hp":
            stats[stat] = calculate_champions_hp(base, sp, level)
        else:
            mult = get_nature_multiplier(nature, stat)
            stats[stat] = calculate_champions_stat(base, sp, mult, level)

    return stats


def format_champions_stats(stats: dict[str, int]) -> str:
    """Format calculated stats as a readable string.

    Example: 'HP: 172 / Atk: 78 / Def: 88 / SpA: 147 / SpD: 105 / Spe: 87'
    """
    parts = []
    for stat in STAT_ORDER:
        name = STAT_NAMES[stat]
        parts.append(f"{name}: {stats[stat]}")
    return " / ".join(parts)
```

- [ ] **Step 10: Run all Task 1 tests**

Run: `uv run python -m pytest tests/test_champions_stats.py -v`
Expected: All PASS

- [ ] **Step 11: Lint check**

Run: `uv run ruff check src/smogon_vgc_mcp/calculator/champions_stats.py tests/test_champions_stats.py && uv run ruff format --check src/smogon_vgc_mcp/calculator/champions_stats.py tests/test_champions_stats.py`
Expected: Clean

- [ ] **Step 12: Commit**

```bash
git add src/smogon_vgc_mcp/calculator/champions_stats.py tests/test_champions_stats.py
git commit -m "feat: add Champions stat calculator with SP system"
```

---

### Task 2: Champions Speed Tiers

**Files:**
- Create: `src/smogon_vgc_mcp/calculator/champions_speed.py`
- Create: `tests/test_champions_speed.py`

- [ ] **Step 1: Write failing tests for speed calculation and benchmarks**

```python
"""Tests for Champions speed tier tools."""

import pytest

from smogon_vgc_mcp.calculator.champions_speed import (
    CHAMPIONS_SPEED_TIERS,
    get_champions_speed,
    compare_champions_speeds,
    find_champions_speed_benchmarks,
    find_champions_speed_sp,
)


class TestGetChampionsSpeed:
    """Tests for get_champions_speed()."""

    def test_base_110_max_sp_positive_nature(self):
        # Gengar: base 110, +nature, 32 SP
        # floor((floor((2*110)*50/100) + 5) * 1.1) + 32
        # = floor(115 * 1.1) + 32 = floor(126.5) + 32 = 126 + 32 = 158
        assert get_champions_speed(base_spe=110, sp=32, nature="Timid") == 158

    def test_base_60_no_sp_neutral(self):
        # Incineroar: base 60, neutral, 0 SP
        # floor((65) * 1.0) + 0 = 65
        assert get_champions_speed(base_spe=60, sp=0, nature="Hardy") == 65

    def test_base_60_max_sp_neutral(self):
        # 65 + 32 = 97
        assert get_champions_speed(base_spe=60, sp=32, nature="Hardy") == 97

    def test_base_80_negative_nature_for_trick_room(self):
        # Dragonite base 80, -spe nature, 0 SP
        # floor((85) * 0.9) + 0 = floor(76.5) = 76
        assert get_champions_speed(base_spe=80, sp=0, nature="Brave") == 76


class TestCompareChampionsSpeeds:
    """Tests for compare_champions_speeds()."""

    def test_faster_pokemon_wins(self):
        result = compare_champions_speeds(
            pokemon1="Gengar", base_spe1=110, sp1=32, nature1="Timid",
            pokemon2="Incineroar", base_spe2=60, sp2=0, nature2="Hardy",
        )
        assert result["result"] == "pokemon1_faster"
        assert result["pokemon1"]["speed"] > result["pokemon2"]["speed"]

    def test_speed_tie(self):
        result = compare_champions_speeds(
            pokemon1="PokemonA", base_spe1=100, sp1=0, nature1="Hardy",
            pokemon2="PokemonB", base_spe2=100, sp2=0, nature2="Hardy",
        )
        assert result["result"] == "tie"

    def test_slower_pokemon(self):
        result = compare_champions_speeds(
            pokemon1="Incineroar", base_spe1=60, sp1=0, nature1="Hardy",
            pokemon2="Gengar", base_spe2=110, sp2=32, nature2="Timid",
        )
        assert result["result"] == "pokemon2_faster"


class TestFindChampionsSpeedBenchmarks:
    """Tests for find_champions_speed_benchmarks()."""

    def test_returns_outspeeds_and_underspeeds(self):
        result = find_champions_speed_benchmarks(
            pokemon="TestMon", speed=150
        )
        assert "outspeeds" in result
        assert "underspeeds" in result
        assert "speed_ties" in result
        assert result["speed"] == 150

    def test_max_speed_outspeeds_many(self):
        result = find_champions_speed_benchmarks(
            pokemon="FastMon", speed=250
        )
        assert len(result["outspeeds"]) > 0

    def test_min_speed_underspeeds_many(self):
        result = find_champions_speed_benchmarks(
            pokemon="SlowMon", speed=50
        )
        assert len(result["underspeeds"]) > 0


class TestFindChampionsSpeedSp:
    """Tests for find_champions_speed_sp()."""

    def test_find_sp_to_outspeed(self):
        # Find SP needed for base 80 to outspeed base 60 max speed
        # Target: base 60, 32 SP, +nature = floor(65*1.1)+32 = 103
        # Me: base 80, +nature: floor(85*1.1) + sp = 93 + sp
        # Need 93 + sp > 103 → sp > 10 → sp = 11
        result = find_champions_speed_sp(
            base_spe=80,
            target_speed=103,
            nature="Jolly",
            goal="outspeed",
        )
        assert result["success"] is True
        assert result["sp_needed"] == 11
        assert result["resulting_speed"] == 104

    def test_find_sp_to_underspeed(self):
        # Find SP for base 80 to underspeed 65 (base 60, neutral, 0 SP)
        # Me: base 80, -nature: floor(85*0.9) + sp = 76 + sp
        # Need 76 + sp < 65 → sp < -11 → impossible
        result = find_champions_speed_sp(
            base_spe=80,
            target_speed=65,
            nature="Brave",
            goal="underspeed",
        )
        assert result["success"] is False

    def test_already_outspeeds(self):
        # base 110 + nature already outspeeds 100
        result = find_champions_speed_sp(
            base_spe=110,
            target_speed=100,
            nature="Timid",
            goal="outspeed",
        )
        assert result["success"] is True
        assert result["sp_needed"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_champions_speed.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `champions_speed.py`**

```python
"""Champions speed tier tools.

Speed tiers from the Champions VGC meta. Uses Champions stat formula
with Stat Points instead of EVs/IVs.
"""

from smogon_vgc_mcp.calculator.champions_stats import calculate_champions_stat
from smogon_vgc_mcp.data.pokemon_data import get_nature_multiplier

# Champions speed benchmarks: (final_speed, pokemon_name, notes)
# Source: memory/reference_champions_speed_tiers.md
CHAMPIONS_SPEED_TIERS: list[tuple[int, str, str]] = [
    (280, "Excadrill", "Sand Rush"),
    (264, "Venusaur", "Chlorophyll/Tailwind"),
    (264, "Dragonite", "Tailwind"),
    (264, "Mega Meganium", "Tailwind"),
    (264, "Eelektross", "Tailwind"),
    (260, "Basculegion", "Swift Swim/Shell Smash"),
    (260, "Mega Blastoise", "Swift Swim"),
    (256, "Pelipper", "Tailwind"),
    (254, "Mega Scizor", "Tailwind"),
    (250, "Mega Charizard X", "Dragon Dance"),
    (250, "Volcarona", "Quiver Dance"),
    (244, "Mega Swampert", "Swift Swim"),
    (243, "Gengar", "Choice Scarf"),
    (228, "Mega Charizard X", "Dragon Dance (1 boost)"),
    (228, "Volcarona", "Quiver Dance (1 boost)"),
    (224, "Primarina", "Tailwind"),
    (224, "Incineroar", "Tailwind"),
    (224, "Aegislash", "Tailwind"),
    (224, "Sylveon", "Tailwind"),
    (223, "Mega Lucario", "Max Speed"),
    (223, "Mega Garchomp", "Max Speed"),
    (222, "Mega Aerodactyl", "Max Speed"),
    (222, "Mega Alakazam", "Max Speed"),
    (213, "Dragapult", "Max Speed"),
    (213, "Mega Greninja", "Max Speed"),
    (205, "Mega Manectric", "Max Speed"),
    (205, "Mega Lopunny", "Max Speed"),
    (200, "Mega Gengar", "Max Speed"),
    (200, "Mega Raichu Y", "Max Speed"),
    (195, "Talonflame", "Max Speed"),
    (194, "Weavile", "Max Speed"),
    (192, "Meowscarada", "Max Speed"),
    (191, "Greninja", "Max Speed"),
    (152, "Mega Charizard X", "Max Speed (unboosted)"),
    (152, "Mega Dragonite", "Max Speed"),
    (150, "Hydreigon", "Max Speed"),
    (150, "Archaludon", "Max Speed"),
    (150, "Kommo-o", "Max Speed"),
    (150, "Ceruledge", "Max Speed"),
    (137, "Archaludon", "Neutral Max SP"),
    (137, "Kommo-o", "Neutral Max SP"),
    (137, "Ceruledge", "Neutral Max SP"),
    (132, "Altaria", "Max Speed"),
    (132, "Dragonite", "Max Speed"),
    (132, "Mega Meganium", "Max Speed"),
    (132, "Chandelure", "Max Speed"),
    (112, "Primarina", "Max Speed"),
    (112, "Incineroar", "Max Speed"),
    (112, "Aegislash", "Max Speed"),
    (112, "Sylveon", "Max Speed"),
    (102, "Kingambit", "Max Speed"),
    (102, "Azumarill", "Max Speed"),
]


def get_champions_speed(
    base_spe: int,
    sp: int = 0,
    nature: str = "Hardy",
    level: int = 50,
) -> int:
    """Calculate Champions speed stat."""
    mult = get_nature_multiplier(nature, "spe")
    return calculate_champions_stat(base_spe, sp, mult, level)


def compare_champions_speeds(
    pokemon1: str,
    base_spe1: int,
    sp1: int,
    nature1: str,
    pokemon2: str,
    base_spe2: int,
    sp2: int,
    nature2: str,
    level: int = 50,
) -> dict:
    """Compare speed between two Champions Pokemon."""
    speed1 = get_champions_speed(base_spe1, sp1, nature1, level)
    speed2 = get_champions_speed(base_spe2, sp2, nature2, level)

    if speed1 > speed2:
        result = "pokemon1_faster"
    elif speed2 > speed1:
        result = "pokemon2_faster"
    else:
        result = "tie"

    return {
        "pokemon1": {"name": pokemon1, "speed": speed1},
        "pokemon2": {"name": pokemon2, "speed": speed2},
        "result": result,
        "difference": abs(speed1 - speed2),
    }


def find_champions_speed_benchmarks(
    pokemon: str, speed: int
) -> dict:
    """Find what Champions meta Pokemon a speed stat outspeeds."""
    outspeeds = []
    underspeeds = []
    speed_ties = []

    seen = set()
    for tier_speed, name, notes in CHAMPIONS_SPEED_TIERS:
        key = (tier_speed, name)
        if key in seen:
            continue
        seen.add(key)

        entry = {"pokemon": name, "speed": tier_speed, "notes": notes}
        if speed > tier_speed:
            outspeeds.append(entry)
        elif speed < tier_speed:
            underspeeds.append(entry)
        else:
            speed_ties.append(entry)

    return {
        "pokemon": pokemon,
        "speed": speed,
        "outspeeds": outspeeds,
        "underspeeds": underspeeds,
        "speed_ties": speed_ties,
    }


def find_champions_speed_sp(
    base_spe: int,
    target_speed: int,
    nature: str = "Jolly",
    goal: str = "outspeed",
    level: int = 50,
) -> dict:
    """Find minimum SP needed to outspeed or underspeed a target."""
    mult = get_nature_multiplier(nature, "spe")
    raw = __import__("math").floor(
        __import__("math").floor((2 * base_spe) * level / 100) + 5
    )
    base_speed_no_sp = __import__("math").floor(raw * mult)

    if goal == "outspeed":
        needed = target_speed + 1 - base_speed_no_sp
        if needed < 0:
            needed = 0
        if needed > 32:
            return {
                "success": False,
                "reason": (
                    f"Cannot outspeed {target_speed} even with 32 SP "
                    f"(max speed: {base_speed_no_sp + 32})"
                ),
            }
        return {
            "success": True,
            "sp_needed": needed,
            "resulting_speed": base_speed_no_sp + needed,
            "target_speed": target_speed,
        }
    else:  # underspeed
        needed_max = target_speed - 1 - base_speed_no_sp
        if needed_max < 0:
            return {
                "success": False,
                "reason": (
                    f"Cannot underspeed {target_speed} "
                    f"(min speed: {base_speed_no_sp})"
                ),
            }
        return {
            "success": True,
            "sp_needed": 0,
            "resulting_speed": base_speed_no_sp,
            "target_speed": target_speed,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_champions_speed.py -v`
Expected: All PASS

- [ ] **Step 5: Lint check**

Run: `uv run ruff check src/smogon_vgc_mcp/calculator/champions_speed.py tests/test_champions_speed.py && uv run ruff format --check src/smogon_vgc_mcp/calculator/champions_speed.py tests/test_champions_speed.py`
Expected: Clean

- [ ] **Step 6: Commit**

```bash
git add src/smogon_vgc_mcp/calculator/champions_speed.py tests/test_champions_speed.py
git commit -m "feat: add Champions speed tier tools and benchmarks"
```

---

### Task 3: Champions SP Optimizer

**Files:**
- Create: `src/smogon_vgc_mcp/calculator/champions_sp_optimizer.py`
- Create: `tests/test_champions_sp_optimizer.py`

- [ ] **Step 1: Write failing tests for SP optimizer**

```python
"""Tests for Champions SP optimizer."""

import pytest

from smogon_vgc_mcp.calculator.champions_sp_optimizer import (
    optimize_champions_sp,
    suggest_hp_sp,
    SpGoal,
    SpeedGoal,
    MaximizeGoal,
    HpThresholdGoal,
)


class TestSuggestHpSp:
    """Tests for HP SP optimization based on divisibility rules."""

    def test_leftovers_optimization(self):
        # base HP 80: floor((2*80)*50/100) + 60 = 140
        # Want HP % 16 == 0 for max Leftovers
        # 140 % 16 == 12, need +4 → 144 % 16 == 0
        result = suggest_hp_sp(base_hp=80, item="Leftovers")
        assert result["recommended_sp"] == 4
        assert result["resulting_hp"] % 16 == 0
        assert result["resulting_hp"] == 144

    def test_life_orb_optimization(self):
        # base HP 80: 140
        # Want HP % 10 == 1 for min Life Orb recoil
        # 140 % 10 == 0, need +1 → 141 % 10 == 1
        result = suggest_hp_sp(base_hp=80, item="Life Orb")
        assert result["recommended_sp"] == 1
        assert result["resulting_hp"] % 10 == 1
        assert result["resulting_hp"] == 141

    def test_no_item_returns_zero(self):
        result = suggest_hp_sp(base_hp=80, item=None)
        assert result["recommended_sp"] == 0

    def test_sitrus_belly_drum(self):
        # Want HP % 4 == 0 for Sitrus + Belly Drum
        result = suggest_hp_sp(base_hp=80, item="Sitrus Berry")
        assert result["resulting_hp"] % 4 == 0

    def test_sp_capped_at_32(self):
        # Even if optimization wants more, cap at 32
        result = suggest_hp_sp(base_hp=80, item="Leftovers")
        assert result["recommended_sp"] <= 32


class TestOptimizeChampionsSp:
    """Tests for full SP optimizer."""

    def test_single_speed_goal(self):
        result = optimize_champions_sp(
            base_stats={
                "hp": 80, "atk": 82, "def": 83,
                "spa": 100, "spd": 100, "spe": 80,
            },
            nature="Modest",
            goals=[SpeedGoal(target_speed=132, mode="outspeed")],
        )
        assert result["success"] is True
        assert result["sp_spread"]["spe"] > 0
        total = sum(result["sp_spread"].values())
        assert total <= 66

    def test_maximize_spa_after_speed(self):
        result = optimize_champions_sp(
            base_stats={
                "hp": 80, "atk": 82, "def": 83,
                "spa": 100, "spd": 100, "spe": 80,
            },
            nature="Modest",
            goals=[
                SpeedGoal(target_speed=100, mode="outspeed"),
                MaximizeGoal(stat="spa"),
            ],
        )
        assert result["success"] is True
        assert result["sp_spread"]["spa"] > 0
        total = sum(result["sp_spread"].values())
        assert total <= 66

    def test_hp_threshold_goal(self):
        result = optimize_champions_sp(
            base_stats={
                "hp": 80, "atk": 82, "def": 83,
                "spa": 100, "spd": 100, "spe": 80,
            },
            nature="Modest",
            goals=[HpThresholdGoal(item="Leftovers")],
        )
        assert result["success"] is True
        hp_sp = result["sp_spread"]["hp"]
        resulting_hp = 140 + hp_sp  # base 80 at lv50 = 140
        assert resulting_hp % 16 == 0

    def test_impossible_goals_reports_failure(self):
        result = optimize_champions_sp(
            base_stats={
                "hp": 80, "atk": 82, "def": 83,
                "spa": 100, "spd": 100, "spe": 80,
            },
            nature="Modest",
            goals=[SpeedGoal(target_speed=300, mode="outspeed")],
        )
        assert result["success"] is False

    def test_total_sp_never_exceeds_66(self):
        result = optimize_champions_sp(
            base_stats={
                "hp": 80, "atk": 82, "def": 83,
                "spa": 100, "spd": 100, "spe": 80,
            },
            nature="Modest",
            goals=[
                SpeedGoal(target_speed=100, mode="outspeed"),
                HpThresholdGoal(item="Leftovers"),
                MaximizeGoal(stat="spa"),
            ],
        )
        total = sum(result["sp_spread"].values())
        assert total <= 66
        for v in result["sp_spread"].values():
            assert 0 <= v <= 32
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_champions_sp_optimizer.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `champions_sp_optimizer.py`**

```python
"""Champions SP allocation optimizer.

Allocates 66 total Stat Points across 6 stats (max 32 each)
based on prioritized goals: speed thresholds, HP optimization,
and stat maximization.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from smogon_vgc_mcp.calculator.champions_stats import (
    MAX_SP_PER_STAT,
    MAX_TOTAL_SP,
    STAT_ORDER,
    calculate_champions_hp,
    calculate_champions_stat,
)
from smogon_vgc_mcp.data.pokemon_data import get_nature_multiplier


@dataclass
class SpeedGoal:
    """Reach a speed threshold."""

    target_speed: int
    mode: str = "outspeed"  # "outspeed" or "underspeed"


@dataclass
class MaximizeGoal:
    """Maximize a specific stat with remaining SP."""

    stat: str  # hp, atk, def, spa, spd, spe


@dataclass
class HpThresholdGoal:
    """Optimize HP for item interaction."""

    item: str  # "Leftovers", "Life Orb", "Sitrus Berry"


SpGoal = SpeedGoal | MaximizeGoal | HpThresholdGoal


def suggest_hp_sp(
    base_hp: int, item: str | None = None, level: int = 50
) -> dict:
    """Suggest HP SP investment based on item divisibility rules."""
    base_hp_stat = calculate_champions_hp(base_hp, sp=0, level=level)

    if item is None:
        return {
            "recommended_sp": 0,
            "resulting_hp": base_hp_stat,
            "reason": "No item specified",
        }

    item_lower = item.lower()

    if item_lower in ("leftovers", "black sludge"):
        # Want HP % 16 == 0
        divisor, target_remainder = 16, 0
        reason = "Maximizes Leftovers recovery (1/16 per turn)"
    elif item_lower == "life orb":
        # Want HP % 10 == 1
        divisor, target_remainder = 10, 1
        reason = "Minimizes Life Orb recoil (1/10 rounds down)"
    elif item_lower == "sitrus berry":
        # Want HP % 4 == 0
        divisor, target_remainder = 4, 0
        reason = "Maximizes Sitrus Berry recovery (1/4 HP)"
    else:
        return {
            "recommended_sp": 0,
            "resulting_hp": base_hp_stat,
            "reason": f"No HP optimization rule for {item}",
        }

    current_remainder = base_hp_stat % divisor
    if current_remainder == target_remainder:
        return {
            "recommended_sp": 0,
            "resulting_hp": base_hp_stat,
            "reason": f"Already optimal for {item}",
        }

    sp_needed = (target_remainder - current_remainder) % divisor
    if sp_needed > MAX_SP_PER_STAT:
        # Find next valid target
        sp_needed = sp_needed % divisor or divisor

    return {
        "recommended_sp": min(sp_needed, MAX_SP_PER_STAT),
        "resulting_hp": base_hp_stat + min(sp_needed, MAX_SP_PER_STAT),
        "reason": reason,
    }


def optimize_champions_sp(
    base_stats: dict[str, int],
    nature: str,
    goals: list[SpGoal],
    level: int = 50,
) -> dict:
    """Optimize SP allocation based on prioritized goals.

    Goals are processed in order. Each goal consumes SP from the
    66-point budget. Remaining SP goes to the last MaximizeGoal
    or is left unallocated.
    """
    sp_spread = {s: 0 for s in STAT_ORDER}
    remaining = MAX_TOTAL_SP
    goal_results = []

    for goal in goals:
        if isinstance(goal, SpeedGoal):
            mult = get_nature_multiplier(nature, "spe")
            raw = math.floor((2 * base_stats["spe"]) * level / 100) + 5
            base_speed = math.floor(raw * mult)

            if goal.mode == "outspeed":
                sp_needed = goal.target_speed + 1 - base_speed
                if sp_needed < 0:
                    sp_needed = 0
                if sp_needed > min(MAX_SP_PER_STAT, remaining):
                    goal_results.append({
                        "goal": f"Outspeed {goal.target_speed}",
                        "achieved": False,
                        "detail": (
                            f"Need {sp_needed} Spe SP but only "
                            f"{min(MAX_SP_PER_STAT, remaining)} available"
                        ),
                    })
                    return {
                        "success": False,
                        "sp_spread": sp_spread,
                        "remaining_sp": remaining,
                        "goal_results": goal_results,
                    }
                sp_spread["spe"] = sp_needed
                remaining -= sp_needed
                goal_results.append({
                    "goal": f"Outspeed {goal.target_speed}",
                    "achieved": True,
                    "sp_used": sp_needed,
                    "resulting_speed": base_speed + sp_needed,
                })
            else:  # underspeed
                # For underspeed, we want minimum speed, so 0 SP
                goal_results.append({
                    "goal": f"Underspeed {goal.target_speed}",
                    "achieved": base_speed < goal.target_speed,
                    "sp_used": 0,
                    "resulting_speed": base_speed,
                })
                if base_speed >= goal.target_speed:
                    return {
                        "success": False,
                        "sp_spread": sp_spread,
                        "remaining_sp": remaining,
                        "goal_results": goal_results,
                    }

        elif isinstance(goal, HpThresholdGoal):
            hp_suggestion = suggest_hp_sp(
                base_stats["hp"], goal.item, level
            )
            sp_needed = hp_suggestion["recommended_sp"]
            sp_needed = min(sp_needed, remaining, MAX_SP_PER_STAT)
            sp_spread["hp"] = sp_needed
            remaining -= sp_needed
            goal_results.append({
                "goal": f"HP optimization for {goal.item}",
                "achieved": True,
                "sp_used": sp_needed,
                "resulting_hp": calculate_champions_hp(
                    base_stats["hp"], sp_needed, level
                ),
            })

        elif isinstance(goal, MaximizeGoal):
            stat = goal.stat
            sp_to_add = min(
                MAX_SP_PER_STAT - sp_spread[stat], remaining
            )
            sp_spread[stat] += sp_to_add
            remaining -= sp_to_add
            goal_results.append({
                "goal": f"Maximize {stat}",
                "achieved": True,
                "sp_used": sp_to_add,
            })

    return {
        "success": True,
        "sp_spread": sp_spread,
        "remaining_sp": remaining,
        "total_sp": MAX_TOTAL_SP - remaining,
        "goal_results": goal_results,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_champions_sp_optimizer.py -v`
Expected: All PASS

- [ ] **Step 5: Lint check**

Run: `uv run ruff check src/smogon_vgc_mcp/calculator/champions_sp_optimizer.py tests/test_champions_sp_optimizer.py && uv run ruff format --check src/smogon_vgc_mcp/calculator/champions_sp_optimizer.py tests/test_champions_sp_optimizer.py`
Expected: Clean

- [ ] **Step 6: Commit**

```bash
git add src/smogon_vgc_mcp/calculator/champions_sp_optimizer.py tests/test_champions_sp_optimizer.py
git commit -m "feat: add Champions SP optimizer with HP thresholds and speed goals"
```

---

### Task 4: Champions Calculator MCP Tools

**Files:**
- Create: `src/smogon_vgc_mcp/tools/champions_calculator.py`
- Modify: `src/smogon_vgc_mcp/tools/__init__.py`
- Modify: `src/smogon_vgc_mcp/server.py`
- Create: `tests/test_champions_calculator_tools.py`

- [ ] **Step 1: Write failing tests for MCP tool registration**

```python
"""Tests for Champions calculator MCP tools."""

import pytest

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.tools.champions_calculator import (
    register_champions_calculator_tools,
)


@pytest.fixture
def mcp_server():
    """Create a test MCP server."""
    return FastMCP("test")


class TestChampionsCalculatorToolRegistration:
    """Tests that Champions tools register correctly."""

    def test_tools_register_without_error(self, mcp_server):
        register_champions_calculator_tools(mcp_server)

    def test_calculate_champions_stats_tool(self, mcp_server):
        register_champions_calculator_tools(mcp_server)
        tools = mcp_server._tool_manager._tools
        assert "calculate_champions_stats" in tools

    def test_compare_champions_speeds_tool(self, mcp_server):
        register_champions_calculator_tools(mcp_server)
        tools = mcp_server._tool_manager._tools
        assert "compare_champions_speeds" in tools

    def test_get_champions_speed_benchmarks_tool(self, mcp_server):
        register_champions_calculator_tools(mcp_server)
        tools = mcp_server._tool_manager._tools
        assert "get_champions_speed_benchmarks" in tools

    def test_suggest_champions_sp_spread_tool(self, mcp_server):
        register_champions_calculator_tools(mcp_server)
        tools = mcp_server._tool_manager._tools
        assert "suggest_champions_sp_spread" in tools


class TestCalculateChampionsStatsTool:
    """Integration tests for calculate_champions_stats tool."""

    @pytest.mark.asyncio
    async def test_valid_pokemon_returns_stats(self, mcp_server):
        register_champions_calculator_tools(mcp_server)
        tool_fn = mcp_server._tool_manager._tools[
            "calculate_champions_stats"
        ].fn
        result = await tool_fn(
            pokemon="venusaur",
            sp_spread="0/0/0/32/0/2",
            nature="Modest",
        )
        assert "calculated_stats" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_invalid_pokemon_returns_error(self, mcp_server):
        register_champions_calculator_tools(mcp_server)
        tool_fn = mcp_server._tool_manager._tools[
            "calculate_champions_stats"
        ].fn
        result = await tool_fn(
            pokemon="notapokemon",
            sp_spread="0/0/0/0/0/0",
            nature="Hardy",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_sp_over_66_returns_error(self, mcp_server):
        register_champions_calculator_tools(mcp_server)
        tool_fn = mcp_server._tool_manager._tools[
            "calculate_champions_stats"
        ].fn
        result = await tool_fn(
            pokemon="venusaur",
            sp_spread="32/32/32/0/0/0",
            nature="Hardy",
        )
        assert "error" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_champions_calculator_tools.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `champions_calculator.py` MCP tools**

```python
"""Champions calculator tools for MCP server.

Separate tool module for Pokemon Champions format calculations.
Uses Stat Points (SP) instead of EVs/IVs.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.calculator.champions_speed import (
    compare_champions_speeds as _compare_speeds,
    find_champions_speed_benchmarks,
    find_champions_speed_sp,
    get_champions_speed,
)
from smogon_vgc_mcp.calculator.champions_sp_optimizer import (
    HpThresholdGoal,
    MaximizeGoal,
    SpeedGoal,
    optimize_champions_sp,
)
from smogon_vgc_mcp.calculator.champions_stats import (
    MAX_SP_PER_STAT,
    MAX_TOTAL_SP,
    STAT_ORDER,
    calculate_all_champions_stats,
    format_champions_stats,
)
from smogon_vgc_mcp.database.models import ChampionsDexPokemon
from smogon_vgc_mcp.database.queries import get_champions_pokemon
from smogon_vgc_mcp.utils import make_error_response


def _parse_sp_spread(sp_string: str) -> dict[str, int] | str:
    """Parse SP spread string 'HP/Atk/Def/SpA/SpD/Spe' into dict.

    Returns dict on success, error string on failure.
    """
    parts = sp_string.split("/")
    if len(parts) != 6:
        return "SP spread must be 6 values separated by / (e.g., '0/0/0/32/0/2')"

    try:
        values = [int(p.strip()) for p in parts]
    except ValueError:
        return "SP values must be integers"

    for i, v in enumerate(values):
        if not 0 <= v <= MAX_SP_PER_STAT:
            return (
                f"{STAT_ORDER[i]} SP must be 0-{MAX_SP_PER_STAT}, got {v}"
            )

    total = sum(values)
    if total > MAX_TOTAL_SP:
        return f"Total SP must not exceed {MAX_TOTAL_SP}, got {total}"

    return dict(zip(STAT_ORDER, values))


async def _get_champions_base_stats(
    pokemon_id: str,
) -> ChampionsDexPokemon | None:
    """Look up Champions Pokemon base stats from database."""
    return await get_champions_pokemon(pokemon_id)


def register_champions_calculator_tools(mcp: FastMCP) -> None:
    """Register Champions calculator tools with the MCP server."""

    @mcp.tool()
    async def calculate_champions_stats(
        pokemon: str,
        sp_spread: str,
        nature: str = "Hardy",
        level: int = 50,
    ) -> dict:
        """Calculate exact stat values for a Champions format Pokemon.

        Champions uses Stat Points (SP) instead of EVs/IVs.
        66 total SP, max 32 per stat.

        Returns: pokemon, level, nature, sp_spread, base_stats,
        calculated_stats, formatted.

        Examples:
        - "What are Venusaur's stats with 32 SpA and Modest?"
        - "Calculate Incineroar's bulk with 32 HP / 32 Def"

        Args:
            pokemon: Pokemon name (e.g., "venusaur", "incineroar").
            sp_spread: SP allocation "HP/Atk/Def/SpA/SpD/Spe"
                       (e.g., "0/0/0/32/0/2"). Max 32 each, 66 total.
            nature: Nature name (e.g., "Modest", "Adamant"). Default neutral.
            level: Pokemon level. Default 50.
        """
        sp = _parse_sp_spread(sp_spread)
        if isinstance(sp, str):
            return make_error_response(sp)

        pokemon_data = await _get_champions_base_stats(
            pokemon.lower().replace(" ", "").replace("-", "")
        )
        if not pokemon_data:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Champions dex",
                hint="Check spelling or use the Champions dex name",
            )

        stats = calculate_all_champions_stats(
            pokemon_data.base_stats, sp, nature, level
        )
        if stats is None:
            return make_error_response(
                f"Invalid nature '{nature}'",
                hint="Use a valid nature like Adamant, Modest, Jolly, etc.",
            )

        return {
            "pokemon": pokemon_data.name,
            "level": level,
            "nature": nature,
            "sp_spread": sp_spread,
            "base_stats": pokemon_data.base_stats,
            "calculated_stats": stats,
            "formatted": format_champions_stats(stats),
        }

    @mcp.tool()
    async def compare_champions_speeds(
        pokemon1: str,
        sp1: int,
        nature1: str,
        pokemon2: str,
        sp2: int,
        nature2: str,
    ) -> dict:
        """Compare speed between two Champions Pokemon builds.

        Returns: pokemon1 {name, speed}, pokemon2 {name, speed},
        result, difference.

        Args:
            pokemon1: First Pokemon name.
            sp1: First Pokemon's Speed SP (0-32).
            nature1: First Pokemon's nature.
            pokemon2: Second Pokemon name.
            sp2: Second Pokemon's Speed SP (0-32).
            nature2: Second Pokemon's nature.
        """
        p1 = await _get_champions_base_stats(
            pokemon1.lower().replace(" ", "").replace("-", "")
        )
        p2 = await _get_champions_base_stats(
            pokemon2.lower().replace(" ", "").replace("-", "")
        )

        if not p1:
            return make_error_response(
                f"Pokemon '{pokemon1}' not found in Champions dex"
            )
        if not p2:
            return make_error_response(
                f"Pokemon '{pokemon2}' not found in Champions dex"
            )

        return _compare_speeds(
            pokemon1=p1.name,
            base_spe1=p1.base_stats["spe"],
            sp1=sp1,
            nature1=nature1,
            pokemon2=p2.name,
            base_spe2=p2.base_stats["spe"],
            sp2=sp2,
            nature2=nature2,
        )

    @mcp.tool()
    async def get_champions_speed_benchmarks(
        pokemon: str,
        sp: int = 0,
        nature: str = "Hardy",
    ) -> dict:
        """Find what Champions meta Pokemon a speed stat outspeeds.

        Uses pre-computed Champions speed tier data including
        weather abilities, Tailwind, and boost benchmarks.

        Returns: pokemon, speed, outspeeds[], underspeeds[], speed_ties[].

        Args:
            pokemon: Pokemon name.
            sp: Speed SP investment (0-32).
            nature: Nature (e.g., "Jolly" for +Spe, "Brave" for -Spe).
        """
        p = await _get_champions_base_stats(
            pokemon.lower().replace(" ", "").replace("-", "")
        )
        if not p:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Champions dex"
            )

        speed = get_champions_speed(
            p.base_stats["spe"], sp, nature
        )
        return find_champions_speed_benchmarks(p.name, speed)

    @mcp.tool()
    async def suggest_champions_sp_spread(
        pokemon: str,
        nature: str,
        goals: list[dict[str, Any]],
        item: str | None = None,
    ) -> dict:
        """Generate an optimized SP spread for a Champions Pokemon.

        Allocates 66 total Stat Points based on prioritized goals.
        Goals are processed in order (first = highest priority).

        Returns: pokemon, sp_spread, remaining_sp, goal_results[],
        calculated_stats.

        Goal types:
        - SPEED: {"type": "speed", "target_speed": int}
          Optional: mode ("outspeed" or "underspeed", default "outspeed")
        - HP: {"type": "hp", "item": str}
          Optimizes HP for Leftovers/Life Orb/Sitrus Berry
        - MAXIMIZE: {"type": "maximize", "stat": str}
          Dumps remaining SP into stat

        Examples:
        - "Build Venusaur to outspeed 132 speed tier, then max SpA"
        - "Optimize Incineroar for Leftovers HP, then max SpD"

        Args:
            pokemon: Pokemon name.
            nature: Nature name.
            goals: List of goal dicts in priority order.
            item: Held item (used for HP optimization).
        """
        p = await _get_champions_base_stats(
            pokemon.lower().replace(" ", "").replace("-", "")
        )
        if not p:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Champions dex"
            )

        parsed_goals = []
        for g in goals:
            goal_type = g.get("type", "").lower()
            if goal_type == "speed":
                parsed_goals.append(SpeedGoal(
                    target_speed=g.get("target_speed", 0),
                    mode=g.get("mode", "outspeed"),
                ))
            elif goal_type == "hp":
                parsed_goals.append(HpThresholdGoal(
                    item=g.get("item", item or ""),
                ))
            elif goal_type == "maximize":
                parsed_goals.append(MaximizeGoal(
                    stat=g.get("stat", "hp"),
                ))

        if not parsed_goals:
            return make_error_response(
                "No valid goals provided",
                hint="Goals need 'type' field: speed, hp, or maximize",
            )

        result = optimize_champions_sp(
            base_stats=p.base_stats,
            nature=nature,
            goals=parsed_goals,
        )

        # Calculate final stats
        if result["success"]:
            stats = calculate_all_champions_stats(
                p.base_stats, result["sp_spread"], nature
            )
            result["calculated_stats"] = stats
            if stats:
                result["formatted"] = format_champions_stats(stats)

        sp_str = "/".join(
            str(result["sp_spread"][s]) for s in STAT_ORDER
        )
        result["pokemon"] = p.name
        result["sp_spread_formatted"] = sp_str

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_champions_calculator_tools.py -v`
Expected: All PASS

- [ ] **Step 5: Update `tools/__init__.py` to export new registration function**

Add to `src/smogon_vgc_mcp/tools/__init__.py`:

```python
from smogon_vgc_mcp.tools.champions_calculator import register_champions_calculator_tools
```

And add `"register_champions_calculator_tools"` to the `__all__` list.

- [ ] **Step 6: Register Champions tools in `server.py`**

Add to `src/smogon_vgc_mcp/server.py`:

```python
from smogon_vgc_mcp.tools import register_champions_calculator_tools
```

And call `register_champions_calculator_tools(logged_mcp)` after the other tool registrations.

- [ ] **Step 7: Run full test suite**

Run: `uv run python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Lint check**

Run: `uv run ruff check src/smogon_vgc_mcp/tools/champions_calculator.py tests/test_champions_calculator_tools.py && uv run ruff format --check src/smogon_vgc_mcp/tools/champions_calculator.py tests/test_champions_calculator_tools.py`
Expected: Clean

- [ ] **Step 9: Commit**

```bash
git add src/smogon_vgc_mcp/tools/champions_calculator.py src/smogon_vgc_mcp/tools/__init__.py src/smogon_vgc_mcp/server.py tests/test_champions_calculator_tools.py
git commit -m "feat: add Champions calculator MCP tools (stats, speed, SP optimizer)"
```

---

### Task 5: Final Integration — Run Full Suite & Verify

**Files:**
- None new; verification only

- [ ] **Step 1: Run full test suite**

Run: `uv run python -m pytest -v --tb=short`
Expected: All tests PASS (existing 131 + new ~50)

- [ ] **Step 2: Type check**

Run: `uv run ty check`
Expected: Clean (or only pre-existing warnings)

- [ ] **Step 3: Lint full project**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: Clean

- [ ] **Step 4: Verify Champions tools are registered**

Run: `uv run python -c "from smogon_vgc_mcp.tools.champions_calculator import register_champions_calculator_tools; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Final commit if any fixes needed**

Only if Steps 1-4 required changes:
```bash
git add -A
git commit -m "fix: resolve integration issues from Champions calculator"
```
