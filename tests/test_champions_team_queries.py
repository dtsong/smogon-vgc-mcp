from pathlib import Path

import pytest

from smogon_vgc_mcp.database.champions_team_queries import (
    compute_team_fingerprint,
    get_champions_team,
    write_or_queue_team,
)
from smogon_vgc_mcp.database.models import ChampionsTeam, ChampionsTeamPokemon
from smogon_vgc_mcp.database.schema import get_connection, init_database


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


def _team(
    *pokes: ChampionsTeamPokemon,
    status: str = "auto",
    conf: float = 1.0,
    fingerprint: str = "abc123",
) -> ChampionsTeam:
    return ChampionsTeam(
        team_id=fingerprint,
        source_type="pokepaste",
        source_url="https://pokepast.es/abc",
        ingestion_status=status,
        confidence_score=conf,
        pokemon=list(pokes),
    )


async def test_write_auto_team(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="Koraidon", sp_atk=32, sp_spe=32),
        fingerprint="fp1",
    )
    async with get_connection(db_path) as db:
        row_id = await write_or_queue_team(db, team)
        assert row_id > 0
        out = await get_champions_team(db, row_id)
    assert out is not None
    assert out.ingestion_status == "auto"
    assert len(out.pokemon) == 1
    assert out.pokemon[0].pokemon == "Koraidon"


async def test_write_queue_team(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"),
        status="review_pending",
        conf=0.5,
        fingerprint="fp2",
    )
    async with get_connection(db_path) as db:
        row_id = await write_or_queue_team(db, team)
        out = await get_champions_team(db, row_id)
    assert out.ingestion_status == "review_pending"
    assert out.confidence_score == pytest.approx(0.5)


async def test_duplicate_fingerprint_returns_existing(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="Koraidon"),
        fingerprint="dup",
    )
    async with get_connection(db_path) as db:
        id1 = await write_or_queue_team(db, team)
        id2 = await write_or_queue_team(db, team)
    assert id1 == id2


async def test_review_reasons_persisted(db_path: Path):
    team = _team(
        ChampionsTeamPokemon(slot=1, pokemon="X"),
        fingerprint="rr",
    )
    team.review_reasons = ["sp_over_total"]
    team.normalizations = ["move_fuzzy:Close Combatt->Close Combat"]
    async with get_connection(db_path) as db:
        row_id = await write_or_queue_team(db, team)
        out = await get_champions_team(db, row_id)
    assert out.review_reasons == ["sp_over_total"]
    assert out.normalizations == ["move_fuzzy:Close Combatt->Close Combat"]


def test_fingerprint_stable_for_same_team():
    team_a = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon", move1="Flare Blitz"))
    team_b = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon", move1="Flare Blitz"))
    assert compute_team_fingerprint(team_a.pokemon) == compute_team_fingerprint(team_b.pokemon)


def test_fingerprint_move_order_insensitive():
    team_a = _team(
        ChampionsTeamPokemon(slot=1, pokemon="X", move1="A", move2="B", move3="C", move4="D")
    )
    team_b = _team(
        ChampionsTeamPokemon(slot=1, pokemon="X", move1="D", move2="C", move3="B", move4="A")
    )
    assert compute_team_fingerprint(team_a.pokemon) == compute_team_fingerprint(team_b.pokemon)


def test_fingerprint_different_when_sets_differ():
    team_a = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon"))
    team_b = _team(ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"))
    assert compute_team_fingerprint(team_a.pokemon) != compute_team_fingerprint(team_b.pokemon)


async def test_get_champions_team_returns_none_when_missing(db_path: Path):
    async with get_connection(db_path) as db:
        out = await get_champions_team(db, row_id=99999)
    assert out is None


async def test_duplicate_fingerprint_isolated_per_format(db_path: Path):
    team_a = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon"), fingerprint="shared_fp")
    team_b = _team(ChampionsTeamPokemon(slot=1, pokemon="Koraidon"), fingerprint="shared_fp")
    team_b.format = "champions_test"
    async with get_connection(db_path) as db:
        id_a = await write_or_queue_team(db, team_a)
        id_b = await write_or_queue_team(db, team_b)
    assert id_a != id_b
