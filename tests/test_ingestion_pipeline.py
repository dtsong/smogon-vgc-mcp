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


async def test_ingest_x_and_blog_not_implemented_yet(db_path: Path):
    result = await ingest_url("https://x.com/u/status/1", db_path=db_path)
    assert result.status == "rejected"
    assert result.reason == "tier_not_implemented"
