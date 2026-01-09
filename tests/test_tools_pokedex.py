"""Tests for tools/pokedex.py - Pokedex lookup tools."""

from unittest.mock import MagicMock, patch

import pytest


# Create mock FastMCP for testing
class MockFastMCP:
    """Mock FastMCP to capture registered tools."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator


class TestDexPokemon:
    """Tests for dex_pokemon tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_pokemon")
    async def test_returns_pokemon_data(self, mock_get_pokemon, mock_mcp):
        """Test returning Pokemon data."""
        mock_pokemon = MagicMock()
        mock_pokemon.name = "Flutter Mane"
        mock_pokemon.types = ["Ghost", "Fairy"]
        mock_pokemon.base_stats = {"hp": 55, "atk": 55, "def": 55, "spa": 135, "spd": 135, "spe": 135}
        mock_pokemon.abilities = ["Protosynthesis"]
        mock_pokemon.ability_hidden = None
        mock_pokemon.height_m = 1.4
        mock_pokemon.weight_kg = 4.0
        mock_pokemon.tier = "OU"
        mock_pokemon.prevo = None
        mock_pokemon.evo_level = None

        mock_get_pokemon.return_value = mock_pokemon

        dex_pokemon = mock_mcp.tools["dex_pokemon"]
        result = await dex_pokemon("Flutter Mane")

        assert result["name"] == "Flutter Mane"
        assert result["types"] == ["Ghost", "Fairy"]
        assert result["bst"] == 570

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_pokemon")
    async def test_returns_error_when_not_found(self, mock_get_pokemon, mock_mcp):
        """Test returning error when Pokemon not found."""
        mock_get_pokemon.return_value = None

        dex_pokemon = mock_mcp.tools["dex_pokemon"]
        result = await dex_pokemon("NotAPokemon")

        assert "error" in result
        assert "not found" in result["error"]


class TestDexMove:
    """Tests for dex_move tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_move")
    async def test_returns_move_data(self, mock_get_move, mock_mcp):
        """Test returning move data."""
        mock_move = MagicMock()
        mock_move.name = "Moonblast"
        mock_move.type = "Fairy"
        mock_move.category = "Special"
        mock_move.base_power = 95
        mock_move.accuracy = 100
        mock_move.pp = 15
        mock_move.priority = 0
        mock_move.target = "normal"
        mock_move.short_desc = "30% chance to lower SpA by 1."
        mock_move.description = None

        mock_get_move.return_value = mock_move

        dex_move = mock_mcp.tools["dex_move"]
        result = await dex_move("Moonblast")

        assert result["name"] == "Moonblast"
        assert result["type"] == "Fairy"
        assert result["base_power"] == 95

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_move")
    async def test_returns_error_when_not_found(self, mock_get_move, mock_mcp):
        """Test returning error when move not found."""
        mock_get_move.return_value = None

        dex_move = mock_mcp.tools["dex_move"]
        result = await dex_move("NotAMove")

        assert "error" in result


class TestDexAbility:
    """Tests for dex_ability tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_ability")
    async def test_returns_ability_data(self, mock_get_ability, mock_mcp):
        """Test returning ability data."""
        mock_ability = MagicMock()
        mock_ability.name = "Intimidate"
        mock_ability.short_desc = "On switch-in, this Pokemon lowers the Attack of opponents by 1 stage."
        mock_ability.description = None
        mock_ability.rating = 4.5

        mock_get_ability.return_value = mock_ability

        dex_ability = mock_mcp.tools["dex_ability"]
        result = await dex_ability("Intimidate")

        assert result["name"] == "Intimidate"
        assert "Attack" in result["effect"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_ability")
    async def test_returns_error_when_not_found(self, mock_get_ability, mock_mcp):
        """Test returning error when ability not found."""
        mock_get_ability.return_value = None

        dex_ability = mock_mcp.tools["dex_ability"]
        result = await dex_ability("NotAnAbility")

        assert "error" in result


class TestDexItem:
    """Tests for dex_item tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_item")
    async def test_returns_item_data(self, mock_get_item, mock_mcp):
        """Test returning item data."""
        mock_item = MagicMock()
        mock_item.name = "Choice Scarf"
        mock_item.short_desc = "Holder's Speed is 1.5x, but it can only use its first move."
        mock_item.description = None
        mock_item.fling_power = 10
        mock_item.gen = 4

        mock_get_item.return_value = mock_item

        dex_item = mock_mcp.tools["dex_item"]
        result = await dex_item("Choice Scarf")

        assert result["name"] == "Choice Scarf"
        assert "Speed" in result["effect"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_dex_item")
    async def test_returns_error_when_not_found(self, mock_get_item, mock_mcp):
        """Test returning error when item not found."""
        mock_get_item.return_value = None

        dex_item = mock_mcp.tools["dex_item"]
        result = await dex_item("NotAnItem")

        assert "error" in result


class TestDexLearnset:
    """Tests for dex_learnset tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_pokemon_learnset")
    async def test_returns_learnset(self, mock_get_learnset, mock_mcp):
        """Test returning learnset."""
        mock_move1 = MagicMock()
        mock_move1.name = "Moonblast"
        mock_move1.type = "Fairy"
        mock_move1.category = "Special"
        mock_move1.base_power = 95
        mock_move1.accuracy = 100

        mock_move2 = MagicMock()
        mock_move2.name = "Shadow Ball"
        mock_move2.type = "Ghost"
        mock_move2.category = "Special"
        mock_move2.base_power = 80
        mock_move2.accuracy = 100

        mock_get_learnset.return_value = [mock_move1, mock_move2]

        dex_learnset = mock_mcp.tools["dex_learnset"]
        result = await dex_learnset("Flutter Mane")

        assert result["pokemon"] == "Flutter Mane"
        assert result["total_moves"] == 2
        assert "Fairy" in result["by_type"]
        assert "Ghost" in result["by_type"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_pokemon_learnset")
    async def test_returns_error_when_not_found(self, mock_get_learnset, mock_mcp):
        """Test returning error when no learnset found."""
        mock_get_learnset.return_value = []

        dex_learnset = mock_mcp.tools["dex_learnset"]
        result = await dex_learnset("NotAPokemon")

        assert "error" in result


class TestDexTypeEffectiveness:
    """Tests for dex_type_effectiveness tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_type_effectiveness")
    async def test_returns_effectiveness(self, mock_get_eff, mock_mcp):
        """Test returning type effectiveness."""
        mock_get_eff.return_value = {
            "attacking_type": "Fire",
            "defending_types": ["Grass", "Steel"],
            "effectiveness": 4.0,
        }

        dex_type_effectiveness = mock_mcp.tools["dex_type_effectiveness"]
        result = await dex_type_effectiveness("Fire", "Grass,Steel")

        assert result["effectiveness"] == 4.0


class TestDexPokemonWeaknesses:
    """Tests for dex_pokemon_weaknesses tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_pokemon_type_matchups")
    async def test_returns_matchups(self, mock_get_matchups, mock_mcp):
        """Test returning type matchups."""
        mock_get_matchups.return_value = {
            "pokemon": "Flutter Mane",
            "types": ["Ghost", "Fairy"],
            "weak_to": ["Ghost", "Steel"],
            "resists": ["Bug"],
            "immune_to": ["Normal", "Dragon", "Fighting"],
        }

        dex_pokemon_weaknesses = mock_mcp.tools["dex_pokemon_weaknesses"]
        result = await dex_pokemon_weaknesses("Flutter Mane")

        assert result["pokemon"] == "Flutter Mane"
        assert "Ghost" in result["weak_to"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_pokemon_type_matchups")
    async def test_returns_error_when_not_found(self, mock_get_matchups, mock_mcp):
        """Test returning error when Pokemon not found."""
        mock_get_matchups.return_value = None

        dex_pokemon_weaknesses = mock_mcp.tools["dex_pokemon_weaknesses"]
        result = await dex_pokemon_weaknesses("NotAPokemon")

        assert "error" in result


class TestSearchDex:
    """Tests for search_dex tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.search_dex_pokemon")
    async def test_search_pokemon(self, mock_search, mock_mcp):
        """Test searching for Pokemon."""
        mock_pokemon = MagicMock()
        mock_pokemon.name = "Flutter Mane"
        mock_pokemon.types = ["Ghost", "Fairy"]
        mock_pokemon.base_stats = {"hp": 55, "atk": 55, "def": 55, "spa": 135, "spd": 135, "spe": 135}

        mock_search.return_value = [mock_pokemon]

        search_dex = mock_mcp.tools["search_dex"]
        result = await search_dex("flutter", "pokemon")

        assert result["count"] == 1
        assert result["results"][0]["name"] == "Flutter Mane"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.search_dex_moves")
    async def test_search_moves(self, mock_search, mock_mcp):
        """Test searching for moves."""
        mock_move = MagicMock()
        mock_move.name = "Moonblast"
        mock_move.type = "Fairy"
        mock_move.category = "Special"
        mock_move.base_power = 95

        mock_search.return_value = [mock_move]

        search_dex = mock_mcp.tools["search_dex"]
        result = await search_dex("moon", "moves")

        assert result["count"] == 1
        assert result["results"][0]["name"] == "Moonblast"

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_category(self, mock_mcp):
        """Test returning error for invalid category."""
        search_dex = mock_mcp.tools["search_dex"]
        result = await search_dex("test", "invalid")

        assert "error" in result
        assert "Unknown category" in result["error"]


class TestDexPokemonByType:
    """Tests for dex_pokemon_by_type tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_pokemon_by_type")
    async def test_returns_pokemon_of_type(self, mock_get_by_type, mock_mcp):
        """Test returning Pokemon of a type."""
        mock_pokemon = MagicMock()
        mock_pokemon.name = "Flutter Mane"
        mock_pokemon.types = ["Ghost", "Fairy"]
        mock_pokemon.base_stats = {"hp": 55, "atk": 55, "def": 55, "spa": 135, "spd": 135, "spe": 135}

        mock_get_by_type.return_value = [mock_pokemon]

        dex_pokemon_by_type = mock_mcp.tools["dex_pokemon_by_type"]
        result = await dex_pokemon_by_type("Fairy")

        assert result["type"] == "Fairy"
        assert result["count"] == 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_pokemon_by_type")
    async def test_returns_error_when_no_results(self, mock_get_by_type, mock_mcp):
        """Test returning error when no Pokemon found."""
        mock_get_by_type.return_value = []

        dex_pokemon_by_type = mock_mcp.tools["dex_pokemon_by_type"]
        result = await dex_pokemon_by_type("invalidtype")

        assert "error" in result


class TestDexMovesByType:
    """Tests for dex_moves_by_type tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools

        mcp = MockFastMCP()
        register_pokedex_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_moves_by_type")
    async def test_returns_moves_of_type(self, mock_get_by_type, mock_mcp):
        """Test returning moves of a type."""
        mock_move = MagicMock()
        mock_move.name = "Moonblast"
        mock_move.category = "Special"
        mock_move.base_power = 95
        mock_move.accuracy = 100
        mock_move.short_desc = "30% chance to lower SpA by 1."

        mock_get_by_type.return_value = [mock_move]

        dex_moves_by_type = mock_mcp.tools["dex_moves_by_type"]
        result = await dex_moves_by_type("Fairy")

        assert result["type"] == "Fairy"
        assert result["count"] == 1
        assert result["moves"][0]["name"] == "Moonblast"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokedex.get_moves_by_type")
    async def test_returns_error_when_no_results(self, mock_get_by_type, mock_mcp):
        """Test returning error when no moves found."""
        mock_get_by_type.return_value = []

        dex_moves_by_type = mock_mcp.tools["dex_moves_by_type"]
        result = await dex_moves_by_type("invalidtype")

        assert "error" in result
