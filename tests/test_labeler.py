"""Tests for the historical VGC labeling workstation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import init_database
from smogon_vgc_mcp.labeler import storage
from smogon_vgc_mcp.labeler.autocomplete import load_autocomplete
from smogon_vgc_mcp.labeler.sources import (
    ArticleDetail,
    ArticleSummary,
    NuggetBridgeSource,
    get_source,
)
from smogon_vgc_mcp.labeler.storage import (
    get_state,
    list_states,
    read_label_json,
    upsert_state,
    write_label_json,
)


async def _seed(db: aiosqlite.Connection) -> None:
    """Insert a handful of nb_posts + champions_dex rows for tests."""
    await db.executemany(
        "INSERT INTO nb_posts (id, slug, url, title, content_html, content_text, "
        "format, fetch_status, published_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "a", "http://x/a", "Old 17 Report", "<p>A</p>", "A", "vgc17", "ok", "2017-06-01"),
            (2, "b", "http://x/b", "Old 14 Report", "<p>B</p>", "B", "vgc14", "ok", "2014-03-10"),
            (3, "c", "http://x/c", "Pending", "<p>C</p>", "C", "vgc17", "pending", "2017-07-01"),
        ],
    )
    await db.executemany(
        "INSERT INTO champions_dex_pokemon "
        "(id, num, name, type1, hp, atk, def, spa, spd, spe) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("pikachu", 25, "Pikachu", "Electric", 35, 55, 40, 50, 50, 90),
            ("garchomp", 445, "Garchomp", "Dragon", 108, 130, 95, 80, 85, 102),
        ],
    )
    await db.execute(
        "INSERT INTO champions_dex_moves (id, num, name, type, category) VALUES (?, ?, ?, ?, ?)",
        ("thunder", 1, "Thunder", "Electric", "Special"),
    )
    await db.execute(
        "INSERT INTO champions_dex_abilities (id, num, name) VALUES (?, ?, ?)",
        ("static", 1, "Static"),
    )
    await db.execute(
        "INSERT INTO nb_sets (post_id, pokemon, pokemon_normalized, item) VALUES (?, ?, ?, ?)",
        (1, "Pikachu", "pikachu", "Light Ball"),
    )
    await db.commit()


@pytest.fixture
async def labeler_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Path]:
    """Isolated SQLite DB seeded with labeler-relevant rows."""
    db_path = tmp_path / "labeler.db"
    labels_dir = tmp_path / "labels"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    monkeypatch.setattr(storage, "DEFAULT_LABELS_DIR", labels_dir)
    await init_database(db_path)
    async with aiosqlite.connect(db_path) as db:
        await _seed(db)
    yield db_path


# =============================================================================
# Schema migration
# =============================================================================


async def test_label_state_table_created(labeler_db: Path) -> None:
    async with aiosqlite.connect(labeler_db) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='label_state'"
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        async with db.execute("PRAGMA table_info(label_state)") as cur:
            cols = {r[1] async for r in cur}
    assert {
        "article_id",
        "source",
        "status",
        "labeled_at",
        "prefill_used",
        "fields_corrected_count",
        "fields_corrected_json",
        "output_path",
        "triage_result",
    } <= cols


# =============================================================================
# NuggetBridgeSource adapter
# =============================================================================


async def test_nugget_bridge_list_filters_fetch_status_ok(labeler_db: Path) -> None:
    src = NuggetBridgeSource()
    async with aiosqlite.connect(labeler_db) as db:
        rows = await src.list_articles(db, format=None, limit=10, offset=0)
    ids = [r.article_id for r in rows]
    assert "3" not in ids  # pending row excluded
    assert {"1", "2"} == set(ids)
    assert all(isinstance(r, ArticleSummary) for r in rows)


async def test_nugget_bridge_list_filters_by_format(labeler_db: Path) -> None:
    src = NuggetBridgeSource()
    async with aiosqlite.connect(labeler_db) as db:
        rows = await src.list_articles(db, format="vgc17", limit=10, offset=0)
    assert [r.article_id for r in rows] == ["1"]


async def test_nugget_bridge_get_article_returns_detail(labeler_db: Path) -> None:
    src = NuggetBridgeSource()
    async with aiosqlite.connect(labeler_db) as db:
        detail = await src.get_article(db, "1")
    assert isinstance(detail, ArticleDetail)
    assert detail.title == "Old 17 Report"
    assert detail.format == "vgc17"
    assert detail.content_html == "<p>A</p>"


async def test_nugget_bridge_get_article_missing_and_non_int(labeler_db: Path) -> None:
    src = NuggetBridgeSource()
    async with aiosqlite.connect(labeler_db) as db:
        assert await src.get_article(db, "9999") is None
        assert await src.get_article(db, "not-a-number") is None


def test_get_source_unknown_raises() -> None:
    with pytest.raises(KeyError, match="Unknown article source"):
        get_source("no-such-source")


# =============================================================================
# Storage: state CRUD + expected-JSON round trip
# =============================================================================


async def test_upsert_state_and_get_state_roundtrip(labeler_db: Path) -> None:
    async with aiosqlite.connect(labeler_db) as db:
        await upsert_state(
            db,
            source="nugget_bridge",
            article_id="1",
            status="labeled",
            output_path="/tmp/1.json",
            prefill_used=True,
            fields_corrected_count=3,
            fields_corrected_json='{"ability": ["Blaze", "Intimidate"]}',
        )
        row = await get_state(db, "nugget_bridge", "1")

    assert row is not None
    assert row["status"] == "labeled"
    assert row["labeled_at"] is not None
    assert row["prefill_used"] == 1
    assert row["fields_corrected_count"] == 3
    assert row["output_path"] == "/tmp/1.json"


async def test_upsert_state_updates_existing_row(labeler_db: Path) -> None:
    async with aiosqlite.connect(labeler_db) as db:
        await upsert_state(db, source="nugget_bridge", article_id="1", status="in_progress")
        first = await get_state(db, "nugget_bridge", "1")
        assert first["status"] == "in_progress"
        assert first["labeled_at"] is None

        await upsert_state(
            db,
            source="nugget_bridge",
            article_id="1",
            status="labeled",
            output_path="/tmp/1.json",
        )
        second = await get_state(db, "nugget_bridge", "1")

    assert second["status"] == "labeled"
    assert second["labeled_at"] is not None


async def test_list_states_filters_by_status(labeler_db: Path) -> None:
    async with aiosqlite.connect(labeler_db) as db:
        await upsert_state(db, source="nugget_bridge", article_id="1", status="labeled")
        await upsert_state(db, source="nugget_bridge", article_id="2", status="skipped")
        labeled = await list_states(db, source="nugget_bridge", statuses=["labeled"])
        all_rows = await list_states(db, source="nugget_bridge")

    assert set(labeled.keys()) == {"1"}
    assert set(all_rows.keys()) == {"1", "2"}


def test_write_and_read_label_json_roundtrip(tmp_path: Path) -> None:
    payload = {"article_id": "1", "sets": [{"pokemon": "Pikachu"}]}
    path = write_label_json("nugget_bridge", "1", payload, labels_dir=tmp_path)
    assert path.exists()
    assert path.parent.name == "nugget_bridge"
    assert path.name == "1.json"

    # File contents are pretty-printed + sorted
    on_disk = json.loads(path.read_text())
    assert on_disk == payload

    # Helper reads the same data back
    loaded = read_label_json("nugget_bridge", "1", labels_dir=tmp_path)
    assert loaded == payload


def test_read_label_json_missing_returns_none(tmp_path: Path) -> None:
    assert read_label_json("nugget_bridge", "nope", labels_dir=tmp_path) is None


# =============================================================================
# Autocomplete
# =============================================================================


async def test_load_autocomplete_returns_expected_keys(labeler_db: Path) -> None:
    async with aiosqlite.connect(labeler_db) as db:
        data = await load_autocomplete(db)

    assert set(data) == {"pokemon", "moves", "abilities", "items", "natures", "stats"}
    assert "Pikachu" in data["pokemon"]
    assert "Garchomp" in data["pokemon"]
    assert "Thunder" in data["moves"]
    assert "Static" in data["abilities"]
    assert "Light Ball" in data["items"]  # from seeded nb_sets row
    assert "Adamant" in data["natures"]
    assert data["stats"] == ["hp", "atk", "def", "spa", "spd", "spe"]


# =============================================================================
# FastAPI routes
# =============================================================================


class FakePrefiller:
    """Deterministic prefiller used to exercise /api/prefill + correction diff."""

    name: str = "fake"
    available: bool = True

    def __init__(self, sets=None, should_raise: bool = False) -> None:
        self._sets = sets or []
        self._raise = should_raise

    async def prefill(self, *, title: str, content_text: str):
        if self._raise:
            raise RuntimeError("boom")
        return list(self._sets)


def _make_client(labeler_db: Path, prefiller=None, triager=None):
    from fastapi.testclient import TestClient

    from smogon_vgc_mcp.labeler.app import create_app

    return TestClient(create_app(prefiller=prefiller, triager=triager))


@pytest.fixture
def client(labeler_db: Path):
    with _make_client(labeler_db) as c:
        yield c


def test_get_sources_lists_nugget_bridge(client) -> None:
    r = client.get("/api/sources")
    assert r.status_code == 200
    assert "nugget_bridge" in r.json()


def test_get_formats_returns_only_historical(client) -> None:
    r = client.get("/api/formats")
    assert r.status_code == 200
    codes = {f["code"] for f in r.json()}
    assert codes >= {"vgc12", "vgc13", "vgc14", "vgc15", "vgc16", "vgc17"}
    assert all(f["is_historical"] for f in r.json())
    assert "regi" not in codes  # live formats excluded


def test_get_articles_default_status_unlabeled(client) -> None:
    r = client.get("/api/articles?source=nugget_bridge")
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 50
    assert {item["article_id"] for item in body["items"]} == {"1", "2"}
    assert all(item["status"] == "unlabeled" for item in body["items"])


def test_get_articles_format_filter(client) -> None:
    r = client.get("/api/articles?source=nugget_bridge&format=vgc14")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["article_id"] for i in items] == ["2"]


def test_get_articles_unknown_source_404(client) -> None:
    r = client.get("/api/articles?source=nope")
    assert r.status_code == 404


def test_get_article_detail_and_missing(client) -> None:
    r = client.get("/api/articles/nugget_bridge/1")
    assert r.status_code == 200
    body = r.json()
    assert body["article"]["title"] == "Old 17 Report"
    assert body["state"] is None
    assert body["label"] is None

    r = client.get("/api/articles/nugget_bridge/9999")
    assert r.status_code == 404


def test_autocomplete_route(client) -> None:
    r = client.get("/api/autocomplete")
    assert r.status_code == 200
    data = r.json()
    assert "Pikachu" in data["pokemon"]
    assert "Thunder" in data["moves"]


def test_save_label_writes_state_and_json(client, tmp_path) -> None:
    payload = {
        "status": "labeled",
        "sets": [
            {
                "pokemon": "Pikachu",
                "ability": "Static",
                "item": "Light Ball",
                "move1": "Thunder",
                "ev_hp": 4,
                "ev_spa": 252,
                "ev_spe": 252,
            }
        ],
        "prefill_used": False,
        "fields_corrected_count": 0,
    }
    r = client.post("/api/labels/nugget_bridge/1", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    out_path = Path(body["output_path"])
    assert out_path.exists()
    written = json.loads(out_path.read_text())
    assert written["sets"][0]["pokemon"] == "Pikachu"
    assert written["format"] == "vgc17"

    # Re-reading the article should surface the persisted state + label
    r = client.get("/api/articles/nugget_bridge/1")
    assert r.status_code == 200
    data = r.json()
    assert data["state"]["status"] == "labeled"
    assert data["label"]["sets"][0]["ability"] == "Static"

    # List endpoint reflects the status change
    r = client.get("/api/articles?source=nugget_bridge")
    item = next(i for i in r.json()["items"] if i["article_id"] == "1")
    assert item["status"] == "labeled"


def test_save_label_invalid_status_422(client) -> None:
    r = client.post(
        "/api/labels/nugget_bridge/1",
        json={"status": "bogus", "sets": []},
    )
    assert r.status_code == 422


def test_save_label_unknown_source_404(client) -> None:
    r = client.post(
        "/api/labels/nope/1",
        json={"status": "labeled", "sets": []},
    )
    assert r.status_code == 404


def test_save_label_missing_article_404(client) -> None:
    r = client.post(
        "/api/labels/nugget_bridge/9999",
        json={"status": "labeled", "sets": []},
    )
    assert r.status_code == 404


def test_index_page_served(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "VGC Historical Labeler" in r.text


def test_static_assets_served(client) -> None:
    r = client.get("/static/labeler.css")
    assert r.status_code == 200
    assert b"set-card" in r.content
    r = client.get("/static/labeler.js")
    assert r.status_code == 200
    assert b"addSet" in r.content


# =============================================================================
# Pre-fill + correction-rate dashboard
# =============================================================================


def test_prefill_info_reports_stub_by_default(client) -> None:
    r = client.get("/api/prefill")
    assert r.status_code == 200
    body = r.json()
    # Default is Anthropic when key is set, else stub. In CI no key → stub.
    assert "name" in body and "available" in body


def test_prefill_endpoint_returns_sets_with_fake(labeler_db: Path) -> None:
    fake_sets = [
        {
            "pokemon": "Pikachu",
            "ability": "Static",
            "item": "Light Ball",
            "move1": "Thunder",
            "move2": "Volt Tackle",
            "level": 50,
        }
    ]
    with _make_client(labeler_db, prefiller=FakePrefiller(sets=fake_sets)) as c:
        info = c.get("/api/prefill").json()
        assert info == {"name": "fake", "available": True}

        r = c.post("/api/prefill/nugget_bridge/1")
        assert r.status_code == 200
        body = r.json()
        assert body["prefiller"] == "fake"
        assert body["sets"] == fake_sets


def test_prefill_endpoint_503_when_unavailable(labeler_db: Path) -> None:
    unavailable = FakePrefiller()
    unavailable.available = False
    with _make_client(labeler_db, prefiller=unavailable) as c:
        r = c.post("/api/prefill/nugget_bridge/1")
        assert r.status_code == 503


def test_prefill_endpoint_502_on_exception(labeler_db: Path) -> None:
    with _make_client(labeler_db, prefiller=FakePrefiller(should_raise=True)) as c:
        r = c.post("/api/prefill/nugget_bridge/1")
        assert r.status_code == 502


def test_prefill_endpoint_404_missing_article(labeler_db: Path) -> None:
    with _make_client(labeler_db, prefiller=FakePrefiller()) as c:
        r = c.post("/api/prefill/nugget_bridge/9999")
        assert r.status_code == 404


def test_correction_rate_empty_when_no_labels(client) -> None:
    r = client.get("/api/stats/correction-rate")
    assert r.status_code == 200
    body = r.json()
    assert body["labeled_count"] == 0
    assert body["prefilled_count"] == 0
    assert body["fields"]["ability"]["rate"] is None


def test_correction_rate_aggregates_corrections(client) -> None:
    # Article 1: pre-filled, labeler corrected ability + item (2 corrections, 1 set)
    payload1 = {
        "status": "labeled",
        "sets": [{"pokemon": "Pikachu", "ability": "Static", "item": "Light Ball"}],
        "prefill_used": True,
        "fields_corrected_count": 2,
        "fields_corrected": {
            "count": 2,
            "set_count": 1,
            "fields": {"ability": 1, "item": 1},
        },
    }
    r = client.post("/api/labels/nugget_bridge/1", json=payload1)
    assert r.status_code == 200

    # Article 2: pre-filled, no corrections (0 out of 1 set)
    payload2 = {
        "status": "labeled",
        "sets": [{"pokemon": "Garchomp"}],
        "prefill_used": True,
        "fields_corrected_count": 0,
        "fields_corrected": {"count": 0, "set_count": 1, "fields": {}},
    }
    r = client.post("/api/labels/nugget_bridge/2", json=payload2)
    assert r.status_code == 200

    r = client.get("/api/stats/correction-rate?source=nugget_bridge")
    assert r.status_code == 200
    body = r.json()
    assert body["labeled_count"] == 2
    assert body["prefilled_count"] == 2
    # ability: 1 correction across 2 sets → 0.5
    ability = body["fields"]["ability"]
    assert ability["corrected"] == 1
    assert ability["total_sets"] == 2
    assert ability["rate"] == pytest.approx(0.5)
    # move1 never corrected → 0 / 2 = 0.0
    assert body["fields"]["move1"]["rate"] == pytest.approx(0.0)


def test_correction_rate_excludes_non_prefilled_labels(client) -> None:
    # Label article 1 without pre-fill → should NOT count in correction-rate denom
    r = client.post(
        "/api/labels/nugget_bridge/1",
        json={
            "status": "labeled",
            "sets": [{"pokemon": "Pikachu"}],
            "prefill_used": False,
            "fields_corrected_count": 0,
        },
    )
    assert r.status_code == 200
    body = client.get("/api/stats/correction-rate").json()
    assert body["labeled_count"] == 1
    assert body["prefilled_count"] == 0
    assert body["fields"]["ability"]["total_sets"] == 0


# =============================================================================
# Prefill module directly
# =============================================================================


async def test_stub_prefiller_returns_empty() -> None:
    from smogon_vgc_mcp.labeler.prefill import StubPrefiller

    sp = StubPrefiller()
    assert sp.available is True
    assert await sp.prefill(title="t", content_text="c") == []


def test_anthropic_prefiller_unavailable_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from smogon_vgc_mcp.labeler.prefill import AnthropicPrefiller, get_default_prefiller

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert AnthropicPrefiller().available is False
    # Default falls back to stub when no key
    assert get_default_prefiller().name == "stub"


# =============================================================================
# Triage
# =============================================================================


class FakeTriager:
    name: str = "fake-triager"
    available: bool = True

    def __init__(self, *, result: bool | None = True, should_raise: bool = False):
        self._result = result
        self._raise = should_raise

    async def classify(self, *, title: str, content_text: str) -> bool | None:
        if self._raise:
            raise RuntimeError("boom")
        return self._result


def test_triage_info_endpoint(labeler_db: Path) -> None:
    with _make_client(labeler_db, triager=FakeTriager()) as c:
        r = c.get("/api/triage")
        assert r.status_code == 200
        assert r.json() == {"name": "fake-triager", "available": True}


def test_triage_batch_classifies_articles(labeler_db: Path) -> None:
    with _make_client(labeler_db, triager=FakeTriager(result=True)) as c:
        r = c.post("/api/triage/nugget_bridge?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert body["triaged"] == 2  # 2 articles with fetch_status=ok
        assert all(x["triage_result"] == "has_sets" for x in body["results"])

        # Articles list now includes triage_result
        r = c.get("/api/articles?source=nugget_bridge")
        items = r.json()["items"]
        triaged = [i for i in items if i.get("triage_result") == "has_sets"]
        assert len(triaged) == 2


def test_triage_no_sets_classification(labeler_db: Path) -> None:
    with _make_client(labeler_db, triager=FakeTriager(result=False)) as c:
        r = c.post("/api/triage/nugget_bridge?limit=10")
        assert r.status_code == 200
        assert all(x["triage_result"] == "no_sets" for x in r.json()["results"])


def test_triage_503_when_unavailable(labeler_db: Path) -> None:
    t = FakeTriager()
    t.available = False
    with _make_client(labeler_db, triager=t) as c:
        r = c.post("/api/triage/nugget_bridge")
        assert r.status_code == 503


def test_triage_skips_already_triaged(labeler_db: Path) -> None:
    with _make_client(labeler_db, triager=FakeTriager(result=True)) as c:
        # First run triages everything
        r1 = c.post("/api/triage/nugget_bridge?limit=10")
        assert r1.json()["triaged"] == 2

        # Second run finds nothing new
        r2 = c.post("/api/triage/nugget_bridge?limit=10")
        assert r2.json()["triaged"] == 0


def test_triage_unknown_source_404(labeler_db: Path) -> None:
    with _make_client(labeler_db, triager=FakeTriager()) as c:
        r = c.post("/api/triage/nope")
        assert r.status_code == 404


async def test_stub_triager_returns_none() -> None:
    from smogon_vgc_mcp.labeler.triage import StubTriager

    t = StubTriager()
    assert t.available is True
    assert await t.classify(title="t", content_text="c") is None


def test_anthropic_triager_unavailable_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from smogon_vgc_mcp.labeler.triage import AnthropicTriager, get_default_triager

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert AnthropicTriager().available is False
    assert get_default_triager().name == "stub"
