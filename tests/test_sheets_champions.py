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


async def test_ingest_champions_sheet_initializes_fresh_db(tmp_path: Path):
    # No pre-init — exercises the cycle-1 init_database call inside
    # ingest_champions_sheet so a brand-new install survives the first run.
    fresh_db = tmp_path / "fresh.db"
    sheet_csv = "URL\nhttps://pokepast.es/abc\n"
    pokepaste_text = (
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
            new=AsyncMock(return_value=FetchResult.ok(pokepaste_text)),
        ),
    ):
        report = await ingest_champions_sheet(db_path=fresh_db)
    assert fresh_db.exists()
    assert report["auto"] == 1


async def test_ingest_champions_sheet_no_sheet_gid_signals_fetch_failed(db_path: Path):
    # Config drift (missing sheet_gid) must surface in the counter dict
    # so scripts that compare counts against zero can distinguish it
    # from a successful run over an empty sheet.
    with patch(
        "smogon_vgc_mcp.fetcher.sheets.get_sheet_csv_url",
        return_value=None,
    ):
        report = await ingest_champions_sheet(db_path=db_path)
    assert report["fetch_failed"] == 1
    assert report["auto"] == 0
    assert report["review_pending"] == 0
    assert report["rejected"] == 0
    assert report["parse_failed"] == 0
    assert report["db_error"] == 0
    assert report["unexpected_error"] == 0


async def test_ingest_champions_sheet_empty_body_signals_fetch_failed(db_path: Path):
    # A success-but-empty-body response (e.g. a 200 that returned
    # scrubbed HTML or a CDN stub) must still land in fetch_failed —
    # the guard on ``not fetched.data`` covers both None and "".
    with patch(
        "smogon_vgc_mcp.fetcher.sheets.fetch_text_resilient",
        new=AsyncMock(return_value=FetchResult.ok(None)),
    ):
        report = await ingest_champions_sheet(db_path=db_path)
    assert report["fetch_failed"] == 1
    assert report["auto"] == 0


async def test_ingest_champions_sheet_rows_without_urls_are_skipped(db_path: Path):
    # Rows with no http(s) URL column must be silently skipped — no
    # crash, no counter increment. Guards against a regression where
    # the ``if not url: continue`` check is removed.
    header_only_csv = "Owner,Tournament,Rank,URL\nAlice,Regional,Top 8,\nBob,Regional,Winner,\n"
    with patch(
        "smogon_vgc_mcp.fetcher.sheets.fetch_text_resilient",
        new=AsyncMock(return_value=FetchResult.ok(header_only_csv)),
    ):
        report = await ingest_champions_sheet(db_path=db_path)
    # No URLs → all counters stay at zero.
    assert all(v == 0 for v in report.values())


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

    # First row crashes inside the pipeline (not a FetchResult.fail) →
    # unexpected_error bucket; the sheet-level fetch_failed bucket is
    # reserved for the sheet-fetch itself failing.
    assert report["unexpected_error"] == 1
    assert report["fetch_failed"] == 0
    assert report["auto"] == 1
