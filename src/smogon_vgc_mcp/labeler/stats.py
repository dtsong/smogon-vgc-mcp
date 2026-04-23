"""Correction-rate aggregation for the labeler dashboard.

Each labeled article that used the pre-fill records which fields the
labeler changed in ``label_state.fields_corrected_json`` (shape:
``{"ability": 1, "item": 0, ...}`` summed across all sets). Dividing
corrected-field counts by the total opportunities yields a per-field
correction rate — the complement of the extractor's precision on
labeled articles. Use this as the steering metric while iterating on
the Tier-1 prompt.
"""

from __future__ import annotations

import json

import aiosqlite

FIELDS = [
    "pokemon",
    "ability",
    "item",
    "nature",
    "tera_type",
    "move1",
    "move2",
    "move3",
    "move4",
    "ev_hp",
    "ev_atk",
    "ev_def",
    "ev_spa",
    "ev_spd",
    "ev_spe",
    "level",
]


async def correction_rate_summary(db: aiosqlite.Connection, *, source: str | None = None) -> dict:
    """Aggregate correction counts across labeled, pre-filled articles.

    Returns a dict with ``labeled_count``, ``prefilled_count``, and a
    ``fields`` map of ``field → {corrected, total_sets, rate}``. ``total_sets``
    is the denominator used when computing the rate: the number of
    (article, set) pairs where this field *could* have been corrected.
    """
    db.row_factory = aiosqlite.Row
    clauses = ["status = 'labeled'", "prefill_used = 1"]
    params: list[object] = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    where = " AND ".join(clauses)
    query = f"SELECT fields_corrected_json FROM label_state WHERE {where}"

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()

    prefilled_count = len(rows)
    field_corrected: dict[str, int] = dict.fromkeys(FIELDS, 0)
    field_total: dict[str, int] = dict.fromkeys(FIELDS, 0)

    for row in rows:
        raw = row["fields_corrected_json"]
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        set_count = int(payload.get("set_count", 0) or 0)
        deltas = payload.get("fields") or {}
        for field in FIELDS:
            field_total[field] += set_count
            corrected = int(deltas.get(field, 0) or 0)
            field_corrected[field] += corrected

    async with db.execute(
        "SELECT COUNT(*) FROM label_state WHERE status = 'labeled'"
        + (" AND source = ?" if source else ""),
        ([source] if source else []),
    ) as cursor:
        labeled_count = (await cursor.fetchone())[0]

    return {
        "labeled_count": labeled_count,
        "prefilled_count": prefilled_count,
        "fields": {
            field: {
                "corrected": field_corrected[field],
                "total_sets": field_total[field],
                "rate": (
                    field_corrected[field] / field_total[field] if field_total[field] else None
                ),
            }
            for field in FIELDS
        },
    }
