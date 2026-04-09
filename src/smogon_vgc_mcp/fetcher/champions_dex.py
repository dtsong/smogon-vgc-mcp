"""Parse and store Pokemon data from real Serebii Champions Pokedex pages.

Serebii URL pattern:
  https://www.serebii.net/pokedex-champions/<slug>/

Each base-form page contains the base Pokemon plus all Mega forms in-page.
This module handles the real Serebii HTML structure:
  - Types: <img class="typeimg" alt="Fire-type"> (strip "-type")
  - Abilities: <td class="fooleft"> containing "Abilities:"
  - Stats: row with "Base Stats - Total:" followed by 6 fooinfo cells
  - Megas: <h3>Mega ...</h3> sections within the same page
"""

from __future__ import annotations

import re

import aiosqlite
from bs4 import BeautifulSoup, Tag

_PURE_TYPE_RE = re.compile(r"^([A-Za-z]+)-type$")
# Matches type image src patterns: ".../type/fire.gif" or ".../type/fire.png"
_TYPE_SRC_RE = re.compile(r"/type/([a-z]+)\.(?:gif|png)$", re.I)


def _extract_types_from_region(region: Tag | BeautifulSoup) -> list[str]:
    """Extract types from a page region.

    Strategy 1: alt exactly "Fire-type" (base form, class="typeimg" imgs).
    Strategy 2: img src ends in /type/fire.gif inside a <td class="cen"> —
                for Mega sections where imgs have no alt attribute.
    Move-type icons like "Acrobatics - Flying-type" are excluded by strategy 1's
    strict regex, and strategy 2 only runs within cen cells.
    """
    types: list[str] = []

    # Strategy 1: alt text exactly "X-type"
    for img in region.find_all("img"):
        alt = img.get("alt", "")
        m = _PURE_TYPE_RE.match(alt)
        if m:
            type_name = m.group(1).capitalize()
            if type_name not in types:
                types.append(type_name)
        if len(types) == 2:
            break

    if types:
        return types

    # Strategy 2: look in <td class="cen"> for type images by src
    for td in region.find_all("td", class_="cen"):
        for img in td.find_all("img"):
            src = img.get("src", "")
            m = _TYPE_SRC_RE.search(src)
            if m:
                type_name = m.group(1).capitalize()
                # Skip non-type names (physical, special, other)
                if type_name.lower() in ("physical", "special", "other", "status"):
                    continue
                if type_name not in types:
                    types.append(type_name)
            if len(types) == 2:
                break
        if types:
            break

    return types


def _extract_abilities_from_region(region: Tag | BeautifulSoup) -> list[str]:
    """Extract abilities from a <td class="fooleft"> containing 'Abilities:'.

    Returns list of ability names (non-empty strings only).
    """
    abilities: list[str] = []
    for td in region.find_all("td", class_="fooleft"):
        text = td.get_text(" ", strip=True)
        if "Abilities" in text:
            for a_tag in td.find_all("a"):
                name = a_tag.get_text(strip=True)
                if name and name not in abilities:
                    abilities.append(name)
            break
    return abilities


def _extract_base_stats_row(region: Tag | BeautifulSoup) -> dict[str, int] | None:
    """Find the first 'Base Stats - Total:' row and extract HP/Atk/Def/SpA/SpD/Spe.

    Returns None if not found or if the stats cells are empty (incomplete Mega data).
    """
    for td in region.find_all("td", class_="fooinfo"):
        text = td.get_text(strip=True)
        if text.startswith("Base Stats - Total:"):
            # This cell spans 2 cols. The next 6 fooinfo sibling tds are the stats.
            row = td.find_parent("tr")
            if not row:
                continue
            stat_cells = [
                c
                for c in row.find_all("td", class_="fooinfo")
                if not c.get_text(strip=True).startswith("Base Stats")
            ]
            if len(stat_cells) < 6:
                return None
            vals: list[str] = [c.get_text(strip=True) for c in stat_cells[:6]]
            # Guard against empty cells (Mega Y case)
            if not all(v for v in vals):
                return None
            try:
                hp, atk, def_, spa, spd, spe = (int(v) for v in vals)
            except ValueError:
                return None
            return {"hp": hp, "atk": atk, "def": def_, "spa": spa, "spd": spd, "spe": spe}
    return None


def _extract_height_weight(region: Tag | BeautifulSoup) -> tuple[float | None, float | None]:
    """Extract height (m) and weight (kg) from fooinfo cells."""
    height_m: float | None = None
    weight_kg: float | None = None

    for td in region.find_all("td", class_="fooinfo"):
        text = td.get_text(" ", strip=True)
        if height_m is None:
            m = re.search(r"([\d.]+)\s*m\b", text)
            if m:
                try:
                    height_m = float(m.group(1))
                except ValueError:
                    pass
        if weight_kg is None:
            m = re.search(r"([\d.]+)\s*kg\b", text)
            if m:
                try:
                    weight_kg = float(m.group(1))
                except ValueError:
                    pass
        if height_m is not None and weight_kg is not None:
            break

    return height_m, weight_kg


def _extract_name_and_num(soup: BeautifulSoup) -> tuple[str, int | None]:
    """Extract Pokemon name from h1 tag and dex number from #NNN pattern."""
    name = ""
    num: int | None = None

    h1 = soup.find("h1")
    if h1:
        # Strip leading #NNN prefix if present (e.g. "#006 Charizard")
        raw = h1.get_text(strip=True)
        name = re.sub(r"^#?\d+\s*", "", raw).strip()

    # National dex number from table cell like "#006"
    for td in soup.find_all("td", class_="fooinfo"):
        m = re.search(r"#0*(\d+)", td.get_text(strip=True))
        if m:
            num = int(m.group(1))
            break

    return name, num


def _parse_mega_section(h3_tag: Tag, base_slug: str, mega_index: int) -> dict | None:
    """Parse a Mega form section starting at an <h3>Mega ...</h3> tag.

    Walks forward from h3 collecting tables until the next <hr> or end of page.
    Returns None if stats are missing/empty (incomplete data).
    """
    mega_name = h3_tag.get_text(strip=True)  # e.g. "Mega Charizard X"

    # Build a local soup fragment by collecting sibling/ancestor tables
    # The h3 is inside a fooevo td, inside a dextable. Walk up to collect
    # all subsequent tables until the next HR separator.
    # Strategy: find all tables after the h3's table, up to the next hr.
    top = h3_tag
    while top.parent and top.parent.name not in ("body", "html", "[document]"):
        top = top.parent

    # Collect HTML from h3's containing table onward
    # The h3 is in a fooevo td -> tr -> table. Grab that table and all
    # following siblings until we hit an <hr> tag or another <a name="mega">.
    container = h3_tag
    while container.name != "table":
        container = container.parent
        if container is None:
            return None

    fragment_tags: list[Tag] = [container]
    for sibling in container.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        # Stop at HR separators (between Mega sections)
        if sibling.name == "p" and sibling.find("hr"):
            break
        if sibling.name == "hr":
            break
        # Stop if we hit another Mega anchor
        if sibling.find("a", attrs={"name": "mega"}):
            break
        fragment_tags.append(sibling)

    fragment_html = "".join(str(t) for t in fragment_tags)
    region = BeautifulSoup(fragment_html, "html.parser")

    # Extract types
    types = _extract_types_from_region(region)

    # Extract abilities
    abilities = _extract_abilities_from_region(region)

    # Extract stats
    stats = _extract_base_stats_row(region)
    if stats is None:
        # Incomplete Mega data (e.g. Mega Y with empty stats)
        return None

    # Determine mega_slug from name
    # "Mega Charizard X" -> charizard-mega-x
    name_lower = mega_name.lower()
    # Remove "mega " prefix and replace spaces with -
    name_lower = re.sub(r"\s+", "-", name_lower.strip())
    # Remove duplicate base name if present: "mega-charizard-x" -> keep as is
    # Build slug: base_slug + "-mega" + optional suffix
    suffix_match = re.search(r"-([xy])$", name_lower)
    if suffix_match:
        mega_slug = f"{base_slug}-mega-{suffix_match.group(1)}"
    elif name_lower.endswith("-mega") or "mega" in name_lower:
        mega_slug = f"{base_slug}-mega"
    else:
        mega_slug = f"{base_slug}-mega-{mega_index}"

    height_m, weight_kg = _extract_height_weight(region)

    return {
        "slug": mega_slug,
        "name": mega_name,
        "types": types,
        "abilities": abilities,
        "stats": stats,
        "height_m": height_m,
        "weight_kg": weight_kg,
    }


def parse_serebii_pokemon_page(html: str, pokemon_id: str) -> dict | None:
    """Parse a real Serebii Champions Pokedex page for a base-form Pokemon.

    Handles base form data and all Mega forms present on the same page.

    Args:
        html: Raw HTML of the Serebii page.
        pokemon_id: The URL slug / DB id (e.g. "charizard").

    Returns:
        Dict with keys:
          id, num, name, types (list), base_stats (dict), abilities (list),
          ability_hidden (None — Serebii Champions doesn't show hidden abilities),
          height_m, weight_kg, mega_forms (list of dicts)
        Returns None for empty or 404-style pages.
    """
    if not html or len(html.strip()) < 100:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Detect 404/empty pages
    if not soup.find("table", class_="dextable"):
        return None

    name, num = _extract_name_and_num(soup)
    if not name:
        return None

    # --- Base form types ---
    # The base form type cell has class="cen" and contains typeimg imgs.
    # It appears in the main info table (not in Mega sections).
    # Strategy: find the first <td class="cen"> that has typeimg imgs.
    base_types: list[str] = []
    for td in soup.find_all("td", class_="cen"):
        types = _extract_types_from_region(td)
        if types:
            base_types = types
            break

    # --- Base form stats ---
    # The first "Base Stats - Total:" row (preceded by <a name="stats">)
    base_stats = _extract_base_stats_row(soup)

    # --- Base form abilities ---
    # Find the first fooleft td with "Abilities:" before any Mega section.
    # Mega sections start at <a name="mega">.
    mega_anchor = soup.find("a", attrs={"name": "mega"})
    base_abilities: list[str] = []
    for td in soup.find_all("td", class_="fooleft"):
        # Ensure this td comes before the first Mega section
        if mega_anchor and _comes_after(td, mega_anchor):
            break
        text = td.get_text(" ", strip=True)
        if "Abilities" in text:
            for a_tag in td.find_all("a"):
                ability_name = a_tag.get_text(strip=True)
                if ability_name and ability_name not in base_abilities:
                    base_abilities.append(ability_name)
            break

    # --- Height / Weight (base form) ---
    height_m, weight_kg = _extract_height_weight(soup)

    # --- Mega forms ---
    mega_forms: list[dict] = []
    mega_index = 0
    for h3 in soup.find_all("h3"):
        if "mega" in h3.get_text(strip=True).lower():
            mega_data = _parse_mega_section(h3, pokemon_id, mega_index)
            if mega_data is not None:
                mega_forms.append(mega_data)
            mega_index += 1

    return {
        "id": pokemon_id,
        "num": num,
        "name": name,
        "types": base_types,
        "base_stats": base_stats or {},
        "abilities": base_abilities,
        "ability_hidden": None,
        "height_m": height_m,
        "weight_kg": weight_kg,
        "mega_forms": mega_forms,
    }


def _comes_after(tag_a: Tag, tag_b: Tag) -> bool:
    """Return True if tag_a appears after tag_b in document order."""
    for tag in tag_b.find_all_next():
        if tag is tag_a:
            return True
    return False


async def store_champions_pokemon_data(
    db: aiosqlite.Connection,
    pokemon_list: list[dict],
    *,
    _commit: bool = True,
) -> int:
    """Store Champions Pokemon data (base forms + Mega forms) into the DB.

    Follows the same pattern as store_pokemon_data() in pokedex.py:
    - DELETE FROM champions_dex_pokemon first
    - INSERT OR REPLACE each Pokemon and each Mega form
    - _commit=False for batch transactions
    - Returns count of stored records

    Each dict in pokemon_list is the output of parse_serebii_pokemon_page().
    """
    await db.execute("DELETE FROM champions_dex_pokemon")

    count = 0
    for pokemon in pokemon_list:
        stats = pokemon.get("base_stats", {})
        types = pokemon.get("types", [])
        abilities = pokemon.get("abilities", [])

        if not types or not stats:
            continue

        await db.execute(
            """INSERT OR REPLACE INTO champions_dex_pokemon
               (id, num, name, type1, type2, hp, atk, def, spa, spd, spe,
                ability1, ability2, ability_hidden,
                base_form_id, is_mega, mega_stone,
                height_m, weight_kg)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pokemon["id"],
                pokemon.get("num"),
                pokemon.get("name"),
                types[0] if types else None,
                types[1] if len(types) > 1 else None,
                stats.get("hp", 0),
                stats.get("atk", 0),
                stats.get("def", 0),
                stats.get("spa", 0),
                stats.get("spd", 0),
                stats.get("spe", 0),
                abilities[0] if len(abilities) > 0 else None,
                abilities[1] if len(abilities) > 1 else None,
                pokemon.get("ability_hidden"),
                pokemon.get("base_form_id"),
                1 if pokemon.get("is_mega") else 0,
                pokemon.get("mega_stone"),
                pokemon.get("height_m"),
                pokemon.get("weight_kg"),
            ),
        )
        count += 1

        # Store each Mega form
        for mega in pokemon.get("mega_forms", []):
            mega_stats = mega.get("stats", {})
            mega_types = mega.get("types", [])
            mega_abilities = mega.get("abilities", [])

            await db.execute(
                """INSERT OR REPLACE INTO champions_dex_pokemon
                   (id, num, name, type1, type2, hp, atk, def, spa, spd, spe,
                    ability1, ability2, ability_hidden,
                    base_form_id, is_mega, mega_stone,
                    height_m, weight_kg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mega["slug"],
                    pokemon.get("num"),
                    mega.get("name"),
                    mega_types[0] if mega_types else None,
                    mega_types[1] if len(mega_types) > 1 else None,
                    mega_stats.get("hp", 0),
                    mega_stats.get("atk", 0),
                    mega_stats.get("def", 0),
                    mega_stats.get("spa", 0),
                    mega_stats.get("spd", 0),
                    mega_stats.get("spe", 0),
                    mega_abilities[0] if len(mega_abilities) > 0 else None,
                    mega_abilities[1] if len(mega_abilities) > 1 else None,
                    None,  # ability_hidden not available for Megas
                    pokemon["id"],  # base_form_id
                    1,  # is_mega
                    mega.get("mega_stone"),
                    mega.get("height_m"),
                    mega.get("weight_kg"),
                ),
            )
            count += 1

    if _commit:
        await db.commit()
    return count
