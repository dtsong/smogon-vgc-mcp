"""VGC format configuration and registry.

This module provides centralized configuration for different VGC formats
(Regulation F, G, H, etc.) including Smogon URLs, available months,
and Google Sheet tab IDs for tournament teams.
"""

from dataclasses import dataclass, field


@dataclass
class FormatConfig:
    """Configuration for a VGC format."""

    code: str  # Short code: "regf", "regg", "regh"
    name: str  # Display name: "Regulation F"
    smogon_format_id: str  # Smogon URL segment: "gen9vgc2026regfbo3"
    available_months: list[str]  # ["2025-11", "2025-12"]
    available_elos: list[int] = field(default_factory=lambda: [0, 1500, 1630, 1760])
    team_id_prefix: str = ""  # "F" for Reg F teams
    sheet_gid: str | None = None  # Google Sheet tab GID for tournament teams
    is_current: bool = False  # Mark the current/default format


# Google Sheet ID for VGC Pastes Repository
SHEET_ID = "1axlwmzPA49rYkqXh7zHvAtSP-TKbM0ijGYBPRflLSWw"

# Format Registry
FORMATS: dict[str, FormatConfig] = {
    "regf": FormatConfig(
        code="regf",
        name="Regulation F",
        smogon_format_id="gen9vgc2026regfbo3",
        available_months=["2025-11", "2025-12"],
        team_id_prefix="F",
        sheet_gid="1837599752",
        is_current=True,
    ),
    # Add more formats as they become available:
    # "regg": FormatConfig(
    #     code="regg",
    #     name="Regulation G",
    #     smogon_format_id="gen9vgc2026reggbo3",
    #     available_months=[],
    #     team_id_prefix="G",
    #     sheet_gid=None,
    # ),
}

DEFAULT_FORMAT = "regf"


def get_format(code: str) -> FormatConfig:
    """Get format configuration by code.

    Args:
        code: Format code (e.g., "regf", "regg")

    Returns:
        FormatConfig for the specified format

    Raises:
        ValueError: If format code is not found
    """
    if code not in FORMATS:
        available = ", ".join(FORMATS.keys())
        raise ValueError(f"Unknown format: {code}. Available formats: {available}")
    return FORMATS[code]


def get_current_format() -> FormatConfig:
    """Get the current default format.

    Returns:
        FormatConfig marked as is_current, or DEFAULT_FORMAT
    """
    for fmt in FORMATS.values():
        if fmt.is_current:
            return fmt
    return FORMATS[DEFAULT_FORMAT]


def list_formats() -> list[FormatConfig]:
    """List all available formats.

    Returns:
        List of all FormatConfig objects
    """
    return list(FORMATS.values())


def get_smogon_stats_url(format_code: str, month: str, elo: int) -> str:
    """Build Smogon chaos JSON URL for a format.

    Args:
        format_code: Format code (e.g., "regf")
        month: Month in YYYY-MM format
        elo: ELO bracket

    Returns:
        Full URL to Smogon stats JSON
    """
    fmt = get_format(format_code)
    return f"https://www.smogon.com/stats/{month}/chaos/{fmt.smogon_format_id}-{elo}.json"


def get_moveset_url(format_code: str, month: str, elo: int) -> str:
    """Build Smogon moveset text URL for a format.

    Args:
        format_code: Format code (e.g., "regf")
        month: Month in YYYY-MM format
        elo: ELO bracket

    Returns:
        Full URL to Smogon moveset text file
    """
    fmt = get_format(format_code)
    return f"https://www.smogon.com/stats/{month}/moveset/{fmt.smogon_format_id}-{elo}.txt"


def get_sheet_csv_url(format_code: str) -> str | None:
    """Build Google Sheet CSV URL for a format's tournament teams.

    Args:
        format_code: Format code (e.g., "regf")

    Returns:
        Full URL to Google Sheet CSV export, or None if no sheet configured
    """
    fmt = get_format(format_code)
    if not fmt.sheet_gid:
        return None
    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={fmt.sheet_gid}"
    )


def validate_month_for_format(format_code: str, month: str) -> None:
    """Validate that a month is available for a format.

    Args:
        format_code: Format code
        month: Month to validate

    Raises:
        ValueError: If month is not available for the format
    """
    fmt = get_format(format_code)
    if fmt.available_months and month not in fmt.available_months:
        available = ", ".join(fmt.available_months) or "none"
        raise ValueError(
            f"Month {month} not available for {fmt.name}. Available months: {available}"
        )
