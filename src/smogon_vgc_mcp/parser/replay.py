"""Pokemon Showdown replay parser for VGC battles."""

import re
import time
from dataclasses import dataclass, field

import httpx

from smogon_vgc_mcp.logging import get_logger

logger = get_logger(__name__)

STAT_ORDER = ("hp", "atk", "def_", "spa", "spd", "spe")


@dataclass
class StatSpread:
    """A 6-stat spread (EVs or IVs)."""

    hp: int = 0
    atk: int = 0
    def_: int = 0
    spa: int = 0
    spd: int = 0
    spe: int = 0

    def as_dict(self) -> dict[str, int]:
        return {s: getattr(self, s) for s in STAT_ORDER}


@dataclass
class Pokemon:
    """A Pokemon on a team with its set information."""

    species: str
    nickname: str | None = None
    item: str | None = None
    ability: str | None = None
    tera_type: str | None = None
    moves: list[str] = field(default_factory=list)
    level: int = 50
    nature: str | None = None
    gender: str | None = None
    shiny: bool = False
    evs: StatSpread | None = None
    ivs: StatSpread | None = None

    @property
    def base_species(self) -> str:
        """Get base species name (without forme suffix)."""
        if "-" in self.species and self.species not in (
            "Ho-Oh",
            "Porygon-Z",
            "Jangmo-o",
            "Hakamo-o",
            "Kommo-o",
        ):
            return self.species.split("-")[0]
        return self.species


@dataclass
class Team:
    """A team of 6 Pokemon."""

    pokemon: list[Pokemon] = field(default_factory=list)

    def get_pokemon(self, species: str) -> Pokemon | None:
        """Find a Pokemon by species name (case-insensitive, handles formes)."""
        species_lower = species.lower()
        for mon in self.pokemon:
            if mon.species.lower() == species_lower:
                return mon
            if mon.base_species.lower() == species_lower:
                return mon
        return None

    def __len__(self) -> int:
        return len(self.pokemon)


@dataclass
class DamageEvent:
    """Damage dealt during a move."""

    hp_remaining: int
    max_hp: int
    damage_dealt: float

    @property
    def hp_percent(self) -> float:
        """Current HP as percentage."""
        return (self.hp_remaining / self.max_hp) * 100 if self.max_hp > 0 else 0


@dataclass
class MoveEvent:
    """A move used during battle."""

    turn: int
    user: str
    user_species: str
    move: str
    target: str | None = None
    target_species: str | None = None
    damage: DamageEvent | None = None
    effectiveness: str | None = None
    critical_hit: bool = False
    missed: bool = False


@dataclass
class TeraEvent:
    """A Terastallization event."""

    turn: int
    player: str
    species: str
    tera_type: str


@dataclass
class FaintEvent:
    """A Pokemon fainting."""

    turn: int
    player: str
    species: str


@dataclass
class BoostEvent:
    """A stat boost or drop."""

    turn: int
    player: str
    species: str
    stat: str
    stages: int


@dataclass
class StatusEvent:
    """A status condition applied or cured."""

    turn: int
    player: str
    species: str
    status: str
    cured: bool = False


@dataclass
class WeatherEvent:
    """Weather change."""

    turn: int
    weather: str | None


@dataclass
class FieldEvent:
    """Field condition change (terrain, trick room, etc.)."""

    turn: int
    effect: str
    started: bool


@dataclass
class HealEvent:
    """HP restoration."""

    turn: int
    player: str
    species: str
    hp_remaining: int
    max_hp: int
    source: str | None = None


EventType = MoveEvent | TeraEvent | FaintEvent | BoostEvent | StatusEvent | WeatherEvent | FieldEvent | HealEvent


@dataclass
class Turn:
    """A single turn in the battle."""

    number: int
    events: list[EventType] = field(default_factory=list)

    @property
    def moves(self) -> list[MoveEvent]:
        return [e for e in self.events if isinstance(e, MoveEvent)]

    @property
    def teras(self) -> list[TeraEvent]:
        return [e for e in self.events if isinstance(e, TeraEvent)]

    @property
    def faints(self) -> list[FaintEvent]:
        return [e for e in self.events if isinstance(e, FaintEvent)]

    @property
    def boosts(self) -> list[BoostEvent]:
        return [e for e in self.events if isinstance(e, BoostEvent)]

    @property
    def statuses(self) -> list[StatusEvent]:
        return [e for e in self.events if isinstance(e, StatusEvent)]


@dataclass
class Player:
    """A player in the battle."""

    name: str
    player_id: str
    rating: int | None = None
    team: Team = field(default_factory=Team)
    brought: list[str] = field(default_factory=list)


@dataclass
class PokemonState:
    """Tracked state of an active Pokemon."""

    species: str
    hp_current: int = 100
    hp_max: int = 100
    status: str | None = None
    boosts: dict[str, int] = field(default_factory=dict)
    terastallized: str | None = None


@dataclass
class FieldState:
    """Tracked field conditions."""

    weather: str | None = None
    terrain: str | None = None
    trick_room: bool = False


@dataclass
class BattleState:
    """Snapshot of battle state at a point in time."""

    active: dict[str, PokemonState] = field(default_factory=dict)
    field: FieldState = field(default_factory=FieldState)
    turn: int = 0


@dataclass
class Bo3Info:
    """Best-of-3 series metadata extracted from a single game."""

    game_number: int
    series_id: str
    linked_games: list[str] = field(default_factory=list)


@dataclass
class Replay:
    """A complete Pokemon Showdown replay."""

    replay_id: str
    format: str
    player1: Player
    player2: Player
    turns: list[Turn] = field(default_factory=list)
    winner: str | None = None
    upload_time: int | None = None
    generation: int | None = None
    is_rated: bool = False
    rules: list[str] = field(default_factory=list)
    battle_state: BattleState = field(default_factory=BattleState)
    bo3: Bo3Info | None = None

    def get_lead_pokemon(self, player_id: str) -> list[str]:
        """Get the lead Pokemon (first 2 brought) for a player."""
        player = self.player1 if player_id == "p1" else self.player2
        return player.brought[:2] if len(player.brought) >= 2 else player.brought

    def get_all_damage_events(self) -> list[MoveEvent]:
        """Get all move events that dealt damage."""
        return [
            move for turn in self.turns for move in turn.moves if move.damage is not None
        ]

    def get_tera_usage(self) -> dict[str, TeraEvent | None]:
        """Get Tera usage for both players."""
        result: dict[str, TeraEvent | None] = {"p1": None, "p2": None}
        for turn in self.turns:
            for tera in turn.teras:
                if tera.player in result and result[tera.player] is None:
                    result[tera.player] = tera
        return result

    def get_ko_count(self) -> dict[str, int]:
        """Get KO counts for each player."""
        counts = {"p1": 0, "p2": 0}
        for turn in self.turns:
            for faint in turn.faints:
                if faint.player == "p1":
                    counts["p2"] += 1
                else:
                    counts["p1"] += 1
        return counts


# ---------------------------------------------------------------------------
# Showteam Parsing
# ---------------------------------------------------------------------------

def _parse_stat_spread(csv: str, default: int = 0) -> StatSpread:
    """Parse comma-separated stat values into a StatSpread."""
    parts = csv.split(",") if csv else []
    values = []
    for i in range(6):
        if i < len(parts) and parts[i].strip():
            try:
                values.append(int(parts[i].strip()))
            except ValueError:
                values.append(default)
        else:
            values.append(default)
    return StatSpread(
        hp=values[0], atk=values[1], def_=values[2],
        spa=values[3], spd=values[4], spe=values[5],
    )


def _parse_showteam_pokemon(packed: str) -> Pokemon | None:
    """Parse a single Pokemon from Showdown packed team format.

    Packed format fields (pipe-separated):
      0: Nickname (or species if no nickname set)
      1: Species (empty if same as nickname)
      2: Item
      3: Ability
      4: Moves (comma-separated)
      5: Nature
      6: EVs (comma-separated: HP,Atk,Def,SpA,SpD,Spe)
      7: Gender
      8: IVs (comma-separated: HP,Atk,Def,SpA,SpD,Spe)
      9: Shiny ('S' or empty)
     10: Level
     11: Happiness,Pokeball,HiddenPowerType,Gigantamax,DynamaxLevel,TeraType
    """
    fields = packed.split("|")
    if len(fields) < 2:
        return None

    nickname_or_species = fields[0].strip()
    species_field = fields[1].strip() if len(fields) > 1 else ""
    species = species_field if species_field else nickname_or_species
    nickname = nickname_or_species if species_field else None

    if not species:
        return None

    item = fields[2].strip() if len(fields) > 2 and fields[2].strip() else None
    ability = fields[3].strip() if len(fields) > 3 and fields[3].strip() else None

    moves: list[str] = []
    if len(fields) > 4 and fields[4].strip():
        moves = [m.strip() for m in fields[4].split(",") if m.strip()]

    nature = fields[5].strip() if len(fields) > 5 and fields[5].strip() else None

    evs = None
    if len(fields) > 6 and fields[6].strip():
        evs = _parse_stat_spread(fields[6], default=0)

    gender = fields[7].strip() if len(fields) > 7 and fields[7].strip() else None

    ivs = None
    if len(fields) > 8 and fields[8].strip():
        ivs = _parse_stat_spread(fields[8], default=31)

    shiny = len(fields) > 9 and fields[9].strip() == "S"

    level = 50
    if len(fields) > 10 and fields[10].strip():
        try:
            level = int(fields[10].strip())
        except ValueError:
            pass

    tera_type = None
    if len(fields) > 11 and fields[11].strip():
        misc_parts = fields[11].split(",")
        if len(misc_parts) >= 6 and misc_parts[5].strip():
            tera_type = misc_parts[5].strip()

    return Pokemon(
        species=species,
        nickname=nickname,
        item=item,
        ability=ability,
        tera_type=tera_type,
        moves=moves,
        level=level,
        nature=nature,
        gender=gender,
        shiny=shiny,
        evs=evs,
        ivs=ivs,
    )


def parse_showteam(showteam_str: str) -> list[Pokemon]:
    """Parse a full Showdown showteam string into a list of Pokemon."""
    pokemon_strs = showteam_str.split("]")
    result = []
    for s in pokemon_strs:
        s = s.strip()
        if not s:
            continue
        mon = _parse_showteam_pokemon(s)
        if mon:
            result.append(mon)
    return result


# ---------------------------------------------------------------------------
# HTML Extraction
# ---------------------------------------------------------------------------

def extract_log_from_html(html: str) -> str | None:
    """Extract battle log from replay HTML page."""
    match = re.search(
        r'<script\s+type="text/plain"\s+class="battle-log-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return None


def extract_replay_id_from_html(html: str) -> str | None:
    """Extract replay ID from HTML hidden input."""
    match = re.search(r'name="replayid"\s+value="([^"]+)"', html)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------
# URL Normalization
# ---------------------------------------------------------------------------

def normalize_replay_url(url: str) -> str:
    """Normalize a replay URL, stripping file extensions."""
    url = url.strip()
    for ext in (".html", ".json", ".log"):
        if url.endswith(ext):
            url = url[: -len(ext)]
    url = re.sub(r"\?p[12]$", "", url)
    return url


def extract_replay_id(url: str) -> str:
    """Extract the replay ID from a URL."""
    url = normalize_replay_url(url)
    match = re.search(r"replay\.pokemonshowdown\.com/([^/?#]+)", url)
    if match:
        return match.group(1)
    return url.rstrip("/").split("/")[-1]


# ---------------------------------------------------------------------------
# Bo3 Detection
# ---------------------------------------------------------------------------

_BO3_PATTERN = re.compile(
    r'\|uhtml\|bestof\|<h2><strong>Game\s+(\d+)</strong>\s+of\s+'
    r'<a\s+href="/game-bestof3-([^"]+)">',
)


def _detect_bo3(log: str) -> Bo3Info | None:
    """Detect Bo3 series info from the battle log."""
    match = _BO3_PATTERN.search(log)
    if not match:
        return None

    game_number = int(match.group(1))
    series_id = match.group(2)

    linked: list[str] = []
    for m in re.finditer(r'\|tempnotify\|choice\|[^|]*\|(/[^\s|]+)', log):
        linked.append(m.group(1))

    return Bo3Info(game_number=game_number, series_id=series_id, linked_games=linked)


# ---------------------------------------------------------------------------
# Core Parser
# ---------------------------------------------------------------------------

def _normalize_species(species: str) -> str:
    """Normalize species name from replay format."""
    species = species.split(",")[0]
    if "|" in species:
        species = species.split("|")[1]
    return species.strip()


def _parse_pokemon_details(details: str) -> dict:
    """Parse Pokemon details string (species, level, gender)."""
    parts = details.split(", ")
    result: dict = {"species": _normalize_species(parts[0]), "level": 50}

    for part in parts[1:]:
        if part.startswith("L"):
            result["level"] = int(part[1:])
        elif part in ("M", "F"):
            result["gender"] = part

    return result


def _parse_hp(hp_str: str) -> tuple[int, int]:
    """Parse HP string like '150/200' or '0 fnt'."""
    if "fnt" in hp_str:
        return 0, 100

    if "/" in hp_str:
        current, max_hp = hp_str.split("/")
        return int(current.strip()), int(max_hp.strip())

    return int(hp_str), 100


def _get_player_id(position: str) -> str:
    """Extract player ID (p1/p2) from a position string like 'p1a: Nickname'."""
    return position.split(":")[0][:2]


def _merge_showteam_into_team(team: Team, showteam_pokemon: list[Pokemon]) -> None:
    """Merge showteam data into existing team, matching by species."""
    for st_mon in showteam_pokemon:
        existing = team.get_pokemon(st_mon.species)
        if existing:
            if st_mon.item:
                existing.item = st_mon.item
            if st_mon.ability:
                existing.ability = st_mon.ability
            if st_mon.tera_type:
                existing.tera_type = st_mon.tera_type
            if st_mon.moves:
                existing.moves = st_mon.moves
            if st_mon.nature:
                existing.nature = st_mon.nature
            if st_mon.evs:
                existing.evs = st_mon.evs
            if st_mon.ivs:
                existing.ivs = st_mon.ivs
            if st_mon.gender:
                existing.gender = st_mon.gender
            if st_mon.nickname:
                existing.nickname = st_mon.nickname
            existing.shiny = st_mon.shiny
            existing.level = st_mon.level
        else:
            team.pokemon.append(st_mon)


def parse_replay(log: str, replay_id: str = "") -> Replay:
    """Parse a Pokemon Showdown replay log into structured data."""
    lines = log.strip().split("\n")

    player1 = Player(name="", player_id="p1")
    player2 = Player(name="", player_id="p2")
    turns: list[Turn] = []
    current_turn = Turn(number=0)
    winner = None
    format_name = ""
    upload_time = None
    generation: int | None = None
    is_rated = False
    rules: list[str] = []

    pokemon_hp: dict[str, tuple[int, int]] = {}
    active_pokemon: dict[str, str] = {}
    pokemon_boosts: dict[str, dict[str, int]] = {}
    pokemon_status: dict[str, str] = {}
    field_state = FieldState()

    bo3 = _detect_bo3(log)

    for line in lines:
        if not line.startswith("|"):
            continue

        parts = line[1:].split("|")
        if len(parts) < 1:
            continue

        cmd = parts[0]

        if cmd == "player" and len(parts) >= 3:
            pid = parts[1]
            name = parts[2]
            rating = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
            if pid == "p1":
                player1.name = name
                player1.rating = rating
            elif pid == "p2":
                player2.name = name
                player2.rating = rating

        elif cmd == "gen" and len(parts) >= 2:
            try:
                generation = int(parts[1])
            except ValueError:
                pass

        elif cmd == "tier" and len(parts) >= 2:
            format_name = parts[1]

        elif cmd == "rated":
            is_rated = True

        elif cmd == "rule" and len(parts) >= 2:
            rules.append(parts[1])

        elif cmd == "poke" and len(parts) >= 3:
            pid = parts[1]
            details = _parse_pokemon_details(parts[2])
            pokemon = Pokemon(
                species=details["species"],
                level=details.get("level", 50),
                gender=details.get("gender"),
            )
            if pid == "p1":
                player1.team.pokemon.append(pokemon)
            elif pid == "p2":
                player2.team.pokemon.append(pokemon)

        elif cmd == "showteam" and len(parts) >= 3:
            pid = parts[1]
            showteam_str = "|".join(parts[2:])
            st_pokemon = parse_showteam(showteam_str)
            team = player1.team if pid == "p1" else player2.team
            _merge_showteam_into_team(team, st_pokemon)

        elif cmd in ("switch", "drag"):
            if len(parts) >= 4:
                position = parts[1]
                pid = _get_player_id(position)
                details = _parse_pokemon_details(parts[2])
                species = details["species"]

                if current_turn.number == 0:
                    player = player1 if pid == "p1" else player2
                    if species not in player.brought:
                        player.brought.append(species)

                active_pokemon[position] = species

                hp_str = parts[3].split()[0] if parts[3] else "100/100"
                hp_current, hp_max = _parse_hp(hp_str)
                pokemon_hp[position] = (hp_current, hp_max)

                pokemon_boosts[position] = {}
                pokemon_status.pop(position, None)

        elif cmd == "turn" and len(parts) >= 2:
            if current_turn.events:
                turns.append(current_turn)
            current_turn = Turn(number=int(parts[1]))

        elif cmd == "move" and len(parts) >= 3:
            position = parts[1]
            pid = _get_player_id(position)
            move_name = parts[2]
            user_species = active_pokemon.get(position, "Unknown")

            target_pos = parts[3] if len(parts) > 3 and parts[3] else None
            target_species = None
            if target_pos and ":" in target_pos:
                target_species = active_pokemon.get(target_pos)

            move_event = MoveEvent(
                turn=current_turn.number,
                user=pid,
                user_species=user_species,
                move=move_name,
                target=_get_player_id(target_pos) if target_pos and ":" in target_pos else None,
                target_species=target_species,
            )
            current_turn.events.append(move_event)

        elif cmd == "-damage" and len(parts) >= 3:
            position = parts[1]
            hp_str = parts[2].split()[0]
            new_hp, max_hp = _parse_hp(hp_str)
            old_hp, _ = pokemon_hp.get(position, (max_hp, max_hp))
            damage_dealt = ((old_hp - new_hp) / max_hp) * 100 if max_hp > 0 else 0

            pokemon_hp[position] = (new_hp, max_hp)

            for event in reversed(current_turn.events):
                if isinstance(event, MoveEvent) and event.damage is None:
                    event.damage = DamageEvent(
                        hp_remaining=new_hp,
                        max_hp=max_hp,
                        damage_dealt=round(damage_dealt, 1),
                    )
                    break

        elif cmd == "-heal" and len(parts) >= 3:
            position = parts[1]
            hp_str = parts[2].split()[0]
            new_hp, max_hp = _parse_hp(hp_str)
            pokemon_hp[position] = (new_hp, max_hp)

            pid = _get_player_id(position)
            species = active_pokemon.get(position, "Unknown")
            source = parts[3] if len(parts) > 3 else None
            current_turn.events.append(HealEvent(
                turn=current_turn.number,
                player=pid,
                species=species,
                hp_remaining=new_hp,
                max_hp=max_hp,
                source=source,
            ))

        elif cmd == "-boost" and len(parts) >= 4:
            position = parts[1]
            stat = parts[2]
            try:
                stages = int(parts[3])
            except ValueError:
                stages = 1
            pid = _get_player_id(position)
            species = active_pokemon.get(position, "Unknown")

            if position not in pokemon_boosts:
                pokemon_boosts[position] = {}
            pokemon_boosts[position][stat] = pokemon_boosts[position].get(stat, 0) + stages

            current_turn.events.append(BoostEvent(
                turn=current_turn.number,
                player=pid,
                species=species,
                stat=stat,
                stages=stages,
            ))

        elif cmd == "-unboost" and len(parts) >= 4:
            position = parts[1]
            stat = parts[2]
            try:
                stages = int(parts[3])
            except ValueError:
                stages = 1
            pid = _get_player_id(position)
            species = active_pokemon.get(position, "Unknown")

            if position not in pokemon_boosts:
                pokemon_boosts[position] = {}
            pokemon_boosts[position][stat] = pokemon_boosts[position].get(stat, 0) - stages

            current_turn.events.append(BoostEvent(
                turn=current_turn.number,
                player=pid,
                species=species,
                stat=stat,
                stages=-stages,
            ))

        elif cmd == "-status" and len(parts) >= 3:
            position = parts[1]
            status = parts[2]
            pid = _get_player_id(position)
            species = active_pokemon.get(position, "Unknown")
            pokemon_status[position] = status

            current_turn.events.append(StatusEvent(
                turn=current_turn.number,
                player=pid,
                species=species,
                status=status,
            ))

        elif cmd == "-curestatus" and len(parts) >= 3:
            position = parts[1]
            status = parts[2]
            pid = _get_player_id(position)
            species = active_pokemon.get(position, "Unknown")
            pokemon_status.pop(position, None)

            current_turn.events.append(StatusEvent(
                turn=current_turn.number,
                player=pid,
                species=species,
                status=status,
                cured=True,
            ))

        elif cmd == "-weather" and len(parts) >= 2:
            weather = parts[1]
            if weather == "none":
                field_state.weather = None
                weather_val = None
            else:
                field_state.weather = weather
                weather_val = weather
            current_turn.events.append(WeatherEvent(
                turn=current_turn.number,
                weather=weather_val,
            ))

        elif cmd == "-fieldstart" and len(parts) >= 2:
            effect = parts[1]
            if "Trick Room" in effect:
                field_state.trick_room = True
            elif "Terrain" in effect:
                field_state.terrain = effect.replace("move: ", "")
            current_turn.events.append(FieldEvent(
                turn=current_turn.number,
                effect=effect,
                started=True,
            ))

        elif cmd == "-fieldend" and len(parts) >= 2:
            effect = parts[1]
            if "Trick Room" in effect:
                field_state.trick_room = False
            elif "Terrain" in effect:
                field_state.terrain = None
            current_turn.events.append(FieldEvent(
                turn=current_turn.number,
                effect=effect,
                started=False,
            ))

        elif cmd == "-supereffective":
            for event in reversed(current_turn.events):
                if isinstance(event, MoveEvent):
                    event.effectiveness = "super effective"
                    break

        elif cmd == "-resisted":
            for event in reversed(current_turn.events):
                if isinstance(event, MoveEvent):
                    event.effectiveness = "resisted"
                    break

        elif cmd == "-immune":
            for event in reversed(current_turn.events):
                if isinstance(event, MoveEvent):
                    event.effectiveness = "immune"
                    break

        elif cmd == "-crit":
            for event in reversed(current_turn.events):
                if isinstance(event, MoveEvent):
                    event.critical_hit = True
                    break

        elif cmd == "-miss":
            for event in reversed(current_turn.events):
                if isinstance(event, MoveEvent):
                    event.missed = True
                    break

        elif cmd == "-fail":
            for event in reversed(current_turn.events):
                if isinstance(event, MoveEvent):
                    event.missed = True
                    break

        elif cmd == "-terastallize" and len(parts) >= 3:
            position = parts[1]
            pid = _get_player_id(position)
            tera_type = parts[2]
            species = active_pokemon.get(position, "Unknown")

            tera_event = TeraEvent(
                turn=current_turn.number,
                player=pid,
                species=species,
                tera_type=tera_type,
            )
            current_turn.events.append(tera_event)

            player = player1 if pid == "p1" else player2
            mon = player.team.get_pokemon(species)
            if mon:
                mon.tera_type = tera_type

        elif cmd == "faint" and len(parts) >= 2:
            position = parts[1]
            pid = _get_player_id(position)
            species = active_pokemon.get(position, "Unknown")

            faint_event = FaintEvent(
                turn=current_turn.number,
                player=pid,
                species=species,
            )
            current_turn.events.append(faint_event)

            pokemon_hp[position] = (0, pokemon_hp.get(position, (0, 100))[1])

        elif cmd == "-item" and len(parts) >= 3:
            position = parts[1]
            item = parts[2]
            pid = _get_player_id(position)
            species = active_pokemon.get(position)

            if species:
                player = player1 if pid == "p1" else player2
                mon = player.team.get_pokemon(species)
                if mon and not mon.item:
                    mon.item = item

        elif cmd == "-ability" and len(parts) >= 3:
            position = parts[1]
            ability = parts[2]
            pid = _get_player_id(position)
            species = active_pokemon.get(position)

            if species:
                player = player1 if pid == "p1" else player2
                mon = player.team.get_pokemon(species)
                if mon and not mon.ability:
                    mon.ability = ability

        elif cmd == "-enditem" and len(parts) >= 3:
            position = parts[1]
            item = parts[2]
            pid = _get_player_id(position)
            species = active_pokemon.get(position)

            if species:
                player = player1 if pid == "p1" else player2
                mon = player.team.get_pokemon(species)
                if mon and not mon.item:
                    mon.item = item

        elif cmd == "win" and len(parts) >= 2:
            winner = parts[1]

        elif cmd == "t:" and len(parts) >= 2:
            try:
                upload_time = int(parts[1])
            except ValueError:
                pass

    if current_turn.events:
        turns.append(current_turn)

    for turn in turns:
        for move in turn.moves:
            player = player1 if move.user == "p1" else player2
            mon = player.team.get_pokemon(move.user_species)
            if mon and move.move not in mon.moves:
                mon.moves.append(move.move)

    active_states: dict[str, PokemonState] = {}
    for pos, species in active_pokemon.items():
        hp_cur, hp_max = pokemon_hp.get(pos, (100, 100))
        active_states[pos] = PokemonState(
            species=species,
            hp_current=hp_cur,
            hp_max=hp_max,
            status=pokemon_status.get(pos),
            boosts=pokemon_boosts.get(pos, {}),
        )

    battle_state = BattleState(
        active=active_states,
        field=field_state,
        turn=turns[-1].number if turns else 0,
    )

    return Replay(
        replay_id=replay_id,
        format=format_name,
        player1=player1,
        player2=player2,
        turns=turns,
        winner=winner,
        upload_time=upload_time,
        generation=generation,
        is_rated=is_rated,
        rules=rules,
        battle_state=battle_state,
        bo3=bo3,
    )


# ---------------------------------------------------------------------------
# Fetch + Parse
# ---------------------------------------------------------------------------

async def fetch_and_parse_replay(url: str) -> Replay:
    """Fetch a replay from Pokemon Showdown and parse it.

    Tries .json first for structured data, then .log for raw log,
    then .html and extracts the embedded battle log.

    Args:
        url: Replay URL (any format: bare, .html, .json, .log)

    Returns:
        Parsed Replay object
    """
    replay_id = extract_replay_id(url)
    base_url = f"https://replay.pokemonshowdown.com/{replay_id}"

    logger.debug(
        f"Fetching replay: {replay_id}",
        extra={"extra_data": {"replay_id": replay_id, "url": base_url}},
    )

    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            log_content = await _fetch_with_fallback(client, base_url, replay_id)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Replay fetch completed",
            extra={
                "extra_data": {
                    "replay_id": replay_id,
                    "duration_ms": round(duration_ms, 2),
                    "content_length": len(log_content),
                }
            },
        )
    except httpx.HTTPStatusError as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "Replay fetch failed: HTTP error",
            extra={
                "extra_data": {
                    "replay_id": replay_id,
                    "status_code": e.response.status_code,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                }
            },
        )
        raise
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "Replay fetch failed",
            extra={
                "extra_data": {
                    "replay_id": replay_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                }
            },
            exc_info=True,
        )
        raise

    parse_start = time.perf_counter()
    replay = parse_replay(log_content, replay_id)
    parse_duration_ms = (time.perf_counter() - parse_start) * 1000

    logger.info(
        "Replay parsed successfully",
        extra={
            "extra_data": {
                "replay_id": replay_id,
                "format": replay.format,
                "turn_count": len(replay.turns),
                "parse_duration_ms": round(parse_duration_ms, 2),
            }
        },
    )

    return replay


async def _fetch_with_fallback(
    client: httpx.AsyncClient, base_url: str, replay_id: str
) -> str:
    """Try .json, then .log, then .html to get battle log content."""
    # Try .json first
    try:
        resp = await client.get(f"{base_url}.json")
        resp.raise_for_status()
        data = resp.json()
        if "log" in data:
            return data["log"]
    except (httpx.HTTPStatusError, ValueError, KeyError):
        pass

    # Try .log
    try:
        resp = await client.get(f"{base_url}.log")
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError:
        pass

    # Try .html and extract
    resp = await client.get(base_url)
    resp.raise_for_status()
    log = extract_log_from_html(resp.text)
    if log:
        return log

    raise ValueError(f"Could not extract battle log from replay {replay_id}")
