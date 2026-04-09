"""Tests for health check module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smogon_vgc_mcp.health import (
    check_circuit_breakers,
    check_database,
    check_node_calc,
    check_tool_registration,
    run_health_check,
)


def _make_db_mock(cursor_mock):
    """Build an async-context-manager mock for get_connection() -> db.execute()."""
    exec_cm = AsyncMock()
    exec_cm.__aenter__ = AsyncMock(return_value=cursor_mock)
    exec_cm.__aexit__ = AsyncMock(return_value=None)

    mock_db = AsyncMock()
    mock_db.execute = MagicMock(return_value=exec_cm)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)

    conn_cm = MagicMock()
    conn_cm.__aenter__ = AsyncMock(return_value=mock_db)
    conn_cm.__aexit__ = AsyncMock(return_value=None)
    return conn_cm


class TestCheckDatabase:
    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.get_connection")
    async def test_ok_when_accessible(self, mock_get_conn):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(5,))

        mock_get_conn.return_value = _make_db_mock(mock_cursor)

        result = await check_database()
        assert result["status"] == "ok"
        assert result["snapshot_count"] == 5

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.get_connection")
    async def test_error_when_connection_fails(self, mock_get_conn):
        conn_cm = MagicMock()
        conn_cm.__aenter__ = AsyncMock(side_effect=Exception("database locked"))
        conn_cm.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = conn_cm

        result = await check_database()
        assert result["status"] == "error"
        assert "database locked" in result["error"]


class TestCheckNodeCalc:
    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.CALC_WRAPPER_PATH")
    @patch("shutil.which")
    @patch("asyncio.to_thread")
    async def test_ok_when_all_available(self, mock_to_thread, mock_which, mock_path):
        mock_path.exists.return_value = True
        mock_path.parent = "/fake/path"
        mock_which.return_value = "/usr/bin/node"
        mock_to_thread.return_value = MagicMock(returncode=0)

        result = await check_node_calc()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.CALC_WRAPPER_PATH")
    @patch("shutil.which")
    async def test_error_when_wrapper_missing(self, mock_which, mock_path):
        mock_path.exists.return_value = False
        mock_path.__str__ = lambda self: "/fake/calc_wrapper.js"
        mock_which.return_value = "/usr/bin/node"

        result = await check_node_calc()
        assert result["status"] == "error"
        assert any("calc_wrapper.js not found" in i for i in result["issues"])

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.CALC_WRAPPER_PATH")
    @patch("shutil.which")
    async def test_error_when_node_unavailable(self, mock_which, mock_path):
        mock_path.exists.return_value = True
        mock_which.return_value = None

        result = await check_node_calc()
        assert result["status"] == "error"
        assert any("node not found" in i for i in result["issues"])

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.CALC_WRAPPER_PATH")
    @patch("shutil.which")
    @patch("asyncio.to_thread")
    async def test_error_when_smogon_calc_missing(self, mock_to_thread, mock_which, mock_path):
        mock_path.exists.return_value = True
        mock_path.parent = "/fake/path"
        mock_which.return_value = "/usr/bin/node"
        mock_to_thread.return_value = MagicMock(
            returncode=1,
            stderr=b"Cannot find module '@smogon/calc'",
        )

        result = await check_node_calc()
        assert result["status"] == "error"
        assert any("@smogon/calc not installed" in i for i in result["issues"])


class TestCheckToolRegistration:
    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.server.create_server")
    async def test_ok_with_enough_tools(self, mock_create):
        mock_mcp = AsyncMock()
        mock_mcp.list_tools = AsyncMock(return_value=[MagicMock()] * 35)
        mock_create.return_value = mock_mcp

        result = await check_tool_registration()
        assert result["status"] == "ok"
        assert result["tool_count"] == 35

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.server.create_server")
    async def test_degraded_with_few_tools(self, mock_create):
        mock_mcp = AsyncMock()
        mock_mcp.list_tools = AsyncMock(return_value=[MagicMock()] * 10)
        mock_create.return_value = mock_mcp

        result = await check_tool_registration()
        assert result["status"] == "degraded"
        assert result["tool_count"] == 10


class TestCheckCircuitBreakers:
    @patch("smogon_vgc_mcp.health.get_all_circuit_states")
    def test_ok_when_all_closed(self, mock_states):
        mock_states.return_value = {
            "smogon": {"state": "closed"},
            "showdown": {"state": "closed"},
        }
        result = check_circuit_breakers()
        assert result["status"] == "ok"
        assert result["open_circuits"] == []

    @patch("smogon_vgc_mcp.health.get_all_circuit_states")
    def test_degraded_when_circuit_open(self, mock_states):
        mock_states.return_value = {
            "smogon": {"state": "open"},
            "showdown": {"state": "closed"},
        }
        result = check_circuit_breakers()
        assert result["status"] == "degraded"
        assert "smogon" in result["open_circuits"]


class TestRunHealthCheck:
    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.check_data_availability")
    @patch("smogon_vgc_mcp.health.check_circuit_breakers")
    @patch("smogon_vgc_mcp.health.check_tool_registration")
    @patch("smogon_vgc_mcp.health.check_node_calc")
    @patch("smogon_vgc_mcp.health.check_database")
    async def test_healthy_when_all_core_ok(
        self, mock_db, mock_node, mock_tools, mock_cb, mock_data
    ):
        mock_db.return_value = {"status": "ok", "snapshot_count": 3}
        mock_node.return_value = {"status": "ok"}
        mock_tools.return_value = {"status": "ok", "tool_count": 35}
        mock_cb.return_value = {"status": "ok", "services": {}, "open_circuits": []}
        mock_data.return_value = {"status": "ok", "usage_snapshots": 3, "teams": 10, "pokedex": {}}

        result = await run_health_check()
        assert result["healthy"] is True
        assert "database" in result["checks"]
        assert "node_calc" in result["checks"]
        assert "tool_registration" in result["checks"]
        assert "circuit_breakers" in result["checks"]
        assert "data_availability" in result["checks"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.check_data_availability")
    @patch("smogon_vgc_mcp.health.check_circuit_breakers")
    @patch("smogon_vgc_mcp.health.check_tool_registration")
    @patch("smogon_vgc_mcp.health.check_node_calc")
    @patch("smogon_vgc_mcp.health.check_database")
    async def test_unhealthy_when_database_fails(
        self, mock_db, mock_node, mock_tools, mock_cb, mock_data
    ):
        mock_db.return_value = {"status": "error", "error": "cannot open database"}
        mock_node.return_value = {"status": "ok"}
        mock_tools.return_value = {"status": "ok", "tool_count": 35}
        mock_cb.return_value = {"status": "ok", "services": {}, "open_circuits": []}
        mock_data.return_value = {"status": "error", "error": "cannot open database"}

        result = await run_health_check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.check_data_availability")
    @patch("smogon_vgc_mcp.health.check_circuit_breakers")
    @patch("smogon_vgc_mcp.health.check_tool_registration")
    @patch("smogon_vgc_mcp.health.check_node_calc")
    @patch("smogon_vgc_mcp.health.check_database")
    async def test_unhealthy_when_node_fails(
        self, mock_db, mock_node, mock_tools, mock_cb, mock_data
    ):
        mock_db.return_value = {"status": "ok", "snapshot_count": 0}
        mock_node.return_value = {"status": "error", "issues": ["node not found"]}
        mock_tools.return_value = {"status": "ok", "tool_count": 35}
        mock_cb.return_value = {"status": "ok", "services": {}, "open_circuits": []}
        mock_data.return_value = {"status": "ok", "usage_snapshots": 0, "teams": 0, "pokedex": {}}

        result = await run_health_check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.health.check_data_availability")
    @patch("smogon_vgc_mcp.health.check_circuit_breakers")
    @patch("smogon_vgc_mcp.health.check_tool_registration")
    @patch("smogon_vgc_mcp.health.check_node_calc")
    @patch("smogon_vgc_mcp.health.check_database")
    async def test_healthy_even_with_degraded_circuit_breakers(
        self, mock_db, mock_node, mock_tools, mock_cb, mock_data
    ):
        mock_db.return_value = {"status": "ok", "snapshot_count": 3}
        mock_node.return_value = {"status": "ok"}
        mock_tools.return_value = {"status": "ok", "tool_count": 35}
        mock_cb.return_value = {
            "status": "degraded",
            "services": {"smogon": {"state": "open"}},
            "open_circuits": ["smogon"],
        }
        mock_data.return_value = {"status": "ok", "usage_snapshots": 0, "teams": 0, "pokedex": {}}

        result = await run_health_check()
        assert result["healthy"] is True
