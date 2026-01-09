"""Tests for database/models.py - Data models."""

from smogon_vgc_mcp.database.models import (
    AbilityUsage,
    CheckCounter,
    DexAbility,
    DexItem,
    DexMove,
    DexPokemon,
    EVSpread,
    ItemUsage,
    MoveUsage,
    PokemonStats,
    Snapshot,
    Team,
    TeammateUsage,
    TeamPokemon,
    TeraTypeUsage,
    UsageRanking,
)


class TestSnapshot:
    """Tests for Snapshot dataclass."""

    def test_create_snapshot(self):
        """Test creating a Snapshot."""
        snapshot = Snapshot(
            id=1,
            format="regf",
            month="2025-12",
            elo_bracket=1500,
            num_battles=100000,
            fetched_at="2025-12-15T10:00:00",
        )

        assert snapshot.id == 1
        assert snapshot.format == "regf"
        assert snapshot.month == "2025-12"
        assert snapshot.elo_bracket == 1500
        assert snapshot.num_battles == 100000

    def test_snapshot_equality(self):
        """Test Snapshot equality comparison."""
        s1 = Snapshot(1, "regf", "2025-12", 1500, 100000, "2025-12-15")
        s2 = Snapshot(1, "regf", "2025-12", 1500, 100000, "2025-12-15")
        assert s1 == s2


class TestAbilityUsage:
    """Tests for AbilityUsage dataclass."""

    def test_create_ability_usage(self):
        """Test creating AbilityUsage."""
        ability = AbilityUsage(ability="Intimidate", count=49000, percent=98.0)

        assert ability.ability == "Intimidate"
        assert ability.count == 49000
        assert ability.percent == 98.0


class TestItemUsage:
    """Tests for ItemUsage dataclass."""

    def test_create_item_usage(self):
        """Test creating ItemUsage."""
        item = ItemUsage(item="Safety Goggles", count=20000, percent=40.0)

        assert item.item == "Safety Goggles"
        assert item.count == 20000
        assert item.percent == 40.0


class TestMoveUsage:
    """Tests for MoveUsage dataclass."""

    def test_create_move_usage(self):
        """Test creating MoveUsage."""
        move = MoveUsage(move="Fake Out", count=48000, percent=96.0)

        assert move.move == "Fake Out"
        assert move.count == 48000
        assert move.percent == 96.0


class TestTeammateUsage:
    """Tests for TeammateUsage dataclass."""

    def test_create_teammate_usage(self):
        """Test creating TeammateUsage."""
        teammate = TeammateUsage(teammate="Flutter Mane", count=25000, percent=50.0)

        assert teammate.teammate == "Flutter Mane"
        assert teammate.count == 25000
        assert teammate.percent == 50.0


class TestEVSpread:
    """Tests for EVSpread dataclass."""

    def test_create_ev_spread(self):
        """Test creating EVSpread."""
        spread = EVSpread(
            nature="Careful",
            hp=252,
            atk=4,
            def_=0,
            spa=0,
            spd=252,
            spe=0,
            count=15000,
            percent=30.0,
        )

        assert spread.nature == "Careful"
        assert spread.hp == 252
        assert spread.spd == 252
        assert spread.def_ == 0  # Note: 'def_' to avoid reserved word

    def test_ev_spread_common_sets(self):
        """Test common VGC EV spreads."""
        # Physical attacker spread
        physical = EVSpread(
            nature="Adamant",
            hp=252,
            atk=252,
            def_=4,
            spa=0,
            spd=0,
            spe=0,
            count=10000,
            percent=20.0,
        )
        assert physical.hp + physical.atk + physical.def_ == 508

        # Speed special attacker spread
        special = EVSpread(
            nature="Timid", hp=4, atk=0, def_=0, spa=252, spd=0, spe=252, count=8000, percent=16.0
        )
        assert special.hp + special.spa + special.spe == 508


class TestTeraTypeUsage:
    """Tests for TeraTypeUsage dataclass."""

    def test_create_tera_type_usage(self):
        """Test creating TeraTypeUsage."""
        tera = TeraTypeUsage(tera_type="Ghost", percent=45.0)

        assert tera.tera_type == "Ghost"
        assert tera.percent == 45.0


class TestCheckCounter:
    """Tests for CheckCounter dataclass."""

    def test_create_check_counter(self):
        """Test creating CheckCounter."""
        counter = CheckCounter(
            counter="Urshifu-Rapid-Strike",
            score=55.0,
            win_percent=60.0,
            ko_percent=35.0,
            switch_percent=25.0,
        )

        assert counter.counter == "Urshifu-Rapid-Strike"
        assert counter.score == 55.0
        assert counter.win_percent == 60.0
        assert counter.ko_percent == 35.0
        assert counter.switch_percent == 25.0


class TestPokemonStats:
    """Tests for PokemonStats dataclass."""

    def test_create_pokemon_stats_minimal(self):
        """Test creating PokemonStats with minimal fields."""
        stats = PokemonStats(
            pokemon="Incineroar",
            raw_count=50000,
            usage_percent=48.39,
            viability_ceiling=[1, 1, 1, 1],
        )

        assert stats.pokemon == "Incineroar"
        assert stats.raw_count == 50000
        assert stats.usage_percent == 48.39
        assert stats.abilities == []
        assert stats.items == []
        assert stats.moves == []

    def test_create_pokemon_stats_full(self):
        """Test creating PokemonStats with all fields."""
        stats = PokemonStats(
            pokemon="Incineroar",
            raw_count=50000,
            usage_percent=48.39,
            viability_ceiling=[1, 1, 1, 1],
            abilities=[AbilityUsage("Intimidate", 49000, 98.0)],
            items=[ItemUsage("Safety Goggles", 20000, 40.0)],
            moves=[MoveUsage("Fake Out", 48000, 96.0)],
            teammates=[TeammateUsage("Flutter Mane", 25000, 50.0)],
            spreads=[EVSpread("Careful", 252, 4, 0, 0, 252, 0, 15000, 30.0)],
            tera_types=[TeraTypeUsage("Ghost", 45.0)],
            checks_counters=[CheckCounter("Urshifu-Rapid-Strike", 55.0, 60.0, 35.0, 25.0)],
        )

        assert len(stats.abilities) == 1
        assert stats.abilities[0].ability == "Intimidate"
        assert len(stats.moves) == 1
        assert stats.moves[0].move == "Fake Out"

    def test_pokemon_stats_default_lists(self):
        """Test that list fields default to empty lists."""
        stats = PokemonStats("Test", 1000, 10.0, [1])

        assert isinstance(stats.abilities, list)
        assert isinstance(stats.items, list)
        assert isinstance(stats.moves, list)
        assert isinstance(stats.teammates, list)
        assert isinstance(stats.spreads, list)
        assert isinstance(stats.tera_types, list)
        assert isinstance(stats.checks_counters, list)


class TestUsageRanking:
    """Tests for UsageRanking dataclass."""

    def test_create_usage_ranking(self):
        """Test creating UsageRanking."""
        ranking = UsageRanking(
            rank=1,
            pokemon="Flutter Mane",
            usage_percent=50.1,
            raw_count=52000,
        )

        assert ranking.rank == 1
        assert ranking.pokemon == "Flutter Mane"
        assert ranking.usage_percent == 50.1
        assert ranking.raw_count == 52000


class TestTeamPokemon:
    """Tests for TeamPokemon dataclass."""

    def test_create_team_pokemon_minimal(self):
        """Test creating TeamPokemon with minimal fields."""
        pokemon = TeamPokemon(slot=1, pokemon="Incineroar")

        assert pokemon.slot == 1
        assert pokemon.pokemon == "Incineroar"
        assert pokemon.item is None
        assert pokemon.ability is None

    def test_create_team_pokemon_full(self):
        """Test creating TeamPokemon with all fields."""
        pokemon = TeamPokemon(
            slot=1,
            pokemon="Incineroar",
            item="Safety Goggles",
            ability="Intimidate",
            tera_type="Ghost",
            nature="Careful",
            hp_ev=252,
            atk_ev=4,
            def_ev=0,
            spa_ev=0,
            spd_ev=252,
            spe_ev=0,
            hp_iv=31,
            atk_iv=31,
            def_iv=31,
            spa_iv=31,
            spd_iv=31,
            spe_iv=31,
            move1="Fake Out",
            move2="Flare Blitz",
            move3="Parting Shot",
            move4="Knock Off",
        )

        assert pokemon.item == "Safety Goggles"
        assert pokemon.ability == "Intimidate"
        assert pokemon.hp_ev == 252
        assert pokemon.move1 == "Fake Out"

    def test_team_pokemon_default_ivs(self):
        """Test TeamPokemon default IVs are 31."""
        pokemon = TeamPokemon(slot=1, pokemon="Test")

        assert pokemon.hp_iv == 31
        assert pokemon.atk_iv == 31
        assert pokemon.def_iv == 31
        assert pokemon.spa_iv == 31
        assert pokemon.spd_iv == 31
        assert pokemon.spe_iv == 31

    def test_team_pokemon_default_evs(self):
        """Test TeamPokemon default EVs are 0."""
        pokemon = TeamPokemon(slot=1, pokemon="Test")

        assert pokemon.hp_ev == 0
        assert pokemon.atk_ev == 0
        assert pokemon.def_ev == 0
        assert pokemon.spa_ev == 0
        assert pokemon.spd_ev == 0
        assert pokemon.spe_ev == 0


class TestTeam:
    """Tests for Team dataclass."""

    def test_create_team_minimal(self):
        """Test creating Team with minimal fields."""
        team = Team(id=1, format="regf", team_id="F1")

        assert team.id == 1
        assert team.format == "regf"
        assert team.team_id == "F1"
        assert team.pokemon == []

    def test_create_team_full(self):
        """Test creating Team with all fields."""
        pokemon1 = TeamPokemon(slot=1, pokemon="Incineroar")
        pokemon2 = TeamPokemon(slot=2, pokemon="Flutter Mane")

        team = Team(
            id=1,
            format="regf",
            team_id="F1",
            description="Sample VGC team",
            owner="TestPlayer",
            tournament="Regional Championship",
            rank="1st",
            rental_code="ABC123",
            pokepaste_url="https://pokepast.es/abc123",
            source_url="https://example.com",
            fetched_at="2025-12-15T10:00:00",
            pokemon=[pokemon1, pokemon2],
        )

        assert team.owner == "TestPlayer"
        assert team.tournament == "Regional Championship"
        assert len(team.pokemon) == 2
        assert team.pokemon[0].pokemon == "Incineroar"


class TestDexPokemon:
    """Tests for DexPokemon dataclass."""

    def test_create_dex_pokemon_minimal(self):
        """Test creating DexPokemon with required fields."""
        pokemon = DexPokemon(
            id="incineroar",
            num=727,
            name="Incineroar",
            types=["Fire", "Dark"],
            base_stats={"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60},
            abilities=["Blaze", "Intimidate"],
        )

        assert pokemon.id == "incineroar"
        assert pokemon.num == 727
        assert pokemon.types == ["Fire", "Dark"]
        assert pokemon.base_stats["atk"] == 115

    def test_create_dex_pokemon_full(self):
        """Test creating DexPokemon with all fields."""
        pokemon = DexPokemon(
            id="fluttermane",
            num=987,
            name="Flutter Mane",
            types=["Ghost", "Fairy"],
            base_stats={"hp": 55, "atk": 55, "def": 55, "spa": 135, "spd": 135, "spe": 135},
            abilities=["Protosynthesis"],
            ability_hidden=None,
            height_m=1.4,
            weight_kg=4.0,
            tier="OU",
            prevo=None,
            evo_level=None,
            base_species="Flutter Mane",
            forme=None,
        )

        assert pokemon.height_m == 1.4
        assert pokemon.weight_kg == 4.0
        assert pokemon.tier == "OU"


class TestDexMove:
    """Tests for DexMove dataclass."""

    def test_create_dex_move(self):
        """Test creating DexMove."""
        move = DexMove(
            id="moonblast",
            num=585,
            name="Moonblast",
            type="Fairy",
            category="Special",
            base_power=95,
            accuracy=100,
            pp=15,
            priority=0,
            target="normal",
            description="Deals damage and may lower SpA.",
            short_desc="30% chance to lower SpA by 1.",
        )

        assert move.name == "Moonblast"
        assert move.type == "Fairy"
        assert move.base_power == 95
        assert move.accuracy == 100

    def test_create_status_move(self):
        """Test creating a status move (no base power)."""
        move = DexMove(
            id="protect",
            num=182,
            name="Protect",
            type="Normal",
            category="Status",
            base_power=None,
            accuracy=None,
            pp=10,
            priority=4,
        )

        assert move.base_power is None
        assert move.accuracy is None
        assert move.priority == 4


class TestDexAbility:
    """Tests for DexAbility dataclass."""

    def test_create_dex_ability(self):
        """Test creating DexAbility."""
        ability = DexAbility(
            id="intimidate",
            num=22,
            name="Intimidate",
            description="On switch-in, this Pokemon lowers the Attack of adjacent foes by 1 stage.",
            short_desc="On switch-in, this Pokemon lowers the Attack of adjacent foes by 1 stage.",
            rating=3.5,
        )

        assert ability.name == "Intimidate"
        assert ability.num == 22
        assert ability.rating == 3.5


class TestDexItem:
    """Tests for DexItem dataclass."""

    def test_create_dex_item(self):
        """Test creating DexItem."""
        item = DexItem(
            id="safetygoggles",
            num=650,
            name="Safety Goggles",
            description="Holder is immune to powder moves and damage from Sandstorm and Hail.",
            short_desc="Protects from powder moves and weather damage.",
            fling_power=80,
            gen=6,
        )

        assert item.name == "Safety Goggles"
        assert item.fling_power == 80
        assert item.gen == 6

    def test_create_dex_item_minimal(self):
        """Test creating DexItem with minimal fields."""
        item = DexItem(id="leftovers", num=234, name="Leftovers")

        assert item.name == "Leftovers"
        assert item.description is None
        assert item.fling_power is None


class TestModelIntegration:
    """Integration tests for model relationships."""

    def test_full_pokemon_stats_structure(self, sample_incineroar_stats):
        """Test full PokemonStats structure from fixture."""
        stats = sample_incineroar_stats

        assert stats.pokemon == "Incineroar"
        assert len(stats.abilities) >= 1
        assert stats.abilities[0].ability == "Intimidate"
        assert len(stats.moves) >= 4
        assert len(stats.spreads) >= 1

    def test_full_team_structure(self, sample_team):
        """Test full Team structure from fixture."""
        team = sample_team

        assert team.team_id == "F1"
        assert len(team.pokemon) >= 2
        assert team.pokemon[0].pokemon == "Incineroar"
        assert team.pokemon[1].pokemon == "Flutter Mane"
