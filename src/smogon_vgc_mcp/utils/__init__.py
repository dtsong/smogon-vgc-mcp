"""Shared utilities for the smogon-vgc-mcp project."""

from smogon_vgc_mcp.utils.ev_iv_parser import (
    default_evs,
    default_ivs,
    parse_ev_string,
    parse_iv_string,
)
from smogon_vgc_mcp.utils.formatting import (
    round_percent,
)
from smogon_vgc_mcp.utils.http_client import (
    fetch_json,
    fetch_text,
)
from smogon_vgc_mcp.utils.limits import (
    DEFAULT_MAX_LIMIT,
    MAX_ABILITIES_DISPLAY,
    MAX_COUNTERS_DISPLAY,
    MAX_ITEMS_DISPLAY,
    MAX_MOVES_DISPLAY,
    MAX_SPREADS_DISPLAY,
    MAX_TEAMMATES_DISPLAY,
    MAX_TERA_TYPES_DISPLAY,
    RANKINGS_MAX_LIMIT,
    cap_limit,
)
from smogon_vgc_mcp.utils.responses import (
    make_error_response,
)
from smogon_vgc_mcp.utils.stat_names import (
    SHOWDOWN_STAT_MAP,
    STAT_NAME_MAP,
    STAT_ORDER,
    normalize_stat_name,
)

__all__ = [
    # Stat names
    "STAT_ORDER",
    "STAT_NAME_MAP",
    "SHOWDOWN_STAT_MAP",
    "normalize_stat_name",
    # EV/IV parsing
    "parse_ev_string",
    "parse_iv_string",
    "default_evs",
    "default_ivs",
    # HTTP client
    "fetch_json",
    "fetch_text",
    # Limits
    "cap_limit",
    "DEFAULT_MAX_LIMIT",
    "RANKINGS_MAX_LIMIT",
    # Display limits
    "MAX_ABILITIES_DISPLAY",
    "MAX_ITEMS_DISPLAY",
    "MAX_MOVES_DISPLAY",
    "MAX_TEAMMATES_DISPLAY",
    "MAX_SPREADS_DISPLAY",
    "MAX_TERA_TYPES_DISPLAY",
    "MAX_COUNTERS_DISPLAY",
    # Formatting
    "round_percent",
    # Responses
    "make_error_response",
]
