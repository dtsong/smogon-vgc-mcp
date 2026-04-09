---
agent: skeptic
round: 2
session: pokemon-champions-format-integration-20260408-1714
---

## Skeptic Response to Architect

**Their position:** Add a `generation` field and `calc_backend` discriminator to `FormatConfig`, a `game`
column to all `dex_*` tables via migration, and a backend protocol that routes Champions calcs to a
Python-native implementation — solving data collision, calc fragility, and format sprawl in one
structural move.

**My response:** Modify

**Reasoning:** Architect's `game` column migration genuinely closes the data collision risk I raised — Gen
9 and Champions pokedex records no longer stomp each other, which is the right fix. The calc backend
protocol is the correct *shape* of solution for routing Champions away from @smogon/calc. However, these
architectural improvements do not address three of my four original risks, and the new Stat Points
revelation actually sharpens them. The `game` column migration says nothing about *when* the migration
runs relative to live data: if `init_database` applies the new schema while a pokedex refresh is
in-flight, the DELETE+reinsert pipeline (`fetch_and_store_pokedex_all`) can still leave the DB in a
partially-wiped state — adding a column doesn't add a transaction boundary. The `calc_backend` protocol
correctly isolates the Python calculator, but isolation without validation is still unverifiable math; the
Stat Points system (66 SP total, 32 max per stat, no IVs, no Tera) is fundamentally different enough
from Gen 9 formulas that there is no safe cross-validation proxy — Gen 9 can no longer serve as a
diff target at all. This actually upgrades my calc risk from High to Critical: we are building novel
formula logic for a new stat system with zero reference implementation and no way to spot-check outputs
against known-good results until real Champion players start reporting wrong damage numbers. The
minimum battle count gate (my Critical risk) remains completely unaddressed by this proposal — the
`game` column doesn't prevent sparse launch stats from being stored and served as meaningful data.
I accept Architect's data isolation approach and backend protocol shape; I need Craftsman to commit to
(a) a transactional wrapper around the full multi-table pokedex refresh, (b) a Champions-specific test
suite with hardcoded expected calc outputs derived from official game sources before the Python calc
ships, and (c) a `min_battles` threshold check in `store_snapshot_data` before I can accept this plan
as safe to implement.
