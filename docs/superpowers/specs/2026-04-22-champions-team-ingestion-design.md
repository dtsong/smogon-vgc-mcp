# Champions Team Ingestion Pipeline — Design

**Status**: Approved (2026-04-22)
**Priority**: Champions format (`champions_ma`) — the format going forward

## Goal

Ingest competitive Champions team sets from three source shapes — pokepaste links, X (Twitter) posts, and blog articles — into new Champions-specific storage tables. Pipeline is hybrid: deterministic parsers + Haiku LLM extractor, gated by confidence. High-confidence extractions land directly in `champions_teams`; low-confidence ones queue into the existing labeler for human review. A deterministic validator runs on every extraction and is re-runnable as a batch audit over stored rows.

## Non-Goals (YAGNI)

- OCR on team screenshots (Tier 4 deferred)
- Proactive scheduled crawler / watchlist walker (phase 2)
- X thread / reply aggregation — single-post scope only
- RSS following of blogs
- Reg I or other-format ingestion — same classifier, different storage (future)

## Background

- Existing `teams` / `team_pokemon` tables use Gen 9 EV/IV shape (hp_ev/atk_ev/... and IVs). Champions uses **Stat Points**: 66 SP total, ≤32 per stat, everyone at level 50. Storage shape is different enough to warrant parallel tables (same pattern used for `champions_dex_*`).
- `ArticleSource` Protocol and `AnthropicPrefiller` were added during the labeler workstation (PR #14) and are source-agnostic — they can be extended to service the new ingestion queue with minimal adaptation.
- The tournament teams Google Sheet already drives `regf` ingestion. A new tab (`gid=791705272`, assumed Champions) contains mixed URL shapes (pokepaste + X + blog) and will seed the pipeline.

## Architecture

```
  vgc-ingest <url>             sheet puller              (phase 2: X/blog watchlist)
         |                         |                              |
         +-------------------------+------------------------------+
                                   v
                       URL Shape Classifier
                                   v
     +-------------+---------------+--------------+
     v             v               v              v
  TIER 1        TIER 2          TIER 3         REJECT
 pokepaste.es  embedded        prose + LLM    (unknown)
 conf = 1.0    Showdown block  conf 0.3-0.9
               conf ~= 0.9
     |             |               |
     +-------------+---------------+
                   v
        Normalize (aliases, fuzzy move/pokemon names)
                   v
        Validate (SP rules + dex + ability + learnset)
                   v
          final_confidence >= 0.85 ?
              |              |
             YES             NO
              v              v
   champions_teams    labeler queue
   (ingestion_status  (ingestion_status
    = 'auto')          = 'review_pending')
```

## Data Model

### New Tables

```sql
CREATE TABLE champions_teams (
  id INTEGER PRIMARY KEY,
  format TEXT NOT NULL DEFAULT 'champions_ma',
  team_id TEXT NOT NULL,                -- deterministic hash of set fingerprint
  description TEXT,
  owner TEXT,
  source_type TEXT NOT NULL,            -- 'sheet' | 'pokepaste' | 'x' | 'blog'
  source_url TEXT NOT NULL,
  ingestion_status TEXT NOT NULL,       -- 'auto' | 'review_pending' | 'labeled'
                                        -- | 'fetch_failed' | 'parse_failed'
  confidence_score REAL NOT NULL,
  review_reasons TEXT,                  -- JSON array of validator reason codes
  normalizations TEXT,                  -- JSON array of auto-fixes applied
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(format, team_id)
);

CREATE TABLE champions_team_pokemon (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES champions_teams(id) ON DELETE CASCADE,
  slot INTEGER NOT NULL,
  pokemon TEXT NOT NULL,
  item TEXT,
  ability TEXT,
  nature TEXT,
  tera_type TEXT,
  level INTEGER DEFAULT 50,
  sp_hp INTEGER DEFAULT 0, sp_atk INTEGER DEFAULT 0, sp_def INTEGER DEFAULT 0,
  sp_spa INTEGER DEFAULT 0, sp_spd INTEGER DEFAULT 0, sp_spe INTEGER DEFAULT 0,
  move1 TEXT, move2 TEXT, move3 TEXT, move4 TEXT,
  UNIQUE(team_id, slot),
  CHECK(sp_hp BETWEEN 0 AND 32),
  CHECK(sp_atk BETWEEN 0 AND 32),
  CHECK(sp_def BETWEEN 0 AND 32),
  CHECK(sp_spa BETWEEN 0 AND 32),
  CHECK(sp_spd BETWEEN 0 AND 32),
  CHECK(sp_spe BETWEEN 0 AND 32),
  CHECK(sp_hp + sp_atk + sp_def + sp_spa + sp_spd + sp_spe <= 66),
  CHECK(slot BETWEEN 1 AND 6)
);

CREATE INDEX idx_champions_teams_format ON champions_teams(format);
CREATE INDEX idx_champions_teams_source ON champions_teams(source_type);
CREATE INDEX idx_champions_teams_status ON champions_teams(ingestion_status);
CREATE INDEX idx_champions_team_pokemon_pokemon ON champions_team_pokemon(pokemon);
CREATE INDEX idx_champions_team_pokemon_team_id ON champions_team_pokemon(team_id);
```

## Components

| Module | Purpose |
|---|---|
| `fetcher/ingestion/classifier.py` | URL regex + domain list → `Tier` enum (`POKEPASTE`, `X`, `BLOG`, `UNKNOWN`) |
| `fetcher/ingestion/tier1_pokepaste.py` | Reuse existing `pokepaste.py`; adapt output to SP fields |
| `fetcher/ingestion/tier2_showdown_block.py` | Python port of `parseShowdownImport` from `labeler/static/labeler.js`; detect and parse embedded Showdown blocks in free text |
| `fetcher/ingestion/tier3_llm.py` | Champions-aware Haiku system prompt (SP field names, 32/66 constraints); reuse `AnthropicPrefiller` client |
| `fetcher/ingestion/x_adapter.py` | Fetch X post text via `publish.twitter.com/oembed` (no auth, public posts only) |
| `fetcher/ingestion/blog_adapter.py` | Generic blog extraction via `trafilatura` (MIT, no Chromium dep) |
| `fetcher/ingestion/normalizer.py` | Alias tables (Pokemon, items), Levenshtein ≤2 fuzzy match for moves |
| `fetcher/ingestion/validator.py` | Pure-function `ValidationReport` generator |
| `fetcher/ingestion/audit.py` | Batch auditor over stored rows |
| `fetcher/ingestion/pipeline.py` | Top-level orchestrator: classify → fetch → extract → normalize → validate → write/queue |
| `database/champions_team_queries.py` | CRUD + write-or-queue routing |
| `fetcher/sheets.py` (extend) | Branch on URL shape when reading the Champions tab |
| `labeler/sources.py::ChampionsTeamQueueSource` | New `ArticleSource` surfacing `review_pending` rows |
| `tools/ingest_team.py` | MCP tool `ingest_team(url)` |
| `entry/ingest_cli.py` | `vgc-ingest <url>` CLI |

## Validator Specification

### `ValidationReport`

```python
@dataclass(frozen=True)
class ValidationReport:
    passed: bool                   # True iff no hard failures
    hard_failures: list[str]       # reason codes (see table below)
    soft_failures: list[str]       # reason codes
    normalizations: list[str]      # audit log of auto-fixes
```

### Check Table

| Reason code | Severity | Rule |
|---|---|---|
| `sp_over_per_stat` | hard | any `sp_X > 32` |
| `sp_over_total` | hard | `sum(sp_X) > 66` |
| `sp_negative` | hard | any `sp_X < 0` |
| `slot_count` | hard | team has 0 slots or > 6 slots |
| `duplicate_species` | hard | same base species appears twice (Species Clause) |
| `pokemon_unknown` | hard | not in `champions_dex_pokemon` after normalization |
| `ability_illegal` | soft | not in that Pokemon's legal ability set |
| `move_illegal` | soft | not in that Pokemon's learnset |
| `item_unknown` | soft | item name not in known item list |
| `nature_unknown` | soft | not one of 25 natures |
| `tera_type_unknown` | soft | not one of 18 types (nullable field) |
| `move_count` | soft | < 1 or > 4 moves per slot |
| `lossy_roundtrip` | soft | Tier 1/2 only — re-serialized Showdown text differs from source |

### Normalization Pass

Runs before checks, logs each change into `normalizations[]`:

- **Pokemon name**: "urshifu-s" → "Urshifu-Single-Strike" via alias table
- **Move name**: Levenshtein ≤ 2 against `champions_dex_moves` (e.g., "Close Combatt" → "Close Combat")
- **Item**: strip trailing " (consumed)", case-fold match against known item list
- **Nature**: title-case
- **Tera type**: title-case, nullable

### Confidence Interaction

```
final_confidence = tier_baseline
                   - 0.1 * len(soft_failures)
                   + tier_modifiers
if hard_failures:
    final_confidence = 0.0   # forces queue regardless of tier
```

## Confidence Scoring

| Tier | Baseline | Modifiers |
|------|----------|-----------|
| 1 pokepaste | 1.00 | −0.10 partial parse; −0.20 on 4xx |
| 2 embedded Showdown | 0.90 | +0.05 if all 6 slots complete; −0.20 if < 3 moves/slot avg |
| 3 LLM prose | 0.50 | +0.10 per fully-populated set; −0.30 if validator rejects |

**Auto-write threshold: `0.85`**. Below → labeler queue with `ingestion_status='review_pending'`.

## Audit Layer

`fetcher/ingestion/audit.py` re-runs the validator over stored rows. Use cases:

- Dex data update invalidates previously valid teams (ability removed, learnset change)
- Normalizer bug fix — stored `normalizations` no longer line up
- Validator rule change — new check retroactively applied

Entry points:

- **CLI `vgc-audit-teams`** — walks `champions_teams`, re-validates, emits TSV report (`team_id\tstatus\treasons`), optionally flips `ingestion_status` to `review_pending` on new failures (gated behind `--apply`)
- **MCP tool `audit_champions_team(team_id)`** — on-demand single-row check

## Data Flow

1. **Reactive**: `vgc-ingest <url>` → classifier → tier handler → normalizer → validator → `champions_teams` (auto) or labeler queue
2. **Sheet seed**: `sheets.py` reads Champions tab (`gid=791705272`), classifies each row's URL, routes through the same pipeline. Pokepaste rows typically auto-land; X/blog rows flow through Tier 2/3
3. **Proactive watchlist (phase 2)**: scheduled job walks known X handles + blog RSS — deferred

## Error Handling

- **Classifier REJECT** (URL shape unknown) → no row written; reactive CLI returns a non-zero exit with reason; sheet puller logs and moves on. No labeler queue entry.
- **Fetch failures** (4xx/5xx, timeout) → `ingestion_status='fetch_failed'`, retried on next sheet pull
- **Parse failures** (unrecognized format, malformed JSON from LLM) → `ingestion_status='parse_failed'` with human-readable reason; surfaces in labeler queue
- **LLM rate limit / 5xx** → exponential backoff with jitter; fall through to queue with reason `llm_unavailable`
- **Hard validator failures** → always queue (`review_pending`), never auto-write
- **Duplicate team_id** (same source_url + same set fingerprint hash) → skip, log at debug

## Testing

- **Unit**: per-tier fixture tests (canned pokepaste raw, canned Showdown block, canned prose article)
- **Property**: SP validator boundaries (32, 33, 66, 67, 0, −1)
- **Routing**: classifier mapping test — 10 canned URLs → expected tier
- **Integration**: sheet row → pipeline → row present in `champions_teams` with expected shape
- **Audit regression**: mutate a stored row to violate a rule, run audit, assert flagged
- **Round-trip**: Tier 1/2 golden set — parse → re-serialize → byte-compare
- **Eval loop**: Champions queue flows into the existing labeler correction-rate dashboard (no new infra needed)

## Integration with Labeler (PR #14)

Once merged, PR #14's labeler gains a new `ArticleSource`:

```python
class ChampionsTeamQueueSource:
    source_name = "champions_team_queue"
    # lists champions_teams rows WHERE ingestion_status = 'review_pending'
    # get_article() synthesizes a read-only detail view with extraction context
```

The existing prefill + correction-rate infra Just Works on this source.

## Open Questions / Assumptions to Verify

- **Sheet tab identity**: Assumed `gid=791705272` is the Champions tab. If it's actually Reg I, either (a) add a second tab for Champions, or (b) route by row `format` column if the sheet has one. Verification on first read is cheap.
- **X oEmbed sufficiency**: Public oEmbed returns tweet text + basic HTML. If posts routinely embed sets as images (screenshots), Tier 3 cannot recover them and OCR becomes necessary — reassess after first 50 X ingestions.
- **Set fingerprint hashing**: Use `sha256(sorted(tuple(pokemon_name, moves_sorted, sp_tuple) for slot in slots))` for dedup — documented in `champions_team_queries.py`.

## Delivery Phases

1. **Schema + validator + normalizer** (foundational, no external I/O)
2. **Tier 1 + sheet extension** (reuse existing pokepaste infra; ships usable ingestion for majority of sheet rows)
3. **Tier 2 (embedded Showdown)** (pure parsing, reuses normalization/validator)
4. **Tier 3 (LLM) + X adapter + blog adapter** (adds network + model cost)
5. **Audit layer + CLI + MCP tool**
6. **Labeler queue source integration**

Each phase ships independently with tests.
