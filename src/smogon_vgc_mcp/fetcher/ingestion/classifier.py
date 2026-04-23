"""URL shape classifier for the ingestion pipeline."""

from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse


class Tier(Enum):
    POKEPASTE = "pokepaste"
    X = "x"
    BLOG = "blog"
    UNKNOWN = "unknown"


_POKEPASTE_HOSTS = frozenset({"pokepast.es", "www.pokepast.es"})
_X_HOSTS = frozenset(
    {
        "twitter.com",
        "www.twitter.com",
        "mobile.twitter.com",
        "x.com",
        "www.x.com",
    }
)


def classify_url(url: str) -> Tier:
    """Return the Tier enum for a raw URL string."""
    if not url:
        return Tier.UNKNOWN
    try:
        parsed = urlparse(url)
    except ValueError:
        return Tier.UNKNOWN
    if parsed.scheme not in ("http", "https"):
        return Tier.UNKNOWN
    host = (parsed.netloc or "").casefold()
    if host in _POKEPASTE_HOSTS:
        return Tier.POKEPASTE
    if host in _X_HOSTS:
        return Tier.X
    if host:  # any other http(s) host counts as a generic blog URL
        return Tier.BLOG
    return Tier.UNKNOWN
