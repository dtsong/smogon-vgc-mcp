## Scout Final Position — Pokemon Champions Format Integration

**Revised recommendation:** Build Champions as a parallel, isolated track — separate tables, separate tool modules, and a thin Python stat calc — using Pikalytics as the primary live data source once ladder volume accumulates (late April/early May 2026), with Champions Lab and Pokemon-Zone as tournament-sourced fallbacks. Do not wait for Smogon chaos JSON or @smogon/calc support; neither has a roadmap for Champions.

**Concessions made:**
- Conceded to Strategist's phasing: I initially flagged data sources as day-zero unstable without recommending a hold. Strategist is right that Phase 1 (pokedex pipeline) and Phase 2 (calc) should not begin until a stable data source is confirmed. The correct Phase 0 scope is Reg I, game scoping in FormatConfig, and prompt guardrails — not Champions data pipelines.
- Conceded on Oracle's separate tool modules: I flagged the input schema incompatibility (SP vs EVs, no Tera) as a storage problem, but Oracle correctly identified it also surfaces as a tool API problem. Separate tool modules (`calculate_champions_damage`, `calculate_champions_stats`) are the right call because the MCP tool input schemas are structurally incompatible — you cannot unify them under a `game` parameter without either polluting the Gen 9 schema with optional SP fields or polluting Champions tools with unused EV/IV fields.

**Non-negotiables:**
1. **No Smogon chaos JSON for Champions until Showdown implements it.** There is no Champions format on Showdown as of April 8, 2026. Any fetcher code that assumes the existing URL pattern works for a Champions format string will silently 404. The fetcher must gate on `format.game` before attempting a chaos JSON fetch.
2. **Porygon Labs and Champions Lab are reference-only.** Neither has a public API. Do not take a runtime dependency on either. Validate our Python calc output against Porygon Labs' web UI spot-checks, then ship our own implementation.
3. **The Champions stat formula has no IVs.** The formula is `floor((2*Base) * Level/100) + Level + 10 + SP`. There is no IV term. Any code path that injects a hardcoded 31 IV into the Champions calc is wrong. This must be enforced at the calc layer, not left to callers.

**Implementation notes:**
- **Data source priority order for Champions meta stats:**
  1. Pikalytics (`pikalytics.com/champions`) — committed to usage stats; first ladder data expected late April/early May 2026. Monitor for a stable URL pattern (likely similar to their existing Reg F endpoints).
  2. Pokemon-Zone (`pokemon-zone.com/champions`) — tournament-sourced usage, available now for Reg M-A. No API documented; HTML scraping or manual import.
  3. Champions Lab (`championslab.xyz`) — simulation-based (2M battles + 250 tournament teams). No API. Use for pre-ladder-data bootstrapping if needed.
- **Champions Python stat calc:** The formula is simpler than Gen 9. Implementation is `floor((2 * base) * 0.5) + 30 + sp` for a Lv50 non-HP stat (standard simplification). HP uses the same base formula plus the +60 offset. No nature multipliers confirmed yet — verify against Porygon Labs before shipping.
- **FormatConfig additions needed (confirms Architect's direction):**
  - `stat_system: Literal["gen9_ev_iv", "champions_sp"]`
  - `calc_backend: Literal["smogon_js", "champions_py"]`
  - `smogon_stats_url: str | None` — `None` for Champions until Showdown support lands
- **Separate Champions tables** (`champions_dex_pokemon`, `champions_spreads`, etc.) — not a `game` column on shared tables. SP values (0–32 per stat, 66 total) cannot be stored in EV columns (0–252, multiples of 4 semantics) without misleading any code that reads those columns.
- **Phase 0 deliverable from Scout's domain:** Document the Pikalytics Champions URL pattern once it goes live (target: late April). Until then, no Champions data fetcher should be built — the source doesn't exist yet.
