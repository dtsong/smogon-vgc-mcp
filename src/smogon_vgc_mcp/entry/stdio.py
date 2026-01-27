"""STDIO entry point for Smogon VGC MCP server."""

import asyncio
import os
import sys

from smogon_vgc_mcp.logging import configure_logging
from smogon_vgc_mcp.server import server


def main() -> None:
    """Run the MCP server with STDIO transport."""
    if "--health" in sys.argv:
        from smogon_vgc_mcp.health import run_health_check

        result = asyncio.run(run_health_check())
        _print_health(result)
        sys.exit(0 if result["healthy"] else 1)

    configure_logging(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        json_output=os.environ.get("LOG_FORMAT", "json") == "json",
    )
    server.run()


def _print_health(result: dict) -> None:
    """Print health check results in human-readable format."""
    status = "HEALTHY" if result["healthy"] else "UNHEALTHY"
    print(f"\n{'=' * 40}")
    print(f"  Server Health: {status}")
    print(f"{'=' * 40}\n")

    for name, check in result["checks"].items():
        label = name.replace("_", " ").title()
        icon = {"ok": "+", "degraded": "~", "error": "!"}
        status_char = icon.get(check["status"], "?")
        print(f"  [{status_char}] {label}: {check['status']}")

        if check.get("error"):
            print(f"      Error: {check['error']}")
        if check.get("issues"):
            for issue in check["issues"]:
                print(f"      - {issue}")
        if check.get("message"):
            print(f"      {check['message']}")
        if check.get("tool_count") is not None:
            print(f"      Tools: {check['tool_count']}")
        if check.get("snapshot_count") is not None:
            print(f"      Snapshots: {check['snapshot_count']}")
        if check.get("open_circuits"):
            print(f"      Open circuits: {', '.join(check['open_circuits'])}")
        if name == "data_availability" and check["status"] == "ok":
            print(f"      Usage snapshots: {check.get('usage_snapshots', 0)}")
            print(f"      Teams: {check.get('teams', 0)}")
            pokedex = check.get("pokedex", {})
            if pokedex:
                total = sum(pokedex.values())
                print(f"      Pokedex entries: {total}")

    print()


if __name__ == "__main__":
    main()
