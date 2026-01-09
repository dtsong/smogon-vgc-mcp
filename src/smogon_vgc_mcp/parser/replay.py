"""Pokemon Showdown replay parser for VGC battles."""

import re
import time
from dataclasses import dataclass, field

import httpx

from smogon_vgc_mcp.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Pokemon:
    """A Pokemon on a team with its set information."""

    species: str
    item: str | None = None
    ability: str | None = None
    tera_type: str | None = None
    moves: list[str] = field(default_factory=list)
    level: int = 50

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
class Turn:
    """A single turn in the battle."""

    number: int
    events: list[MoveEvent | TeraEvent | FaintEvent] = field(default_factory=list)

    @property
    def moves(self) -> list[MoveEvent]:
        """Get all move events in this turn."""
        return [e for e in self.events if isinstance(e, MoveEvent)]

    @property
    def teras(self) -> list[TeraEvent]:
        """Get all Tera events in this turn."""
        return [e for e in self.events if isinstance(e, TeraEvent)]

    @property
    def faints(self) -> list[FaintEvent]:
        """Get all faint events in this turn."""
        return [e for e in self.events if isinstance(e, FaintEvent)]


@dataclass
class Player:
    """A player in the battle."""

    name: str
    player_id: str
    rating: int | None = None
    team: Team = field(default_factory=Team)
    brought: list[str] = field(default_factory=list)


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


def _normalize_species(species: str) -> str:
    """Normalize species name from replay format."""
    species = species.split(",")[0]
    if "|" in species:
        species = species.split("|")[1]
    return species.strip()


def _parse_pokemon_details(details: str) -> dict:
    """Parse Pokemon details string (species, level, gender)."""
    parts = details.split(", ")
    result = {"species": _normalize_species(parts[0]), "level": 50}

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
        return int(current), int(max_hp)

    return int(hp_str), 100


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

    pokemon_hp: dict[str, tuple[int, int]] = {}
    active_pokemon: dict[str, str] = {}

    for line in lines:
        if not line.startswith("|"):
            continue

        parts = line[1:].split("|")
        if len(parts) < 1:
            continue

        cmd = parts[0]

        if cmd == "player" and len(parts) >= 3:
            player_id = parts[1]
            name = parts[2]
            rating = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
            if player_id == "p1":
                player1.name = name
                player1.rating = rating
            elif player_id == "p2":
                player2.name = name
                player2.rating = rating

        elif cmd == "gametype":
            pass

        elif cmd == "gen":
            pass

        elif cmd == "tier" and len(parts) >= 2:
            format_name = parts[1]

        elif cmd == "poke" and len(parts) >= 3:
            player_id = parts[1]
            details = _parse_pokemon_details(parts[2])
            pokemon = Pokemon(
                species=details["species"],
                level=details.get("level", 50),
            )
            if player_id == "p1":
                player1.team.pokemon.append(pokemon)
            elif player_id == "p2":
                player2.team.pokemon.append(pokemon)

        elif cmd == "switch" or cmd == "drag":
            if len(parts) >= 4:
                position = parts[1]
                player_id = position.split(":")[0][:2]
                details = _parse_pokemon_details(parts[2])
                species = details["species"]

                if current_turn.number == 0:
                    player = player1 if player_id == "p1" else player2
                    if species not in player.brought:
                        player.brought.append(species)

                active_pokemon[position] = species

                hp_str = parts[3].split()[0] if parts[3] else "100/100"
                hp_current, hp_max = _parse_hp(hp_str)
                pokemon_hp[position] = (hp_current, hp_max)

        elif cmd == "turn" and len(parts) >= 2:
            if current_turn.events:
                turns.append(current_turn)
            current_turn = Turn(number=int(parts[1]))

        elif cmd == "move" and len(parts) >= 3:
            position = parts[1]
            player_id = position.split(":")[0][:2]
            move_name = parts[2]

            user_species = active_pokemon.get(position, "Unknown")

            target_pos = parts[3] if len(parts) > 3 and parts[3] else None
            target_species = None
            if target_pos and ":" in target_pos:
                target_species = active_pokemon.get(target_pos)

            move_event = MoveEvent(
                turn=current_turn.number,
                user=player_id,
                user_species=user_species,
                move=move_name,
                target=target_pos.split(":")[0][:2] if target_pos and ":" in target_pos else None,
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

        elif cmd == "-terastallize" and len(parts) >= 3:
            position = parts[1]
            player_id = position.split(":")[0][:2]
            tera_type = parts[2]
            species = active_pokemon.get(position, "Unknown")

            tera_event = TeraEvent(
                turn=current_turn.number,
                player=player_id,
                species=species,
                tera_type=tera_type,
            )
            current_turn.events.append(tera_event)

            player = player1 if player_id == "p1" else player2
            mon = player.team.get_pokemon(species)
            if mon:
                mon.tera_type = tera_type

        elif cmd == "faint" and len(parts) >= 2:
            position = parts[1]
            player_id = position.split(":")[0][:2]
            species = active_pokemon.get(position, "Unknown")

            faint_event = FaintEvent(
                turn=current_turn.number,
                player=player_id,
                species=species,
            )
            current_turn.events.append(faint_event)

        elif cmd == "-item" and len(parts) >= 3:
            position = parts[1]
            item = parts[2]
            player_id = position.split(":")[0][:2]
            species = active_pokemon.get(position)

            if species:
                player = player1 if player_id == "p1" else player2
                mon = player.team.get_pokemon(species)
                if mon and not mon.item:
                    mon.item = item

        elif cmd == "-ability" and len(parts) >= 3:
            position = parts[1]
            ability = parts[2]
            player_id = position.split(":")[0][:2]
            species = active_pokemon.get(position)

            if species:
                player = player1 if player_id == "p1" else player2
                mon = player.team.get_pokemon(species)
                if mon and not mon.ability:
                    mon.ability = ability

        elif cmd == "-enditem" and len(parts) >= 3:
            position = parts[1]
            item = parts[2]
            player_id = position.split(":")[0][:2]
            species = active_pokemon.get(position)

            if species:
                player = player1 if player_id == "p1" else player2
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

    return Replay(
        replay_id=replay_id,
        format=format_name,
        player1=player1,
        player2=player2,
        turns=turns,
        winner=winner,
        upload_time=upload_time,
    )


async def fetch_and_parse_replay(url: str) -> Replay:
    """Fetch a replay from Pokemon Showdown and parse it.

    Args:
        url: Replay URL (e.g., https://replay.pokemonshowdown.com/gen9vgc2026regf-123456)

    Returns:
        Parsed Replay object
    """
    replay_id_match = re.search(r"replay\.pokemonshowdown\.com/([^/]+)", url)
    if replay_id_match:
        replay_id = replay_id_match.group(1)
    else:
        replay_id = url.split("/")[-1]

    log_url = f"https://replay.pokemonshowdown.com/{replay_id}.log"

    logger.debug(
        f"Fetching replay log: {replay_id}",
        extra={"extra_data": {"replay_id": replay_id, "url": log_url}},
    )

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(log_url)
            response.raise_for_status()
            log_content = response.text

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Replay fetch completed",
            extra={
                "extra_data": {
                    "replay_id": replay_id,
                    "url": log_url,
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
                    "url": log_url,
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
                    "url": log_url,
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
