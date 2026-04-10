"""Fetch Nugget Bridge posts from the WordPress REST API.

Nugget Bridge runs an old (WP 4.9) WordPress install with the public
``/wp-json/wp/v2/posts`` endpoint exposed. The corpus is frozen — last
post 2016-12-25 — so we cache raw JSON to disk **before** parsing so
that re-runs (after changing the extraction prompt, chunker rules, or
embedding model) never re-hit the dormant origin.

Only single-post fetch is implemented in this phase; the full-corpus
crawl lands in PR 2 with cost caps and ``--resume`` handling.
"""

from __future__ import annotations

import json
from pathlib import Path

from smogon_vgc_mcp.database.schema import get_db_path
from smogon_vgc_mcp.logging import get_logger
from smogon_vgc_mcp.resilience import FetchResult
from smogon_vgc_mcp.utils import fetch_json_resilient

logger = get_logger(__name__)

NUGGET_BRIDGE_API_BASE = "https://nuggetbridge.com/wp-json/wp/v2"
SERVICE_NAME = "nugget_bridge"


def get_raw_cache_dir(db_path: Path | None = None) -> Path:
    """Return the directory holding raw WP JSON blobs.

    Lives next to ``data/smogon.db`` so cache and database share the
    same deployment volume.
    """
    if db_path is None:
        db_path = get_db_path()
    return db_path.parent / "nugget_bridge" / "raw"


def _raw_cache_path(post_id: int, db_path: Path | None = None) -> Path:
    return get_raw_cache_dir(db_path) / f"{post_id}.json"


def load_cached_post(post_id: int, db_path: Path | None = None) -> dict | None:
    """Return the cached raw WP post JSON for ``post_id``, or ``None``
    if no cache file exists."""
    path = _raw_cache_path(post_id, db_path)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to read cached post %s: %s", post_id, e)
        return None


def _write_cache(post_id: int, payload: dict, db_path: Path | None = None) -> Path:
    path = _raw_cache_path(post_id, db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
    return path


async def fetch_post_by_id(
    post_id: int,
    db_path: Path | None = None,
    use_cache: bool = True,
) -> FetchResult[dict]:
    """Fetch one Nugget Bridge post by WP ID, caching raw JSON to disk.

    Args:
        post_id: WordPress post id.
        db_path: Override database path (the cache lives next to it).
        use_cache: When True (default), return the cached copy if
            present and skip the network call entirely. Pass False to
            force a refresh.

    Returns:
        ``FetchResult`` wrapping the raw WP post dict. On cache hit the
        result is always successful.
    """
    if use_cache:
        cached = load_cached_post(post_id, db_path)
        if cached is not None:
            logger.debug("Nugget Bridge cache hit for post %s", post_id)
            return FetchResult.ok(cached)

    url = f"{NUGGET_BRIDGE_API_BASE}/posts/{post_id}"
    result = await fetch_json_resilient(url, service=SERVICE_NAME)
    if result.success and result.data is not None:
        try:
            _write_cache(post_id, result.data, db_path)
        except OSError as e:
            # Cache write failure is non-fatal; the caller still gets the
            # payload. Logged loudly because it undermines resume safety.
            logger.error("Failed to write raw cache for post %s: %s", post_id, e)
    return result


def extract_post_fields(raw: dict) -> dict:
    """Flatten a WP REST ``posts`` payload into the shape expected by
    ``nb_posts`` upserts.

    The WP payload wraps rendered HTML in ``{"rendered": "..."}`` objects
    and exposes categories/tags as integer IDs. We store the ids as JSON
    for now; the name resolution happens in the ingest entry point,
    which has ``/wp-json/wp/v2/categories`` available.
    """
    title = (raw.get("title") or {}).get("rendered", "") or ""
    content_html = (raw.get("content") or {}).get("rendered", "") or ""
    return {
        "id": int(raw["id"]),
        "slug": raw.get("slug", "") or "",
        "url": raw.get("link", "") or "",
        "title": title,
        "published_at": raw.get("date_gmt"),
        "modified_at": raw.get("modified_gmt"),
        "author": str(raw.get("author", "") or ""),
        "categories_json": json.dumps(raw.get("categories", []) or []),
        "tags_json": json.dumps(raw.get("tags", []) or []),
        "content_html": content_html,
    }
