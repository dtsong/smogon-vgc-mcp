"""Tests for replay list MCP tool wrappers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from smogon_vgc_mcp.fetcher.replay_list import ReplayListEntry, ReplayListError, ReplayListResult


def _make_result(count: int = 3, private: bool = False) -> ReplayListResult:
    return ReplayListResult(
        replays=[
            ReplayListEntry(
                replay_id=f"replay-{i}",
                format="gen9vgc2026regf",
                players=["Alice", "Bob"],
                upload_time=1700000000 - i,
                rating=1500 + i,
                is_private=private,
            )
            for i in range(count)
        ],
        total_fetched=count,
        pages_fetched=1,
        has_more=False,
    )


@pytest.fixture
def _register_tools():
    """Register replay tools on a FastMCP instance and return the tool functions."""
    from mcp.server.fastmcp import FastMCP

    from smogon_vgc_mcp.tools.replay import register_replay_tools

    mcp = FastMCP("test")
    register_replay_tools(mcp)

    tools = {}
    for name, tool in mcp._tool_manager._tools.items():
        tools[name] = tool.fn
    return tools


class TestFetchUserPublicReplays:
    @pytest.mark.asyncio
    async def test_returns_correct_format(self, _register_tools):
        tool_fn = _register_tools["fetch_user_public_replays"]
        mock_result = _make_result(3)

        with patch(
            "smogon_vgc_mcp.tools.replay.fetch_public_replay_list",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await tool_fn("testuser")

        assert result["username"] == "testuser"
        assert result["format_filter"] is None
        assert len(result["replays"]) == 3
        assert result["total_found"] == 3
        assert result["pages_fetched"] == 1
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_replay_fields(self, _register_tools):
        tool_fn = _register_tools["fetch_user_public_replays"]
        mock_result = _make_result(1)

        with patch(
            "smogon_vgc_mcp.tools.replay.fetch_public_replay_list",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await tool_fn("testuser")

        replay = result["replays"][0]
        assert "replay_id" in replay
        assert "url" in replay
        assert "format" in replay
        assert "players" in replay
        assert "rating" in replay
        assert "upload_time" in replay
        assert "is_private" in replay

    @pytest.mark.asyncio
    async def test_format_filter_passed(self, _register_tools):
        tool_fn = _register_tools["fetch_user_public_replays"]

        with patch(
            "smogon_vgc_mcp.tools.replay.fetch_public_replay_list",
            new_callable=AsyncMock,
            return_value=_make_result(0),
        ) as mock_fetch:
            result = await tool_fn("user", format="gen9vgc2026regf")

        assert result["format_filter"] == "gen9vgc2026regf"
        mock_fetch.assert_called_once_with(
            username="user",
            format="gen9vgc2026regf",
            max_pages=5,
        )

    @pytest.mark.asyncio
    async def test_max_pages_capped_at_20(self, _register_tools):
        tool_fn = _register_tools["fetch_user_public_replays"]

        with patch(
            "smogon_vgc_mcp.tools.replay.fetch_public_replay_list",
            new_callable=AsyncMock,
            return_value=_make_result(0),
        ) as mock_fetch:
            await tool_fn("user", max_pages=100)

        assert mock_fetch.call_args.kwargs["max_pages"] == 20

    @pytest.mark.asyncio
    async def test_empty_username_returns_error(self, _register_tools):
        tool_fn = _register_tools["fetch_user_public_replays"]
        result = await tool_fn("")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_api_error_handled(self, _register_tools):
        tool_fn = _register_tools["fetch_user_public_replays"]

        with patch(
            "smogon_vgc_mcp.tools.replay.fetch_public_replay_list",
            new_callable=AsyncMock,
            side_effect=ReplayListError("API down"),
        ):
            result = await tool_fn("user")

        assert "error" in result
        assert "API" in result["error"]


class TestFetchPrivateReplays:
    @pytest.mark.asyncio
    async def test_returns_correct_format(self, _register_tools):
        tool_fn = _register_tools["fetch_private_replays"]
        mock_result = _make_result(2, private=True)
        mock_session = AsyncMock()
        mock_session.username = "testuser"
        mock_session.sid_cookie = "sid-value"

        with (
            patch(
                "smogon_vgc_mcp.fetcher.showdown_auth.authenticate_showdown",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch(
                "smogon_vgc_mcp.fetcher.replay_list.fetch_private_replay_list",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await tool_fn("testuser", "password123")

        assert result["username"] == "testuser"
        assert len(result["replays"]) == 2
        assert result["total_found"] == 2

    @pytest.mark.asyncio
    async def test_password_never_in_response(self, _register_tools):
        tool_fn = _register_tools["fetch_private_replays"]
        mock_result = _make_result(1, private=True)
        mock_session = AsyncMock()
        mock_session.username = "user"
        mock_session.sid_cookie = "sid"

        with (
            patch(
                "smogon_vgc_mcp.fetcher.showdown_auth.authenticate_showdown",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch(
                "smogon_vgc_mcp.fetcher.replay_list.fetch_private_replay_list",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await tool_fn("user", "supersecretpassword")

        result_str = str(result)
        assert "supersecretpassword" not in result_str
        assert "sid" not in result_str or "replay_id" in result_str

    @pytest.mark.asyncio
    async def test_auth_failure_returns_error(self, _register_tools):
        tool_fn = _register_tools["fetch_private_replays"]

        from smogon_vgc_mcp.fetcher.showdown_auth import AuthenticationError

        with patch(
            "smogon_vgc_mcp.fetcher.showdown_auth.authenticate_showdown",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("bad password"),
        ):
            result = await tool_fn("user", "wrongpass")

        assert "error" in result
        assert "Authentication" in result["error"]

    @pytest.mark.asyncio
    async def test_playwright_not_installed_returns_error(self, _register_tools):
        tool_fn = _register_tools["fetch_private_replays"]

        with patch(
            "smogon_vgc_mcp.fetcher.showdown_auth.authenticate_showdown",
            new_callable=AsyncMock,
            side_effect=ImportError("playwright not installed"),
        ):
            result = await tool_fn("user", "pass")

        assert "error" in result
        assert "playwright" in result["error"].lower() or "playwright" in result.get("hint", "").lower()

    @pytest.mark.asyncio
    async def test_empty_username_returns_error(self, _register_tools):
        tool_fn = _register_tools["fetch_private_replays"]
        result = await tool_fn("", "pass")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_max_pages_capped(self, _register_tools):
        tool_fn = _register_tools["fetch_private_replays"]
        mock_session = AsyncMock()
        mock_session.username = "user"
        mock_session.sid_cookie = "sid"

        with (
            patch(
                "smogon_vgc_mcp.fetcher.showdown_auth.authenticate_showdown",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch(
                "smogon_vgc_mcp.fetcher.replay_list.fetch_private_replay_list",
                new_callable=AsyncMock,
                return_value=_make_result(0),
            ) as mock_fetch,
        ):
            await tool_fn("user", "pass", max_pages=50)

        assert mock_fetch.call_args.kwargs["max_pages"] == 20
