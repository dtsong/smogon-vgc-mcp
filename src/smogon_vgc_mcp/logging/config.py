"""Logging configuration utilities."""

import logging
import sys

from smogon_vgc_mcp.logging.formatters import JSONFormatter


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure the root logger with structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Default INFO.
        json_output: If True, use JSON format. If False, use plain text.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance by name."""
    return logging.getLogger(name)
