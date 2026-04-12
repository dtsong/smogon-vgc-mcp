"""CRUD helpers for the Nugget Bridge archive tables.

All helpers take an already-open ``aiosqlite.Connection``. The ingest
entry point owns the transaction and the connection lifecycle; these
functions just translate domain operations into SQL and do not commit
on their own unless explicitly noted.
"""

from __future__ import annotations

from collections.abc import Iterable

import aiosqlite

from smogon_vgc_mcp.fetcher.nugget_bridge_chunk import Chunk

# Stage columns allowed by ``mark_stage_status``. Narrow allow-list so a
# caller can't write to an arbitrary column.
_STAGE_COLUMNS = frozenset({"fetch_status", "extract_status", "chunk_status", "embed_status"})
_STATUS_VALUES = frozenset({"pending", "ok", "failed"})


async def upsert_post(
    db: aiosqlite.Connection,
    *,
    id: int,
    slug: str,
    url: str,
    title: str,
    content_html: str,
    published_at: str | None = None,
    modified_at: str | None = None,
    author: str | None = None,
    categories_json: str | None = None,
    tags_json: str | None = None,
    category: str | None = None,
    content_text: str | None = None,
    format: str | None = None,
    format_confidence: str | None = None,
    content_hash: str | None = None,
) -> None:
    """Insert or update a row in ``nb_posts`` keyed on WP post id.

    Does **not** reset pipeline status columns — an idempotent refetch of
    the same row leaves extract/chunk/embed progress intact. Callers
    that want to force re-processing should explicitly call
    :func:`mark_stage_status` afterwards.
    """
    await db.execute(
        """
        INSERT INTO nb_posts (
            id, slug, url, title, published_at, modified_at, author,
            categories_json, tags_json, category, content_html, content_text,
            format, format_confidence, content_hash, fetch_status, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            slug = excluded.slug,
            url = excluded.url,
            title = excluded.title,
            published_at = excluded.published_at,
            modified_at = excluded.modified_at,
            author = excluded.author,
            categories_json = excluded.categories_json,
            tags_json = excluded.tags_json,
            category = COALESCE(excluded.category, nb_posts.category),
            content_html = excluded.content_html,
            content_text = COALESCE(excluded.content_text, nb_posts.content_text),
            format = COALESCE(excluded.format, nb_posts.format),
            format_confidence = COALESCE(excluded.format_confidence, nb_posts.format_confidence),
            content_hash = excluded.content_hash,
            fetch_status = 'ok',
            fetched_at = CURRENT_TIMESTAMP
        """,
        (
            id,
            slug,
            url,
            title,
            published_at,
            modified_at,
            author,
            categories_json,
            tags_json,
            category,
            content_html,
            content_text,
            format,
            format_confidence,
            content_hash,
        ),
    )


async def mark_stage_status(
    db: aiosqlite.Connection,
    post_id: int,
    stage: str,
    status: str,
    error: str | None = None,
) -> None:
    """Update one of the ``*_status`` columns on ``nb_posts``.

    Args:
        stage: One of ``fetch_status``, ``extract_status``,
            ``chunk_status``, ``embed_status``.
        status: ``pending`` | ``ok`` | ``failed``.
        error: Optional error message, stored in the matching
            ``*_error`` column when it exists (only extract/embed have
            dedicated error columns).
    """
    if stage not in _STAGE_COLUMNS:
        raise ValueError(f"Unknown stage column: {stage!r}")
    if status not in _STATUS_VALUES:
        raise ValueError(f"Invalid status value: {status!r}")

    # Known columns, narrow interpolation is safe.
    await db.execute(
        f"UPDATE nb_posts SET {stage} = ? WHERE id = ?",
        (status, post_id),
    )
    if error is not None and stage in ("extract_status", "embed_status"):
        error_col = "extract_error" if stage == "extract_status" else "embed_error"
        await db.execute(
            f"UPDATE nb_posts SET {error_col} = ? WHERE id = ?",
            (error, post_id),
        )


async def get_post(db: aiosqlite.Connection, post_id: int) -> dict | None:
    """Return an ``nb_posts`` row as a dict, or ``None`` if absent."""
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM nb_posts WHERE id = ?", (post_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_posts_by_stage(
    db: aiosqlite.Connection,
    stage: str,
    status: str,
    limit: int | None = None,
) -> list[dict]:
    """Return rows whose ``<stage>`` column equals ``status``, ordered
    by id. Handy for iterating pipeline work queues."""
    if stage not in _STAGE_COLUMNS:
        raise ValueError(f"Unknown stage column: {stage!r}")
    if status not in _STATUS_VALUES:
        raise ValueError(f"Invalid status value: {status!r}")

    db.row_factory = aiosqlite.Row
    query = f"SELECT * FROM nb_posts WHERE {stage} = ? ORDER BY id"
    params: tuple = (status,)
    if limit is not None:
        query += " LIMIT ?"
        params = (status, limit)
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def replace_chunks(
    db: aiosqlite.Connection,
    post_id: int,
    chunks: Iterable[Chunk],
    *,
    format: str | None = None,
    published_at: str | None = None,
    title: str | None = None,
    url: str | None = None,
    category: str | None = None,
    pokemon_mentions_json: str | None = None,
) -> int:
    """Replace all chunks for a post in one transaction-local pass.

    Deletes any existing ``nb_chunks`` rows for the post (cascade drops
    their embeddings, so the post will need re-embedding), then bulk
    inserts the new chunks with denormalized post metadata for
    filter-then-rank semantic queries.

    Returns the number of chunks inserted.
    """
    await db.execute("DELETE FROM nb_chunks WHERE post_id = ?", (post_id,))

    rows = [
        (
            post_id,
            chunk.chunk_index,
            chunk.text,
            chunk.token_count,
            chunk.section_heading,
            format,
            published_at,
            title,
            url,
            category,
            pokemon_mentions_json,
        )
        for chunk in chunks
    ]
    if not rows:
        return 0

    await db.executemany(
        """
        INSERT INTO nb_chunks (
            post_id, chunk_index, text, token_count, section_heading,
            format, published_at, title, url, category, pokemon_mentions_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


async def count_by_stage(db: aiosqlite.Connection) -> dict[str, dict[str, int]]:
    """Return per-stage status counts for ``nugget_bridge_status`` /
    admin display.

    Shape: ``{"fetch": {"ok": 894, "failed": 0, "pending": 0}, ...}``.
    """
    out: dict[str, dict[str, int]] = {}
    for stage in _STAGE_COLUMNS:
        key = stage.removesuffix("_status")
        out[key] = {v: 0 for v in _STATUS_VALUES}
        async with db.execute(f"SELECT {stage}, COUNT(*) FROM nb_posts GROUP BY {stage}") as cursor:
            async for status, count in cursor:
                if status in out[key]:
                    out[key][status] = count
    return out
