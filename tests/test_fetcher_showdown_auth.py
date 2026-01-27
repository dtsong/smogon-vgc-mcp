"""Tests for Showdown authentication module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from smogon_vgc_mcp.fetcher.showdown_auth import (
    ShowdownSession,
    verify_session,
)


class TestShowdownSession:
    def test_cookie_header(self):
        session = ShowdownSession(sid_cookie="user,abc123,hash", username="testuser")
        assert session.cookie_header() == "sid=user,abc123,hash"

    def test_fields(self):
        session = ShowdownSession(sid_cookie="sid-value", username="myuser")
        assert session.sid_cookie == "sid-value"
        assert session.username == "myuser"


class TestVerifySession:
    @pytest.mark.asyncio
    async def test_valid_session(self):
        response = httpx.Response(
            status_code=200,
            content=b"]testuser,sysop",
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.showdown_auth.httpx.AsyncClient", return_value=mock_client):
            result = await verify_session("valid-sid")

        assert result == "testuser"

    @pytest.mark.asyncio
    async def test_guest_session(self):
        response = httpx.Response(
            status_code=200,
            content=b"]guest,0",
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.showdown_auth.httpx.AsyncClient", return_value=mock_client):
            result = await verify_session("expired-sid")

        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.showdown_auth.httpx.AsyncClient", return_value=mock_client):
            result = await verify_session("any-sid")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_response(self):
        response = httpx.Response(
            status_code=200,
            content=b"]",
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("smogon_vgc_mcp.fetcher.showdown_auth.httpx.AsyncClient", return_value=mock_client):
            result = await verify_session("sid")

        assert result is None


class TestAuthenticateShowdown:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            from smogon_vgc_mcp.fetcher.showdown_auth import authenticate_showdown

            with pytest.raises(ImportError, match="playwright"):
                await authenticate_showdown("user", "pass")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_login_flow(self):
        """Integration test: requires real credentials and playwright installed.

        Run with: pytest -m integration --showdown-user=X --showdown-pass=Y
        """
        pytest.skip("Requires real Showdown credentials")
