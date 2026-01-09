"""Tests for Pokemon Showdown replay parser."""

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
    parse_replay,
)


class TestPokemonModel:
    """Tests for Pokemon data model."""

    def test_basic_pokemon(self):
        """Test basic Pokemon creation."""
        mon = Pokemon(species="Incineroar", item="Sitrus Berry", ability="Intimidate")
        assert mon.species == "Incineroar"
        assert mon.item == "Sitrus Berry"
        assert mon.ability == "Intimidate"
        assert mon.level == 50

    def test_base_species_simple(self):
        """Test base_species for simple Pokemon."""
        mon = Pokemon(species="Incineroar")
        assert mon.base_species == "Incineroar"

    def test_base_species_forme(self):
        """Test base_species for forme Pokemon."""
        mon = Pokemon(species="Urshifu-Rapid-Strike")
        assert mon.base_species == "Urshifu"

    def test_base_species_exceptions(self):
        """Test base_species preserves hyphenated names."""
        mon = Pokemon(species="Ho-Oh")
        assert mon.base_species == "Ho-Oh"

        mon2 = Pokemon(species="Porygon-Z")
        assert mon2.base_species == "Porygon-Z"


class TestTeamModel:
    """Tests for Team data model."""

    def test_get_pokemon_exact_match(self):
        """Test finding Pokemon by exact name."""
        team = Team(
            pokemon=[
                Pokemon(species="Incineroar"),
                Pokemon(species="Flutter Mane"),
            ]
        )
        mon = team.get_pokemon("Incineroar")
        assert mon is not None
        assert mon.species == "Incineroar"

    def test_get_pokemon_case_insensitive(self):
        """Test finding Pokemon is case-insensitive."""
        team = Team(pokemon=[Pokemon(species="Incineroar")])
        assert team.get_pokemon("incineroar") is not None
        assert team.get_pokemon("INCINEROAR") is not None

    def test_get_pokemon_not_found(self):
        """Test None returned when Pokemon not found."""
        team = Team(pokemon=[Pokemon(species="Incineroar")])
        assert team.get_pokemon("Charizard") is None

    def test_team_length(self):
        """Test team length."""
        team = Team(pokemon=[Pokemon(species="A"), Pokemon(species="B")])
        assert len(team) == 2


class TestDamageEvent:
    """Tests for DamageEvent data model."""

    def test_hp_percent(self):
        """Test HP percentage calculation."""
        event = DamageEvent(hp_remaining=75, max_hp=150, damage_dealt=50.0)
        assert event.hp_percent == 50.0

    def test_hp_percent_zero_max(self):
        """Test HP percentage with zero max HP."""
        event = DamageEvent(hp_remaining=0, max_hp=0, damage_dealt=0)
        assert event.hp_percent == 0


class TestTurn:
    """Tests for Turn data model."""

    def test_moves_filter(self):
        """Test filtering move events."""
        turn = Turn(
            number=1,
            events=[
                MoveEvent(turn=1, user="p1", user_species="Incineroar", move="Fake Out"),
                TeraEvent(turn=1, player="p1", species="Incineroar", tera_type="Ghost"),
                MoveEvent(turn=1, user="p2", user_species="Flutter Mane", move="Moonblast"),
            ],
        )
        assert len(turn.moves) == 2
        assert turn.moves[0].move == "Fake Out"

    def test_teras_filter(self):
        """Test filtering tera events."""
        turn = Turn(
            number=1,
            events=[
                MoveEvent(turn=1, user="p1", user_species="Incineroar", move="Fake Out"),
                TeraEvent(turn=1, player="p1", species="Incineroar", tera_type="Ghost"),
            ],
        )
        assert len(turn.teras) == 1
        assert turn.teras[0].tera_type == "Ghost"

    def test_faints_filter(self):
        """Test filtering faint events."""
        turn = Turn(
            number=5,
            events=[
                FaintEvent(turn=5, player="p2", species="Flutter Mane"),
            ],
        )
        assert len(turn.faints) == 1
        assert turn.faints[0].species == "Flutter Mane"


class TestReplay:
    """Tests for Replay data model."""

    def test_get_lead_pokemon(self):
        """Test getting lead Pokemon."""
        replay = Replay(
            replay_id="test",
            format="gen9vgc2026regf",
            player1=Player(
                name="Player1",
                player_id="p1",
                brought=["Incineroar", "Flutter Mane", "Rillaboom"],
            ),
            player2=Player(
                name="Player2",
                player_id="p2",
                brought=["Urshifu", "Amoonguss"],
            ),
        )
        assert replay.get_lead_pokemon("p1") == ["Incineroar", "Flutter Mane"]
        assert replay.get_lead_pokemon("p2") == ["Urshifu", "Amoonguss"]

    def test_get_all_damage_events(self):
        """Test getting all damage events."""
        damage = DamageEvent(hp_remaining=50, max_hp=100, damage_dealt=50.0)
        replay = Replay(
            replay_id="test",
            format="gen9vgc2026regf",
            player1=Player(name="P1", player_id="p1"),
            player2=Player(name="P2", player_id="p2"),
            turns=[
                Turn(
                    number=1,
                    events=[
                        MoveEvent(
                            turn=1,
                            user="p1",
                            user_species="Incineroar",
                            move="Fake Out",
                            damage=damage,
                        ),
                        MoveEvent(
                            turn=1,
                            user="p2",
                            user_species="Flutter Mane",
                            move="Protect",
                        ),
                    ],
                ),
            ],
        )
        damage_events = replay.get_all_damage_events()
        assert len(damage_events) == 1
        assert damage_events[0].move == "Fake Out"

    def test_get_tera_usage(self):
        """Test getting Tera usage."""
        replay = Replay(
            replay_id="test",
            format="gen9vgc2026regf",
            player1=Player(name="P1", player_id="p1"),
            player2=Player(name="P2", player_id="p2"),
            turns=[
                Turn(
                    number=2,
                    events=[
                        TeraEvent(turn=2, player="p1", species="Incineroar", tera_type="Ghost"),
                    ],
                ),
                Turn(
                    number=3,
                    events=[
                        TeraEvent(turn=3, player="p2", species="Flutter Mane", tera_type="Fairy"),
                    ],
                ),
            ],
        )
        tera = replay.get_tera_usage()
        assert tera["p1"] is not None
        assert tera["p1"].tera_type == "Ghost"
        assert tera["p2"] is not None
        assert tera["p2"].tera_type == "Fairy"

    def test_get_ko_count(self):
        """Test getting KO counts."""
        replay = Replay(
            replay_id="test",
            format="gen9vgc2026regf",
            player1=Player(name="P1", player_id="p1"),
            player2=Player(name="P2", player_id="p2"),
            turns=[
                Turn(number=3, events=[FaintEvent(turn=3, player="p2", species="Flutter Mane")]),
                Turn(number=5, events=[FaintEvent(turn=5, player="p2", species="Rillaboom")]),
                Turn(number=6, events=[FaintEvent(turn=6, player="p1", species="Incineroar")]),
            ],
        )
        kos = replay.get_ko_count()
        assert kos["p1"] == 2
        assert kos["p2"] == 1


class TestParseReplay:
    """Tests for replay parsing."""

    def test_parse_player_info(self):
        """Test parsing player information."""
        log = """|player|p1|TestPlayer1|avatar|1500
|player|p2|TestPlayer2|avatar|1600
|teamsize|p1|6
|teamsize|p2|6
|gametype|doubles
|gen|9
|tier|[Gen 9] VGC 2026 Reg F
"""
        replay = parse_replay(log, "test-123")
        assert replay.player1.name == "TestPlayer1"
        assert replay.player1.rating == 1500
        assert replay.player2.name == "TestPlayer2"
        assert replay.player2.rating == 1600
        assert replay.format == "[Gen 9] VGC 2026 Reg F"

    def test_parse_team_preview(self):
        """Test parsing team preview."""
        log = """|player|p1|Player1|avatar|1500
|player|p2|Player2|avatar|1500
|poke|p1|Incineroar, L50, M
|poke|p1|Flutter Mane, L50
|poke|p2|Urshifu-Rapid-Strike, L50, M
|poke|p2|Amoonguss, L50, F
"""
        replay = parse_replay(log, "test")
        assert len(replay.player1.team) == 2
        assert replay.player1.team.pokemon[0].species == "Incineroar"
        assert replay.player1.team.pokemon[1].species == "Flutter Mane"
        assert len(replay.player2.team) == 2
        assert replay.player2.team.pokemon[0].species == "Urshifu-Rapid-Strike"

    def test_parse_switch_and_leads(self):
        """Test parsing switches and leads."""
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|poke|p1|Incineroar, L50
|poke|p1|Flutter Mane, L50
|poke|p2|Urshifu, L50
|poke|p2|Amoonguss, L50
|switch|p1a: Incineroar|Incineroar, L50, M|100/100
|switch|p1b: Flutter Mane|Flutter Mane, L50|100/100
|switch|p2a: Urshifu|Urshifu, L50, M|100/100
|switch|p2b: Amoonguss|Amoonguss, L50, F|100/100
"""
        replay = parse_replay(log, "test")
        assert replay.player1.brought == ["Incineroar", "Flutter Mane"]
        assert replay.player2.brought == ["Urshifu", "Amoonguss"]

    def test_parse_moves(self):
        """Test parsing move usage."""
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|poke|p1|Incineroar, L50
|poke|p2|Flutter Mane, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|switch|p2a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|move|p1a: Incineroar|Fake Out|p2a: Flutter Mane
|-damage|p2a: Flutter Mane|85/100
"""
        replay = parse_replay(log, "test")
        assert len(replay.turns) == 1
        assert len(replay.turns[0].moves) == 1
        move = replay.turns[0].moves[0]
        assert move.move == "Fake Out"
        assert move.user_species == "Incineroar"
        assert move.damage is not None
        assert move.damage.damage_dealt == 15.0

    def test_parse_terastallization(self):
        """Test parsing Terastallization."""
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|poke|p1|Incineroar, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|turn|1
|-terastallize|p1a: Incineroar|Ghost
"""
        replay = parse_replay(log, "test")
        assert len(replay.turns[0].teras) == 1
        tera = replay.turns[0].teras[0]
        assert tera.species == "Incineroar"
        assert tera.tera_type == "Ghost"
        assert replay.player1.team.pokemon[0].tera_type == "Ghost"

    def test_parse_faint(self):
        """Test parsing faints."""
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|poke|p2|Flutter Mane, L50
|switch|p2a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|faint|p2a: Flutter Mane
"""
        replay = parse_replay(log, "test")
        assert len(replay.turns[0].faints) == 1
        faint = replay.turns[0].faints[0]
        assert faint.species == "Flutter Mane"
        assert faint.player == "p2"

    def test_parse_effectiveness(self):
        """Test parsing type effectiveness."""
        log = """|player|p1|Player1|avatar
|poke|p1|Incineroar, L50
|poke|p2|Amoonguss, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|switch|p2a: Amoonguss|Amoonguss, L50|100/100
|turn|1
|move|p1a: Incineroar|Flare Blitz|p2a: Amoonguss
|-supereffective|p2a: Amoonguss
|-damage|p2a: Amoonguss|10/100
"""
        replay = parse_replay(log, "test")
        move = replay.turns[0].moves[0]
        assert move.effectiveness == "super effective"

    def test_parse_critical_hit(self):
        """Test parsing critical hits."""
        log = """|player|p1|Player1|avatar
|poke|p1|Incineroar, L50
|poke|p2|Flutter Mane, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|switch|p2a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|move|p1a: Incineroar|Knock Off|p2a: Flutter Mane
|-crit|p2a: Flutter Mane
|-damage|p2a: Flutter Mane|50/100
"""
        replay = parse_replay(log, "test")
        move = replay.turns[0].moves[0]
        assert move.critical_hit is True

    def test_parse_winner(self):
        """Test parsing winner."""
        log = """|player|p1|Winner|avatar
|player|p2|Loser|avatar
|win|Winner
"""
        replay = parse_replay(log, "test")
        assert replay.winner == "Winner"

    def test_parse_item_reveal(self):
        """Test parsing revealed items."""
        log = """|player|p1|Player1|avatar
|poke|p1|Incineroar, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|turn|1
|-item|p1a: Incineroar|Sitrus Berry|[from] ability: Frisk
"""
        replay = parse_replay(log, "test")
        assert replay.player1.team.pokemon[0].item == "Sitrus Berry"

    def test_parse_ability_reveal(self):
        """Test parsing revealed abilities."""
        log = """|player|p1|Player1|avatar
|poke|p1|Incineroar, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|turn|1
|-ability|p1a: Incineroar|Intimidate|boost
"""
        replay = parse_replay(log, "test")
        assert replay.player1.team.pokemon[0].ability == "Intimidate"

    def test_moves_added_to_pokemon(self):
        """Test that revealed moves are added to Pokemon."""
        log = """|player|p1|Player1|avatar
|poke|p1|Incineroar, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|turn|1
|move|p1a: Incineroar|Fake Out|p2a: Target
|turn|2
|move|p1a: Incineroar|Flare Blitz|p2a: Target
"""
        replay = parse_replay(log, "test")
        mon = replay.player1.team.pokemon[0]
        assert "Fake Out" in mon.moves
        assert "Flare Blitz" in mon.moves
