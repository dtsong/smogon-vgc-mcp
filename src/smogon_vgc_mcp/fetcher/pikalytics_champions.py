"""Parse Pokemon Champions usage data from Pikalytics.

URL pattern:
  https://www.pikalytics.com/pokedex/championspreview/<pokemon_slug>

Each page is server-rendered HTML and embeds several JSON-LD blocks.
The FAQPage JSON-LD block contains structured answer text with percentage
data for moves, items, abilities, and teammates.  We parse that block first
for the four sections, and fall back to plain-text search for the top-level
usage percentage.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import aiosqlite
from bs4 import BeautifulSoup

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.resilience import get_all_circuit_states
from smogon_vgc_mcp.utils import fetch_text_resilient

# Matches "Label Name (41.092%)" patterns in FAQ answer text
_FAQ_ENTRY_RE = re.compile(r"([A-Za-z][^(]+?)\s*\(([\d.]+)%\)")
_USAGE_RE = re.compile(r"Usage\s+Percent\s+([\d.]+)\s*%", re.I)

# Preamble terminators: FAQ answers start with "The top X are ...", "... synergizes well with ..."
_PREAMBLE_SEPS = (" are ", " include ", " is ", " with ")


def _strip_faq_preamble(answer: str) -> str:
    """Strip the introductory sentence from a Pikalytics FAQ answer.

    Answers like "The top moves for Incineroar ... are Fake Out (41%)" have a
    prose preamble before the first real entry name.  Split on the last
    occurrence of a known terminator and keep the trailing portion so the
    first regex match starts at the entry name rather than the preamble.
    """
    for sep in _PREAMBLE_SEPS:
        idx = answer.rfind(sep)
        if idx >= 0:
            return answer[idx + len(sep) :]
    return answer


def _extract_faq_answers(soup: BeautifulSoup) -> dict[str, str]:
    """Return a mapping of lowercased question keyword -> answer text from FAQPage JSON-LD."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict) or payload.get("@type") != "FAQPage":
            continue
        answers: dict[str, str] = {}
        for item in payload.get("mainEntity", []):
            if not isinstance(item, dict):
                continue
            question = (item.get("name") or "").lower()
            answer_obj = item.get("acceptedAnswer", {})
            answer_text = answer_obj.get("text", "") if isinstance(answer_obj, dict) else ""
            answers[question] = answer_text
        return answers
    return {}


def _parse_faq_section(answers: dict[str, str], keyword: str) -> list[tuple[str, float]]:
    """Find the answer whose question contains *keyword* and extract (name, pct) pairs."""
    for question, text in answers.items():
        if keyword not in question:
            continue
        results: list[tuple[str, float]] = []
        for m in _FAQ_ENTRY_RE.finditer(_strip_faq_preamble(text)):
            name = m.group(1).strip()
            try:
                pct = float(m.group(2))
            except ValueError:
                continue
            if name:
                results.append((name, pct))
        if results:
            return results
    return []


def parse_pikalytics_page(html: str, pokemon_slug: str) -> dict[str, Any] | None:
    """Parse a Pikalytics championspreview page into a usage dict.

    Returns None for empty or 404-style pages.  Returned dict has keys:
      pokemon, usage_percent, rank, raw_count,
      moves, items, abilities, teammates
    """
    if not html or len(html.strip()) < 200:
        return None
    if "Not Found" in html[:500]:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # --- Top-level usage percent from visible page text ---
    usage_percent: float | None = None
    body_text = soup.get_text(" ", strip=True)
    m = _USAGE_RE.search(body_text)
    if m:
        try:
            usage_percent = float(m.group(1))
        except ValueError:
            pass

    # --- Section data from FAQPage JSON-LD ---
    faq = _extract_faq_answers(soup)
    moves = _parse_faq_section(faq, "move")
    items = _parse_faq_section(faq, "item")
    abilities = _parse_faq_section(faq, "abilit")
    teammates = _parse_faq_section(faq, "teammate")

    # Require at least one signal to consider the page valid
    if usage_percent is None and not moves and not items and not abilities:
        return None

    return {
        "pokemon": pokemon_slug,
        "usage_percent": usage_percent,
        "rank": None,
        "raw_count": None,
        "moves": moves,
        "items": items,
        "abilities": abilities,
        "teammates": teammates,
    }


PIKALYTICS_URL_TEMPLATE = "https://www.pikalytics.com/pokedex/championspreview/{slug}"

# Known Champions Pokemon with Pikalytics data (as of 2026-04-08)
PIKALYTICS_POKEMON_SLUGS = [
    "incineroar",
    "sneasler",
    "sinistcha",
    "archaludon",
    "whimsicott",
    "pelipper",
    "ursaluna",
    "garchomp",
    "farigiraf",
    "dragonite",
    "charizard",
    "basculegion",
    "tyranitar",
    "kingambit",
]

ELO_CUTOFFS = ["0+", "1500+", "1630+", "1760+"]


async def store_champions_usage(
    db: aiosqlite.Connection,
    elo_cutoff: str,
    pokemon_data: list[dict],
    *,
    _commit: bool = True,
) -> tuple[int, int]:
    """Upsert a Pikalytics snapshot for one ELO cutoff.

    Deletes any existing snapshot for this (source, elo_cutoff) so child
    rows are cleared via ON DELETE CASCADE, then inserts a fresh snapshot
    and its children. Returns (snapshot_id, pokemon_count).
    """
    await db.execute(
        "DELETE FROM champions_usage_snapshots WHERE source = 'pikalytics' AND elo_cutoff = ?",
        (elo_cutoff,),
    )

    cursor = await db.execute(
        "INSERT INTO champions_usage_snapshots (elo_cutoff, source) VALUES (?, 'pikalytics')",
        (elo_cutoff,),
    )
    snapshot_id = cursor.lastrowid
    assert snapshot_id is not None

    count = 0
    for entry in pokemon_data:
        poke_cursor = await db.execute(
            """INSERT INTO champions_pokemon_usage
               (snapshot_id, pokemon, usage_percent, rank, raw_count)
               VALUES (?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                entry["pokemon"],
                entry.get("usage_percent"),
                entry.get("rank"),
                entry.get("raw_count"),
            ),
        )
        pu_id = poke_cursor.lastrowid
        assert pu_id is not None

        for move, pct in entry.get("moves", []):
            await db.execute(
                "INSERT INTO champions_usage_moves"
                " (pokemon_usage_id, move, percent) VALUES (?, ?, ?)",
                (pu_id, move, pct),
            )
        for item, pct in entry.get("items", []):
            await db.execute(
                "INSERT INTO champions_usage_items"
                " (pokemon_usage_id, item, percent) VALUES (?, ?, ?)",
                (pu_id, item, pct),
            )
        for ability, pct in entry.get("abilities", []):
            await db.execute(
                "INSERT INTO champions_usage_abilities"
                " (pokemon_usage_id, ability, percent) VALUES (?, ?, ?)",
                (pu_id, ability, pct),
            )
        for teammate, pct in entry.get("teammates", []):
            await db.execute(
                "INSERT INTO champions_usage_teammates"
                " (pokemon_usage_id, teammate, percent) VALUES (?, ?, ?)",
                (pu_id, teammate, pct),
            )
        count += 1

    if _commit:
        await db.commit()
    return snapshot_id, count


async def fetch_pikalytics_pokemon(slug: str) -> tuple[dict | None, str | None]:
    """Fetch a single Pokemon page from Pikalytics and parse it.

    Returns (parsed_data, error_message). On success, error_message is None.
    On failure, parsed_data is None and error_message describes why.
    """
    url = PIKALYTICS_URL_TEMPLATE.format(slug=slug)
    result = await fetch_text_resilient(url, service="pikalytics")
    if not result.success or not result.data:
        err = result.error.message if result.error else "fetch returned no data"
        return None, err
    parsed = parse_pikalytics_page(result.data, pokemon_slug=slug)
    if parsed is None:
        return None, "parser returned None (404 or unparseable page)"
    return parsed, None


async def fetch_and_store_pikalytics_champions(
    db_path: Path | None = None,
    *,
    elo_cutoff: str = "0+",
    dry_run: bool = False,
    slugs: list[str] | None = None,
    request_delay: float = 1.0,
) -> dict:
    """Fetch all Pikalytics Champions pages and store atomically.

    One snapshot per ELO cutoff. Callers loop over cutoffs themselves.
    """
    if db_path is None:
        db_path = get_db_path()
    await init_database(db_path)

    target_slugs = slugs if slugs is not None else PIKALYTICS_POKEMON_SLUGS
    errors: list[dict] = []
    results: list[dict] = []

    for slug in target_slugs:
        data, err = await fetch_pikalytics_pokemon(slug)
        if data is None:
            errors.append({"slug": slug, "message": err or "unknown error"})
        else:
            results.append(data)
        if request_delay > 0:
            await asyncio.sleep(request_delay)

    if dry_run:
        return {
            "fetched": len(results),
            "stored": 0,
            "errors": errors,
            "circuit_states": get_all_circuit_states(),
            "dry_run": True,
            "results": results,
        }

    snapshot_id = 0
    stored = 0
    async with get_connection(db_path) as db:
        try:
            snapshot_id, stored = await store_champions_usage(
                db, elo_cutoff=elo_cutoff, pokemon_data=results, _commit=False
            )
            await db.commit()
        except aiosqlite.Error as exc:
            await db.rollback()
            errors.append({"slug": "store", "message": str(exc)})

    return {
        "fetched": len(results),
        "stored": stored,
        "snapshot_id": snapshot_id,
        "elo_cutoff": elo_cutoff,
        "errors": errors,
        "circuit_states": get_all_circuit_states(),
        "dry_run": False,
    }
