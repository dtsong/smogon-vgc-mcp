import pytest

from smogon_vgc_mcp.fetcher.ingestion.classifier import Tier, classify_url


@pytest.mark.parametrize(
    "url, tier",
    [
        ("https://pokepast.es/abc123", Tier.POKEPASTE),
        ("http://pokepast.es/abc123", Tier.POKEPASTE),
        ("https://pokepast.es/abc123/raw", Tier.POKEPASTE),
        ("https://www.pokepast.es/abc123", Tier.POKEPASTE),
        ("https://twitter.com/user/status/12345", Tier.X),
        ("https://x.com/user/status/12345", Tier.X),
        ("https://mobile.twitter.com/user/status/12345", Tier.X),
        ("https://nuggetbridge.com/2016/01/foo", Tier.BLOG),
        ("https://smogon.com/forums/threads/x.12345/", Tier.BLOG),
        ("https://medium.com/@user/my-team", Tier.BLOG),
        ("", Tier.UNKNOWN),
        ("not-a-url", Tier.UNKNOWN),
        ("ftp://example.com/file", Tier.UNKNOWN),
    ],
)
def test_classify_url(url: str, tier: Tier):
    assert classify_url(url) == tier
