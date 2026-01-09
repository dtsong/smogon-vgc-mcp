"""FastMCP wrapper that adds logging to all registered tools."""

from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.logging.decorators import log_tool_call


class LoggedFastMCP:
    """Wrapper around FastMCP that automatically adds logging to all tools.

    Use this in place of FastMCP when registering tools to get automatic
    structured logging with timing, correlation IDs, and error tracking.
    """

    def __init__(self, mcp: FastMCP) -> None:
        self._mcp = mcp

    def tool(self) -> Callable[[Callable], Callable]:
        """Return a tool decorator that wraps functions with logging."""
        original_decorator = self._mcp.tool()

        def wrapper(func: Callable) -> Callable:
            logged_func = log_tool_call(func)
            return original_decorator(logged_func)

        return wrapper

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the underlying FastMCP instance."""
        return getattr(self._mcp, name)
