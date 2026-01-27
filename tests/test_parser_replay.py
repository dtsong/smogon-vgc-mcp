"""Tests for Pokemon Showdown replay parser."""

from smogon_vgc_mcp.parser.replay import (
    Bo3Info,
    BoostEvent,
    DamageEvent,
    FaintEvent,
    FieldEvent,
    HealEvent,
    MoveEvent,
    Player,
    Pokemon,
    Replay,
    StatSpread,
    StatusEvent,
    Team,
    TeraEvent,
    Turn,
    WeatherEvent,
    extract_log_from_html,
    extract_replay_id,
    extract_replay_id_from_html,
    normalize_replay_url,
    parse_replay,
    parse_showteam,
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


class TestStatSpread:
    def test_defaults(self):
        spread = StatSpread()
        assert spread.hp == 0
        assert spread.spe == 0

    def test_as_dict(self):
        spread = StatSpread(hp=252, def_=4, spd=252)
        d = spread.as_dict()
        assert d["hp"] == 252
        assert d["def_"] == 4
        assert d["atk"] == 0


class TestShowteamParsing:
    def test_parse_full_pokemon(self):
        packed = "Incineroar||Sitrus Berry|Intimidate|Fake Out,Flare Blitz,Parting Shot,Knock Off|Careful|252,0,4,0,252,0|M|31,31,31,31,31,31||50|,,,,,Dark"
        pokemon = parse_showteam(packed)
        assert len(pokemon) == 1
        mon = pokemon[0]
        assert mon.species == "Incineroar"
        assert mon.item == "Sitrus Berry"
        assert mon.ability == "Intimidate"
        assert mon.nature == "Careful"
        assert mon.moves == ["Fake Out", "Flare Blitz", "Parting Shot", "Knock Off"]
        assert mon.evs is not None
        assert mon.evs.hp == 252
        assert mon.evs.def_ == 4
        assert mon.evs.spd == 252
        assert mon.evs.atk == 0
        assert mon.ivs is not None
        assert mon.ivs.hp == 31
        assert mon.gender == "M"
        assert mon.level == 50
        assert mon.tera_type == "Dark"

    def test_parse_minimal_pokemon(self):
        packed = "Raging Bolt||Leftovers|Protosynthesis|Protect,CalmMind,DragonPulse,Thunderclap||||||50|,,,,,Fairy"
        pokemon = parse_showteam(packed)
        assert len(pokemon) == 1
        mon = pokemon[0]
        assert mon.species == "Raging Bolt"
        assert mon.item == "Leftovers"
        assert mon.ability == "Protosynthesis"
        assert mon.nature is None
        assert mon.evs is None
        assert mon.tera_type == "Fairy"
        assert mon.level == 50

    def test_parse_nicknamed_pokemon(self):
        packed = "Rocky|Incineroar|Sitrus Berry|Intimidate|Fake Out|||M|||50|,,,,,Dark"
        pokemon = parse_showteam(packed)
        assert len(pokemon) == 1
        mon = pokemon[0]
        assert mon.species == "Incineroar"
        assert mon.nickname == "Rocky"

    def test_parse_multiple_pokemon(self):
        packed = "Incineroar||Sitrus Berry|Intimidate|Fake Out||||||50|,,,,,Dark]Flutter Mane||Booster Energy|Protosynthesis|Moonblast||||||50|,,,,,Fairy"
        pokemon = parse_showteam(packed)
        assert len(pokemon) == 2
        assert pokemon[0].species == "Incineroar"
        assert pokemon[1].species == "Flutter Mane"

    def test_parse_shiny_pokemon(self):
        packed = "Incineroar||Sitrus Berry|Intimidate|Fake Out|||||S|50|"
        pokemon = parse_showteam(packed)
        assert len(pokemon) == 1
        assert pokemon[0].shiny is True

    def test_empty_showteam(self):
        assert parse_showteam("") == []
        assert parse_showteam("  ") == []


class TestShowteamIntegration:
    def test_showteam_merged_into_team(self):
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|poke|p1|Incineroar, L50, M
|poke|p1|Flutter Mane, L50
|showteam|p1|Incineroar||Sitrus Berry|Intimidate|Fake Out,Flare Blitz,Parting Shot,Knock Off|Careful|252,0,4,0,252,0|M|31,31,31,31,31,31||50|,,,,,Dark]Flutter Mane||Booster Energy|Protosynthesis|Moonblast,Shadow Ball,Dazzling Gleam,Protect|Timid|4,0,0,252,0,252||31,31,31,31,31,31||50|,,,,,Fairy
"""
        replay = parse_replay(log, "test")
        incin = replay.player1.team.get_pokemon("Incineroar")
        assert incin is not None
        assert incin.item == "Sitrus Berry"
        assert incin.ability == "Intimidate"
        assert incin.nature == "Careful"
        assert incin.evs is not None
        assert incin.evs.hp == 252
        assert incin.tera_type == "Dark"
        assert incin.moves == ["Fake Out", "Flare Blitz", "Parting Shot", "Knock Off"]

        flutter = replay.player1.team.get_pokemon("Flutter Mane")
        assert flutter is not None
        assert flutter.ability == "Protosynthesis"
        assert flutter.tera_type == "Fairy"


class TestHealEvent:
    def test_parse_heal(self):
        log = """|player|p1|Player1|avatar
|poke|p1|Incineroar, L50
|switch|p1a: Incineroar|Incineroar, L50|50/100
|turn|1
|-heal|p1a: Incineroar|62/100|[from] item: Sitrus Berry
"""
        replay = parse_replay(log, "test")
        heal_events = [e for e in replay.turns[0].events if isinstance(e, HealEvent)]
        assert len(heal_events) == 1
        assert heal_events[0].species == "Incineroar"
        assert heal_events[0].hp_remaining == 62
        assert heal_events[0].source == "[from] item: Sitrus Berry"


class TestBoostEvents:
    def test_parse_boost(self):
        log = """|player|p1|Player1|avatar
|poke|p1|Flutter Mane, L50
|switch|p1a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|-boost|p1a: Flutter Mane|spa|1
"""
        replay = parse_replay(log, "test")
        boost_events = replay.turns[0].boosts
        assert len(boost_events) == 1
        assert boost_events[0].stat == "spa"
        assert boost_events[0].stages == 1

    def test_parse_unboost(self):
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|poke|p1|Incineroar, L50
|poke|p2|Flutter Mane, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|switch|p2a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|-ability|p1a: Incineroar|Intimidate|boost
|-unboost|p2a: Flutter Mane|atk|1
"""
        replay = parse_replay(log, "test")
        boost_events = replay.turns[0].boosts
        assert len(boost_events) == 1
        assert boost_events[0].stat == "atk"
        assert boost_events[0].stages == -1

    def test_boost_tracking_in_state(self):
        log = """|player|p1|Player1|avatar
|poke|p1|Flutter Mane, L50
|switch|p1a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|-boost|p1a: Flutter Mane|spa|1
|turn|2
|-boost|p1a: Flutter Mane|spa|1
"""
        replay = parse_replay(log, "test")
        state = replay.battle_state.active.get("p1a: Flutter Mane")
        assert state is not None
        assert state.boosts.get("spa") == 2


class TestStatusEvents:
    def test_parse_status(self):
        log = """|player|p1|Player1|avatar
|poke|p2|Incineroar, L50
|switch|p2a: Incineroar|Incineroar, L50|100/100
|turn|1
|-status|p2a: Incineroar|brn
"""
        replay = parse_replay(log, "test")
        status_events = replay.turns[0].statuses
        assert len(status_events) == 1
        assert status_events[0].status == "brn"
        assert status_events[0].cured is False

    def test_parse_cure_status(self):
        log = """|player|p1|Player1|avatar
|poke|p2|Incineroar, L50
|switch|p2a: Incineroar|Incineroar, L50|100/100
|turn|1
|-status|p2a: Incineroar|brn
|turn|2
|-curestatus|p2a: Incineroar|brn
"""
        replay = parse_replay(log, "test")
        status_events = replay.turns[1].statuses
        assert len(status_events) == 1
        assert status_events[0].cured is True


class TestWeatherEvents:
    def test_parse_weather(self):
        log = """|player|p1|Player1|avatar
|turn|1
|-weather|SunnyDay|[from] ability: Drought|[of] p1a: Torkoal
"""
        replay = parse_replay(log, "test")
        weather_events = [e for e in replay.turns[0].events if isinstance(e, WeatherEvent)]
        assert len(weather_events) == 1
        assert weather_events[0].weather == "SunnyDay"
        assert replay.battle_state.field.weather == "SunnyDay"

    def test_weather_none(self):
        log = """|player|p1|Player1|avatar
|turn|1
|-weather|SunnyDay
|turn|2
|-weather|none
"""
        replay = parse_replay(log, "test")
        assert replay.battle_state.field.weather is None


class TestFieldEvents:
    def test_parse_trick_room(self):
        log = """|player|p1|Player1|avatar
|turn|1
|-fieldstart|move: Trick Room
"""
        replay = parse_replay(log, "test")
        field_events = [e for e in replay.turns[0].events if isinstance(e, FieldEvent)]
        assert len(field_events) == 1
        assert field_events[0].started is True
        assert "Trick Room" in field_events[0].effect
        assert replay.battle_state.field.trick_room is True

    def test_trick_room_end(self):
        log = """|player|p1|Player1|avatar
|turn|1
|-fieldstart|move: Trick Room
|turn|5
|-fieldend|move: Trick Room
"""
        replay = parse_replay(log, "test")
        assert replay.battle_state.field.trick_room is False

    def test_parse_terrain(self):
        log = """|player|p1|Player1|avatar
|turn|1
|-fieldstart|move: Grassy Terrain|[from] ability: Grassy Surge|[of] p1a: Rillaboom
"""
        replay = parse_replay(log, "test")
        assert replay.battle_state.field.terrain == "Grassy Terrain"


class TestBattleState:
    def test_hp_tracking(self):
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
        state = replay.battle_state.active["p2a: Flutter Mane"]
        assert state.hp_current == 85
        assert state.hp_max == 100

    def test_faint_sets_hp_zero(self):
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|poke|p2|Flutter Mane, L50
|switch|p2a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|faint|p2a: Flutter Mane
"""
        replay = parse_replay(log, "test")
        state = replay.battle_state.active["p2a: Flutter Mane"]
        assert state.hp_current == 0


class TestReplayMetadata:
    def test_generation(self):
        log = """|gen|9
|tier|[Gen 9] VGC 2026 Reg F
"""
        replay = parse_replay(log)
        assert replay.generation == 9

    def test_rated(self):
        log = """|rated|
"""
        replay = parse_replay(log)
        assert replay.is_rated is True

    def test_rules(self):
        log = """|rule|Species Clause: Limit one of each Pokémon
|rule|Item Clause: Limit one of each item
"""
        replay = parse_replay(log)
        assert len(replay.rules) == 2
        assert "Species Clause" in replay.rules[0]


class TestBo3Detection:
    def test_detect_bo3(self):
        log = """|player|p1|Player1|avatar
|player|p2|Player2|avatar
|uhtml|bestof|<h2><strong>Game 1</strong> of <a href="/game-bestof3-gen9vgc2026regfbo3-123456">a best-of-3</a></h2>
|turn|1
"""
        replay = parse_replay(log, "test")
        assert replay.bo3 is not None
        assert replay.bo3.game_number == 1
        assert replay.bo3.series_id == "gen9vgc2026regfbo3-123456"

    def test_detect_bo3_game2(self):
        log = """|uhtml|bestof|<h2><strong>Game 2</strong> of <a href="/game-bestof3-gen9vgc2026regfbo3-789">a best-of-3</a></h2>
"""
        replay = parse_replay(log)
        assert replay.bo3 is not None
        assert replay.bo3.game_number == 2

    def test_no_bo3(self):
        log = """|player|p1|Player1|avatar
|turn|1
"""
        replay = parse_replay(log)
        assert replay.bo3 is None

    def test_linked_games(self):
        log = """|uhtml|bestof|<h2><strong>Game 1</strong> of <a href="/game-bestof3-gen9vgc2026regfbo3-123">a best-of-3</a></h2>
|tempnotify|choice|Next game|/gen9vgc2026regfbo3-456
"""
        replay = parse_replay(log)
        assert replay.bo3 is not None
        assert "/gen9vgc2026regfbo3-456" in replay.bo3.linked_games


class TestHTMLExtraction:
    def test_extract_log_from_html(self):
        html = """<!DOCTYPE html>
<html>
<head><title>Test Replay</title></head>
<body>
<script type="text/plain" class="battle-log-data">
|player|p1|TestPlayer|avatar
|gen|9
|turn|1
</script>
</body>
</html>"""
        log = extract_log_from_html(html)
        assert log is not None
        assert "|player|p1|TestPlayer|avatar" in log
        assert "|gen|9" in log

    def test_extract_log_none_when_missing(self):
        html = "<html><body>No log here</body></html>"
        assert extract_log_from_html(html) is None

    def test_extract_replay_id_from_html(self):
        html = '<input type="hidden" name="replayid" value="gen9vgc2026regf-123456">'
        rid = extract_replay_id_from_html(html)
        assert rid == "gen9vgc2026regf-123456"

    def test_extract_replay_id_missing(self):
        assert extract_replay_id_from_html("<html></html>") is None


class TestURLNormalization:
    def test_strip_html_extension(self):
        assert normalize_replay_url("https://replay.pokemonshowdown.com/gen9vgc-123.html") == \
            "https://replay.pokemonshowdown.com/gen9vgc-123"

    def test_strip_json_extension(self):
        assert normalize_replay_url("https://replay.pokemonshowdown.com/gen9vgc-123.json") == \
            "https://replay.pokemonshowdown.com/gen9vgc-123"

    def test_strip_log_extension(self):
        assert normalize_replay_url("https://replay.pokemonshowdown.com/gen9vgc-123.log") == \
            "https://replay.pokemonshowdown.com/gen9vgc-123"

    def test_strip_player_suffix(self):
        assert normalize_replay_url("https://replay.pokemonshowdown.com/gen9vgc-123?p2") == \
            "https://replay.pokemonshowdown.com/gen9vgc-123"

    def test_bare_url_unchanged(self):
        url = "https://replay.pokemonshowdown.com/gen9vgc-123"
        assert normalize_replay_url(url) == url

    def test_extract_replay_id(self):
        assert extract_replay_id("https://replay.pokemonshowdown.com/gen9vgc2026regf-123456") == \
            "gen9vgc2026regf-123456"

    def test_extract_replay_id_with_extension(self):
        assert extract_replay_id("https://replay.pokemonshowdown.com/gen9vgc-123.html") == \
            "gen9vgc-123"

    def test_extract_replay_id_with_player_suffix(self):
        assert extract_replay_id("https://replay.pokemonshowdown.com/gen9vgc-123?p1") == \
            "gen9vgc-123"


class TestFailEvent:
    def test_fail_marks_move_missed(self):
        log = """|player|p1|Player1|avatar
|poke|p1|Incineroar, L50
|switch|p1a: Incineroar|Incineroar, L50|100/100
|turn|1
|move|p1a: Incineroar|Fake Out|p2a: Target
|-fail|p2a: Target
"""
        replay = parse_replay(log, "test")
        move = replay.turns[0].moves[0]
        assert move.missed is True


class TestSwitchResetsBoosts:
    def test_switch_clears_boosts(self):
        log = """|player|p1|Player1|avatar
|poke|p1|Flutter Mane, L50
|poke|p1|Incineroar, L50
|switch|p1a: Flutter Mane|Flutter Mane, L50|100/100
|turn|1
|-boost|p1a: Flutter Mane|spa|2
|turn|2
|switch|p1a: Incineroar|Incineroar, L50|100/100
"""
        replay = parse_replay(log, "test")
        state = replay.battle_state.active.get("p1a: Incineroar")
        assert state is not None
        assert state.boosts == {}
