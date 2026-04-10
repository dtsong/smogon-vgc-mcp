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

import re
from pathlib import Path

import aiosqlite
from bs4 import BeautifulSoup, Tag

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.resilience import get_all_circuit_states
from smogon_vgc_mcp.utils import fetch_text_resilient

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


def _slugify_move(name: str) -> str:
    """Convert a move name to a lowercase alphanumeric slug (no separators)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _parse_int_or_none(text: str) -> int | None:
    """Return int if parseable, else None. "--", "—", "101" (always-hits) → None."""
    cleaned = text.strip()
    if not cleaned or cleaned in ("--", "—", "-"):
        return None
    try:
        val = int(cleaned)
        # 101 is Serebii's sentinel for "always hits" (no accuracy check).
        return None if val == 101 else val
    except ValueError:
        return None


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


def parse_serebii_moves_page(html: str) -> list[dict]:
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

    Returns an empty list for empty or malformed HTML.
    """
    if not html or len(html.strip()) < 100:
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="tab")
    if table is None:
        return []

    moves: list[dict] = []

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        # Champions rows have exactly 9 cells; skip header and S/V rows.
        if len(cells) != 9:
            continue
        if cells[1].get_text(strip=True) != "Champions":
            continue

        # Move name — always an <a> tag linking to the move's attackdex page.
        name_a = cells[0].find("a")
        name = name_a.get_text(strip=True) if name_a else cells[0].get_text(strip=True)
        if not name:
            continue

        move_type = _type_from_img(cells[2])
        category = _category_from_img(cells[3])

        if move_type is None or category is None:
            continue

        pp = _parse_int_or_none(cells[4].get_text(strip=True))
        base_power = _parse_int_or_none(cells[5].get_text(strip=True))
        accuracy = _parse_int_or_none(cells[6].get_text(strip=True))
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
    """
    await db.execute("DELETE FROM champions_dex_moves")
    count = 0
    for m in moves:
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
                m.get("base_power"),
                m.get("accuracy"),
                m.get("pp"),
                m.get("priority", 0),
                m.get("target"),
                m.get("description"),
                m.get("short_desc"),
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
        errors.append({"url": SEREBII_MOVES_URL, "message": "Fetch failed"})
        return {
            "fetched": 0,
            "stored": 0,
            "errors": errors,
            "circuit_states": get_all_circuit_states(),
            "dry_run": dry_run,
        }

    moves = parse_serebii_moves_page(result.data)

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
    async with get_connection(db_path) as db:
        try:
            stored = await store_champions_moves(db, moves, _commit=False)
            await db.commit()
        except aiosqlite.Error as exc:
            await db.rollback()
            errors.append({"url": "store", "message": str(exc)})

    return {
        "fetched": len(moves),
        "stored": stored,
        "errors": errors,
        "circuit_states": get_all_circuit_states(),
        "dry_run": False,
    }
