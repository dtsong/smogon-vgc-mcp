"""STDIO entry point for Smogon VGC MCP server."""

import os

from smogon_vgc_mcp.logging import configure_logging
from smogon_vgc_mcp.server import server


def main() -> None:
    """Run the MCP server with STDIO transport."""
    configure_logging(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        json_output=os.environ.get("LOG_FORMAT", "json") == "json",
    )
    server.run()


if __name__ == "__main__":
    main()
