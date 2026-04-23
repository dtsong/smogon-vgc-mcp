from pathlib import Path

import pytest

from smogon_vgc_mcp.database.schema import get_connection, init_database


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    await init_database(db_path)
    async with get_connection(db_path) as conn:
        yield conn


async def test_champions_teams_table_created(db):
    async with db.execute("PRAGMA table_info(champions_teams)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    assert {
        "id",
        "format",
        "team_id",
        "description",
        "owner",
        "source_type",
        "source_url",
        "ingestion_status",
        "confidence_score",
        "review_reasons",
        "normalizations",
        "ingested_at",
    } <= cols


async def test_champions_team_pokemon_table_created(db):
    async with db.execute("PRAGMA table_info(champions_team_pokemon)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    assert {
        "id",
        "team_id",
        "slot",
        "pokemon",
        "item",
        "ability",
        "nature",
        "tera_type",
        "level",
        "sp_hp",
        "sp_atk",
        "sp_def",
        "sp_spa",
        "sp_spd",
        "sp_spe",
        "move1",
        "move2",
        "move3",
        "move4",
    } <= cols


async def test_sp_constraints_enforced(db):
    await db.execute(
        "INSERT INTO champions_teams(format, team_id, source_type, source_url, "
        "ingestion_status, confidence_score) VALUES "
        "('champions_ma', 't1', 'pokepaste', 'https://x', 'auto', 1.0)"
    )
    # Per-stat > 32 must fail
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO champions_team_pokemon(team_id, slot, pokemon, sp_hp) "
            "VALUES (1, 1, 'Flutter Mane', 33)"
        )


async def test_sp_total_constraint_enforced(db):
    await db.execute(
        "INSERT INTO champions_teams(format, team_id, source_type, source_url, "
        "ingestion_status, confidence_score) VALUES "
        "('champions_ma', 't2', 'pokepaste', 'https://x', 'auto', 1.0)"
    )
    # Sum > 66 must fail: 32 + 32 + 10 = 74
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO champions_team_pokemon(team_id, slot, pokemon, "
            "sp_hp, sp_atk, sp_def) VALUES (1, 1, 'Koraidon', 32, 32, 10)"
        )


async def test_slot_constraint_enforced_low(db):
    await db.execute(
        "INSERT INTO champions_teams(format, team_id, source_type, source_url, "
        "ingestion_status, confidence_score) VALUES "
        "('champions_ma', 't3', 'pokepaste', 'https://x', 'auto', 1.0)"
    )
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO champions_team_pokemon(team_id, slot, pokemon) VALUES (1, 0, 'Koraidon')"
        )


async def test_slot_constraint_enforced_high(db):
    await db.execute(
        "INSERT INTO champions_teams(format, team_id, source_type, source_url, "
        "ingestion_status, confidence_score) VALUES "
        "('champions_ma', 't4', 'pokepaste', 'https://x', 'auto', 1.0)"
    )
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO champions_team_pokemon(team_id, slot, pokemon) VALUES (1, 7, 'Koraidon')"
        )
