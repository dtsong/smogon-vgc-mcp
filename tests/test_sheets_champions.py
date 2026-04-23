from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from smogon_vgc_mcp.database.schema import init_database
from smogon_vgc_mcp.fetcher.sheets import ingest_champions_sheet
from smogon_vgc_mcp.resilience import FetchResult


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


MIXED_SHEET_CSV = """Owner,Tournament,Rank,URL
Alice,Regional A,Top 8,https://pokepast.es/abc123
Bob,Regional B,Winner,https://x.com/bob/status/42
Carol,Regional C,Top 4,https://someblog.example/post
"""


async def test_ingest_champions_sheet_routes_by_url_shape(db_path: Path):
    pokepaste_text = (
        "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\nEVs: 32 Atk\n"
        "Adamant Nature\n- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"
    )

    with (
        patch(
            "smogon_vgc_mcp.fetcher.sheets.fetch_text_resilient",
            new=AsyncMock(return_value=FetchResult.ok(MIXED_SHEET_CSV)),
        ),
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
            new=AsyncMock(return_value=FetchResult.ok(pokepaste_text)),
        ),
    ):
        report = await ingest_champions_sheet(db_path=db_path)

    # 3 rows: 1 pokepaste (auto), 2 rejected as tier_not_implemented
    assert report["auto"] == 1
    assert report["rejected"] == 2
    assert report["fetch_failed"] == 0


async def test_ingest_champions_sheet_fetch_failure_records_counter(db_path: Path):
    from smogon_vgc_mcp.resilience import ErrorCategory, ServiceError

    err = ServiceError(
        category=ErrorCategory.HTTP_CLIENT_ERROR,
        service="sheets",
        message="503",
        is_recoverable=True,
    )
    with patch(
        "smogon_vgc_mcp.fetcher.sheets.fetch_text_resilient",
        new=AsyncMock(return_value=FetchResult.fail(err)),
    ):
        report = await ingest_champions_sheet(db_path=db_path)
    assert report["fetch_failed"] == 1
    assert report["auto"] == 0
    assert report["rejected"] == 0


async def test_ingest_champions_sheet_per_row_exception_isolated(db_path: Path):
    sheet_csv = "URL\nhttps://pokepast.es/a\nhttps://pokepast.es/b\n"
    call_count = {"n": 0}

    async def flaky_fetch(url: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated transient error")
        return FetchResult.ok(
            "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\n"
            "EVs: 32 Atk\nAdamant Nature\n"
            "- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"
        )

    with (
        patch(
            "smogon_vgc_mcp.fetcher.sheets.fetch_text_resilient",
            new=AsyncMock(return_value=FetchResult.ok(sheet_csv)),
        ),
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
            new=flaky_fetch,
        ),
    ):
        report = await ingest_champions_sheet(db_path=db_path)

    # First row crashes → fetch_failed, second succeeds → auto
    assert report["fetch_failed"] == 1
    assert report["auto"] == 1
