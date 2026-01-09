"""MCP server setup for Smogon VGC stats."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.logging import LoggedFastMCP
from smogon_vgc_mcp.resources import register_vgc_resources
from smogon_vgc_mcp.tools import (
    register_admin_tools,
    register_calculator_tools,
    register_damage_tools,
    register_ev_generator_tools,
    register_pokedex_tools,
    register_pokemon_tools,
    register_rankings_tools,
    register_team_tools,
    register_teambuilding_tools,
)


def create_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP(
        name="smogon-vgc",
        instructions="VGC competitive Pokemon stats from Smogon. Supports multiple formats "
        "(Reg F, Reg G, etc.) via the 'format' parameter on tools. Default format is 'regf'. "
        "Use list_available_formats() to see supported formats.",
    )

    logged_mcp = LoggedFastMCP(mcp)

    # Register tools with logging wrapper
    register_pokemon_tools(logged_mcp)
    register_rankings_tools(logged_mcp)
    register_teambuilding_tools(logged_mcp)
    register_team_tools(logged_mcp)
    register_calculator_tools(logged_mcp)
    register_damage_tools(logged_mcp)
    register_ev_generator_tools(logged_mcp)
    register_pokedex_tools(logged_mcp)
    register_admin_tools(logged_mcp)

    # Register resources (no logging needed for resources)
    register_vgc_resources(mcp)

    return mcp


# Create the server instance
server = create_server()
