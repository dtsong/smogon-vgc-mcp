"""Tests for replay list fetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from smogon_vgc_mcp.fetcher.replay_list import (
    ReplayListEntry,
    ReplayListError,
    _check_action_error,
    _parse_replay_entries,
    _strip_dispatch_prefix,
    fetch_private_replay_list,
    fetch_public_replay_list,
)


class TestReplayListEntry:
    def test_url_public(self):
        entry = ReplayListEntry(
            replay_id="gen9vgc2026regf-123456",
            format="gen9vgc2026regf",
            players=["Alice", "Bob"],
            upload_time=1700000000,
        )
        assert entry.url == "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"

    def test_url_with_password(self):
        entry = ReplayListEntry(
            replay_id="gen9vgc2026regf-123456",
            format="gen9vgc2026regf",
            players=["Alice", "Bob"],
            upload_time=1700000000,
            password="abc123",
        )
        assert entry.url == "https://replay.pokemonshowdown.com/gen9vgc2026regf-123456-abc123pw"

    def test_private_flag(self):
        entry = ReplayListEntry(
            replay_id="test-1",
            format="gen9vgc2026regf",
            players=["A", "B"],
            upload_time=1,
            is_private=True,
        )
        assert entry.is_private is True

    def test_default_values(self):
        entry = ReplayListEntry(
            replay_id="test-1",
            format="gen9vgc2026regf",
            players=["A", "B"],
            upload_time=1,
        )
        assert entry.rating is None
        assert entry.is_private is False
        assert entry.password is None


class TestParseReplayEntries:
    def test_standard_entries(self):
        data = [
            {
                "id": "gen9vgc2026regf-100",
                "format": "gen9vgc2026regf",
                "p1": "Alice",
                "p2": "Bob",
                "uploadtime": 1700000000,
                "rating": 1500,
            },
            {
                "id": "gen9vgc2026regf-101",
                "format": "gen9vgc2026regf",
                "p1": "Charlie",
                "p2": "Diana",
                "uploadtime": 1700000001,
            },
        ]
        entries = _parse_replay_entries(data)
        assert len(entries) == 2
        assert entries[0].replay_id == "gen9vgc2026regf-100"
        assert entries[0].players == ["Alice", "Bob"]
        assert entries[0].rating == 1500
        assert entries[1].rating is None

    def test_empty_list(self):
        assert _parse_replay_entries([]) == []

    def test_unicode_players(self):
        data = [
            {
                "id": "test-1",
                "format": "gen9vgc2026regf",
                "p1": "用户名",
                "p2": "ユーザー",
                "uploadtime": 1,
            }
        ]
        entries = _parse_replay_entries(data)
        assert entries[0].players == ["用户名", "ユーザー"]

    def test_private_flag_propagated(self):
        data = [{"id": "x", "format": "f", "p1": "a", "p2": "b", "uploadtime": 1}]
        entries = _parse_replay_entries(data, private=True)
        assert entries[0].is_private is True

    def test_missing_fields_use_defaults(self):
        data = [{}]
        entries = _parse_replay_entries(data)
        assert entries[0].replay_id == ""
        assert entries[0].format == ""
        assert entries[0].players == ["", ""]
        assert entries[0].upload_time == 0


class TestStripDispatchPrefix:
    def test_with_prefix(self):
        assert _strip_dispatch_prefix(']{"key":"value"}') == '{"key":"value"}'

    def test_without_prefix(self):
        assert _strip_dispatch_prefix('{"key":"value"}') == '{"key":"value"}'

    def test_empty_string(self):
        assert _strip_dispatch_prefix("") == ""

    def test_only_prefix(self):
        assert _strip_dispatch_prefix("]") == ""

    def test_double_prefix(self):
        assert _strip_dispatch_prefix("]]data") == "]data"


class TestCheckActionError:
    def test_raises_on_actionerror(self):
        with pytest.raises(ReplayListError, match="not found"):
            _check_action_error({"actionerror": "not found"})

    def test_no_error_dict(self):
        _check_action_error({"data": "ok"})

    def test_no_error_list(self):
        _check_action_error([{"id": "x"}])


def _make_response(data, status_code=200):
    """Build a mock httpx.Response."""
    import json

    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        request=httpx.Request("GET", "https://example.com"),
    )


def _make_text_response(text, status_code=200):
    """Build a mock httpx.Response with raw text."""
    return httpx.Response(
        status_code=status_code,
        content=text.encode(),
        request=httpx.Request("GET", "https://example.com"),
    )


class TestFetchPublicReplayList:
    @pytest.mark.asyncio
    async def test_single_page(self):
        replays = [
            {"id": f"replay-{i}", "format": "gen9vgc2026regf", "p1": "A", "p2": "B", "uploadtime": 100 - i}
            for i in range(10)
        ]
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_response(replays))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_public_replay_list("testuser")

        assert result.total_fetched == 10
        assert result.pages_fetched == 1
        assert result.has_more is False
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_pagination_multiple_pages(self):
        page1 = [
            {"id": f"replay-{i}", "format": "f", "p1": "A", "p2": "B", "uploadtime": 200 - i}
            for i in range(51)
        ]
        page2 = [
            {"id": f"replay-{i + 51}", "format": "f", "p1": "A", "p2": "B", "uploadtime": 100 - i}
            for i in range(10)
        ]
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[_make_response(page1), _make_response(page2)])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client),
            patch("smogon_vgc_mcp.fetcher.replay_list.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await fetch_public_replay_list("testuser", max_pages=5)

        assert result.pages_fetched == 2
        assert result.total_fetched == 60
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_format_filter(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_response([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_public_replay_list("testuser", format="gen9vgc2026regf")

        call_kwargs = mock_client.get.call_args
        assert "gen9vgc2026regf" in str(call_kwargs)
        assert result.total_fetched == 0

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_response([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_public_replay_list("nonexistent")

        assert result.total_fetched == 0
        assert result.pages_fetched == 0
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_http_error(self):
        mock_client = AsyncMock()
        error_response = httpx.Response(
            status_code=500,
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("Server Error", request=httpx.Request("GET", "https://example.com"), response=error_response))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_public_replay_list("testuser")

        assert len(result.errors) == 1
        assert "500" in result.errors[0]

    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self):
        page1 = [
            {"id": f"replay-{i}", "format": "f", "p1": "A", "p2": "B", "uploadtime": 200 - i}
            for i in range(51)
        ]
        page2 = [
            {"id": f"replay-{i + 51}", "format": "f", "p1": "A", "p2": "B", "uploadtime": 100 - i}
            for i in range(5)
        ]
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[_make_response(page1), _make_response(page2)])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_sleep = AsyncMock()
        with (
            patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client),
            patch("smogon_vgc_mcp.fetcher.replay_list.asyncio.sleep", mock_sleep),
        ):
            await fetch_public_replay_list("testuser", max_pages=5)

        mock_sleep.assert_called_once_with(1.0)


class TestFetchPrivateReplayList:
    @pytest.mark.asyncio
    async def test_valid_cookie(self):
        import json

        replays = [
            {"id": f"private-{i}", "format": "gen9vgc2026regf", "p1": "Me", "p2": "Them", "uploadtime": 100 - i, "private": True}
            for i in range(5)
        ]
        raw_text = "]" + json.dumps(replays)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_text_response(raw_text))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_private_replay_list("testuser", "valid-sid-cookie")

        assert result.total_fetched == 5
        assert all(r.is_private for r in result.replays)

    @pytest.mark.asyncio
    async def test_invalid_cookie_actionerror(self):
        import json

        raw_text = "]" + json.dumps({"actionerror": "not logged in"})
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_text_response(raw_text))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(ReplayListError, match="not logged in"),
        ):
            await fetch_private_replay_list("testuser", "invalid-sid")

    @pytest.mark.asyncio
    async def test_prefix_stripping(self):
        import json

        replays = [{"id": "x", "format": "f", "p1": "a", "p2": "b", "uploadtime": 1}]
        raw_text = "]" + json.dumps(replays)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_text_response(raw_text))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_private_replay_list("user", "sid")

        assert result.total_fetched == 1

    @pytest.mark.asyncio
    async def test_cookie_header_sent(self):
        import json

        raw_text = "]" + json.dumps([])
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_text_response(raw_text))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.replay_list.httpx.AsyncClient", return_value=mock_client):
            await fetch_private_replay_list("user", "my-sid-value")

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["headers"]["Cookie"] == "sid=my-sid-value"
