"""Health check module for verifying server subsystems."""

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

from smogon_vgc_mcp.database import get_all_snapshots, get_pokedex_stats, get_team_count
from smogon_vgc_mcp.database.schema import get_connection
from smogon_vgc_mcp.resilience import get_all_circuit_states

CALC_WRAPPER_PATH = Path(__file__).parent.parent.parent / "calc" / "calc_wrapper.js"


async def check_database() -> dict[str, Any]:
    """Verify SQLite database is accessible and queryable."""
    try:
        async with get_connection() as db:
            async with db.execute("SELECT COUNT(*) FROM snapshots") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
        return {"status": "ok", "snapshot_count": count}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_node_calc() -> dict[str, Any]:
    """Verify calc_wrapper.js exists, node is available, and @smogon/calc is installed."""
    issues = []

    if not CALC_WRAPPER_PATH.exists():
        issues.append(f"calc_wrapper.js not found at {CALC_WRAPPER_PATH}")

    if not shutil.which("node"):
        issues.append("node not found on PATH")

    if not issues:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["node", "-e", "require('@smogon/calc')"],
                capture_output=True,
                timeout=10,
                cwd=CALC_WRAPPER_PATH.parent,
            )
            if result.returncode != 0:
                issues.append(f"@smogon/calc not installed: {result.stderr.decode().strip()}")
        except subprocess.TimeoutExpired:
            issues.append("node timed out checking @smogon/calc")
        except Exception as e:
            issues.append(f"node check failed: {e}")

    if issues:
        return {"status": "error", "issues": issues}
    return {"status": "ok"}


async def check_tool_registration() -> dict[str, Any]:
    """Verify the FastMCP server has the expected number of tools registered."""
    try:
        from smogon_vgc_mcp.server import create_server

        mcp = create_server()
        tools = await mcp.list_tools()
        tool_count = len(tools)
        if tool_count >= 30:
            return {"status": "ok", "tool_count": tool_count}
        return {
            "status": "degraded",
            "tool_count": tool_count,
            "message": f"Expected >= 30 tools, found {tool_count}",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_circuit_breakers() -> dict[str, Any]:
    """Return current circuit breaker states for all external services."""
    try:
        states = get_all_circuit_states()
        open_circuits = [name for name, s in states.items() if s.get("state") == "open"]
        return {
            "status": "ok" if not open_circuits else "degraded",
            "services": states,
            "open_circuits": open_circuits,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_data_availability() -> dict[str, Any]:
    """Check what data has been fetched and is available for queries."""
    try:
        snapshots = await get_all_snapshots()
        team_count = await get_team_count()
        pokedex = await get_pokedex_stats()

        return {
            "status": "ok",
            "usage_snapshots": len(snapshots),
            "teams": team_count,
            "pokedex": pokedex,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def run_health_check() -> dict[str, Any]:
    """Run all health checks and return aggregate result.

    healthy = True when database + tool registration + node calc are all "ok".
    Circuit breakers and data availability are informational only.
    """
    database, node_calc, tools = await asyncio.gather(
        check_database(),
        check_node_calc(),
        check_tool_registration(),
    )

    circuit_breakers = check_circuit_breakers()
    data = await check_data_availability()

    core_checks = {
        "database": database,
        "node_calc": node_calc,
        "tool_registration": tools,
    }
    healthy = all(c["status"] == "ok" for c in core_checks.values())

    return {
        "healthy": healthy,
        "checks": {
            **core_checks,
            "circuit_breakers": circuit_breakers,
            "data_availability": data,
        },
    }
