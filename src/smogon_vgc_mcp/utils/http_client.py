"""Unified async HTTP client utilities.

This module consolidates HTTP fetching patterns from:
- fetcher/smogon.py
- fetcher/pokedex.py
- fetcher/moveset.py
- fetcher/sheets.py
- fetcher/pokepaste.py
"""

import httpx

from smogon_vgc_mcp.logging import get_logger, log_http_request

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 60.0


@log_http_request
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
            logger.error("Failed to fetch JSON from %s: %s", url, e)
            return None


@log_http_request
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
            logger.error("Failed to fetch text from %s: %s", url, e)
            return None
