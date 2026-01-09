"""Structured logging module for the Smogon VGC MCP server."""

from smogon_vgc_mcp.logging.config import configure_logging, get_logger
from smogon_vgc_mcp.logging.context import (
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)
from smogon_vgc_mcp.logging.decorators import (
    log_database_operation,
    log_http_request,
    log_tool_call,
)
from smogon_vgc_mcp.logging.formatters import JSONFormatter
from smogon_vgc_mcp.logging.redaction import redact_sensitive
from smogon_vgc_mcp.logging.tool_wrapper import LoggedFastMCP

__all__ = [
    "configure_logging",
    "get_logger",
    "correlation_context",
    "get_correlation_id",
    "set_correlation_id",
    "log_database_operation",
    "log_http_request",
    "log_tool_call",
    "JSONFormatter",
    "redact_sensitive",
    "LoggedFastMCP",
]
