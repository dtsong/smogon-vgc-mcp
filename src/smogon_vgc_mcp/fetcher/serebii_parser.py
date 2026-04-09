"""Parse Pokemon data from Serebii Champions pages.

Serebii URL pattern:
  https://www.serebii.net/champions/pokemon/<slug>.shtml

Each page contains:
- Pokemon name (in <h1> or the main fooinfo table)
- Types (type icons with alt text)
- Base stats table (HP/Attack/Defense/Sp.Atk/Sp.Def/Speed rows)
- Abilities (listed in abilities section)
- Mega Evolution links (links to Mega form pages, if any)

Returns a dict matching the champions_dex_pokemon schema shape so callers
can pass it directly to store_champions_pokemon_data().
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

# Serebii base URL for Champions pages
SEREBII_CHAMPIONS_BASE = "https://www.serebii.net/champions/pokemon"


def _to_id(name: str) -> str:
    """Convert a display name to a lowercase slug id (e.g. 'Charizard' -> 'charizard')."""
    return re.sub(r"[^a-z0-9]+", "", name.lower().replace("-", "").replace(" ", ""))


def _parse_types(soup: BeautifulSoup) -> list[str]:
    """Extract type(s) from the page.

    Serebii renders types as <img> tags with alt text like 'Fire Type' or
    as links containing type images. We look for <a> tags whose href
    contains '/type/' and whose img alt attribute ends with 'Type'.
    Falls back to scanning all imgs with alt ending in 'Type'.
    """
    types: list[str] = []

    # Primary strategy: type links like <a href="/type/fire.shtml"><img alt="Fire Type" ...>
    type_links = soup.find_all("a", href=re.compile(r"/type/", re.I))
    for link in type_links:
        img = link.find("img")
        if img and img.get("alt", "").endswith("Type"):
            type_name = img["alt"].replace(" Type", "").strip()
            if type_name and type_name not in types:
                types.append(type_name)
        if len(types) == 2:
            break

    if types:
        return types

    # Fallback: any img with alt="X Type"
    for img in soup.find_all("img"):
        alt = img.get("alt", "")
        if alt.endswith("Type"):
            type_name = alt.replace(" Type", "").strip()
            if type_name and type_name not in types:
                types.append(type_name)
        if len(types) == 2:
            break

    return types


def _parse_base_stats(soup: BeautifulSoup) -> dict[str, int]:
    """Extract base stats from the stats table.

    Serebii stats tables have rows like:
      <td>HP</td><td>45</td>
    or use a tabbed/labelled layout. We search for cells with the stat
    label text and take the numeric sibling.
    """
    stat_map = {
        "HP": "hp",
        "Attack": "atk",
        "Defense": "def",
        "Sp. Atk": "spa",
        "Sp.Atk": "spa",
        "Sp. Attack": "spa",
        "Special Attack": "spa",
        "Sp. Def": "spd",
        "Sp.Def": "spd",
        "Sp. Defense": "spd",
        "Special Defense": "spd",
        "Speed": "spe",
    }

    stats: dict[str, int] = {}

    # Find all <td> cells; look for stat label cells followed by numeric cells
    cells = soup.find_all("td")
    for i, cell in enumerate(cells):
        text = cell.get_text(strip=True)
        if text in stat_map and i + 1 < len(cells):
            value_text = cells[i + 1].get_text(strip=True)
            # value cell might contain "45" or "45 / 45" (base / max)
            numeric_match = re.match(r"(\d+)", value_text)
            if numeric_match:
                key = stat_map[text]
                if key not in stats:  # take first occurrence
                    stats[key] = int(numeric_match.group(1))

    return stats


def _parse_abilities(soup: BeautifulSoup) -> tuple[list[str], str | None]:
    """Extract regular abilities and hidden ability.

    Returns (abilities_list, hidden_ability_or_None).

    Strategy: iterate over text-bearing tags (p, td, th, li) and look for
    lines that start with 'Abilities:' or 'Hidden Ability:'. This is more
    robust than a full-page regex because BeautifulSoup's get_text() with a
    space separator merges multi-paragraph content into one long string where
    terminators are hard to predict.
    """
    abilities: list[str] = []
    hidden: str | None = None

    for tag in soup.find_all(["p", "td", "th", "li", "div", "span"]):
        text = tag.get_text(" ", strip=True)

        # "Abilities: Blaze | Solar Power"
        if re.match(r"Abilities?\s*:", text, re.I):
            after_colon = re.sub(r"^Abilities?\s*:\s*", "", text, flags=re.I)
            # Split on " | " or " / "
            parts = re.split(r"\s*[|/]\s*", after_colon)
            for part in parts:
                part = part.strip()
                # Stop if we hit "Hidden" or a non-ability word
                if re.match(r"Hidden", part, re.I):
                    break
                if part and re.match(r"^[A-Z][A-Za-z\s'\-]+$", part):
                    abilities.append(part)

        # "Hidden Ability: Chlorophyll" or "Hidden Ability (H): Chlorophyll"
        elif re.match(r"Hidden Ability", text, re.I):
            after_colon = re.sub(r"^Hidden Ability(?:\s*\([^)]*\))?\s*:\s*", "", text, flags=re.I)
            ability_name = after_colon.strip()
            if ability_name and re.match(r"^[A-Z][A-Za-z\s'\-]+$", ability_name):
                hidden = ability_name
                # Remove from regular list if it snuck in
                if hidden in abilities:
                    abilities.remove(hidden)

    return abilities, hidden


def _parse_mega_links(soup: BeautifulSoup, base_slug: str) -> list[str]:
    """Extract Mega Evolution form slugs from the page.

    Serebii links to Mega forms like:
      <a href="/champions/pokemon/charizard-mega-x.shtml">Mega Charizard X</a>

    Returns list of Mega slugs (e.g. ['charizard-mega-x', 'charizard-mega-y']).
    """
    mega_slugs: list[str] = []
    pattern = re.compile(
        rf"/champions/pokemon/({re.escape(base_slug)}-mega[^.]*?)\.shtml", re.I
    )
    for a_tag in soup.find_all("a", href=pattern):
        href = a_tag.get("href", "")
        m = pattern.search(href)
        if m:
            slug = m.group(1).lower()
            if slug not in mega_slugs:
                mega_slugs.append(slug)

    return mega_slugs


def _parse_name_and_num(soup: BeautifulSoup) -> tuple[str, int | None]:
    """Extract Pokemon display name and Dex number from the page.

    Serebii shows the name in <h1> or a prominent header cell.
    The dex number often appears as '#001' or 'No. 001'.
    """
    name = ""
    num: int | None = None

    # Try <h1> first
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)

    # If no h1, look for a large font/table-header cell
    if not name:
        for tag in soup.find_all(["h2", "td", "th"]):
            text = tag.get_text(strip=True)
            # Heuristic: short non-numeric text in a header-like context
            if 2 < len(text) < 30 and not text.startswith("#") and not re.match(r"^\d", text):
                parent = tag.parent
                if parent and parent.name in ("tr", "thead", "table"):
                    name = text
                    break

    # Extract dex number — patterns: "#001", "No. 001", "001"
    full_text = soup.get_text(" ")
    num_match = re.search(r"(?:No\.\s*|#)0*(\d+)", full_text)
    if num_match:
        num = int(num_match.group(1))

    return name, num


def _parse_height_weight(soup: BeautifulSoup) -> tuple[float, float]:
    """Extract height (m) and weight (kg) from the page."""
    height_m = 0.0
    weight_kg = 0.0

    full_text = soup.get_text(" ", strip=True)

    # Height: "1.7m" or "Height: 1.70m" or "Height 1.70m"
    h_match = re.search(r"Height\s*:?\s*([\d.]+)\s*m", full_text, re.I)
    if h_match:
        try:
            height_m = float(h_match.group(1))
        except ValueError:
            pass

    # Weight: "90.5kg" or "Weight: 90.5kg"
    w_match = re.search(r"Weight\s*:?\s*([\d.]+)\s*kg", full_text, re.I)
    if w_match:
        try:
            weight_kg = float(w_match.group(1))
        except ValueError:
            pass

    return height_m, weight_kg


def _parse_mega_stone(soup: BeautifulSoup, slug: str) -> str | None:
    """Extract Mega Stone name for a Mega form page."""
    full_text = soup.get_text(" ", strip=True)

    # Pattern: "Mega Stone: Charizardite X" or "Hold Item: Charizardite X"
    stone_match = re.search(
        r"(?:Mega Stone|Hold Item)\s*:\s*([A-Za-z][A-Za-z\s]+?)(?:\s*$|\n|\.|Type)",
        full_text,
    )
    if stone_match:
        return stone_match.group(1).strip()

    # Fallback: infer from slug — "charizard-mega-x" -> "Charizardite X"
    mega_match = re.match(r"(\w+)-mega(?:-(.+))?$", slug)
    if mega_match:
        base = mega_match.group(1).capitalize()
        suffix = mega_match.group(2)
        if suffix:
            return f"{base}ite {suffix.upper()}"
        return f"{base}ite"

    return None


def parse_serebii_pokemon_page(
    html: str,
    slug: str,
    *,
    is_mega: bool = False,
    base_form_id: str | None = None,
) -> dict:
    """Parse a Serebii Champions Pokemon page into a data dict.

    Args:
        html: Raw HTML string of the page.
        slug: URL slug for this Pokemon (e.g. 'charizard', 'charizard-mega-x').
        is_mega: True if this is a Mega Evolution form page.
        base_form_id: Slug of the base form (required when is_mega=True).

    Returns:
        Dict with keys matching the champions_dex_pokemon table columns plus
        'mega_links' (list[str]) for base forms. All fields are present;
        missing values are None or 0.

    Raises:
        ValueError: If the page contains no parseable stat data (likely a
                    fetch error or wrong page).
    """
    soup = BeautifulSoup(html, "html.parser")

    name, num = _parse_name_and_num(soup)
    types = _parse_types(soup)
    stats = _parse_base_stats(soup)
    abilities, hidden_ability = _parse_abilities(soup)
    height_m, weight_kg = _parse_height_weight(soup)

    mega_links: list[str] = []
    mega_stone: str | None = None

    if is_mega:
        mega_stone = _parse_mega_stone(soup, slug)
    else:
        mega_links = _parse_mega_links(soup, slug)

    if not stats:
        raise ValueError(
            f"No stat data found for slug='{slug}'. "
            "Page may have failed to load or the HTML structure has changed."
        )

    return {
        "id": slug,
        "num": num,
        "name": name,
        "type1": types[0] if types else None,
        "type2": types[1] if len(types) > 1 else None,
        "hp": stats.get("hp", 0),
        "atk": stats.get("atk", 0),
        "def": stats.get("def", 0),
        "spa": stats.get("spa", 0),
        "spd": stats.get("spd", 0),
        "spe": stats.get("spe", 0),
        "ability1": abilities[0] if len(abilities) > 0 else None,
        "ability2": abilities[1] if len(abilities) > 1 else None,
        "ability_hidden": hidden_ability,
        "base_form_id": base_form_id,
        "is_mega": is_mega,
        "mega_stone": mega_stone,
        "height_m": height_m,
        "weight_kg": weight_kg,
        # Extra field consumed by the fetch orchestrator, not stored in DB
        "mega_links": mega_links,
    }
