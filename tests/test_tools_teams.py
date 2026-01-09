"""Tests for tools/teams.py - Team lookup tools."""

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


class TestGetTournamentTeam:
    """Tests for get_tournament_team tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teams import register_team_tools

        mcp = MockFastMCP()
        register_team_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_team")
    async def test_returns_team_details(self, mock_get_team, mock_mcp):
        """Test returning full team details."""
        # Create mock team with Pokemon
        mock_pokemon = MagicMock()
        mock_pokemon.slot = 1
        mock_pokemon.pokemon = "Incineroar"
        mock_pokemon.item = "Safety Goggles"
        mock_pokemon.ability = "Intimidate"
        mock_pokemon.tera_type = "Ghost"
        mock_pokemon.nature = "Careful"
        mock_pokemon.hp_ev = 252
        mock_pokemon.atk_ev = 4
        mock_pokemon.def_ev = 0
        mock_pokemon.spa_ev = 0
        mock_pokemon.spd_ev = 252
        mock_pokemon.spe_ev = 0
        mock_pokemon.hp_iv = 31
        mock_pokemon.atk_iv = 31
        mock_pokemon.def_iv = 31
        mock_pokemon.spa_iv = 31
        mock_pokemon.spd_iv = 31
        mock_pokemon.spe_iv = 31
        mock_pokemon.move1 = "Fake Out"
        mock_pokemon.move2 = "Knock Off"
        mock_pokemon.move3 = "Flare Blitz"
        mock_pokemon.move4 = "Parting Shot"

        mock_team = MagicMock()
        mock_team.team_id = "F123"
        mock_team.description = "Top 8 Worlds"
        mock_team.owner = "Player123"
        mock_team.tournament = "World Championships"
        mock_team.rank = "Top 8"
        mock_team.rental_code = "ABC123"
        mock_team.pokepaste_url = "https://pokepast.es/123"
        mock_team.pokemon = [mock_pokemon]

        mock_get_team.return_value = mock_team

        get_tournament_team = mock_mcp.tools["get_tournament_team"]
        result = await get_tournament_team("F123")

        assert result["team_id"] == "F123"
        assert result["owner"] == "Player123"
        assert len(result["pokemon"]) == 1
        assert result["pokemon"][0]["pokemon"] == "Incineroar"
        assert result["pokemon"][0]["evs"] == "252/4/0/0/252/0"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_team")
    async def test_returns_error_when_not_found(self, mock_get_team, mock_mcp):
        """Test returning error when team not found."""
        mock_get_team.return_value = None

        get_tournament_team = mock_mcp.tools["get_tournament_team"]
        result = await get_tournament_team("F999")

        assert "error" in result
        assert "not found" in result["error"]
        assert "hint" in result


class TestSearchTournamentTeams:
    """Tests for search_tournament_teams tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teams import register_team_tools

        mcp = MockFastMCP()
        register_team_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_returns_error_when_no_params(self, mock_mcp):
        """Test returning error when no search parameters provided."""
        search_tournament_teams = mock_mcp.tools["search_tournament_teams"]
        result = await search_tournament_teams()

        assert "error" in result
        assert "At least one search parameter" in result["error"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.search_teams")
    async def test_returns_matching_teams(self, mock_search, mock_mcp):
        """Test returning matching teams."""
        mock_pokemon = MagicMock()
        mock_pokemon.pokemon = "Incineroar"

        mock_team = MagicMock()
        mock_team.team_id = "F123"
        mock_team.description = "Top 8"
        mock_team.owner = "Player123"
        mock_team.tournament = "Worlds"
        mock_team.rank = "Top 8"
        mock_team.rental_code = "ABC123"
        mock_team.pokemon = [mock_pokemon]

        mock_search.return_value = [mock_team]

        search_tournament_teams = mock_mcp.tools["search_tournament_teams"]
        result = await search_tournament_teams(pokemon="Incineroar")

        assert result["count"] == 1
        assert result["teams"][0]["team_id"] == "F123"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.search_teams")
    async def test_returns_empty_when_no_match(self, mock_search, mock_mcp):
        """Test returning empty when no matches."""
        mock_search.return_value = []

        search_tournament_teams = mock_mcp.tools["search_tournament_teams"]
        result = await search_tournament_teams(pokemon="NotAPokemon")

        assert result["count"] == 0
        assert result["teams"] == []
        assert "No teams found" in result["message"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.search_teams")
    async def test_limits_to_20(self, mock_search, mock_mcp):
        """Test that limit is capped at 20."""
        mock_search.return_value = []

        search_tournament_teams = mock_mcp.tools["search_tournament_teams"]
        await search_tournament_teams(pokemon="Incineroar", limit=50)

        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args[1]["limit"] == 20


class TestGetPokemonTournamentSpreads:
    """Tests for get_pokemon_tournament_spreads tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teams import register_team_tools

        mcp = MockFastMCP()
        register_team_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_tournament_ev_spreads")
    async def test_returns_spreads(self, mock_get_spreads, mock_mcp):
        """Test returning EV spreads."""
        mock_get_spreads.return_value = [
            {"nature": "Careful", "evs": "252/4/0/0/252/0", "count": 10, "team_ids": ["F1", "F2", "F3"]},
        ]

        get_pokemon_tournament_spreads = mock_mcp.tools["get_pokemon_tournament_spreads"]
        result = await get_pokemon_tournament_spreads("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert result["count"] == 1
        assert result["spreads"][0]["nature"] == "Careful"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_tournament_ev_spreads")
    async def test_returns_empty_when_no_data(self, mock_get_spreads, mock_mcp):
        """Test returning empty when no data."""
        mock_get_spreads.return_value = []

        get_pokemon_tournament_spreads = mock_mcp.tools["get_pokemon_tournament_spreads"]
        result = await get_pokemon_tournament_spreads("NotAPokemon")

        assert result["count"] == 0
        assert "No tournament data" in result["message"]


class TestFindTeamsWithPokemonCore:
    """Tests for find_teams_with_pokemon_core tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teams import register_team_tools

        mcp = MockFastMCP()
        register_team_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_teams_with_core")
    async def test_returns_teams_with_core(self, mock_get_core, mock_mcp):
        """Test returning teams with Pokemon core."""
        mock_pokemon1 = MagicMock()
        mock_pokemon1.pokemon = "Incineroar"
        mock_pokemon2 = MagicMock()
        mock_pokemon2.pokemon = "Flutter Mane"

        mock_team = MagicMock()
        mock_team.team_id = "F123"
        mock_team.description = "Top 8"
        mock_team.owner = "Player123"
        mock_team.tournament = "Worlds"
        mock_team.rank = "Top 8"
        mock_team.rental_code = "ABC123"
        mock_team.pokemon = [mock_pokemon1, mock_pokemon2]

        mock_get_core.return_value = [mock_team]

        find_teams_with_pokemon_core = mock_mcp.tools["find_teams_with_pokemon_core"]
        result = await find_teams_with_pokemon_core("Incineroar", "Flutter Mane")

        assert result["core"] == ["Incineroar", "Flutter Mane"]
        assert result["count"] == 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_teams_with_core")
    async def test_returns_empty_when_no_teams(self, mock_get_core, mock_mcp):
        """Test returning empty when no teams found."""
        mock_get_core.return_value = []

        find_teams_with_pokemon_core = mock_mcp.tools["find_teams_with_pokemon_core"]
        result = await find_teams_with_pokemon_core("Charizard", "Venusaur")

        assert result["count"] == 0
        assert "No teams found" in result["message"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_teams_with_core")
    async def test_handles_three_pokemon_core(self, mock_get_core, mock_mcp):
        """Test handling three Pokemon core."""
        mock_get_core.return_value = []

        find_teams_with_pokemon_core = mock_mcp.tools["find_teams_with_pokemon_core"]
        result = await find_teams_with_pokemon_core("Incineroar", "Flutter Mane", "Raging Bolt")

        assert result["core"] == ["Incineroar", "Flutter Mane", "Raging Bolt"]


class TestGetTeamDatabaseStats:
    """Tests for get_team_database_stats tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teams import register_team_tools

        mcp = MockFastMCP()
        register_team_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teams.get_format")
    @patch("smogon_vgc_mcp.tools.teams.get_team_count")
    async def test_returns_stats(self, mock_count, mock_format, mock_mcp):
        """Test returning database stats."""
        mock_count.return_value = 500

        mock_fmt = MagicMock()
        mock_fmt.name = "Regulation F"
        mock_format.return_value = mock_fmt

        get_team_database_stats = mock_mcp.tools["get_team_database_stats"]
        result = await get_team_database_stats(format="regf")

        assert result["total_teams"] == 500
        assert "VGC Pastes Repository" in result["source"]
