"""VGC format configuration and registry.

This module provides centralized configuration for different VGC formats
(Regulation F, G, H, etc.) including Smogon URLs, available months,
and Google Sheet tab IDs for tournament teams.
"""

from dataclasses import dataclass, field
from datetime import date, datetime


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
    generation: int = 9  # Pokemon generation (9 = Scarlet/Violet, 10 = Champions)
    stat_system: str = "gen9_ev_iv"  # Stat system: "gen9_ev_iv" or "champions_sp"
    calc_backend: str = "smogon_calc_gen9"  # Calc backend: "smogon_calc_gen9" or "python_native"
    smogon_stats_available: bool = True  # Whether Smogon chaos JSON stats exist
    min_battles: int = 500  # Minimum battle count to consider stats reliable
    # Historical archive support (Nugget Bridge indexing). Inclusive
    # (YYYY-MM-DD, YYYY-MM-DD) bounds used by get_format_for_date.
    date_range: tuple[str, str] | None = None
    is_historical: bool = False  # Archive-only format; skip live stats/sheet refresh


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
        is_current=False,
    ),
    "regi": FormatConfig(
        code="regi",
        name="Regulation I",
        smogon_format_id="gen9vgc2026regibo3",
        available_months=["2026-03", "2026-04", "2026-05"],
        team_id_prefix="I",
        sheet_gid=None,
        is_current=True,
    ),
    "champions_ma": FormatConfig(
        code="champions_ma",
        name="Champions Regulation M-A",
        smogon_format_id="",
        available_months=[],
        generation=10,
        stat_system="champions_sp",
        calc_backend="python_native",
        smogon_stats_available=False,
        sheet_gid="791705272",
        is_current=False,
    ),
    # Historical archives — Nugget Bridge corpus (2012-2017). No live stats,
    # no sheet data, read-only set/prose lookup via nugget_bridge tools.
    "vgc12": FormatConfig(
        code="vgc12",
        name="VGC 2012 (BW)",
        smogon_format_id="",
        available_months=[],
        generation=5,
        smogon_stats_available=False,
        date_range=("2012-01-01", "2012-12-31"),
        is_historical=True,
    ),
    "vgc13": FormatConfig(
        code="vgc13",
        name="VGC 2013 (BW2)",
        smogon_format_id="",
        available_months=[],
        generation=5,
        smogon_stats_available=False,
        date_range=("2013-01-01", "2013-12-31"),
        is_historical=True,
    ),
    "vgc14": FormatConfig(
        code="vgc14",
        name="VGC 2014 (XY)",
        smogon_format_id="",
        available_months=[],
        generation=6,
        smogon_stats_available=False,
        date_range=("2014-01-01", "2014-12-31"),
        is_historical=True,
    ),
    "vgc15": FormatConfig(
        code="vgc15",
        name="VGC 2015 (ORAS)",
        smogon_format_id="",
        available_months=[],
        generation=6,
        smogon_stats_available=False,
        date_range=("2015-01-01", "2015-12-31"),
        is_historical=True,
    ),
    "vgc16": FormatConfig(
        code="vgc16",
        name="VGC 2016 (ORAS restricted)",
        smogon_format_id="",
        available_months=[],
        generation=6,
        smogon_stats_available=False,
        date_range=("2016-01-01", "2016-08-31"),
        is_historical=True,
    ),
    "vgc17": FormatConfig(
        code="vgc17",
        name="VGC 2017 (SM)",
        smogon_format_id="",
        available_months=[],
        generation=7,
        smogon_stats_available=False,
        # Date range intentionally starts Sept 2016 (Sun/Moon release
        # window) even though the code year is 2017 — the competitive
        # VGC17 season opened before calendar 2017.
        date_range=("2016-09-01", "2017-12-31"),
        is_historical=True,
    ),
}

DEFAULT_FORMAT = "regi"


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


def get_format_for_date(dt: datetime | date | str) -> FormatConfig | None:
    """Resolve a FormatConfig from a publication date.

    Scans formats with a ``date_range`` and returns the first whose inclusive
    bounds contain ``dt``. Used by the Nugget Bridge ingest to tag historical
    posts with their contemporaneous VGC format.

    Args:
        dt: Date as a ``datetime``/``date`` or an ISO-8601 string (the first
            10 characters are parsed as ``YYYY-MM-DD``).

    Returns:
        Matching FormatConfig, or None if no format covers the date.
    """
    if isinstance(dt, str):
        iso = dt[:10]
    elif isinstance(dt, datetime):
        iso = dt.date().isoformat()
    else:
        iso = dt.isoformat()

    for fmt in FORMATS.values():
        if fmt.date_range is None:
            continue
        start, end = fmt.date_range
        if start <= iso <= end:
            return fmt
    return None


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
