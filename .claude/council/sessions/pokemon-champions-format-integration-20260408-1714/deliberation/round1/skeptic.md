---
agent: skeptic
round: 1
session: pokemon-champions-format-integration-20260408-1714
---

## Skeptic Position — Pokemon Champions Format Integration

**Core recommendation:** The transition's three biggest risks are simultaneous: (1) Champions data will be
sparse or nonexistent at launch — Smogon stats lag live play by months, (2) building a Python damage
calculator without @smogon/calc as a verification oracle means shipping unvalidated math with no
ground truth to diff against, and (3) the Showdown pokedex pipeline will silently omit or misrepresent
Champions-specific mechanics because it was designed for Gen 9 with stable data contracts.

**Key argument:**
The architecture is built on an assumption of data stability that doesn't hold for a brand-new game.
The Smogon stats fetcher (`src/smogon_vgc_mcp/fetcher/smogon.py`) expects a well-populated
`smogon.com/stats/{month}/chaos/{format_id}-{elo}.json` endpoint. For a newly released game, that
endpoint either won't exist or will have 50-200 battles of noise — statistically meaningless, but the
system will store it as fact with no quality gate (no minimum battle count check in `store_snapshot_data`).
The pokedex pipeline (`fetcher/pokedex.py`) pulls from three separate Pokemon Showdown sources:
`pokedex.json`, `moves.json`, and TypeScript source files parsed with a bespoke regex extractor. That
regex parser (`parse_ts_object`) worked when it was written against a known TypeScript shape — it will
silently drop entries or extract corrupt data if Champions introduces new field names, new ability
mechanics encoded differently in the TS, or structural changes to the file format. The damage calculator
transition carries compounding risk: the current `calc/calc_wrapper.js` delegates to `@smogon/calc` which
has Gen 9 battle logic battle-tested by thousands of users. A replacement Python calculator will implement
the same formulas but has no diff target to validate against during Champions' early-access window, when
move interactions and ability mechanics may not yet be finalized in any authoritative source.

**Risks if ignored:**

- **Critical — Data quality contamination:** Sparse launch-window stats (sub-500 battles) stored without
  a minimum threshold will pollute usage percentages, making the MCP surface misleading recommendations
  to competitive players during the meta's most critical formation period. The `usage_percent` calculation
  in `store_snapshot_data` is `raw_count / (num_battles * 2) * 100` with no floor guard — 1 battle of
  data produces "valid" percentages.

- **High — Silent data loss from Showdown pipeline:** `fetch_and_store_pokedex_all` performs DELETE then
  re-insert for every table (`DELETE FROM dex_pokemon`, etc.) with no transaction wrapping the full
  multi-source operation. If the abilities or items fetch fails mid-run, the DB is left in a partially
  wiped state with no rollback to the previous good state. For Champions, where Showdown support may lag
  behind game release, this creates a window of degraded or empty dex data.

- **High — Unverifiable damage calculator accuracy:** The Python damage calc replacement will process
  Champions mechanics with no reference implementation to diff against. Gen 9 mechanics (Tera, Ruin
  abilities, Protosynthesis, Quark Drive) are already complex; Champions will introduce new mechanics.
  Shipping a calculator that appears to work but produces subtly wrong results (off-by-one on spread
  move halving, incorrect Tera STAB stacking) will corrupt every teambuilding recommendation that
  depends on damage thresholds.

- **Medium — Tournament team pipeline breaks on unknown format ID:** `sheets.py` uses
  `fmt.team_id_prefix` to filter rows with a strict regex `^{prefix}\d+$`. Until Champions gets a
  `sheet_gid` assigned in `formats.py`, the fetcher returns an empty result silently (FetchResult.ok([]))
  with no indication to the caller that team data is unavailable vs. the sheet simply being empty.

**Dependencies on other agents' domains:**

- **Architect:** Needs to define a phased data availability strategy — what does the system return when
  Champions stats don't exist yet? Graceful degradation vs. hard error vs. "data not yet available"
  metadata in the response. The current `failed` list in `fetch_and_store_all` discards this signal.

- **Craftsman:** The Python damage calculator needs a validation harness from day one — not post-hoc.
  Before shipping, there must be a test suite that runs the same calculations through both @smogon/calc
  (Gen 9 as proxy) and the Python implementation, with a tolerance threshold, so divergence is caught
  before it reaches production.

- **Architect/Craftsman:** The Showdown pipeline's multi-table wipe-and-reload needs a transactional
  safety wrapper. Either all tables update atomically or none do. This is a pre-existing risk that becomes
  critical when Champions data is incomplete and a partial wipe leaves the DB in an unknown state.
