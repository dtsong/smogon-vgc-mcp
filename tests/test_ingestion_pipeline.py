from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from smogon_vgc_mcp.database.champions_team_queries import get_champions_team
from smogon_vgc_mcp.database.schema import get_connection, init_database
from smogon_vgc_mcp.fetcher.ingestion.pipeline import ingest_url
from smogon_vgc_mcp.resilience import FetchResult

FIXTURE = Path(__file__).parent / "fixtures" / "champions_pokepaste_sample.txt"


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


async def test_ingest_unknown_url_returns_rejected(db_path: Path):
    result = await ingest_url("not-a-url", db_path=db_path)
    assert result.status == "rejected"
    assert result.reason == "classifier_unknown_tier"
    assert result.team_row_id is None


async def test_ingest_pokepaste_auto_writes(db_path: Path):
    text = FIXTURE.read_text()
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(text)),
    ):
        result = await ingest_url("https://pokepast.es/abc", db_path=db_path)
    assert result.status == "auto"
    assert result.team_row_id is not None
    async with get_connection(db_path) as db:
        stored = await get_champions_team(db, result.team_row_id)
    assert stored.ingestion_status == "auto"
    assert stored.confidence_score == pytest.approx(1.0)
    assert len(stored.pokemon) == 2


async def test_ingest_fetch_failure_returns_fetch_failed(db_path: Path):
    from smogon_vgc_mcp.resilience import ErrorCategory, ServiceError

    err = ServiceError(
        category=ErrorCategory.HTTP_CLIENT_ERROR,
        service="pokepaste",
        message="404",
        is_recoverable=False,
    )
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.fail(err)),
    ):
        result = await ingest_url("https://pokepast.es/missing", db_path=db_path)
    assert result.status == "fetch_failed"
    assert result.team_row_id is None
    # The CLI surfaces `reason` to users — must be the actionable
    # message, not a dataclass repr.
    assert result.reason == "404"


async def test_ingest_x_and_blog_not_implemented_yet(db_path: Path):
    result = await ingest_url("https://x.com/u/status/1", db_path=db_path)
    assert result.status == "rejected"
    assert result.reason == "tier_not_implemented"


async def test_ingest_empty_pokepaste_returns_parse_failed(db_path: Path):
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok("")),
    ):
        result = await ingest_url("https://pokepast.es/empty", db_path=db_path)
    assert result.status == "parse_failed"
    assert result.team_row_id is None


async def test_ingest_pokepaste_review_pending_when_confidence_low(db_path: Path):
    # Two soft failures (unknown nature + unknown tera type) drops 1.0 → 0.8 < 0.85
    text = (
        "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\n"
        "Tera Type: Plasma\nEVs: 32 Atk\nFooNature Nature\n"
        "- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"
    )
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(text)),
    ):
        result = await ingest_url("https://pokepast.es/soft", db_path=db_path)
    assert result.status == "review_pending"
    assert result.team_row_id is not None
    assert result.confidence == pytest.approx(0.8)
    async with get_connection(db_path) as db:
        stored = await get_champions_team(db, result.team_row_id)
    assert stored.ingestion_status == "review_pending"
    assert stored.review_reasons is not None
    assert "nature_unknown" in stored.review_reasons
    assert "tera_type_unknown" in stored.review_reasons


async def test_ingest_pokepaste_parse_exception_returns_parse_failed(db_path: Path):
    # Force parse_pokepaste_to_champions_draft to raise; pipeline wraps
    # it into a FetchResult.fail(PARSE_ERROR) which must surface as
    # parse_failed (CLI exit 4), not fetch_failed (CLI exit 3).
    def boom(*a, **kw):
        raise ValueError("boom")

    with (
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
            new=AsyncMock(return_value=FetchResult.ok("anything")),
        ),
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.parse_pokepaste_to_champions_draft",
            new=boom,
        ),
    ):
        result = await ingest_url("https://pokepast.es/exc", db_path=db_path)
    assert result.status == "parse_failed"
    assert result.reason is not None
    assert "Failed to parse pokepaste" in result.reason


async def test_ingest_whitespace_body_returns_parse_failed(db_path: Path):
    # Whitespace-only body parses to zero pokemon; the zero-pokemon
    # branch in _fetch_tier1 returns FetchResult.ok(None), which the
    # caller maps to parse_failed with reason="empty_parse".
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok("   \n\n   ")),
    ):
        result = await ingest_url("https://pokepast.es/ws", db_path=db_path)
    assert result.status == "parse_failed"
    assert result.reason == "empty_parse"


async def test_ingest_db_write_failure_returns_db_error(db_path: Path):
    text = FIXTURE.read_text()

    async def boom(db, team):
        raise RuntimeError("disk full")

    with (
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
            new=AsyncMock(return_value=FetchResult.ok(text)),
        ),
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.write_or_queue_team",
            new=boom,
        ),
    ):
        result = await ingest_url("https://pokepast.es/dbfail", db_path=db_path)
    assert result.status == "db_error"
    assert result.reason is not None
    assert "db_write_error" in result.reason
    assert result.team_row_id is None
    # Confidence is computed before the DB write, so it should still be
    # populated to preserve the validator signal.
    assert result.confidence is not None


async def test_ingest_hard_failure_writes_review_pending_with_zero_confidence(db_path: Path):
    # Duplicate species triggers a hard failure (`duplicate_species`)
    # without violating DB CHECK constraints. Hard failures drop
    # confidence to 0.0 and land below AUTO_WRITE_THRESHOLD, so the
    # team is still persisted but marked review_pending. This behavior
    # is intentional (preserve for audit) and covered here so future
    # refactors can't silently flip it to 'rejected' without breaking
    # a test.
    text = (
        "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\n"
        "Tera Type: Fire\nAdamant Nature\n"
        "- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw\n\n"
        "Koraidon @ Choice Band\nAbility: Orichalcum Pulse\nLevel: 50\n"
        "Tera Type: Fire\nAdamant Nature\n"
        "- Flare Blitz\n- U-turn\n- Collision Course\n- Dragon Claw"
    )
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(text)),
    ):
        result = await ingest_url("https://pokepast.es/hardfail", db_path=db_path)
    assert result.status == "review_pending"
    assert result.confidence == pytest.approx(0.0)
    assert result.team_row_id is not None
    async with get_connection(db_path) as db:
        stored = await get_champions_team(db, result.team_row_id)
    assert stored.ingestion_status == "review_pending"
    assert stored.review_reasons is not None
    assert "duplicate_species" in stored.review_reasons


async def test_load_dex_lookup_returns_none_when_empty(db_path: Path):
    from smogon_vgc_mcp.fetcher.ingestion.pipeline import load_dex_lookup

    result = await load_dex_lookup(db_path)
    assert result is None


async def test_load_dex_lookup_builds_entries_from_populated_tables(db_path: Path):
    from smogon_vgc_mcp.database.schema import get_connection
    from smogon_vgc_mcp.fetcher.ingestion.pipeline import load_dex_lookup

    async with get_connection(db_path) as db:
        await db.execute(
            "INSERT INTO champions_dex_pokemon(id, name, type1, hp, atk, def, spa, spd, spe, "
            "ability1, ability2, ability_hidden) VALUES "
            "('koraidon', 'Koraidon', 'Dragon', 100, 100, 100, 100, 100, 100, "
            "'Orichalcum Pulse', NULL, NULL)"
        )
        await db.execute(
            "INSERT INTO champions_dex_moves(id, name, type, category) VALUES "
            "('flareblitz', 'Flare Blitz', 'Fire', 'Physical')"
        )
        await db.execute(
            "INSERT INTO champions_dex_learnsets(pokemon_id, move_id, method) VALUES "
            "('koraidon', 'flareblitz', 'level-up')"
        )
        await db.commit()

    result = await load_dex_lookup(db_path)
    assert result is not None
    entry = result["koraidon"]
    assert entry["abilities"] == ["Orichalcum Pulse"]
    assert entry["moves"] == ["Flare Blitz"]


async def test_ingest_url_uses_provided_dex_to_flag_illegal_ability(db_path: Path):
    # Koraidon's only legal ability here is Orichalcum Pulse; the
    # pokepaste claims "Fake Ability" so the soft failure ability_illegal
    # must fire. Two soft failures drop confidence to 0.8 < threshold.
    dex_lookup = {
        "koraidon": {"abilities": ["Orichalcum Pulse"], "moves": ["Flare Blitz"]},
    }
    text = (
        "Koraidon @ Life Orb\nAbility: Fake Ability\nLevel: 50\nEVs: 32 Atk\n"
        "Adamant Nature\n- Flare Blitz\n- Flare Blitz\n- Flare Blitz\n- Flare Blitz"
    )
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(text)),
    ):
        result = await ingest_url(
            "https://pokepast.es/abil", db_path=db_path, dex_lookup=dex_lookup
        )
    assert result.team_row_id is not None
    async with get_connection(db_path) as db:
        stored = await get_champions_team(db, result.team_row_id)
    assert stored.review_reasons is not None
    assert "ability_illegal" in stored.review_reasons


def test_score_arithmetic_matches_threshold():
    from smogon_vgc_mcp.database.models import ChampionsTeamDraft
    from smogon_vgc_mcp.fetcher.ingestion.pipeline import (
        AUTO_WRITE_THRESHOLD,
        _score,
    )

    draft = ChampionsTeamDraft(
        source_type="pokepaste",
        source_url="https://x",
        tier_baseline_confidence=1.0,
    )
    assert _score(draft, 0) == pytest.approx(1.0)
    assert _score(draft, 1) == pytest.approx(0.9)
    assert _score(draft, 2) == pytest.approx(0.8)
    assert _score(draft, 100) == 0.0
    # one soft failure stays auto, two flips to review_pending
    assert _score(draft, 1) >= AUTO_WRITE_THRESHOLD
    assert _score(draft, 2) < AUTO_WRITE_THRESHOLD
