from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from smogon_vgc_mcp.database.schema import init_database
from smogon_vgc_mcp.entry.ingest_cli import main_async
from smogon_vgc_mcp.resilience import FetchResult


@pytest.fixture
async def db_path(tmp_path: Path):
    p = tmp_path / "test.db"
    await init_database(p)
    return p


async def test_cli_auto_write_exit_zero(db_path: Path, capsys):
    pokepaste_text = (
        "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\nEVs: 32 Atk\n"
        "Adamant Nature\n- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"
    )
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(pokepaste_text)),
    ):
        exit_code = await main_async(["https://pokepast.es/abc"], db_path=db_path)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "auto" in captured.out.lower()


async def test_cli_rejected_exit_nonzero(db_path: Path, capsys):
    exit_code = await main_async(["not-a-url"], db_path=db_path)
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "rejected" in captured.out.lower()


async def test_cli_missing_url_exit_usage(db_path: Path, capsys):
    exit_code = await main_async([], db_path=db_path)
    assert exit_code == 1


async def test_cli_parse_failed_exit_four(db_path: Path, capsys):
    # Empty pokepaste body → parse_failed → exit code 4.
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok("")),
    ):
        exit_code = await main_async(["https://pokepast.es/empty"], db_path=db_path)
    assert exit_code == 4


async def test_cli_db_error_exit_five(db_path: Path, capsys):
    # DB write failure → db_error → exit code 5.
    import aiosqlite

    pokepaste_text = (
        "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\nEVs: 32 Atk\n"
        "Adamant Nature\n- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"
    )

    async def boom(db, team):
        raise aiosqlite.OperationalError("disk full")

    with (
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
            new=AsyncMock(return_value=FetchResult.ok(pokepaste_text)),
        ),
        patch(
            "smogon_vgc_mcp.fetcher.ingestion.pipeline.write_or_queue_team",
            new=boom,
        ),
    ):
        exit_code = await main_async(["https://pokepast.es/dbfail"], db_path=db_path)
    assert exit_code == 5


async def test_cli_review_pending_exit_zero(db_path: Path, capsys):
    # Two soft failures (nature + tera unknown) drop confidence below
    # AUTO_WRITE_THRESHOLD, producing review_pending — which is still a
    # successful persist and must map to exit 0 (same as auto). CI
    # scripts key on exit code, so a regression that separates
    # review_pending into nonzero would silently break dashboards.
    text = (
        "Koraidon @ Life Orb\nAbility: Orichalcum Pulse\nLevel: 50\n"
        "Tera Type: Plasma\nEVs: 32 Atk\nFooNature Nature\n"
        "- Flare Blitz\n- Protect\n- Collision Course\n- Dragon Claw"
    )
    with patch(
        "smogon_vgc_mcp.fetcher.ingestion.pipeline.fetch_pokepaste",
        new=AsyncMock(return_value=FetchResult.ok(text)),
    ):
        exit_code = await main_async(["https://pokepast.es/soft"], db_path=db_path)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "review_pending" in captured.out.lower()


async def test_cli_fetch_failed_exit_three(db_path: Path, capsys):
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
        exit_code = await main_async(["https://pokepast.es/missing"], db_path=db_path)
    assert exit_code == 3


def test_main_unhandled_exception_exits_three(capsys, monkeypatch):
    from smogon_vgc_mcp.entry import ingest_cli

    async def boom(*a, **kw):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(ingest_cli, "main_async", boom)
    monkeypatch.setattr("sys.argv", ["vgc-ingest", "https://pokepast.es/x"])
    with pytest.raises(SystemExit) as excinfo:
        ingest_cli.main()
    assert excinfo.value.code == 3
    captured = capsys.readouterr()
    assert "kaboom" in captured.err
    assert "RuntimeError" in captured.err  # traceback printed
