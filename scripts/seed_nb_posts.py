#!/usr/bin/env python3
"""Seed nb_posts with a handful of Nugget Bridge articles for smoke testing.

Usage:
    uv run python scripts/seed_nb_posts.py
"""

from __future__ import annotations

import asyncio
import sys

from smogon_vgc_mcp.database.nugget_bridge_queries import upsert_post
from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.fetcher.nugget_bridge import extract_post_fields

SEED_COUNT = 10


async def list_recent_posts(count: int = 10) -> list[dict]:
    """Fetch a page of posts from the NB WordPress API."""
    from smogon_vgc_mcp.utils import fetch_json_resilient

    url = f"https://nuggetbridge.com/wp-json/wp/v2/posts?per_page={count}&orderby=date&order=desc"
    result = await fetch_json_resilient(url, service="nugget_bridge")
    if not result.success or result.data is None:
        print(f"Failed to list posts: {result.error}", file=sys.stderr)
        return []
    return result.data if isinstance(result.data, list) else []


async def main() -> None:
    db_path = get_db_path()
    print(f"Database: {db_path}")

    await init_database(db_path)

    print(f"Fetching {SEED_COUNT} posts from Nugget Bridge API...")
    posts = await list_recent_posts(SEED_COUNT)

    if not posts:
        print("No posts returned from API. NB may be down.", file=sys.stderr)
        sys.exit(1)

    print(f"Got {len(posts)} posts. Inserting into nb_posts...")
    async with get_connection(db_path) as db:
        for raw in posts:
            fields = extract_post_fields(raw)
            await upsert_post(db, **fields)
            print(f"  #{fields['id']}: {fields['title'][:60]}")
        await db.commit()

    print(f"\nDone. Seeded {len(posts)} posts into {db_path}")
    print("Run: uv run --extra labeler vgc-label")


if __name__ == "__main__":
    asyncio.run(main())
