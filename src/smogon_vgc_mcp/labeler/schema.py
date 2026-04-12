"""Labeler state schema — additive migration.

The ``label_state`` table tracks which articles have been labeled, which
were pre-filled by the extractor, and where the resulting golden JSON
lives on disk. The JSON files themselves are the source of truth for
F1 evaluation; this table is the index.
"""

from __future__ import annotations

import aiosqlite

LABELER_SCHEMA = """
CREATE TABLE IF NOT EXISTS label_state (
    article_id TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unlabeled',
    labeled_at TIMESTAMP,
    prefill_used INTEGER NOT NULL DEFAULT 0,
    fields_corrected_count INTEGER NOT NULL DEFAULT 0,
    fields_corrected_json TEXT,
    output_path TEXT,
    PRIMARY KEY (source, article_id)
);

CREATE INDEX IF NOT EXISTS idx_label_state_status ON label_state(status);
CREATE INDEX IF NOT EXISTS idx_label_state_source_status
    ON label_state(source, status);
"""


async def migrate_add_labeler_tables(db: aiosqlite.Connection) -> None:
    """Create the ``label_state`` table. Safe to run on every startup."""
    await db.executescript(LABELER_SCHEMA)
    await db.commit()
