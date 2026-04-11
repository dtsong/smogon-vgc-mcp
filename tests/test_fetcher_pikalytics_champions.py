"""Tests for Pikalytics Champions usage parser."""

from pathlib import Path

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.pikalytics_champions import (
    fetch_and_store_pikalytics_champions,
    parse_pikalytics_page,
    store_champions_usage,
)
from smogon_vgc_mcp.resilience.errors import FetchResult, ServiceError

FIXTURE = Path(__file__).parent / "fixtures" / "pikalytics_incineroar.html"


@pytest.fixture
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_returns_usage_dict(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert result["pokemon"] == "incineroar"
    assert result["usage_percent"] is not None
    assert 0 < result["usage_percent"] <= 100


def test_parse_extracts_moves(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert isinstance(result["moves"], list)
    assert len(result["moves"]) > 0
    name, pct = result["moves"][0]
    assert isinstance(name, str) and name
    assert isinstance(pct, float)


def test_parse_moves_first_entry_clean(html: str) -> None:
    """Regression: first move entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, pct = result["moves"][0]
    assert name == "Fake Out", f"Expected 'Fake Out', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"
    assert "the" not in name.lower().split(), f"Sentence fragment in label: {name!r}"
    assert pct == pytest.approx(41.092)


def test_parse_items_first_entry_clean(html: str) -> None:
    """Regression: first item entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, _pct = result["items"][0]
    assert name == "Sitrus Berry", f"Expected 'Sitrus Berry', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"


def test_parse_abilities_first_entry_clean(html: str) -> None:
    """Regression: first ability entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, _pct = result["abilities"][0]
    assert name == "Intimidate", f"Expected 'Intimidate', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"


def test_parse_teammates_first_entry_clean(html: str) -> None:
    """Regression: first teammate entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, _pct = result["teammates"][0]
    assert name == "Sinistcha", f"Expected 'Sinistcha', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"


def test_parse_extracts_items_abilities_teammates(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert len(result["items"]) > 0
    assert len(result["abilities"]) > 0
    assert len(result["teammates"]) > 0


def test_parse_handles_404() -> None:
    assert parse_pikalytics_page("", pokemon_slug="missingno") is None
    assert parse_pikalytics_page("<html>Not Found</html>", pokemon_slug="missingno") is None


@pytest.mark.asyncio
async def test_store_creates_snapshot_and_rows() -> None:
    payload = [
        {
            "pokemon": "incineroar",
            "usage_percent": 35.8,
            "rank": 1,
            "raw_count": None,
            "moves": [("Fake Out", 95.2), ("Flare Blitz", 78.1)],
            "items": [("Safety Goggles", 40.0)],
            "abilities": [("Intimidate", 100.0)],
            "teammates": [("Farigiraf", 22.0)],
        }
    ]
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        snapshot_id, count = await store_champions_usage(db, elo_cutoff="0+", pokemon_data=payload)
        assert snapshot_id > 0
        assert count == 1
        async with db.execute("SELECT COUNT(*) FROM champions_usage_moves") as cursor:
            (moves_count,) = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_abilities") as cursor:
            (ab_count,) = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_items") as cursor:
            (items_count,) = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_teammates") as cursor:
            (teammates_count,) = await cursor.fetchone()
    assert moves_count == 2
    assert ab_count == 1
    assert items_count == 1
    assert teammates_count == 1


@pytest.mark.asyncio
async def test_store_replaces_same_elo_snapshot() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        first = [
            {
                "pokemon": "incineroar",
                "usage_percent": 35.8,
                "rank": 1,
                "raw_count": None,
                "moves": [("A", 10.0)],
                "items": [],
                "abilities": [],
                "teammates": [],
            }
        ]
        await store_champions_usage(db, elo_cutoff="0+", pokemon_data=first)
        second = [
            {
                "pokemon": "incineroar",
                "usage_percent": 40.0,
                "rank": 1,
                "raw_count": None,
                "moves": [("B", 20.0)],
                "items": [],
                "abilities": [],
                "teammates": [],
            }
        ]
        await store_champions_usage(db, elo_cutoff="0+", pokemon_data=second)
        async with db.execute("SELECT COUNT(*) FROM champions_usage_snapshots") as cursor:
            (snap_count,) = await cursor.fetchone()
        async with db.execute("SELECT move, percent FROM champions_usage_moves") as cursor:
            rows = await cursor.fetchall()
    assert snap_count == 1
    assert rows == [("B", 20.0)]


@pytest.mark.asyncio
async def test_fetch_and_store_orchestrator_mocks_network(
    tmp_path: Path, html: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orchestrator fetches, parses, and persists a snapshot end-to-end.

    Mocks fetch_text_resilient so the pipeline runs against the real fixture
    HTML without touching the network, then verifies the SQLite DB contains
    both the snapshot row and distribution children.
    """
    db_path = tmp_path / "orchestrator.db"

    async def fake_fetch(url: str, service: str) -> FetchResult[str]:
        return FetchResult.ok(html)

    monkeypatch.setattr(
        "smogon_vgc_mcp.fetcher.pikalytics_champions.fetch_text_resilient",
        fake_fetch,
    )

    result = await fetch_and_store_pikalytics_champions(
        db_path=db_path,
        elo_cutoff="0+",
        slugs=["incineroar"],
        request_delay=0.0,
    )

    assert result["fetched"] == 1
    assert result["stored"] == 1
    assert result["errors"] == []
    assert result["snapshot_id"] > 0
    assert result["elo_cutoff"] == "0+"

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM champions_usage_snapshots") as c:
            (snap_count,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_pokemon_usage") as c:
            (poke_count,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_moves") as c:
            (moves_count,) = await c.fetchone()

    assert snap_count == 1
    assert poke_count == 1
    assert moves_count > 0


@pytest.mark.asyncio
async def test_store_refuses_empty_list_and_preserves_snapshot() -> None:
    """Passing [] to store_champions_usage must not wipe the existing snapshot.

    Regression guard: a parser regression that returned an empty results list
    would otherwise DELETE the live snapshot and replace it with an empty
    one, causing silent data loss for the entire ELO bucket.
    """
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        seed = [
            {
                "pokemon": "incineroar",
                "usage_percent": 35.8,
                "rank": 1,
                "raw_count": None,
                "moves": [("Fake Out", 95.2)],
                "items": [],
                "abilities": [],
                "teammates": [],
            }
        ]
        await store_champions_usage(db, elo_cutoff="0+", pokemon_data=seed)
        with pytest.raises(ValueError, match="empty Pikalytics snapshot"):
            await store_champions_usage(db, elo_cutoff="0+", pokemon_data=[])
        async with db.execute("SELECT COUNT(*) FROM champions_usage_snapshots") as cursor:
            (snap_count,) = await cursor.fetchone()
        async with db.execute("SELECT move FROM champions_usage_moves") as cursor:
            moves = await cursor.fetchall()
    assert snap_count == 1, "original snapshot must survive a refused empty store"
    assert moves == [("Fake Out",)], "child rows must be untouched"


@pytest.mark.asyncio
async def test_fetch_and_store_orchestrator_preserves_data_when_all_fetches_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When every per-slug fetch fails, the orchestrator must NOT enter
    store_champions_usage — the existing snapshot must survive intact."""
    from smogon_vgc_mcp.resilience.errors import ErrorCategory

    db_path = tmp_path / "preserve.db"

    # Seed an existing snapshot via the real store path.
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        await store_champions_usage(
            db,
            elo_cutoff="0+",
            pokemon_data=[
                {
                    "pokemon": "incineroar",
                    "usage_percent": 35.8,
                    "rank": 1,
                    "raw_count": None,
                    "moves": [("Fake Out", 95.2)],
                    "items": [],
                    "abilities": [],
                    "teammates": [],
                }
            ],
        )

    async def fake_fetch(url: str, service: str) -> FetchResult[str]:
        return FetchResult.fail(
            ServiceError(
                category=ErrorCategory.NETWORK,
                service="pikalytics",
                message="simulated total outage",
            )
        )

    monkeypatch.setattr(
        "smogon_vgc_mcp.fetcher.pikalytics_champions.fetch_text_resilient",
        fake_fetch,
    )

    result = await fetch_and_store_pikalytics_champions(
        db_path=db_path,
        elo_cutoff="0+",
        slugs=["incineroar", "sneasler"],
        request_delay=0.0,
    )

    assert result["fetched"] == 0
    assert result["stored"] == 0
    assert any("preserved" in e["message"] for e in result["errors"])

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM champions_usage_snapshots") as cursor:
            (snap_count,) = await cursor.fetchone()
        async with db.execute("SELECT move FROM champions_usage_moves") as cursor:
            moves = await cursor.fetchall()
    assert snap_count == 1, "seed snapshot must still exist"
    assert moves == [("Fake Out",)], "seed child rows must still exist"


@pytest.mark.asyncio
async def test_fetch_and_store_orchestrator_records_fetch_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed fetches are recorded in errors[] without aborting the run."""
    from smogon_vgc_mcp.resilience.errors import ErrorCategory

    db_path = tmp_path / "orchestrator_fail.db"

    async def fake_fetch(url: str, service: str) -> FetchResult[str]:
        return FetchResult.fail(
            ServiceError(
                category=ErrorCategory.NETWORK,
                service="pikalytics",
                message="simulated network failure",
            )
        )

    monkeypatch.setattr(
        "smogon_vgc_mcp.fetcher.pikalytics_champions.fetch_text_resilient",
        fake_fetch,
    )

    result = await fetch_and_store_pikalytics_champions(
        db_path=db_path,
        elo_cutoff="0+",
        slugs=["incineroar", "sneasler"],
        request_delay=0.0,
    )

    assert result["fetched"] == 0
    assert result["stored"] == 0
    # Two per-slug fetch errors plus one "skipped store" entry from the
    # data-loss guard that refuses to wipe the snapshot with nothing.
    fetch_errors = [e for e in result["errors"] if e["slug"] != "store"]
    assert len(fetch_errors) == 2
    assert all("simulated network failure" in e["message"] for e in fetch_errors)


# -----------------------------------------------------------------------------
# Regression tests for Cycle 1 review findings
# -----------------------------------------------------------------------------


def test_parse_empty_html_returns_none_with_log(caplog: pytest.LogCaptureFixture) -> None:
    """Short/empty HTML must log a warning and return None (not silently drop)."""
    import logging

    with caplog.at_level(logging.WARNING, logger="smogon_vgc_mcp.fetcher.pikalytics_champions"):
        result = parse_pikalytics_page("", pokemon_slug="incineroar")
    assert result is None
    assert any("HTML too short" in r.message for r in caplog.records)


def test_parse_no_faq_block_logs_and_returns_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A long body with no FAQPage JSON-LD block must log schema-drift warning."""
    import logging

    # No <script type="application/ld+json"> at all.
    html = "<html><body>" + ("<p>lorem ipsum</p>" * 50) + "</body></html>"
    with caplog.at_level(logging.WARNING, logger="smogon_vgc_mcp.fetcher.pikalytics_champions"):
        result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is None
    # Expect the no-FAQ-block warning AND the no-signal warning.
    messages = [r.message for r in caplog.records]
    assert any("no FAQPage JSON-LD block" in m for m in messages)
    assert any("no usage signal extracted" in m for m in messages)


def test_parse_malformed_json_ld_logs_and_returns_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Corrupt JSON-LD block must be logged and not silently yield empty sections."""
    import logging

    html = (
        "<html><body>"
        + ("<p>filler</p>" * 30)
        + '<script type="application/ld+json">{not json}</script>'
        + "</body></html>"
    )
    with caplog.at_level(logging.WARNING, logger="smogon_vgc_mcp.fetcher.pikalytics_champions"):
        result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is None
    assert any("failed to parse" in r.message for r in caplog.records)


def test_parse_soft_not_found_no_longer_dropped() -> None:
    """The old fragile `"Not Found" in html[:500]` check must be gone.

    Any page whose early bytes contain the words "Not Found" (e.g. a page whose
    navigation links to a "Page Not Found" help article) used to be silently
    dropped.  With the check removed, such pages parse normally when they have
    a real FAQPage block and a usage-percent signal.
    """
    faq_html = (
        "<html><body>"
        '<a href="/help">Page Not Found help</a>'
        "<p>Usage Percent 35.8%</p>"
        '<script type="application/ld+json">'
        '{"@type": "FAQPage", "mainEntity": [{"@type": "Question", '
        '"name": "What moves does Incineroar use?", "acceptedAnswer": '
        '{"@type": "Answer", "text": "The top moves are Fake Out (50.0%)"}}]}'
        "</script>" + ("<p>padding</p>" * 20) + "</body></html>"
    )
    result = parse_pikalytics_page(faq_html, pokemon_slug="incineroar")
    assert result is not None
    assert result["usage_percent"] == pytest.approx(35.8)
    assert ("Fake Out", 50.0) in result["moves"]
