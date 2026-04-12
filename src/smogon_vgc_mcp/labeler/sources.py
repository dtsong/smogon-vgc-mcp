"""Article source abstraction for the labeler.

The labeler UI is source-agnostic: it pulls candidate articles from any
implementation of :class:`ArticleSource`. Nugget Bridge is the first
adapter; the other four historical sources (Trainer Tower, Victory Road,
Nimbasa City Post, Boiler Room VGC, imoutoisland) drop in as additional
Protocol implementations later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import aiosqlite


@dataclass(frozen=True)
class ArticleSummary:
    """Minimal row for the article list pane."""

    article_id: str
    source: str
    title: str
    url: str
    published_at: str | None
    format: str | None


@dataclass(frozen=True)
class ArticleDetail:
    """Full article body for the editor pane."""

    article_id: str
    source: str
    title: str
    url: str
    published_at: str | None
    format: str | None
    content_html: str
    content_text: str | None


class ArticleSource(Protocol):
    """Read-only adapter over one historical content source."""

    source_name: str

    async def list_articles(
        self,
        db: aiosqlite.Connection,
        *,
        format: str | None,
        limit: int,
        offset: int,
    ) -> list[ArticleSummary]:
        """Return articles eligible for labeling, newest first."""
        ...

    async def get_article(self, db: aiosqlite.Connection, article_id: str) -> ArticleDetail | None:
        """Return the full article body, or None if not found."""
        ...


class NuggetBridgeSource:
    """ArticleSource backed by the ``nb_posts`` table."""

    source_name: str = "nugget_bridge"

    async def list_articles(
        self,
        db: aiosqlite.Connection,
        *,
        format: str | None,
        limit: int,
        offset: int,
    ) -> list[ArticleSummary]:
        db.row_factory = aiosqlite.Row
        clauses = ["fetch_status = 'ok'"]
        params: list[object] = []
        if format:
            clauses.append("format = ?")
            params.append(format)
        where = " AND ".join(clauses)
        params.extend([limit, offset])
        query = (
            "SELECT id, title, url, published_at, format "
            f"FROM nb_posts WHERE {where} "
            "ORDER BY published_at DESC NULLS LAST, id DESC "
            "LIMIT ? OFFSET ?"
        )
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [
            ArticleSummary(
                article_id=str(row["id"]),
                source=self.source_name,
                title=row["title"],
                url=row["url"],
                published_at=row["published_at"],
                format=row["format"],
            )
            for row in rows
        ]

    async def get_article(self, db: aiosqlite.Connection, article_id: str) -> ArticleDetail | None:
        try:
            post_id = int(article_id)
        except ValueError:
            return None
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, title, url, published_at, format, content_html, content_text "
            "FROM nb_posts WHERE id = ?",
            (post_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return ArticleDetail(
            article_id=str(row["id"]),
            source=self.source_name,
            title=row["title"],
            url=row["url"],
            published_at=row["published_at"],
            format=row["format"],
            content_html=row["content_html"],
            content_text=row["content_text"],
        )


SOURCES: dict[str, ArticleSource] = {
    NuggetBridgeSource.source_name: NuggetBridgeSource(),
}


def get_source(name: str) -> ArticleSource:
    if name not in SOURCES:
        available = ", ".join(sorted(SOURCES))
        raise KeyError(f"Unknown article source: {name!r}. Available: {available}")
    return SOURCES[name]
