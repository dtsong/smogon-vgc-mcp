"""STDIO entry point for Smogon VGC MCP server."""

from smogon_vgc_mcp.server import server


def main() -> None:
    """Run the MCP server with STDIO transport."""
    server.run()


if __name__ == "__main__":
    main()
