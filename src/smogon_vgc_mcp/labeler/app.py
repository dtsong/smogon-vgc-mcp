"""FastAPI application for the offline labeling workstation.

Routes:

- ``GET  /``                               — split-pane editor shell
- ``GET  /api/formats``                    — historical formats dropdown
- ``GET  /api/articles``                   — paged article list + status
- ``GET  /api/articles/{source}/{id}``     — full article + existing label
- ``POST /api/labels/{source}/{id}``       — save label + update state
- ``GET  /api/autocomplete``               — species/move/ability/item/nature
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from smogon_vgc_mcp.database.schema import get_connection, init_database
from smogon_vgc_mcp.formats import list_formats
from smogon_vgc_mcp.labeler.autocomplete import load_autocomplete
from smogon_vgc_mcp.labeler.sources import SOURCES, get_source
from smogon_vgc_mcp.labeler.storage import (
    label_output_path,
    list_states,
    read_label_json,
    upsert_state,
    write_label_json,
)

_HERE = Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"


class LabeledSet(BaseModel):
    """One Pokemon set within an article's golden label."""

    pokemon: str
    ability: str | None = None
    item: str | None = None
    nature: str | None = None
    tera_type: str | None = None
    ev_hp: int | None = None
    ev_atk: int | None = None
    ev_def: int | None = None
    ev_spa: int | None = None
    ev_spd: int | None = None
    ev_spe: int | None = None
    iv_hp: int | None = 31
    iv_atk: int | None = 31
    iv_def: int | None = 31
    iv_spa: int | None = 31
    iv_spd: int | None = 31
    iv_spe: int | None = 31
    move1: str | None = None
    move2: str | None = None
    move3: str | None = None
    move4: str | None = None
    level: int | None = 50
    raw_snippet: str | None = None


class LabelPayload(BaseModel):
    """Full payload posted by the UI when saving a golden label."""

    status: str = Field(pattern="^(labeled|skipped|in_progress)$")
    sets: list[LabeledSet] = Field(default_factory=list)
    prefill_used: bool = False
    fields_corrected_count: int = 0
    fields_corrected: dict[str, Any] | None = None
    notes: str | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Smogon VGC Labeler", version="0.1.0", lifespan=_lifespan)

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        index_path = _TEMPLATES_DIR / "index.html"
        if index_path.exists():
            return HTMLResponse(index_path.read_text())
        return HTMLResponse(
            "<!doctype html><title>VGC Labeler</title>"
            "<p>UI pending (Task L3). API is live — see <code>/docs</code>.</p>"
        )

    @app.get("/api/formats")
    async def get_formats() -> list[dict]:
        return [
            {"code": f.code, "name": f.name, "is_historical": f.is_historical}
            for f in list_formats()
            if f.is_historical
        ]

    @app.get("/api/sources")
    async def get_sources() -> list[str]:
        return sorted(SOURCES)

    @app.get("/api/articles")
    async def get_articles(
        source: str = "nugget_bridge",
        format: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        try:
            adapter = get_source(source)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        async with get_connection() as db:
            summaries = await adapter.list_articles(db, format=format, limit=limit, offset=offset)
            states = await list_states(db, source=source)

        items = []
        for summary in summaries:
            state = states.get(summary.article_id)
            items.append(
                {
                    **asdict(summary),
                    "status": (state or {}).get("status", "unlabeled"),
                    "labeled_at": (state or {}).get("labeled_at"),
                    "prefill_used": bool((state or {}).get("prefill_used", 0)),
                }
            )
        return {"items": items, "limit": limit, "offset": offset}

    @app.get("/api/articles/{source}/{article_id}")
    async def get_article(source: str, article_id: str) -> dict:
        try:
            adapter = get_source(source)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        async with get_connection() as db:
            detail = await adapter.get_article(db, article_id)
            if detail is None:
                raise HTTPException(status_code=404, detail="Article not found")
            state = await list_states(db, source=source)
            state_row = state.get(article_id)

        existing_label = read_label_json(source, article_id)

        return {
            "article": asdict(detail),
            "state": state_row,
            "label": existing_label,
        }

    @app.post("/api/labels/{source}/{article_id}")
    async def save_label(source: str, article_id: str, payload: LabelPayload) -> dict:
        if source not in SOURCES:
            raise HTTPException(status_code=404, detail=f"Unknown source: {source}")

        async with get_connection() as db:
            adapter = SOURCES[source]
            detail = await adapter.get_article(db, article_id)
            if detail is None:
                raise HTTPException(status_code=404, detail="Article not found")

            label_blob = {
                "article_id": article_id,
                "source": source,
                "format": detail.format,
                "url": detail.url,
                "title": detail.title,
                "sets": [s.model_dump() for s in payload.sets],
                "notes": payload.notes,
            }
            path = write_label_json(source, article_id, label_blob)

            await upsert_state(
                db,
                source=source,
                article_id=article_id,
                status=payload.status,
                output_path=str(path),
                prefill_used=payload.prefill_used,
                fields_corrected_count=payload.fields_corrected_count,
                fields_corrected_json=(
                    json.dumps(payload.fields_corrected)
                    if payload.fields_corrected is not None
                    else None
                ),
            )

        return {"ok": True, "output_path": str(path)}

    @app.get("/api/autocomplete")
    async def get_autocomplete() -> dict[str, list[str]]:
        async with get_connection() as db:
            return await load_autocomplete(db)

    @app.get("/api/labels/{source}/{article_id}/path")
    async def get_label_path(source: str, article_id: str) -> dict:
        return {"path": str(label_output_path(source, article_id))}

    return app
