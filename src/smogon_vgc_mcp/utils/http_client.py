"""Unified async HTTP client utilities.

This module consolidates HTTP fetching patterns from:
- fetcher/smogon.py
- fetcher/pokedex.py
- fetcher/moveset.py
- fetcher/sheets.py
- fetcher/pokepaste.py
"""

import httpx

DEFAULT_TIMEOUT = 60.0


async def fetch_json(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict | None:
    """Fetch and parse JSON from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default 60)

    Returns:
        Parsed JSON as dict, or None if fetch failed
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Failed to fetch {url}: {e}")
            return None


async def fetch_text(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> str | None:
    """Fetch text content from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default 60)
        verify: Whether to verify SSL certificates (default True)

    Returns:
        Response text, or None if fetch failed
    """
    async with httpx.AsyncClient(timeout=timeout, verify=verify) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            print(f"Failed to fetch {url}: {e}")
            return None
