## Strategist Final Position — Pokemon Champions Format Integration

**Revised recommendation:** Ship Phase 0 (Reg I + game scoping + prompt guardrails) immediately as a single PR with no external dependencies. Hold all Champions implementation work until one viable Pokedex data source is confirmed — that decision gates Phases 1-3 entirely. Separate Champions tool modules (Oracle's position) and FormatConfig-driven routing (Architect's position) are compatible and together constitute the right architecture for Phase 1+.

**Concessions made:**

- **Game scoping in Phase 0** (from Oracle via Round 2): Accepted. `game` parameter on relevant tools plus prompt guardrails returning explicit "no Champions data" errors belong in Phase 0 alongside Reg I. Cost is ~1-2 days with zero data dependency.
- **Separate Champions tool modules** (from Oracle): Accepted. `calculate_champions_damage` and `calculate_champions_stats` as distinct modules is the right call — the input schemas are structurally incompatible (SP vs EVs, no Tera). A `game` parameter that silently changes the parameter semantics is a footgun. Separate tools make the contract explicit at the API surface.
- **`stat_system` + `calc_backend` on FormatConfig** (from Architect): Accepted. These fields are config metadata, not business logic. They document which system a format uses and which backend to invoke — that belongs in FormatConfig. The separate tool modules then dispatch based on this metadata. These two positions are fully compatible.

**Non-negotiables:**

1. **No Champions implementation before data source is confirmed.** The stat formula is known (Scout confirmed it). The architecture is settled. But without a confirmed source for the 169-mon dex (base stats, types, moves), Phase 1 cannot start. Building the pipeline against an unconfirmed source risks throwing away the work entirely. This is the single hardest gate in the roadmap.

2. **Phase 0 ships as one atomic PR.** Reg I + game scoping + prompt guardrails together. Not three separate PRs, not game scoping deferred to "later." These three things are only coherent together — Reg I alone without game scoping creates the exact data bleed Oracle warned about.

3. **Champions calc ships with a test suite, not before.** Scout confirmed the formula: `floor((2*Base) * Level/100) + Level + 10 + SP`. It's simple enough to implement in a day. It's also simple enough that an off-by-one in floor/truncation semantics will silently produce wrong numbers. Skeptic's `validate_against_reference` hook is the minimum bar for shipping Phase 2.

**Implementation notes:**

Phase 0 (ship immediately, one PR):
- Add `regi` to `FORMATS` dict in `formats.py`, mark `is_current=True`, move `regf` to `is_current=False`
- Add `game: Literal["gen9", "champions"] = "gen9"` to `FormatConfig` (or equivalent discriminator)
- Update `validate_format_code` and any tool that filters by format to propagate game context
- Update agent prompts: Champions game context returns `{"error": "Champions data not yet available"}` — no Gen 9 fallback, no hallucination surface

Phase 1 (blocked on data source confirmation):
- Champions Pokedex pipeline with separate tables (`champions_dex_pokemon`, etc.)
- Transactional refresh (Skeptic's non-negotiable, Architect conceded — prerequisite before any write)

Phase 2 (blocked on Phase 1):
- `calculate_champions_stats` and `calculate_champions_damage` as separate tool modules
- Python calc implementing `floor((2*Base) * Level/100) + Level + 10 + SP`
- Reference validation hook before ship

Phase 3 (blocked on live data):
- Usage rankings, tournament teams — defer until Smogon publishes Champions stats

**GitHub issues to create:**
1. Phase 0: Add Regulation I + game scoping + prompt guardrails
2. Spike: Confirm Champions Pokedex data source (decision gate for all subsequent issues)
3. Phase 1: Champions Pokedex pipeline (separate tables, transactional refresh)
4. Phase 2: Champions stat + damage calculators (separate tool modules, test suite required)
5. Phase 3: Champions meta tools (usage rankings, tournament teams) — backlog, no timeline
