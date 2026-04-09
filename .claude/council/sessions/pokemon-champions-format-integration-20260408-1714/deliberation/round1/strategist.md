## Strategist Position — Pokemon Champions Format Integration

**Core recommendation:** Ship Regulation I as a pure config addition (1 day, zero risk), then build Champions support as a phased 3-milestone effort: data pipeline first, calc second, meta tooling last. Do not attempt Champions day-1 feature parity with Gen 9.

**Key argument:**
The format system is already the right abstraction — `FormatConfig` is purely data with no logic coupling. Regulation I is a one-line registry addition, and that work should be done in hours, not days. Champions support is a different beast: it requires a new Pokedex data source, a new damage calc engine (Python-native until @smogon/calc adds Champions support), and entirely new meta stats once Smogon publishes them. The MVP for Champions is: correct damage output for Champions Pokemon + a usable Pokedex — that alone unlocks the teambuilder agents and most LLM use cases. Usage rankings and tournament teams can come when the data sources exist. Building the Python calc now is the right call because @smogon/calc's Champions support timeline is unknown; a clean Python implementation doesn't need to be perfect, it needs to be correct for the core damage formula.

**Risks if ignored:**
- Over-investing in Gen 9 Reg I maintenance delays Champions work while the game is fresh and user demand is highest — first-mover advantage for Champions tooling is real.
- Building the damage calc and Pokedex simultaneously as one giant PR creates a tangled dependency graph; if calc is blocked on data, nothing ships. Sequencing data first eliminates this risk.
- Assuming @smogon/calc Champions support will arrive "soon" and deferring the Python calc could leave the server with no damage calculation at all for Champions — the JS library's timeline is not ours to control.

**Dependencies on other agents' domains:**

- **Architect:** FormatConfig may need a `game_gen` or `dex_source` discriminator field to branch logic for Champions vs Gen 9 (different Pokedex, different calc engine, possibly different stat formula). Need to know if the current abstraction handles this cleanly or if the registry needs a protocol/interface split.
- **Advocate:** Champions has no official API and no Smogon stats at launch. Need a confirmed third-party data source for the Pokedex (species, base stats, types, moves) before any implementation work starts — this is the single biggest risk to the timeline.
- **Skeptic:** The Python damage calc is the highest-risk deliverable. Need confidence assessment on formula accuracy (Champions may have new mechanics) and a test strategy so we know when "done" actually means correct.

---

**Proposed phasing:**

| Phase | Scope | Blocking on |
|-------|-------|-------------|
| 0 — Reg I | Add `regi` to FORMATS dict, update DEFAULT_FORMAT | Nothing |
| 1 — Champions Pokedex | Data pipeline for Champions species/stats/types/moves | Confirmed data source |
| 2 — Champions Calc | Python damage calc for Champions, wired to MCP tools | Phase 1 |
| 3 — Champions Meta | Usage rankings + tournament teams once sources exist | External data availability |

**Must-have for Champions MVP (Phase 1+2):** Pokedex lookup, stat calculation, damage calculation.
**Explicitly deferred:** Usage rankings, tournament teams, EV optimizer for Champions — these depend on live data that doesn't exist at launch.
