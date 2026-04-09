---
agent: skeptic
round: 3
session: pokemon-champions-format-integration-20260408-1714
---

## Skeptic Final Position — Pokemon Champions Format Integration

**Revised recommendation:** The convergence is sound — separate Champions tables, separate tool modules,
and a Python-native calc are all the right calls. Ship this only after the three structural safety
requirements (transactional pokedex refresh, `min_battles` gate, and a calc test suite with hardcoded
expected values) are implemented as prerequisites, not follow-up work. The phased rollout Strategist
proposed is the correct risk sequencer.

**Concessions made:**

- **Accepted: Python calc without @smogon/calc verification.** Scout's confirmation of the Champions
  formula (`floor((2*Base) * Level/100) + Level + 10 + SP`) is simpler than Gen 9, not more complex.
  A verified formula with hardcoded expected outputs from official sources is sufficient as a test
  oracle — we don't need a parallel implementation to diff against. I raised this risk because I
  assumed the formula would be as opaque as Gen 9 Tera mechanics. It isn't. I accept the calc can
  ship with a formula-based test suite rather than a reference implementation.

- **Accepted: Separate Champions tables rather than `game` column.** This is strictly safer than my
  original concern allowed for. Separate table sets (`champions_dex_pokemon` etc.) mean no shared-
  table migration risk, no accidental cross-game query contamination, and a clean DELETE scope per
  game on pokedex refresh. This closes my data collision concern more fully than the `game` column
  approach would have.

- **Accepted: Oracle's separate tool modules.** `calculate_champions_damage` and
  `calculate_champions_stats` as distinct MCP tools — not a `game` parameter on existing tools —
  is correct. The input schemas are structurally incompatible (SP integers vs EV strings, no Tera
  parameter, no nature in the same form). Sharing a tool surface would require either nullable fields
  that produce silent wrong results when callers pass the wrong game's parameters, or runtime
  validation that replicates the schema split anyway.

**Non-negotiables — required before any Champions code ships:**

1. **Transactional pokedex refresh.** The multi-table DELETE+reinsert in `fetch_and_store_pokedex_all`
   (`src/smogon_vgc_mcp/fetcher/pokedex.py:557-654`) must be wrapped in a single transaction: either
   all game-scoped tables update atomically or none do. This applies to both Gen 9 and Champions
   refresh paths. A mid-run failure currently leaves the DB in an unknown partial state. Fix this
   before Champions tables are introduced — adding more tables to an unsafe pipeline multiplies the
   blast radius.

2. **`min_battles` threshold in `store_snapshot_data`.** Add a configurable `min_battles: int` field
   to `FormatConfig` (default 0 for backwards compat, meaningful value for Champions at launch). In
   `store_snapshot_data` (`smogon.py:55-193`), if `num_battles < fmt.min_battles`, skip storage and
   return a structured warning rather than committing noise. This is a one-line guard with a config
   knob — there is no acceptable reason to defer it.

3. **Champions calc test suite with hardcoded expected outputs before ship.** The test file must
   include at minimum: (a) stat calculations for 3-5 Champions Pokemon at boundary SP values (0 SP,
   32 SP, 66 SP distributed), (b) damage outputs for representative move matchups cross-checked
   against official game screenshots or community-verified results, (c) a regression marker so any
   formula change that alters expected outputs fails CI explicitly. The suite is the verification
   oracle. It must exist before the `calculate_champions_damage` tool is registered in the MCP server.

**Implementation notes:**

- **Phase ordering is a hard constraint, not a suggestion.** Transaction safety and `min_battles` gate
  belong in Phase 0 alongside Reg I config — they are retrofits to existing code, not Champions-
  specific features. If they slip to Phase 1 or Phase 2, they will never be prioritized correctly.

- **The `stat_system` field on `FormatConfig` should be an enum, not a string literal.** Routing logic
  that branches on `stat_system` must be exhaustive — any new stat system added in the future should
  cause a type error at the branch site, not a silent fallthrough to Gen 9 defaults.

- **Silent failures in `sheets.py` remain unresolved.** The `FetchResult.ok([])` return when no
  `sheet_gid` is configured is still indistinguishable from a legitimately empty sheet. For Champions,
  where tournament data will be absent at launch, callers have no way to know whether "no teams found"
  means the format has no configured sheet or genuinely zero teams. This should return a typed
  `DataUnavailable` sentinel rather than an empty success, but I accept this can be Phase 1 work since
  it doesn't affect data integrity.

- **Do not remove `@smogon/calc` until Champions calc test suite passes CI.** The Node dependency is
  a maintenance burden, but it is currently the only verified damage calculation path. Remove it in
  the same PR that adds the Champions calc suite — not before.
