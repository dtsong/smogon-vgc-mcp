"""Label-state CRUD + expected-JSON writer.

The JSON files under ``data/labels/<source>/<article_id>.json`` are the
source of truth for the F1 eval. ``label_state`` is an index keyed on
``(source, article_id)`` recording status, pre-fill usage, and the
corresponding on-disk path.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

DEFAULT_LABELS_DIR = Path(__file__).resolve().parents[3] / "data" / "labels"

LabelStatus = str  # "unlabeled" | "in_progress" | "labeled" | "skipped"


def get_labels_dir() -> Path:
    return DEFAULT_LABELS_DIR


def label_output_path(source: str, article_id: str, labels_dir: Path | None = None) -> Path:
    base = labels_dir or get_labels_dir()
    return base / source / f"{article_id}.json"


async def get_state(db: aiosqlite.Connection, source: str, article_id: str) -> dict | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM label_state WHERE source = ? AND article_id = ?",
        (source, article_id),
    ) as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else None


async def upsert_state(
    db: aiosqlite.Connection,
    *,
    source: str,
    article_id: str,
    status: LabelStatus,
    output_path: str | None = None,
    prefill_used: bool = False,
    fields_corrected_count: int = 0,
    fields_corrected_json: str | None = None,
) -> None:
    labeled_at = datetime.now(UTC).isoformat() if status == "labeled" else None
    await db.execute(
        """
        INSERT INTO label_state (
            article_id, source, status, labeled_at, prefill_used,
            fields_corrected_count, fields_corrected_json, output_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, article_id) DO UPDATE SET
            status = excluded.status,
            labeled_at = COALESCE(excluded.labeled_at, label_state.labeled_at),
            prefill_used = excluded.prefill_used,
            fields_corrected_count = excluded.fields_corrected_count,
            fields_corrected_json = excluded.fields_corrected_json,
            output_path = COALESCE(excluded.output_path, label_state.output_path)
        """,
        (
            article_id,
            source,
            status,
            labeled_at,
            1 if prefill_used else 0,
            fields_corrected_count,
            fields_corrected_json,
            output_path,
        ),
    )
    await db.commit()


async def list_states(
    db: aiosqlite.Connection,
    *,
    source: str,
    statuses: list[str] | None = None,
) -> dict[str, dict]:
    """Return ``{article_id: state_row}`` for the source."""
    db.row_factory = aiosqlite.Row
    query = "SELECT * FROM label_state WHERE source = ?"
    params: list[object] = [source]
    if statuses:
        placeholders = ",".join("?" * len(statuses))
        query += f" AND status IN ({placeholders})"
        params.extend(statuses)
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return {row["article_id"]: dict(row) for row in rows}


async def set_triage_result(
    db: aiosqlite.Connection,
    *,
    source: str,
    article_id: str,
    triage_result: str,
) -> None:
    await db.execute(
        """
        INSERT INTO label_state (article_id, source, status, triage_result)
        VALUES (?, ?, 'unlabeled', ?)
        ON CONFLICT(source, article_id) DO UPDATE SET
            triage_result = excluded.triage_result
        """,
        (article_id, source, triage_result),
    )
    await db.commit()


def write_label_json(
    source: str,
    article_id: str,
    payload: dict,
    labels_dir: Path | None = None,
) -> Path:
    """Write the golden JSON for an article. Returns the path written."""
    path = label_output_path(source, article_id, labels_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def read_label_json(source: str, article_id: str, labels_dir: Path | None = None) -> dict | None:
    path = label_output_path(source, article_id, labels_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text())
