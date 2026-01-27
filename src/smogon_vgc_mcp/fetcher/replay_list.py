"""Fetch replay lists from Pokemon Showdown's JSON API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx

from smogon_vgc_mcp.logging import get_logger

logger = get_logger(__name__)

SHOWDOWN_REPLAY_BASE = "https://replay.pokemonshowdown.com"
SHOWDOWN_API_BASE = "https://replay.pokemonshowdown.com/api/replays"
PAGE_SIZE = 51
RATE_LIMIT_DELAY = 1.0
DEFAULT_TIMEOUT = 30.0


class ReplayListError(Exception):
    """Raised when a replay list fetch encounters an API-level error."""


@dataclass
class ReplayListEntry:
    replay_id: str
    format: str
    players: list[str]
    upload_time: int
    rating: int | None = None
    is_private: bool = False
    password: str | None = None

    @property
    def url(self) -> str:
        base = f"{SHOWDOWN_REPLAY_BASE}/{self.replay_id}"
        if self.password:
            return f"{base}-{self.password}pw"
        return base


@dataclass
class ReplayListResult:
    replays: list[ReplayListEntry] = field(default_factory=list)
    total_fetched: int = 0
    pages_fetched: int = 0
    has_more: bool = False
    errors: list[str] = field(default_factory=list)


def _strip_dispatch_prefix(text: str) -> str:
    """Strip the leading `]` prefix from Showdown API responses."""
    if text.startswith("]"):
        return text[1:]
    return text


def _check_action_error(data: dict | list) -> None:
    """Raise ReplayListError if the response contains an actionerror."""
    if isinstance(data, dict) and "actionerror" in data:
        raise ReplayListError(data["actionerror"])


def _parse_replay_entries(data: list[dict], private: bool = False) -> list[ReplayListEntry]:
    """Parse raw JSON entries into ReplayListEntry objects."""
    entries = []
    for item in data:
        entries.append(
            ReplayListEntry(
                replay_id=item.get("id", ""),
                format=item.get("format", ""),
                players=[
                    item.get("p1", ""),
                    item.get("p2", ""),
                ],
                upload_time=item.get("uploadtime", 0),
                rating=item.get("rating", None),
                is_private=private or bool(item.get("private")),
                password=item.get("password"),
            )
        )
    return entries


async def fetch_public_replay_list(
    username: str,
    format: str = "",
    max_pages: int = 5,
) -> ReplayListResult:
    """Fetch a user's public replays via /search.json with cursor pagination.

    Uses `before=uploadtime` of the last result for pagination.
    Rate-limits to 1 request/sec between pages.
    """
    result = ReplayListResult()
    before: int | None = None

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        for page in range(max_pages):
            params: dict[str, str | int] = {"user": username}
            if format:
                params["format"] = format
            if before is not None:
                params["before"] = before

            try:
                response = await client.get(
                    f"{SHOWDOWN_REPLAY_BASE}/search.json",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                result.errors.append(f"HTTP {e.response.status_code} on page {page + 1}")
                break
            except httpx.HTTPError as e:
                result.errors.append(f"Request error on page {page + 1}: {e}")
                break

            if not isinstance(data, list):
                _check_action_error(data)
                break

            if not data:
                break

            has_more_page = len(data) >= PAGE_SIZE
            entries_this_page = data[:PAGE_SIZE - 1] if has_more_page else data
            result.replays.extend(_parse_replay_entries(entries_this_page))
            result.pages_fetched = page + 1
            result.total_fetched = len(result.replays)
            result.has_more = has_more_page

            if not has_more_page:
                break

            before = entries_this_page[-1].get("uploadtime", 0)

            if page < max_pages - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY)

    return result


async def fetch_private_replay_list(
    username: str,
    sid_cookie: str,
    format: str = "",
    max_pages: int = 5,
) -> ReplayListResult:
    """Fetch a user's private replays via /api/replays/searchprivate.

    Requires a valid `sid` cookie. Uses `page=N` pagination.
    Rate-limits to 1 request/sec between pages.
    """
    result = ReplayListResult()
    headers = {"Cookie": f"sid={sid_cookie}"}

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        for page_num in range(1, max_pages + 1):
            params: dict[str, str | int] = {
                "username": username,
                "page": page_num,
            }
            if format:
                params["format"] = format

            try:
                response = await client.get(
                    f"{SHOWDOWN_API_BASE}/searchprivate",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                raw_text = response.text
            except httpx.HTTPStatusError as e:
                result.errors.append(f"HTTP {e.response.status_code} on page {page_num}")
                break
            except httpx.HTTPError as e:
                result.errors.append(f"Request error on page {page_num}: {e}")
                break

            try:
                import json

                cleaned = _strip_dispatch_prefix(raw_text)
                data = json.loads(cleaned)
                _check_action_error(data)
            except ReplayListError:
                raise
            except (json.JSONDecodeError, ValueError) as e:
                result.errors.append(f"Parse error on page {page_num}: {e}")
                break

            if not isinstance(data, list) or not data:
                break

            has_more_page = len(data) >= PAGE_SIZE
            entries_this_page = data[:PAGE_SIZE - 1] if has_more_page else data
            result.replays.extend(_parse_replay_entries(entries_this_page, private=True))
            result.pages_fetched = page_num
            result.total_fetched = len(result.replays)
            result.has_more = has_more_page

            if not has_more_page:
                break

            if page_num < max_pages:
                await asyncio.sleep(RATE_LIMIT_DELAY)

    return result
