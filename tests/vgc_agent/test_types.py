"""Tests for core types."""

from vgc_agent.core.types import (
    Phase,
    PokemonSet,
    SessionState,
    TeamDesign,
    Weakness,
    WeaknessReport,
)


class TestPokemonSet:
    def test_basic_set(self):
        p = PokemonSet(species="Incineroar")
        assert p.species == "Incineroar"
        assert p.item is None

    def test_to_showdown(self):
        p = PokemonSet(
            species="Incineroar",
            item="Safety Goggles",
            ability="Intimidate",
            tera_type="Ghost",
            moves=["Fake Out", "Knock Off"],
            nature="Careful",
            evs={"hp": 252, "spd": 252},
        )
        s = p.to_showdown()
        assert "Incineroar @ Safety Goggles" in s
        assert "Ability: Intimidate" in s
        assert "- Fake Out" in s

    def test_to_showdown_with_ivs(self):
        p = PokemonSet(
            species="Torkoal",
            ability="Drought",
            nature="Quiet",
            ivs={"spe": 0},
        )
        s = p.to_showdown()
        assert "IVs: 0 Spe" in s

    def test_to_dict(self):
        p = PokemonSet(species="Rillaboom", role="support")
        d = p.to_dict()
        assert d["species"] == "Rillaboom"
        assert d["role"] == "support"


class TestTeamDesign:
    def test_empty_team(self):
        t = TeamDesign()
        assert t.pokemon == []

    def test_to_showdown(self):
        t = TeamDesign(
            pokemon=[
                PokemonSet(species="Incineroar", moves=["Fake Out"]),
                PokemonSet(species="Flutter Mane", moves=["Moonblast"]),
            ]
        )
        s = t.to_showdown()
        assert "Incineroar" in s
        assert "Flutter Mane" in s

    def test_to_dict(self):
        t = TeamDesign(
            core=["Kyogre", "Pelipper"],
            mode="rain",
            game_plan="Set rain and sweep",
        )
        d = t.to_dict()
        assert d["core"] == ["Kyogre", "Pelipper"]
        assert d["mode"] == "rain"


class TestWeakness:
    def test_weakness_creation(self):
        w = Weakness(
            threat="Urshifu",
            severity="severe",
            description="Threatens entire team",
            affected_pokemon=["Incineroar", "Rillaboom"],
        )
        assert w.threat == "Urshifu"
        assert w.severity == "severe"

    def test_to_dict(self):
        w = Weakness(
            threat="Flutter Mane",
            severity="critical",
            description="No answers",
        )
        d = w.to_dict()
        assert d["threat"] == "Flutter Mane"
        assert d["severity"] == "critical"


class TestWeaknessReport:
    def test_with_weaknesses(self):
        r = WeaknessReport(
            weaknesses=[
                Weakness(threat="Urshifu", severity="severe", description="Threatens team")
            ],
            overall_severity="severe",
            iteration_needed=True,
        )
        assert len(r.weaknesses) == 1
        assert r.iteration_needed

    def test_to_dict(self):
        r = WeaknessReport(
            overall_severity="moderate",
            suggestions=["Add a fairy type"],
        )
        d = r.to_dict()
        assert d["overall_severity"] == "moderate"
        assert "Add a fairy type" in d["suggestions"]


class TestSessionState:
    def test_initial_state(self):
        s = SessionState(session_id="test", requirements="Build a team")
        assert s.phase == Phase.INITIALIZED
        assert s.iteration == 0

    def test_to_dict(self):
        s = SessionState(
            session_id="test",
            requirements="Build a team",
            phase=Phase.ARCHITECTING,
            iteration=1,
        )
        d = s.to_dict()
        assert d["phase"] == "architecting"
        assert d["iteration"] == 1

    def test_with_team_design(self):
        s = SessionState(
            session_id="test",
            requirements="Build rain team",
            team_design=TeamDesign(mode="rain"),
        )
        d = s.to_dict()
        assert d["team_design"]["mode"] == "rain"
