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

import json
import re
from typing import Any

from bs4 import BeautifulSoup

# Matches "Label Name (41.092%)" patterns in FAQ answer text
_FAQ_ENTRY_RE = re.compile(r"([A-Za-z][\w\s\-'.]+?)\s*\(([\d.]+)%\)")
_USAGE_RE = re.compile(r"Usage\s+Percent\s+([\d.]+)\s*%", re.I)
_PERCENT_RE = re.compile(r"([\d.]+)\s*%")


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
        for m in _FAQ_ENTRY_RE.finditer(text):
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
      moves, items, abilities, teammates, spreads
    """
    if not html or len(html.strip()) < 200:
        return None
    if "Not Found" in html[:500] or "404" in html[:200]:
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
        "spreads": [],
    }
