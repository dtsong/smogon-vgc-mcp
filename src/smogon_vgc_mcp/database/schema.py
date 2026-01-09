"""SQLite database schema for Smogon VGC stats."""

import os
from pathlib import Path

import aiosqlite

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "vgc_stats.db"

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


async def init_database(db_path: Path | None = None) -> None:
    """Initialize the database with schema and run migrations."""
    if db_path is None:
        db_path = get_db_path()

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await migrate_add_format_column(db)
        await db.commit()


def get_connection(db_path: Path | None = None) -> aiosqlite.Connection:
    """Get a database connection context manager.

    Usage:
        async with get_connection() as db:
            ...
    """
    if db_path is None:
        db_path = get_db_path()

    return aiosqlite.connect(db_path)
