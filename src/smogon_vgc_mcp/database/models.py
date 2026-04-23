"""Data models for Smogon VGC stats."""

from dataclasses import dataclass, field
from typing import Literal

ChampionsSourceType = Literal["sheet", "pokepaste", "x", "blog"]
# Only statuses actually persisted to champions_teams.ingestion_status.
# Transient pipeline outcomes (fetch_failed / parse_failed / db_error /
# rejected) are represented on IngestResult, not on ChampionsTeam.
ChampionsIngestionStatus = Literal["auto", "review_pending", "labeled"]


@dataclass
class Snapshot:
    """Metadata about a stats snapshot."""

    id: int
    format: str
    month: str
    elo_bracket: int
    num_battles: int
    fetched_at: str


@dataclass
class AbilityUsage:
    """Ability usage data."""

    ability: str
    count: float
    percent: float


@dataclass
class ItemUsage:
    """Item usage data."""

    item: str
    count: float
    percent: float


@dataclass
class MoveUsage:
    """Move usage data."""

    move: str
    count: float
    percent: float


@dataclass
class TeammateUsage:
    """Teammate usage data."""

    teammate: str
    count: float
    percent: float


@dataclass
class EVSpread:
    """EV spread data."""

    nature: str
    hp: int
    atk: int
    def_: int  # 'def' is reserved
    spa: int
    spd: int
    spe: int
    count: float
    percent: float


@dataclass
class TeraTypeUsage:
    """Tera Type usage data (from moveset txt files)."""

    tera_type: str
    percent: float


@dataclass
class CheckCounter:
    """Check/Counter data (from moveset txt files)."""

    counter: str
    score: float
    win_percent: float
    ko_percent: float
    switch_percent: float


@dataclass
class PokemonStats:
    """Complete stats for a Pokemon."""

    pokemon: str
    raw_count: int
    usage_percent: float
    viability_ceiling: list[int]
    abilities: list[AbilityUsage] = field(default_factory=list)
    items: list[ItemUsage] = field(default_factory=list)
    moves: list[MoveUsage] = field(default_factory=list)
    teammates: list[TeammateUsage] = field(default_factory=list)
    spreads: list[EVSpread] = field(default_factory=list)
    tera_types: list[TeraTypeUsage] = field(default_factory=list)
    checks_counters: list[CheckCounter] = field(default_factory=list)


@dataclass
class UsageRanking:
    """Pokemon usage ranking entry."""

    rank: int
    pokemon: str
    usage_percent: float
    raw_count: int


@dataclass
class TeamPokemon:
    """A Pokemon on a tournament team (parsed from pokepaste)."""

    slot: int
    pokemon: str
    item: str | None = None
    ability: str | None = None
    tera_type: str | None = None
    nature: str | None = None
    hp_ev: int = 0
    atk_ev: int = 0
    def_ev: int = 0
    spa_ev: int = 0
    spd_ev: int = 0
    spe_ev: int = 0
    hp_iv: int = 31
    atk_iv: int = 31
    def_iv: int = 31
    spa_iv: int = 31
    spd_iv: int = 31
    spe_iv: int = 31
    move1: str | None = None
    move2: str | None = None
    move3: str | None = None
    move4: str | None = None


@dataclass
class Team:
    """A tournament team from the pokepaste repository."""

    id: int
    format: str
    team_id: str
    description: str | None = None
    owner: str | None = None
    tournament: str | None = None
    rank: str | None = None
    rental_code: str | None = None
    pokepaste_url: str | None = None
    source_url: str | None = None
    fetched_at: str | None = None
    pokemon: list[TeamPokemon] = field(default_factory=list)


# =============================================================================
# Pokedex data models (from Pokemon Showdown)
# =============================================================================


@dataclass
class DexPokemon:
    """Pokemon species data from the Pokedex."""

    id: str
    num: int
    name: str
    types: list[str]
    base_stats: dict[str, int]
    abilities: list[str]
    ability_hidden: str | None = None
    height_m: float = 0.0
    weight_kg: float = 0.0
    tier: str | None = None
    prevo: str | None = None
    evo_level: int | None = None
    base_species: str | None = None
    forme: str | None = None


@dataclass
class DexMove:
    """Move data from the Pokedex."""

    id: str
    num: int
    name: str
    type: str
    category: str
    base_power: int | None
    accuracy: int | None
    pp: int
    priority: int = 0
    target: str | None = None
    description: str | None = None
    short_desc: str | None = None


@dataclass
class DexAbility:
    """Ability data from the Pokedex."""

    id: str
    num: int
    name: str
    description: str | None = None
    short_desc: str | None = None
    rating: float = 0.0


@dataclass
class DexItem:
    """Item data from the Pokedex."""

    id: str
    num: int
    name: str
    description: str | None = None
    short_desc: str | None = None
    fling_power: int | None = None
    gen: int | None = None


# =============================================================================
# Champions Pokedex data models (from Serebii)
# =============================================================================


@dataclass
class ChampionsDexPokemon:
    """Champions Pokemon species data (rebalanced stats, Mega forms)."""

    id: str
    num: int
    name: str
    types: list[str]
    base_stats: dict[str, int]  # hp, atk, def, spa, spd, spe
    abilities: list[str]
    ability_hidden: str | None = None
    height_m: float = 0.0
    weight_kg: float = 0.0
    is_mega: bool = False
    base_form_id: str | None = None  # FK to base form for Megas
    mega_stone: str | None = None


@dataclass
class ChampionsDexMove:
    """Champions move data (includes rebalanced moves)."""

    id: str
    # NULL when unknown — Serebii's updated-attacks page does not expose
    # `num`; coercing to 0 would hide genuine DB drift from consumers.
    num: int | None
    name: str
    type: str
    category: str
    base_power: int | None
    accuracy: int | None
    # NULL for status-only rows where Serebii prints "--".  Kept nullable
    # so 0 remains a meaningful "move has no PP" value instead of a
    # sentinel for "we don't know."
    pp: int | None
    priority: int | None = 0
    target: str | None = None
    description: str | None = None
    short_desc: str | None = None


# =============================================================================
# Champions usage data models (from Pikalytics)
# =============================================================================


@dataclass
class ChampionsUsageSnapshot:
    """A single Pikalytics Champions usage snapshot for one ELO cutoff."""

    id: int
    # Live set lives in `fetcher.pikalytics_champions.ELO_CUTOFFS` — only
    # "0+" is supported today; multi-cutoff support is gated on Pikalytics
    # exposing a real ELO query parameter.
    elo_cutoff: str
    source: str = "pikalytics"
    fetched_at: str | None = None


# =============================================================================
# Champions team ingestion data models
# =============================================================================


@dataclass
class ChampionsTeamPokemon:
    """A Pokemon on a Champions team (Stat Points, not EVs/IVs)."""

    slot: int
    pokemon: str
    item: str | None = None
    ability: str | None = None
    nature: str | None = None
    tera_type: str | None = None
    level: int = 50
    sp_hp: int = 0
    sp_atk: int = 0
    sp_def: int = 0
    sp_spa: int = 0
    sp_spd: int = 0
    sp_spe: int = 0
    move1: str | None = None
    move2: str | None = None
    move3: str | None = None
    move4: str | None = None


@dataclass
class ChampionsTeam:
    """A Champions team as stored in champions_teams."""

    team_id: str
    source_type: ChampionsSourceType
    source_url: str
    ingestion_status: ChampionsIngestionStatus
    confidence_score: float
    format: str = "champions_ma"
    description: str | None = None
    owner: str | None = None
    review_reasons: list[str] | None = None
    normalizations: list[str] | None = None
    pokemon: list[ChampionsTeamPokemon] = field(default_factory=list)


@dataclass
class ChampionsTeamDraft:
    """In-flight team from an extractor before validation/write.

    Missing ``team_id``, ``ingestion_status``, and ``confidence_score`` —
    the pipeline assigns these after validation, not extractors.
    """

    source_type: ChampionsSourceType
    source_url: str
    tier_baseline_confidence: float
    description: str | None = None
    owner: str | None = None
    pokemon: list[ChampionsTeamPokemon] = field(default_factory=list)
