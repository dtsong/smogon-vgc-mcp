"""CRUD + routing for Champions teams."""

from __future__ import annotations

import hashlib
import json

import aiosqlite

from smogon_vgc_mcp.database.models import ChampionsTeam, ChampionsTeamPokemon


def compute_team_fingerprint(pokemon: list[ChampionsTeamPokemon]) -> str:
    """Stable 16-hex-char prefix of SHA256 over the team's structure.

    The full SHA256 digest is truncated to its first 16 hex characters
    (64 bits) — collision probability is negligible at champion-team
    volumes but note the hash is not full-strength.

    Pokemon are sorted by ``(slot, pokemon)`` and moves within a set
    are sorted before hashing — reordering moves within a slot does
    not change the fingerprint, but reassigning a species to a
    different slot does.
    """
    canonical = []
    for p in sorted(pokemon, key=lambda x: (x.slot, x.pokemon.casefold())):
        moves = tuple(sorted(m for m in (p.move1, p.move2, p.move3, p.move4) if m))
        canonical.append(
            (
                p.slot,
                p.pokemon.casefold(),
                (p.ability or "").casefold(),
                (p.item or "").casefold(),
                (p.nature or "").casefold(),
                (p.tera_type or "").casefold(),
                p.level,
                p.sp_hp,
                p.sp_atk,
                p.sp_def,
                p.sp_spa,
                p.sp_spd,
                p.sp_spe,
                moves,
            )
        )
    digest = hashlib.sha256(json.dumps(canonical).encode()).hexdigest()
    return digest[:16]


async def write_or_queue_team(db: aiosqlite.Connection, team: ChampionsTeam) -> int:
    """Insert the team. Returns the row id. Duplicate (format, team_id) returns existing id.

    Dedup is by ``(format, team_id)`` — on collision the *existing* row
    is returned untouched; the new ``team`` payload (including its
    ``source_url``, ``review_reasons``, and Pokemon rows) is discarded.
    Callers that need update-on-conflict semantics must delete the
    prior row first.

    Commits internally; the caller should not wrap this in its own
    transaction expecting to rollback. ``db.row_factory`` is temporarily
    switched to ``aiosqlite.Row`` for the dedup lookup and restored
    before return, so the caller's connection state is preserved for
    any subsequent queries that expect tuples.
    """
    prior_factory = db.row_factory
    db.row_factory = aiosqlite.Row
    try:
        existing = await db.execute_fetchall(
            "SELECT id FROM champions_teams WHERE format = ? AND team_id = ?",
            (team.format, team.team_id),
        )
        if existing:
            return int(existing[0]["id"])

        cursor = await db.execute(
            """
            INSERT INTO champions_teams(
                format, team_id, description, owner, source_type, source_url,
                ingestion_status, confidence_score, review_reasons, normalizations
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team.format,
                team.team_id,
                team.description,
                team.owner,
                team.source_type,
                team.source_url,
                team.ingestion_status,
                team.confidence_score,
                json.dumps(team.review_reasons) if team.review_reasons else None,
                json.dumps(team.normalizations) if team.normalizations else None,
            ),
        )
        team_row_id = cursor.lastrowid
        if team_row_id is None:
            raise RuntimeError("INSERT into champions_teams returned no lastrowid")

        for poke in team.pokemon:
            await db.execute(
                """
                INSERT INTO champions_team_pokemon(
                    team_id, slot, pokemon, item, ability, nature, tera_type, level,
                    sp_hp, sp_atk, sp_def, sp_spa, sp_spd, sp_spe,
                    move1, move2, move3, move4
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_row_id,
                    poke.slot,
                    poke.pokemon,
                    poke.item,
                    poke.ability,
                    poke.nature,
                    poke.tera_type,
                    poke.level,
                    poke.sp_hp,
                    poke.sp_atk,
                    poke.sp_def,
                    poke.sp_spa,
                    poke.sp_spd,
                    poke.sp_spe,
                    poke.move1,
                    poke.move2,
                    poke.move3,
                    poke.move4,
                ),
            )

        await db.commit()
        return int(team_row_id)
    finally:
        db.row_factory = prior_factory


async def get_champions_team(db: aiosqlite.Connection, row_id: int) -> ChampionsTeam | None:
    prior_factory = db.row_factory
    db.row_factory = aiosqlite.Row
    try:
        team_row = await db.execute_fetchall(
            "SELECT * FROM champions_teams WHERE id = ?", (row_id,)
        )
        if not team_row:
            return None
        t = team_row[0]

        poke_rows = await db.execute_fetchall(
            "SELECT * FROM champions_team_pokemon WHERE team_id = ? ORDER BY slot",
            (row_id,),
        )
        pokemon = [
            ChampionsTeamPokemon(
                slot=p["slot"],
                pokemon=p["pokemon"],
                item=p["item"],
                ability=p["ability"],
                nature=p["nature"],
                tera_type=p["tera_type"],
                level=p["level"],
                sp_hp=p["sp_hp"],
                sp_atk=p["sp_atk"],
                sp_def=p["sp_def"],
                sp_spa=p["sp_spa"],
                sp_spd=p["sp_spd"],
                sp_spe=p["sp_spe"],
                move1=p["move1"],
                move2=p["move2"],
                move3=p["move3"],
                move4=p["move4"],
            )
            for p in poke_rows
        ]

        return ChampionsTeam(
            team_id=t["team_id"],
            format=t["format"],
            description=t["description"],
            owner=t["owner"],
            source_type=t["source_type"],
            source_url=t["source_url"],
            ingestion_status=t["ingestion_status"],
            confidence_score=t["confidence_score"],
            review_reasons=json.loads(t["review_reasons"]) if t["review_reasons"] else None,
            normalizations=json.loads(t["normalizations"]) if t["normalizations"] else None,
            pokemon=pokemon,
        )
    finally:
        db.row_factory = prior_factory
