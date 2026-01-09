"""Tests for tools/replay.py - Replay analysis tools."""

from unittest.mock import patch

import pytest

from smogon_vgc_mcp.parser.replay import (
    DamageEvent,
    FaintEvent,
    MoveEvent,
    Player,
    Pokemon,
    Replay,
    Team,
    TeraEvent,
    Turn,
)
from smogon_vgc_mcp.utils import ValidationError


class MockFastMCP:
    """Mock FastMCP to capture registered tools."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def make_sample_replay(
    winner: str | None = "Player1",
    p1_team: list[Pokemon] | None = None,
    p2_team: list[Pokemon] | None = None,
    turns: list[Turn] | None = None,
    p1_rating: int | None = 1500,
    p2_rating: int | None = 1400,
) -> Replay:
    """Create a sample Replay object for testing."""
    if p1_team is None:
        p1_team = [
            Pokemon(
                species="Incineroar",
                item="Safety Goggles",
                ability="Intimidate",
                tera_type="Ghost",
                moves=["Fake Out", "Flare Blitz"],
            ),
            Pokemon(
                species="Flutter Mane",
                item="Booster Energy",
                ability="Protosynthesis",
                tera_type="Fairy",
                moves=["Moonblast", "Shadow Ball"],
            ),
        ]
    if p2_team is None:
        p2_team = [
            Pokemon(
                species="Urshifu-Rapid-Strike",
                item="Choice Band",
                ability="Unseen Fist",
                tera_type="Water",
                moves=["Surging Strikes"],
            ),
            Pokemon(
                species="Rillaboom",
                item="Assault Vest",
                ability="Grassy Surge",
                tera_type="Grass",
                moves=["Grassy Glide"],
            ),
        ]
    if turns is None:
        turns = [
            Turn(
                number=1,
                events=[
                    MoveEvent(
                        turn=1,
                        user="p1",
                        user_species="Incineroar",
                        move="Fake Out",
                        target="p2",
                        target_species="Urshifu-Rapid-Strike",
                    ),
                ],
            ),
        ]

    return Replay(
        replay_id="gen9vgc2026regf-123456",
        format="[Gen 9] VGC 2026 Reg F",
        player1=Player(
            name="Player1",
            player_id="p1",
            rating=p1_rating,
            team=Team(pokemon=p1_team),
            brought=["Incineroar", "Flutter Mane"],
        ),
        player2=Player(
            name="Player2",
            player_id="p2",
            rating=p2_rating,
            team=Team(pokemon=p2_team),
            brought=["Urshifu-Rapid-Strike", "Rillaboom"],
        ),
        turns=turns,
        winner=winner,
    )


class TestAnalyzeReplay:
    """Tests for analyze_replay tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.replay import register_replay_tools

        mcp = MockFastMCP()
        register_replay_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_returns_replay_analysis(self, mock_validate, mock_fetch, mock_mcp):
        """Test valid URL returns full analysis."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay()

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert "error" not in result
        assert result["replay_id"] == "gen9vgc2026regf-123456"
        assert result["format"] == "[Gen 9] VGC 2026 Reg F"
        assert result["winner"] == "Player1"
        assert result["turn_count"] == 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_formats_team_correctly(self, mock_validate, mock_fetch, mock_mcp):
        """Test team has species, item, ability, tera, moves."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay()

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        team = result["player1"]["team"]
        assert len(team) == 2
        assert team[0]["species"] == "Incineroar"
        assert team[0]["item"] == "Safety Goggles"
        assert team[0]["ability"] == "Intimidate"
        assert team[0]["tera_type"] == "Ghost"
        assert team[0]["moves"] == ["Fake Out", "Flare Blitz"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_includes_player_ratings(self, mock_validate, mock_fetch, mock_mcp):
        """Test ratings included when present."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay(p1_rating=1650, p2_rating=1580)

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["player1"]["rating"] == 1650
        assert result["player2"]["rating"] == 1580

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_includes_leads(self, mock_validate, mock_fetch, mock_mcp):
        """Test lead Pokemon extracted."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay()

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["player1"]["leads"] == ["Incineroar", "Flutter Mane"]
        assert result["player2"]["leads"] == ["Urshifu-Rapid-Strike", "Rillaboom"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_handles_null_moves(self, mock_validate, mock_fetch, mock_mcp):
        """Test Pokemon with no revealed moves."""
        p1_team = [Pokemon(species="Incineroar", moves=[])]
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay(p1_team=p1_team)

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["player1"]["team"][0]["moves"] is None

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_empty_team(self, mock_validate, mock_fetch, mock_mcp):
        """Test empty team returns empty list."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay(p1_team=[])

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["player1"]["team"] == []

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_no_winner(self, mock_validate, mock_fetch, mock_mcp):
        """Test incomplete replay (winner=None)."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay(winner=None)

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["winner"] is None

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_validation_error_returns_error(self, mock_validate, mock_mcp):
        """Test invalid URL format returns error."""
        mock_validate.side_effect = ValidationError(
            "Invalid replay URL", hint="URL must start with https://replay.pokemonshowdown.com/"
        )

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(url="https://invalid.com/replay")

        assert "error" in result
        assert "hint" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_fetch_error_returns_error(self, mock_validate, mock_fetch, mock_mcp):
        """Test network/fetch failure returns error."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.side_effect = Exception("Connection failed")

        analyze_replay = mock_mcp.tools["analyze_replay"]
        result = await analyze_replay(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert "error" in result
        assert "hint" in result
        assert "valid and accessible" in result["hint"]


class TestGetDamageObservations:
    """Tests for get_damage_observations tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.replay import register_replay_tools

        mcp = MockFastMCP()
        register_replay_tools(mcp)
        return mcp

    def make_replay_with_damage(
        self, damage_events: list[tuple[str, str, str, float, str | None, bool]] | None = None
    ) -> Replay:
        """Create replay with specific damage events."""
        if damage_events is None:
            damage_events = [
                ("Incineroar", "Urshifu-Rapid-Strike", "Fake Out", 15.0, None, False),
                ("Flutter Mane", "Rillaboom", "Moonblast", 85.0, "super effective", False),
            ]

        turns = []
        for i, (attacker, defender, move, damage, effectiveness, crit) in enumerate(damage_events):
            event = MoveEvent(
                turn=i + 1,
                user="p1",
                user_species=attacker,
                move=move,
                target="p2",
                target_species=defender,
                damage=DamageEvent(hp_remaining=int(100 - damage), max_hp=100, damage_dealt=damage),
                effectiveness=effectiveness,
                critical_hit=crit,
            )
            turns.append(Turn(number=i + 1, events=[event]))

        return make_sample_replay(turns=turns)

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_returns_damage_observations(self, mock_validate, mock_fetch, mock_mcp):
        """Test returns damage events list."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_damage()

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert "error" not in result
        assert result["observation_count"] == 2
        assert len(result["observations"]) == 2

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_filters_by_min_damage(self, mock_validate, mock_fetch, mock_mcp):
        """Test min_damage filters correctly."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_damage(
            [
                ("Incineroar", "Urshifu", "Fake Out", 15.0, None, False),
                ("Flutter Mane", "Rillaboom", "Moonblast", 85.0, "super effective", False),
            ]
        )

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456", min_damage=50.0
        )

        assert result["observation_count"] == 1
        assert result["observations"][0]["damage_percent"] == 85.0

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_includes_effectiveness(self, mock_validate, mock_fetch, mock_mcp):
        """Test effectiveness field present."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_damage(
            [
                ("Flutter Mane", "Rillaboom", "Moonblast", 85.0, "super effective", False),
            ]
        )

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["observations"][0]["effectiveness"] == "super effective"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_includes_critical_hits(self, mock_validate, mock_fetch, mock_mcp):
        """Test critical hit flag works."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_damage(
            [
                ("Flutter Mane", "Incineroar", "Moonblast", 120.0, "super effective", True),
            ]
        )

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["observations"][0]["critical_hit"] is True

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_min_damage_zero_returns_all(self, mock_validate, mock_fetch, mock_mcp):
        """Test default returns all damage events."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_damage(
            [
                ("Incineroar", "Urshifu", "Fake Out", 5.0, None, False),
                ("Flutter Mane", "Rillaboom", "Moonblast", 85.0, None, False),
            ]
        )

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456", min_damage=0.0
        )

        assert result["observation_count"] == 2

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_no_damage_events(self, mock_validate, mock_fetch, mock_mcp):
        """Test empty observations list."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = make_sample_replay(turns=[Turn(number=1, events=[])])

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["observations"] == []
        assert result["observation_count"] == 0

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_validation_error_returns_error(self, mock_validate, mock_mcp):
        """Test invalid URL returns error."""
        mock_validate.side_effect = ValidationError("Invalid replay URL", hint="Check URL format")

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(url="invalid")

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_fetch_failure_returns_error(self, mock_validate, mock_fetch, mock_mcp):
        """Test network failure returns error."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.side_effect = Exception("Network error")

        get_damage_observations = mock_mcp.tools["get_damage_observations"]
        result = await get_damage_observations(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert "error" in result
        assert "hint" in result


class TestGetBattleSummary:
    """Tests for get_battle_summary tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.replay import register_replay_tools

        mcp = MockFastMCP()
        register_replay_tools(mcp)
        return mcp

    def make_replay_with_events(
        self,
        tera_events: list[tuple[str, str, str, int]] | None = None,
        faint_events: list[tuple[str, str, int]] | None = None,
    ) -> Replay:
        """Create replay with specific Tera and faint events."""
        turns = []

        if tera_events:
            for player, species, tera_type, turn_num in tera_events:
                event = TeraEvent(
                    turn=turn_num, player=player, species=species, tera_type=tera_type
                )
                existing = next((t for t in turns if t.number == turn_num), None)
                if existing:
                    existing.events.append(event)
                else:
                    turns.append(Turn(number=turn_num, events=[event]))

        if faint_events:
            for player, species, turn_num in faint_events:
                event = FaintEvent(turn=turn_num, player=player, species=species)
                existing = next((t for t in turns if t.number == turn_num), None)
                if existing:
                    existing.events.append(event)
                else:
                    turns.append(Turn(number=turn_num, events=[event]))

        turns.sort(key=lambda t: t.number)
        return make_sample_replay(turns=turns if turns else [Turn(number=1, events=[])])

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_returns_battle_summary(self, mock_validate, mock_fetch, mock_mcp):
        """Test full summary structure."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_events()

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert "error" not in result
        assert result["replay_id"] == "gen9vgc2026regf-123456"
        assert result["format"] == "[Gen 9] VGC 2026 Reg F"
        assert result["winner"] == "Player1"
        assert "players" in result
        assert "tera_usage" in result
        assert "ko_count" in result
        assert "key_kos" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_includes_tera_usage(self, mock_validate, mock_fetch, mock_mcp):
        """Test both players' Tera captured."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_events(
            tera_events=[
                ("p1", "Incineroar", "Ghost", 2),
                ("p2", "Urshifu-Rapid-Strike", "Water", 3),
            ]
        )

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["tera_usage"]["p1"]["species"] == "Incineroar"
        assert result["tera_usage"]["p1"]["tera_type"] == "Ghost"
        assert result["tera_usage"]["p1"]["turn"] == 2
        assert result["tera_usage"]["p2"]["species"] == "Urshifu-Rapid-Strike"
        assert result["tera_usage"]["p2"]["tera_type"] == "Water"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_includes_ko_counts(self, mock_validate, mock_fetch, mock_mcp):
        """Test KO counts calculated."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_events(
            faint_events=[
                ("p2", "Urshifu", 3),
                ("p2", "Rillaboom", 5),
                ("p1", "Flutter Mane", 4),
            ]
        )

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["ko_count"]["p1"] == 2
        assert result["ko_count"]["p2"] == 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_includes_key_kos(self, mock_validate, mock_fetch, mock_mcp):
        """Test faint events listed."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_events(
            faint_events=[
                ("p2", "Urshifu", 3),
                ("p1", "Flutter Mane", 4),
            ]
        )

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert len(result["key_kos"]) == 2
        assert result["key_kos"][0]["turn"] == 3
        assert result["key_kos"][0]["pokemon"] == "Urshifu"
        assert result["key_kos"][0]["player"] == "p2"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_no_tera_usage(self, mock_validate, mock_fetch, mock_mcp):
        """Test handles no Terastallization."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_events(tera_events=[])

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["tera_usage"]["p1"] is None
        assert result["tera_usage"]["p2"] is None

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_no_faints(self, mock_validate, mock_fetch, mock_mcp):
        """Test no knockouts."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.return_value = self.make_replay_with_events(faint_events=[])

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert result["key_kos"] == []
        assert result["ko_count"]["p1"] == 0
        assert result["ko_count"]["p2"] == 0

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_validation_error_returns_error(self, mock_validate, mock_mcp):
        """Test invalid URL returns error."""
        mock_validate.side_effect = ValidationError("Invalid URL", hint="Check format")

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(url="invalid")

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.replay.fetch_and_parse_replay")
    @patch("smogon_vgc_mcp.tools.replay.validate_replay_url")
    async def test_generic_exception_returns_error(self, mock_validate, mock_fetch, mock_mcp):
        """Test fetch failure returns error."""
        mock_validate.return_value = "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        mock_fetch.side_effect = Exception("Unexpected error")

        get_battle_summary = mock_mcp.tools["get_battle_summary"]
        result = await get_battle_summary(
            url="https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        )

        assert "error" in result
        assert "hint" in result
