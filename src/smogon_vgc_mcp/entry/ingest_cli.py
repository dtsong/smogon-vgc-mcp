"""vgc-ingest CLI: ingest a single URL into champions_teams."""

from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

from smogon_vgc_mcp.fetcher.ingestion.pipeline import ingest_url


async def main_async(argv: list[str], *, db_path: Path | None = None) -> int:
    if not argv:
        print("Usage: vgc-ingest <url>", file=sys.stderr)
        return 1
    url = argv[0]
    result = await ingest_url(url, db_path=db_path)
    print(f"status: {result.status}")
    if result.team_row_id is not None:
        print(f"team_row_id: {result.team_row_id}")
    if result.confidence is not None:
        print(f"confidence: {result.confidence:.2f}")
    if result.reason:
        print(f"reason: {result.reason}")

    # Exit code mapping (for scripting / CI):
    #   0  — persisted (auto or review_pending)
    #   2  — rejected (URL unsupported or tier not implemented)
    #   3  — fetch_failed (network / HTTP error)
    #   4  — parse_failed (non-parseable content)
    #   5  — db_error (validated team couldn't be persisted)
    if result.status in ("auto", "review_pending"):
        return 0
    if result.status == "fetch_failed":
        return 3
    if result.status == "parse_failed":
        return 4
    if result.status == "db_error":
        return 5
    return 2  # rejected


def main() -> None:
    try:
        sys.exit(asyncio.run(main_async(sys.argv[1:])))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
