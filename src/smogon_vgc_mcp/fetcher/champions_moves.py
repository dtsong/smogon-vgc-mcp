"""Parse Pokemon Champions move changes from Serebii.

Page: https://www.serebii.net/pokemonchampions/updatedattacks.shtml

The page contains a single <table class="tab"> where each move occupies two
rows — a "Champions" row and an "S/V" row.  The Champions row (9 cells) has:
  [0] move name (rowspan=2, contains <a href="...">Name</a>)
  [1] "Champions" label
  [2] type image
  [3] category image (physical / special / other/status; sometimes rowspan=2)
  [4] PP
  [5] Base Power ("--" for status moves)
  [6] Accuracy (101 means "always hits" → stored as None)
  [7] effect description (rowspan=2)
  [8] effect chance

Only Champions-game values are extracted; S/V rows are ignored.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import aiosqlite
from bs4 import BeautifulSoup, Tag

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.resilience import get_all_circuit_states
from smogon_vgc_mcp.utils import fetch_text_resilient

logger = logging.getLogger(__name__)

SEREBII_MOVES_URL = "https://www.serebii.net/pokemonchampions/updatedattacks.shtml"

# Maps category image filename stem to canonical category string.
_CATEGORY_MAP: dict[str, str] = {
    "physical": "Physical",
    "special": "Special",
    "other": "Status",
    "status": "Status",
}

# Matches "/type/<name>.gif" or "/type/<name>.png" in img src attributes.
_TYPE_SRC_RE = re.compile(r"/type/([a-z]+)\.(?:gif|png)$", re.I)

# Legitimate "no value" sentinels for numeric cells (status moves, etc.).
# Anything else that fails int() is a layout regression and must be surfaced,
# not silently coerced to None.
_NUMERIC_SENTINELS = frozenset({"", "--", "—", "-"})


class ParseError(ValueError):
    """Raised when a numeric cell contains unparseable non-sentinel text."""


def _slugify_move(name: str) -> str:
    """Convert a move name to a lowercase alphanumeric slug (no separators)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _parse_int_or_none(text: str, *, field: str = "value") -> int | None:
    """Return int if parseable, None for documented sentinels, raise on garbage.

    Sentinels (legitimate "no value"): "", "--", "—", "-", and 101 in the
    accuracy column (Serebii's "always hits" marker). Any other text that
    fails int() is a parser regression and raises ParseError so the caller
    can surface it rather than silently coercing to None.
    """
    cleaned = text.strip()
    if cleaned in _NUMERIC_SENTINELS:
        return None
    try:
        val = int(cleaned)
    except ValueError as exc:
        raise ParseError(f"unparseable {field}: {cleaned!r}") from exc
    # 101 is Serebii's sentinel for "always hits" in the accuracy column.
    if field == "accuracy" and val == 101:
        return None
    return val


def _type_from_img(td: Tag) -> str | None:
    """Extract a type name from an img src within the given td."""
    img = td.find("img")
    if not img:
        return None
    src = img.get("src") or ""
    m = _TYPE_SRC_RE.search(src.lower())
    if not m:
        return None
    return m.group(1).capitalize()


def _category_from_img(td: Tag) -> str | None:
    """Extract a category string from an img src within the given td."""
    img = td.find("img")
    if not img:
        return None
    src = (img.get("src") or "").lower()
    # Serebii serves category icons (physical/special/other) from the same /type/ path as types.
    m = _TYPE_SRC_RE.search(src)
    if not m:
        return None
    key = m.group(1).lower()
    return _CATEGORY_MAP.get(key)


def parse_serebii_moves_page(
    html: str,
    skip_reasons: dict[str, int] | None = None,
) -> list[dict]:
    """Parse the Serebii updated attacks page into a list of move dicts.

    Each dict contains:
      id           – lowercase alphanumeric slug (e.g. "ironhead")
      name         – display name (e.g. "Iron Head")
      type         – type string (e.g. "Steel")
      category     – "Physical" | "Special" | "Status"
      base_power   – int or None for status moves
      accuracy     – int or None for moves that always hit
      pp           – int or None if unparseable
      priority     – always 0 (not on this page)
      target       – always None (not on this page)
      description  – effect text or None
      short_desc   – same as description (Serebii provides one text;
                     mirrored for schema parity with ChampionsDexMove)

    Rows skipped for unexpected reasons (missing type/category image,
    empty name, garbage numeric cells) are counted into *skip_reasons* if
    provided so the caller can surface layout regressions. Structural
    skips (header rows, S/V rows) are silent.

    Returns an empty list for empty or malformed HTML.
    """
    if not html or len(html.strip()) < 100:
        logger.warning(
            "Serebii moves page: HTML too short (len=%d) — returning empty list",
            len(html or ""),
        )
        if skip_reasons is not None:
            skip_reasons["html_too_short"] = skip_reasons.get("html_too_short", 0) + 1
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="tab")
    if table is None:
        logger.warning("Serebii moves page: no <table class='tab'> found — likely layout change")
        if skip_reasons is not None:
            skip_reasons["missing_table"] = skip_reasons.get("missing_table", 0) + 1
        return []

    def _skip(reason: str) -> None:
        if skip_reasons is not None:
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    moves: list[dict] = []

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        # Champions rows have exactly 9 cells; header and S/V rows are a
        # structural part of the page — not regressions.
        if len(cells) != 9:
            continue
        if cells[1].get_text(strip=True) != "Champions":
            continue

        # Move name — always an <a> tag linking to the move's attackdex page.
        name_a = cells[0].find("a")
        name = name_a.get_text(strip=True) if name_a else cells[0].get_text(strip=True)
        if not name:
            _skip("missing_name")
            logger.warning("Serebii row dropped: missing move name")
            continue

        move_type = _type_from_img(cells[2])
        if move_type is None:
            _skip("missing_type_img")
            logger.warning("Serebii row dropped: missing type image for %r", name)
            continue

        category = _category_from_img(cells[3])
        if category is None:
            _skip("missing_category_img")
            logger.warning("Serebii row dropped: missing category image for %r", name)
            continue

        try:
            pp = _parse_int_or_none(cells[4].get_text(strip=True), field="pp")
            base_power = _parse_int_or_none(cells[5].get_text(strip=True), field="base_power")
            accuracy = _parse_int_or_none(cells[6].get_text(strip=True), field="accuracy")
        except ParseError as exc:
            _skip("unparseable_numeric")
            logger.warning("Serebii row dropped for %r: %s", name, exc)
            continue

        description = cells[7].get_text(" ", strip=True) or None

        moves.append(
            {
                "id": _slugify_move(name),
                "name": name,
                "type": move_type,
                "category": category,
                "base_power": base_power,
                "accuracy": accuracy,
                "pp": pp,
                "priority": 0,
                "target": None,
                "description": description,
                "short_desc": description,
            }
        )

    return moves


async def store_champions_moves(
    db: aiosqlite.Connection,
    moves: list[dict],
    *,
    _commit: bool = True,
) -> int:
    """Replace all Champions moves with the provided list.

    DELETE + INSERT OR REPLACE pattern matching store_champions_pokemon_data.
    Returns count of stored rows.

    Raises ValueError if moves is empty — a parser regression or Serebii
    layout change would otherwise wipe the whole table with no warning.
    """
    if not moves:
        raise ValueError("refusing to store empty Champions moves list — would delete all rows")
    await db.execute("DELETE FROM champions_dex_moves")
    count = 0
    for m in moves:
        # Every field in the parser output is populated explicitly (see
        # parse_serebii_moves_page) — use direct key access so a future
        # schema change to the parser fails loudly instead of silently
        # storing NULLs. `num` is the one field the parser never sets.
        await db.execute(
            """INSERT OR REPLACE INTO champions_dex_moves
               (id, num, name, type, category, base_power, accuracy, pp,
                priority, target, description, short_desc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m["id"],
                m.get("num"),
                m["name"],
                m["type"],
                m["category"],
                m["base_power"],
                m["accuracy"],
                m["pp"],
                m["priority"],
                m["target"],
                m["description"],
                m["short_desc"],
            ),
        )
        count += 1
    if _commit:
        await db.commit()
    return count


async def fetch_and_store_champions_moves(
    db_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict:
    """Fetch the Serebii updated attacks page and store parsed moves.

    Returns dict: {fetched, stored, errors, circuit_states, dry_run}.
    """
    if db_path is None:
        db_path = get_db_path()

    await init_database(db_path)

    result = await fetch_text_resilient(SEREBII_MOVES_URL, service="serebii")
    errors: list[dict] = []
    if not result.success or not result.data:
        err_msg = result.error.message if result.error else "fetch returned no data"
        errors.append({"url": SEREBII_MOVES_URL, "message": err_msg})
        return {
            "fetched": 0,
            "stored": 0,
            "errors": errors,
            "circuit_states": get_all_circuit_states(),
            "dry_run": dry_run,
        }

    skip_reasons: dict[str, int] = {}
    moves = parse_serebii_moves_page(result.data, skip_reasons=skip_reasons)
    if skip_reasons:
        errors.append(
            {
                "url": SEREBII_MOVES_URL,
                "message": f"parser skipped rows: {skip_reasons}",
            }
        )

    if dry_run:
        return {
            "fetched": len(moves),
            "stored": 0,
            "errors": errors,
            "circuit_states": get_all_circuit_states(),
            "dry_run": True,
            "results": moves,
        }

    stored = 0
    if not moves:
        # Parser returned nothing (empty page, layout change, or bad HTML).
        # Never DELETE the existing rows in that case — preserve live data.
        errors.append(
            {
                "url": SEREBII_MOVES_URL,
                "message": (
                    "skipped: parser returned 0 moves; existing champions_dex_moves rows preserved"
                ),
            }
        )
    else:
        async with get_connection(db_path) as db:
            try:
                stored = await store_champions_moves(db, moves, _commit=False)
                await db.commit()
            except (aiosqlite.Error, ValueError) as exc:
                await db.rollback()
                errors.append({"url": "store", "message": str(exc)})

    return {
        "fetched": len(moves),
        "stored": stored,
        "errors": errors,
        "circuit_states": get_all_circuit_states(),
        "dry_run": False,
    }
