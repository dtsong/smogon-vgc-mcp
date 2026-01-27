"""Integration tests for health check via MCP protocol."""

import pytest

from tests.integration.conftest import extract_tool_result


@pytest.mark.integration
class TestHealthCheckIntegration:
    @pytest.mark.asyncio
    async def test_get_service_health_returns_healthy(self, mcp_client):
        result = await mcp_client.call_tool("get_service_health")
        data = extract_tool_result(result)

        assert "healthy" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_get_service_health_has_all_checks(self, mcp_client):
        result = await mcp_client.call_tool("get_service_health")
        data = extract_tool_result(result)

        checks = data["checks"]
        assert "database" in checks
        assert "node_calc" in checks
        assert "tool_registration" in checks
        assert "circuit_breakers" in checks
        assert "data_availability" in checks

    @pytest.mark.asyncio
    async def test_database_check_ok_with_seeded_data(self, mcp_client):
        result = await mcp_client.call_tool("get_service_health")
        data = extract_tool_result(result)

        db_check = data["checks"]["database"]
        assert db_check["status"] == "ok"
        assert db_check["snapshot_count"] >= 1

    @pytest.mark.asyncio
    async def test_tool_registration_has_enough_tools(self, mcp_client):
        result = await mcp_client.call_tool("get_service_health")
        data = extract_tool_result(result)

        tools_check = data["checks"]["tool_registration"]
        assert tools_check["status"] == "ok"
        assert tools_check["tool_count"] >= 30

    @pytest.mark.asyncio
    async def test_data_availability_reflects_seeded_data(self, mcp_client):
        result = await mcp_client.call_tool("get_service_health")
        data = extract_tool_result(result)

        data_check = data["checks"]["data_availability"]
        assert data_check["status"] == "ok"
        assert data_check["usage_snapshots"] >= 1
        assert data_check["teams"] >= 1
