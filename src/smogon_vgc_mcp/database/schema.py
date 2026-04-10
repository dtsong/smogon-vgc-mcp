"""SQLite database schema for Smogon VGC stats."""

import os
from pathlib import Path

import aiosqlite

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "vgc_stats.db"

# Database connection timeout in seconds
DB_TIMEOUT = 30.0

SCHEMA = """
-- Metadata about each data snapshot
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    format TEXT NOT NULL DEFAULT 'regf',
    month TEXT NOT NULL,
    elo_bracket INTEGER NOT NULL,
    num_battles INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(format, month, elo_bracket)
);

-- Pokemon usage data
CREATE TABLE IF NOT EXISTS pokemon_usage (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    pokemon TEXT NOT NULL,
    raw_count INTEGER,
    usage_percent REAL,
    viability_ceiling TEXT,
    UNIQUE(snapshot_id, pokemon)
);

-- Abilities distribution
CREATE TABLE IF NOT EXISTS abilities (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES pokemon_usage(id) ON DELETE CASCADE,
    ability TEXT NOT NULL,
    count REAL,
    percent REAL
);

-- Items distribution
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES pokemon_usage(id) ON DELETE CASCADE,
    item TEXT NOT NULL,
    count REAL,
    percent REAL
);

-- Moves distribution
CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES pokemon_usage(id) ON DELETE CASCADE,
    move TEXT NOT NULL,
    count REAL,
    percent REAL
);

-- Teammates distribution
CREATE TABLE IF NOT EXISTS teammates (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES pokemon_usage(id) ON DELETE CASCADE,
    teammate TEXT NOT NULL,
    count REAL,
    percent REAL
);

-- EV Spreads
CREATE TABLE IF NOT EXISTS spreads (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES pokemon_usage(id) ON DELETE CASCADE,
    nature TEXT,
    hp INTEGER,
    atk INTEGER,
    def INTEGER,
    spa INTEGER,
    spd INTEGER,
    spe INTEGER,
    count REAL,
    percent REAL
);

-- Tera Type distribution (from moveset txt files)
CREATE TABLE IF NOT EXISTS tera_types (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES pokemon_usage(id) ON DELETE CASCADE,
    tera_type TEXT NOT NULL,
    percent REAL
);

-- Checks and Counters (from moveset txt files)
CREATE TABLE IF NOT EXISTS checks_counters (
    id INTEGER PRIMARY KEY,
    pokemon_usage_id INTEGER REFERENCES pokemon_usage(id) ON DELETE CASCADE,
    counter TEXT NOT NULL,
    score REAL,
    win_percent REAL,
    ko_percent REAL,
    switch_percent REAL
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_snapshots_format ON snapshots(format);
CREATE INDEX IF NOT EXISTS idx_pokemon_usage_pokemon ON pokemon_usage(pokemon);
CREATE INDEX IF NOT EXISTS idx_pokemon_usage_snapshot ON pokemon_usage(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_items_item ON items(item);
CREATE INDEX IF NOT EXISTS idx_moves_move ON moves(move);
CREATE INDEX IF NOT EXISTS idx_teammates_teammate ON teammates(teammate);
CREATE INDEX IF NOT EXISTS idx_abilities_ability ON abilities(ability);
CREATE INDEX IF NOT EXISTS idx_tera_types_tera ON tera_types(tera_type);
CREATE INDEX IF NOT EXISTS idx_checks_counters_counter ON checks_counters(counter);

-- Tournament teams from Google Sheet pokepaste repository
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    format TEXT NOT NULL DEFAULT 'regf',
    team_id TEXT NOT NULL,
    description TEXT,
    owner TEXT,
    tournament TEXT,
    rank TEXT,
    rental_code TEXT,
    pokepaste_url TEXT,
    source_url TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(format, team_id)
);

-- Individual Pokemon on teams (parsed from pokepaste)
CREATE TABLE IF NOT EXISTS team_pokemon (
    id INTEGER PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    slot INTEGER NOT NULL,
    pokemon TEXT NOT NULL,
    item TEXT,
    ability TEXT,
    tera_type TEXT,
    nature TEXT,
    hp_ev INTEGER DEFAULT 0,
    atk_ev INTEGER DEFAULT 0,
    def_ev INTEGER DEFAULT 0,
    spa_ev INTEGER DEFAULT 0,
    spd_ev INTEGER DEFAULT 0,
    spe_ev INTEGER DEFAULT 0,
    hp_iv INTEGER DEFAULT 31,
    atk_iv INTEGER DEFAULT 31,
    def_iv INTEGER DEFAULT 31,
    spa_iv INTEGER DEFAULT 31,
    spd_iv INTEGER DEFAULT 31,
    spe_iv INTEGER DEFAULT 31,
    move1 TEXT,
    move2 TEXT,
    move3 TEXT,
    move4 TEXT,
    UNIQUE(team_id, slot)
);

-- Indexes for team queries
CREATE INDEX IF NOT EXISTS idx_teams_format ON teams(format);
CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id);
CREATE INDEX IF NOT EXISTS idx_teams_tournament ON teams(tournament);
CREATE INDEX IF NOT EXISTS idx_teams_owner ON teams(owner);
CREATE INDEX IF NOT EXISTS idx_team_pokemon_pokemon ON team_pokemon(pokemon);
CREATE INDEX IF NOT EXISTS idx_team_pokemon_team_id ON team_pokemon(team_id);

-- =============================================================================
-- Pokedex data (from Pokemon Showdown)
-- =============================================================================

-- Pokemon species data
CREATE TABLE IF NOT EXISTS dex_pokemon (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    type1 TEXT NOT NULL,
    type2 TEXT,
    hp INTEGER,
    atk INTEGER,
    def INTEGER,
    spa INTEGER,
    spd INTEGER,
    spe INTEGER,
    ability1 TEXT,
    ability2 TEXT,
    ability_hidden TEXT,
    height_m REAL,
    weight_kg REAL,
    color TEXT,
    tier TEXT,
    prevo TEXT,
    evo_level INTEGER,
    base_species TEXT,
    forme TEXT,
    is_nonstandard TEXT
);

-- Move data
CREATE TABLE IF NOT EXISTS dex_moves (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    category TEXT NOT NULL,
    base_power INTEGER,
    accuracy INTEGER,
    pp INTEGER,
    priority INTEGER DEFAULT 0,
    target TEXT,
    description TEXT,
    short_desc TEXT,
    is_nonstandard TEXT
);

-- Ability data
CREATE TABLE IF NOT EXISTS dex_abilities (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    short_desc TEXT,
    rating REAL,
    is_nonstandard TEXT
);

-- Item data
CREATE TABLE IF NOT EXISTS dex_items (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    short_desc TEXT,
    fling_power INTEGER,
    gen INTEGER,
    is_nonstandard TEXT
);

-- Learnsets (Pokemon -> Move mapping)
CREATE TABLE IF NOT EXISTS dex_learnsets (
    pokemon_id TEXT,
    move_id TEXT,
    methods TEXT,
    PRIMARY KEY (pokemon_id, move_id)
);

-- Type chart (attacking_type vs defending_type effectiveness)
CREATE TABLE IF NOT EXISTS dex_type_chart (
    attacking_type TEXT,
    defending_type TEXT,
    multiplier REAL,
    PRIMARY KEY (attacking_type, defending_type)
);

-- Indexes for Pokedex queries
CREATE INDEX IF NOT EXISTS idx_dex_pokemon_name ON dex_pokemon(name);
CREATE INDEX IF NOT EXISTS idx_dex_pokemon_type1 ON dex_pokemon(type1);
CREATE INDEX IF NOT EXISTS idx_dex_pokemon_type2 ON dex_pokemon(type2);
CREATE INDEX IF NOT EXISTS idx_dex_pokemon_tier ON dex_pokemon(tier);
CREATE INDEX IF NOT EXISTS idx_dex_moves_type ON dex_moves(type);
CREATE INDEX IF NOT EXISTS idx_dex_moves_category ON dex_moves(category);
CREATE INDEX IF NOT EXISTS idx_dex_abilities_name ON dex_abilities(name);
CREATE INDEX IF NOT EXISTS idx_dex_items_name ON dex_items(name);

-- =============================================================================
-- Champions Pokedex data (from Serebii)
-- =============================================================================

-- Champions Pokemon species data (rebalanced stats, Mega forms)
CREATE TABLE IF NOT EXISTS champions_dex_pokemon (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    type1 TEXT NOT NULL,
    type2 TEXT,
    hp INTEGER NOT NULL,
    atk INTEGER NOT NULL,
    def INTEGER NOT NULL,
    spa INTEGER NOT NULL,
    spd INTEGER NOT NULL,
    spe INTEGER NOT NULL,
    ability1 TEXT,
    ability2 TEXT,
    ability_hidden TEXT,
    base_form_id TEXT,
    is_mega INTEGER NOT NULL DEFAULT 0,
    mega_stone TEXT,
    height_m REAL,
    weight_kg REAL
);

-- Champions move data (includes rebalanced moves)
CREATE TABLE IF NOT EXISTS champions_dex_moves (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    category TEXT NOT NULL,
    base_power INTEGER,
    accuracy INTEGER,
    pp INTEGER,
    priority INTEGER DEFAULT 0,
    target TEXT,
    description TEXT,
    short_desc TEXT
);

-- Champions ability data
CREATE TABLE IF NOT EXISTS champions_dex_abilities (
    id TEXT PRIMARY KEY,
    num INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    short_desc TEXT
);

-- Champions learnsets (Pokemon -> Move mapping)
CREATE TABLE IF NOT EXISTS champions_dex_learnsets (
    pokemon_id TEXT,
    move_id TEXT,
    method TEXT,
    PRIMARY KEY (pokemon_id, move_id)
);

-- Indexes for Champions Pokedex queries
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_name ON champions_dex_pokemon(name);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_type1 ON champions_dex_pokemon(type1);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_type2 ON champions_dex_pokemon(type2);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_base_form ON champions_dex_pokemon(base_form_id);
CREATE INDEX IF NOT EXISTS idx_champ_pokemon_is_mega ON champions_dex_pokemon(is_mega);
CREATE INDEX IF NOT EXISTS idx_champ_moves_type ON champions_dex_moves(type);
CREATE INDEX IF NOT EXISTS idx_champ_moves_category ON champions_dex_moves(category);
CREATE INDEX IF NOT EXISTS idx_champ_abilities_name ON champions_dex_abilities(name);
"""

# =============================================================================
# Nugget Bridge historical indexing (VGC12-VGC17 archive)
# =============================================================================
# Four additive tables. All rows are per-WordPress-post, per-stage state is
# tracked via *_status columns so the ingest pipeline is idempotent and
# resumable. See docs/nugget-bridge.md (PR3) for the pipeline diagram.

NUGGET_BRIDGE_SCHEMA = """
-- Raw WordPress post payload + per-stage pipeline state
CREATE TABLE IF NOT EXISTS nb_posts (
    id INTEGER PRIMARY KEY,                   -- WP post id
    slug TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMP,
    modified_at TIMESTAMP,
    author TEXT,
    categories_json TEXT,                     -- JSON array of category names
    tags_json TEXT,                           -- JSON array of tag names
    category TEXT,                            -- primary category (e.g. "Reports")
    content_html TEXT NOT NULL,
    content_text TEXT,                        -- BS4-stripped plaintext
    format TEXT,                              -- resolved via get_format_for_date
    format_confidence TEXT,                   -- "declared" | "inferred" | "unknown"
    fetch_status TEXT DEFAULT 'pending',      -- pending|ok|failed
    extract_status TEXT DEFAULT 'pending',
    chunk_status TEXT DEFAULT 'pending',
    embed_status TEXT DEFAULT 'pending',
    extract_error TEXT,
    embed_error TEXT,
    extract_model TEXT,
    extract_cost_usd REAL DEFAULT 0,
    embed_cost_usd REAL DEFAULT 0,
    content_hash TEXT,
    fetched_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nb_posts_format ON nb_posts(format);
CREATE INDEX IF NOT EXISTS idx_nb_posts_published ON nb_posts(published_at);
CREATE INDEX IF NOT EXISTS idx_nb_posts_category ON nb_posts(category);
CREATE INDEX IF NOT EXISTS idx_nb_posts_fetch_status ON nb_posts(fetch_status);
CREATE INDEX IF NOT EXISTS idx_nb_posts_extract_status ON nb_posts(extract_status);

-- LLM-extracted Pokemon sets
CREATE TABLE IF NOT EXISTS nb_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES nb_posts(id) ON DELETE CASCADE,
    format TEXT,                              -- denormalized from nb_posts.format
    pokemon TEXT NOT NULL,                    -- as-written
    pokemon_normalized TEXT NOT NULL,         -- canonical form for lookup
    ability TEXT,
    item TEXT,
    nature TEXT,
    tera_type TEXT,                           -- always NULL pre-SwSh eras
    ev_hp INTEGER,
    ev_atk INTEGER,
    ev_def INTEGER,
    ev_spa INTEGER,
    ev_spd INTEGER,
    ev_spe INTEGER,
    iv_hp INTEGER DEFAULT 31,
    iv_atk INTEGER DEFAULT 31,
    iv_def INTEGER DEFAULT 31,
    iv_spa INTEGER DEFAULT 31,
    iv_spd INTEGER DEFAULT 31,
    iv_spe INTEGER DEFAULT 31,
    move1 TEXT,
    move2 TEXT,
    move3 TEXT,
    move4 TEXT,
    level INTEGER DEFAULT 50,
    confidence REAL,
    raw_snippet TEXT,                         -- verbatim source region, ≤300 chars
    extractor_version TEXT,
    validated INTEGER DEFAULT 0,              -- 1 if dex cross-check passed
    source_position INTEGER                   -- ordinal within post
);

CREATE INDEX IF NOT EXISTS idx_nb_sets_pokemon_format
    ON nb_sets(pokemon_normalized, format);
CREATE INDEX IF NOT EXISTS idx_nb_sets_post ON nb_sets(post_id);
CREATE INDEX IF NOT EXISTS idx_nb_sets_pokemon ON nb_sets(pokemon_normalized);

-- Semantic chunks (heading-aware, tiktoken ~500 tokens)
CREATE TABLE IF NOT EXISTS nb_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES nb_posts(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER,
    section_heading TEXT,
    -- Denormalized for filter-then-rank semantic queries
    format TEXT,
    published_at TIMESTAMP,
    title TEXT,
    url TEXT,
    category TEXT,
    pokemon_mentions_json TEXT,               -- JSON array of normalized names
    UNIQUE(post_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_nb_chunks_format ON nb_chunks(format);
CREATE INDEX IF NOT EXISTS idx_nb_chunks_post ON nb_chunks(post_id);

-- Float32 embeddings (numpy tobytes, little-endian). Loaded in-memory at
-- query time; BLOB keeps the deployment footprint to one SQLite file.
CREATE TABLE IF NOT EXISTS nb_chunk_embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES nb_chunks(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_path() -> Path:
    """Get the database path, respecting environment variable override."""
    env_path = os.environ.get("SMOGON_VGC_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


async def migrate_add_format_column(db: aiosqlite.Connection) -> None:
    """Add format column to snapshots and teams tables if not present.

    This migration handles existing databases that don't have the format column.
    Existing data will get 'regf' as the default value.
    """
    # Check if column exists in snapshots
    async with db.execute("PRAGMA table_info(snapshots)") as cursor:
        columns = [row[1] async for row in cursor]

    if "format" not in columns:
        await db.execute("ALTER TABLE snapshots ADD COLUMN format TEXT DEFAULT 'regf'")

    # Check if column exists in teams
    async with db.execute("PRAGMA table_info(teams)") as cursor:
        columns = [row[1] async for row in cursor]

    if "format" not in columns:
        await db.execute("ALTER TABLE teams ADD COLUMN format TEXT DEFAULT 'regf'")

    await db.commit()


async def migrate_add_nugget_bridge_tables(db: aiosqlite.Connection) -> None:
    """Create Nugget Bridge archive tables (nb_posts, nb_sets, nb_chunks,
    nb_chunk_embeddings). All statements use ``CREATE TABLE IF NOT EXISTS``
    so this is safe to run on every startup."""
    await db.executescript(NUGGET_BRIDGE_SCHEMA)
    await db.commit()


async def init_database(db_path: Path | None = None) -> None:
    """Initialize the database with schema and run migrations."""
    if db_path is None:
        db_path = get_db_path()

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path, timeout=DB_TIMEOUT) as db:
        await db.executescript(SCHEMA)
        await migrate_add_format_column(db)
        await migrate_add_nugget_bridge_tables(db)
        await db.commit()


def get_connection(db_path: Path | None = None) -> aiosqlite.Connection:
    """Get a database connection context manager.

    Usage:
        async with get_connection() as db:
            ...
    """
    if db_path is None:
        db_path = get_db_path()

    return aiosqlite.connect(db_path, timeout=DB_TIMEOUT)
