## Scout Position — Pokemon Champions Data Sources

**Core recommendation:** No single drop-in replacement for Smogon's chaos JSON exists yet for Champions. Plan a multi-source strategy: Pikalytics (ladder usage), Champions Lab (tournament/simulation data), and Porygon Labs (damage calc) are the emerging primary sources, but all three launched the same day as the game (April 8, 2026) and have zero historical data depth yet.

**Key argument:**
Pokemon Champions (released April 8, 2026, the same day as this deliberation) is a standalone battle-only game that replaces Scarlet/Violet as the VGC platform. The data landscape is fragmenting in a way the current codebase isn't designed for:

1. **Smogon chaos JSON** — No Champions-specific chaos JSON exists yet. Smogon's stats infrastructure is built on Showdown ladder data, and Showdown itself has not implemented Champions as a playable format (Showdown covers Gen 1–9 only; Champions is effectively a new system). No commits or PRs in the Showdown repo add Champions support as of today. The `/stats/{year}-{month}/chaos/{format}-{elo}.json` URL pattern will not work for Champions until Showdown implements it — which has no announced timeline.

2. **Showdown data files** (`play.pokemonshowdown.com/data/`) — The directory as of April 5, 2026 shows no Champions-specific files. The pokedex.json was last modified April 5, 2026 (three days before Champions launch), but no separate Champions pokedex file exists yet. Showdown Tier explicitly notes they will analyze Champions "once the metagame is implemented on Showdown" — conditional, not confirmed.

3. **Third-party tools available now:**
   - **Pikalytics** (`pikalytics.com/champions`) — Publicly committed to Champions support (usage stats, tier lists, team builder, Mega Evolution tracking). As of today they list "preparing to support" language, meaning data will flow once ladder volume accumulates.
   - **Champions Lab** (`championslab.xyz`) — Available now, uses 2,000,000 simulated battles + 250 tournament teams as a data foundation. No public API. Sources: proprietary simulation + tournament scraping.
   - **Porygon Labs** (`porygonlabs.com`) — Champions-native damage calculator supporting Regulation M-A, Stat Points (Champions' EV/IV replacement), and Mega Evolutions. Has internal API endpoints (rate-limited) but no public API documented. Pokepaste integration exists.
   - **Pokemon-Zone** (`pokemon-zone.com/champions`) — Tournament-sourced usage data, switching from Reg F2 to Reg M-A on April 8. Data source is real tournament results, not ladder.

4. **@smogon/calc** — Latest version 0.11.0 (published ~April 2026), no Champions support mentioned in TASKS.md or README. The calc library is strictly Gen 1–9. Champions has a fundamentally different stat system (Stat Points replace EVs/IVs, 66 SP total, 32 max per stat), meaning a direct port is non-trivial. Porygon Labs appears to be the first damage calc with native Champions support.

5. **No official TPC API** — The Pokemon Company has not released a public API for Champions ranked ladder data. In-game VP/ranking data is not externally accessible. The only ladder-adjacent data will come from third-party scraping (community replay parsing, Pikalytics' proprietary access) similar to how Showdown stats work today.

6. **169 eligible Pokemon, Regulation M-A** — Champions launches with a curated dex of 169 Pokemon, no Tera Types at launch. This is a meaningfully smaller and different pool from Reg F.

**Risks if ignored:**
- **The current `/stats/{month}/chaos/{format}-{elo}.json` fetch code will return 404s for any Champions format string.** Callers that don't handle this gracefully will silently fail or error on Champions format queries.
- **Stat Points are not EVs.** Any damage calculation logic that feeds IVs/EVs directly into the `@smogon/calc` library will produce wrong results for Champions Pokemon. The stat system is a breaking mechanical difference, not just new Pokemon names.
- **Data lag is real.** The first month of Champions ranked data won't exist until late April/early May 2026. Tournament data (Indianapolis Regionals: May 29–31, 2026) won't be available until June. Planning to show Champions stats before that window requires simulation-based sources, not real usage data.

**Dependencies on other domains:**
- **Architect** needs to decide whether Champions is a parallel format track (like adding Reg G alongside Reg F) or a new "generation" requiring a separate code path. The stat system difference (Stat Points) pushes toward a separate code path.
- **Calculator agent** is most directly impacted: the damage calculator subprocess uses `@smogon/calc`, which has no Champions support. Either a new Champions-native calc (e.g., Porygon Labs' engine) must be integrated, or a Champions-specific stat conversion layer must be built.
- **Advocate** should weigh whether to wait for Pikalytics/Smogon to stabilize (lower implementation risk) vs. building scraper integrations now (earlier Champions support but fragile data sources).
