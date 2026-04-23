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
