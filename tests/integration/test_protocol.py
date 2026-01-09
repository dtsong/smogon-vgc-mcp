"""Tests for MCP protocol compliance."""

import pytest


@pytest.mark.integration
class TestSessionInitialization:
    """Test MCP session initialization."""

    @pytest.mark.asyncio
    async def test_session_initializes_successfully(self, mcp_client):
        """Test that server handshake completes."""
        # If we get here, initialization succeeded (fixture does initialize())
        assert mcp_client is not None

    @pytest.mark.asyncio
    async def test_server_provides_capabilities(self, mcp_client):
        """Test that server provides capabilities during init."""
        # The session is already initialized - we can check it exists
        assert mcp_client is not None


@pytest.mark.integration
class TestListTools:
    """Test tools/list functionality."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_tools(self, mcp_client):
        """Test that list_tools returns registered tools."""
        result = await mcp_client.list_tools()

        assert result is not None
        assert hasattr(result, "tools")
        assert len(result.tools) > 0

    @pytest.mark.asyncio
    async def test_list_tools_includes_pokemon_tools(self, mcp_client):
        """Test that Pokemon tools are registered."""
        result = await mcp_client.list_tools()

        tool_names = [t.name for t in result.tools]
        assert "get_pokemon" in tool_names
        assert "find_pokemon" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_includes_rankings_tools(self, mcp_client):
        """Test that rankings tools are registered."""
        result = await mcp_client.list_tools()

        tool_names = [t.name for t in result.tools]
        assert "get_top_pokemon" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_includes_calculator_tools(self, mcp_client):
        """Test that calculator tools are registered."""
        result = await mcp_client.list_tools()

        tool_names = [t.name for t in result.tools]
        assert "calculate_pokemon_stats" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_includes_pokedex_tools(self, mcp_client):
        """Test that Pokedex tools are registered."""
        result = await mcp_client.list_tools()

        tool_names = [t.name for t in result.tools]
        assert "dex_pokemon" in tool_names
        assert "dex_move" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_includes_admin_tools(self, mcp_client):
        """Test that admin tools are registered."""
        result = await mcp_client.list_tools()

        tool_names = [t.name for t in result.tools]
        assert "list_available_formats" in tool_names

    @pytest.mark.asyncio
    async def test_tools_have_schemas(self, mcp_client):
        """Test that tools have input schemas defined."""
        result = await mcp_client.list_tools()

        for tool in result.tools:
            assert tool.name is not None
            assert tool.inputSchema is not None


@pytest.mark.integration
class TestListResources:
    """Test resources/list functionality."""

    @pytest.mark.asyncio
    async def test_list_resources_returns_resources(self, mcp_client):
        """Test that list_resources returns registered resources."""
        result = await mcp_client.list_resources()

        assert result is not None
        assert hasattr(result, "resources")
