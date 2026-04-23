"""Top-level ingestion orchestrator.

Routes a URL through the classifier to the appropriate tier handler,
then normalizes, validates, and writes (or queues) the result.

Additional tiers are added by inserting a branch in ``ingest_url``
and wiring a ``_fetch_tierN`` coroutine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
from smogon_vgc_mcp.fetcher.ingestion.validator import validate
from smogon_vgc_mcp.fetcher.pokepaste import fetch_pokepaste
from smogon_vgc_mcp.resilience import ErrorCategory, FetchResult, ServiceError

logger = logging.getLogger(__name__)

AUTO_WRITE_THRESHOLD = 0.85

IngestStatus = Literal["auto", "review_pending", "fetch_failed", "parse_failed", "rejected"]
# Subset actually persisted to ChampionsTeam.ingestion_status — terminal
# statuses (fetch_failed, parse_failed, rejected) return before any DB write.
WrittenIngestionStatus = Literal["auto", "review_pending"]


@dataclass(frozen=True)
class IngestResult:
    status: IngestStatus
    team_row_id: int | None = None
    confidence: float | None = None
    reason: str | None = None


async def _fetch_tier1(url: str) -> FetchResult[ChampionsTeamDraft]:
    fetched = await fetch_pokepaste(url)
    if not fetched.success or not fetched.data:
        if fetched.error is not None:
            return FetchResult.fail(fetched.error)
        return FetchResult.ok(None)
    try:
        draft = parse_pokepaste_to_champions_draft(fetched.data, source_url=url)
    except Exception as exc:
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
    return max(0.0, draft.tier_baseline_confidence - 0.1 * soft_count)


async def ingest_url(url: str, *, db_path: Path | None = None) -> IngestResult:
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
        return IngestResult(status="fetch_failed", reason=str(fetched.error))
    if fetched.data is None:
        return IngestResult(status="parse_failed", reason="empty_parse")

    draft = fetched.data
    normalized, norm_log = normalize(draft)
    report = validate(normalized)

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
    except Exception as exc:
        logger.exception("ingest_url: db write failed for url=%s", url)
        return IngestResult(
            status="fetch_failed",
            confidence=confidence,
            reason=f"db_write_error: {exc}",
        )

    return IngestResult(status=status, team_row_id=row_id, confidence=confidence)
