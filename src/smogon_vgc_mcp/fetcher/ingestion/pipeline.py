"""Top-level ingestion orchestrator.

Routes a URL through the classifier to the appropriate tier handler,
then normalizes, validates, and writes the team to ChampionsTeam with
either ``auto`` or ``review_pending`` ingestion_status based on
confidence.

Additional tiers are added by inserting a branch in ``ingest_url``
and wiring a ``_fetch_tierN`` coroutine.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import aiosqlite

from smogon_vgc_mcp.database.champions_team_queries import (
    compute_team_fingerprint,
    write_or_queue_team,
)
from smogon_vgc_mcp.database.models import ChampionsTeam, ChampionsTeamDraft
from smogon_vgc_mcp.database.schema import get_connection, init_database
from smogon_vgc_mcp.fetcher.ingestion.classifier import Tier, classify_url
from smogon_vgc_mcp.fetcher.ingestion.normalizer import normalize
from smogon_vgc_mcp.fetcher.ingestion.tier1_pokepaste import (
    parse_pokepaste_to_champions_draft,
)
from smogon_vgc_mcp.fetcher.ingestion.validator import DexLookup, validate
from smogon_vgc_mcp.fetcher.pokepaste import fetch_pokepaste
from smogon_vgc_mcp.resilience import ErrorCategory, FetchResult, ServiceError

logger = logging.getLogger(__name__)

AUTO_WRITE_THRESHOLD = 0.85

IngestStatus = Literal[
    "auto", "review_pending", "fetch_failed", "parse_failed", "db_error", "rejected"
]
# Subset actually persisted to ChampionsTeam.ingestion_status. Other
# IngestStatus values are transient: either we never got to a DB write
# (fetch_failed / parse_failed / rejected) or the write itself raised
# (db_error).
WrittenIngestionStatus = Literal["auto", "review_pending"]


@dataclass(frozen=True)
class IngestResult:
    status: IngestStatus
    team_row_id: int | None = None
    confidence: float | None = None
    reason: str | None = None


async def _fetch_tier1(url: str) -> FetchResult[ChampionsTeamDraft]:
    fetched = await fetch_pokepaste(url)
    if not fetched.success or fetched.data is None or fetched.data == "":
        if fetched.error is not None:
            return FetchResult.fail(fetched.error)
        # Empty body on a 2xx (e.g. rate-limit HTML scrubbed or a CDN
        # 200-with-no-content). Logged at warning so the later
        # parse_failed(empty_parse) bucket is explainable in logs.
        logger.warning("pokepaste fetch succeeded with empty body: url=%s", url)
        return FetchResult.ok(None)
    try:
        draft = parse_pokepaste_to_champions_draft(fetched.data, source_url=url)
    except (ValueError, KeyError, IndexError, AttributeError, TypeError, re.error) as exc:
        # Narrow catch — parser bugs surface as real parse errors; let
        # system-level failures (MemoryError, RecursionError) propagate
        # so a resource-exhaustion crash isn't mislabeled parse_failed.
        # re.error is included because the parser uses regex and any
        # future dynamic pattern would raise this on malformed input.
        return FetchResult.fail(
            ServiceError(
                category=ErrorCategory.PARSE_ERROR,
                service="pokepaste",
                message=f"Failed to parse pokepaste from {url}: {exc}",
            )
        )
    if not draft.pokemon:
        logger.warning("pokepaste parsed to zero pokemon: url=%s", url)
        return FetchResult.ok(None)
    return FetchResult.ok(draft)


def _score(draft: ChampionsTeamDraft, soft_count: int) -> float:
    """Tier baseline minus 0.1 per soft-failure code, clamped at 0.0."""
    return max(0.0, draft.tier_baseline_confidence - 0.1 * soft_count)


async def load_dex_lookup(db_path: Path | None = None) -> DexLookup | None:
    """Build a dex lookup keyed on casefolded Pokemon name.

    Returns None if the ``champions_dex_pokemon`` table has no rows or
    if the query fails for any reason — callers should treat that as
    "dex not loaded" and skip identity/legality checks. Logs once at
    warning level when empty and at error level on DB failure, so the
    silent-skip condition is visible in production.
    """
    try:
        async with get_connection(db_path) as db:
            db.row_factory = aiosqlite.Row
            pokemon_rows = await db.execute_fetchall(
                "SELECT name, ability1, ability2, ability_hidden FROM champions_dex_pokemon"
            )
            if not pokemon_rows:
                logger.warning(
                    "load_dex_lookup: champions_dex_pokemon is empty — "
                    "identity/legality checks will be skipped"
                )
                return None

            learnset_rows = await db.execute_fetchall(
                """
                SELECT p.name AS pokemon_name, m.name AS move_name
                FROM champions_dex_learnsets l
                JOIN champions_dex_pokemon p ON p.id = l.pokemon_id
                JOIN champions_dex_moves m ON m.id = l.move_id
                """
            )
            if not learnset_rows:
                # Pokemon rows exist but the learnset join is empty —
                # returning a partial lookup would pass identity checks
                # while flagging every move as move_illegal, flooding
                # every team into review_pending. Returning None instead
                # skips all dex-dependent checks, matching the
                # "dex not loaded" contract documented in the docstring.
                logger.warning(
                    "load_dex_lookup: champions_dex_learnsets is empty — "
                    "skipping all dex-dependent checks"
                )
                return None
    except (aiosqlite.Error, OSError):
        # A missing/corrupt dex should not take down the whole ingest
        # run. Skip the optional checks and let the pipeline proceed on
        # SP/shape/vocab validation alone. Narrower than `Exception` so
        # programming bugs (TypeError, KeyError) still surface.
        logger.exception("load_dex_lookup: failed to load champions dex; skipping identity checks")
        return None

    lookup: DexLookup = {}
    for row in pokemon_rows:
        abilities = [row[k] for k in ("ability1", "ability2", "ability_hidden") if row[k]]
        lookup[row["name"].casefold()] = {"abilities": abilities, "moves": []}
    for row in learnset_rows:
        key = row["pokemon_name"].casefold()
        entry = lookup.get(key)
        if entry is not None:
            entry["moves"].append(row["move_name"])
    return lookup


async def ingest_url(
    url: str,
    *,
    db_path: Path | None = None,
    dex_lookup: DexLookup | None = None,
    skip_init: bool = False,
) -> IngestResult:
    # Batch callers that already initialized the DB (e.g. the sheet
    # runner) can pass ``skip_init=True`` to avoid rerunning migrations
    # per row. Single-URL callers leave it False so the first CLI run
    # on a fresh install still bootstraps the schema.
    if not skip_init:
        await init_database(db_path)
    tier = classify_url(url)

    if tier == Tier.UNKNOWN:
        return IngestResult(status="rejected", reason="classifier_unknown_tier")
    if tier in (Tier.X, Tier.BLOG):
        return IngestResult(status="rejected", reason="tier_not_implemented")

    if tier == Tier.POKEPASTE:
        fetched = await _fetch_tier1(url)
    else:
        return IngestResult(status="rejected", reason="tier_not_implemented")

    if not fetched.success:
        # ServiceError.message is the actionable text; its dataclass repr
        # buries the message behind category/service/is_recoverable noise.
        err = fetched.error
        reason = err.message if err is not None else "unknown_error"
        # A wrapped parse exception from _fetch_tier1 must surface as
        # parse_failed, not fetch_failed — the two map to different CLI
        # exit codes (4 vs 3) and different operator retry strategies.
        if err is not None and err.category == ErrorCategory.PARSE_ERROR:
            return IngestResult(status="parse_failed", reason=reason)
        return IngestResult(status="fetch_failed", reason=reason)
    if fetched.data is None:
        return IngestResult(status="parse_failed", reason="empty_parse")

    # Load the dex now that we know the URL will actually be processed,
    # so rejected/fetch-failed URLs don't pay the round-trip cost.
    if dex_lookup is None:
        dex_lookup = await load_dex_lookup(db_path)

    draft = fetched.data
    # Flatten dex into a known-moves set so the normalizer's fuzzy-move
    # correction actually fires in production (no-op when dex is absent).
    known_moves: set[str] | None = None
    if dex_lookup is not None:
        known_moves = {m for entry in dex_lookup.values() for m in entry["moves"]}
    normalized, norm_log = normalize(draft, known_moves=known_moves)
    report = validate(normalized, dex_lookup=dex_lookup)

    if report.hard_failures:
        confidence = 0.0
    else:
        confidence = _score(normalized, len(report.soft_failures))

    status: WrittenIngestionStatus = (
        "auto" if confidence >= AUTO_WRITE_THRESHOLD else "review_pending"
    )

    team = ChampionsTeam(
        team_id=compute_team_fingerprint(normalized.pokemon),
        source_type=normalized.source_type,
        source_url=normalized.source_url,
        ingestion_status=status,
        confidence_score=confidence,
        review_reasons=list(report.hard_failures + report.soft_failures) or None,
        normalizations=norm_log or None,
        pokemon=normalized.pokemon,
    )

    try:
        async with get_connection(db_path) as db:
            row_id = await write_or_queue_team(db, team)
    except (aiosqlite.Error, OSError, RuntimeError) as exc:
        # Narrow catch — genuine DB/disk failures and write_or_queue_team's
        # RuntimeError for a missing lastrowid (a DB-layer contract
        # violation, not a programming bug) both bucket to db_error.
        # Programmer bugs (TypeError/AttributeError) still propagate so
        # they surface as real crashes instead of silently re-queuing.
        logger.exception("ingest_url: db write failed for url=%s", url)
        return IngestResult(
            status="db_error",
            confidence=confidence,
            reason=f"db_write_error: {exc}",
        )

    return IngestResult(status=status, team_row_id=row_id, confidence=confidence)
