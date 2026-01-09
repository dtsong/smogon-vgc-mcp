"""Damage calculation MCP tools."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.calculator.damage import (
    build_field_dict,
    build_pokemon_dict,
    calculate_damage_simple,
)
from smogon_vgc_mcp.calculator.damage import (
    calculate_damage as calc_damage_internal,
)
from smogon_vgc_mcp.utils import (
    ValidationError,
    make_error_response,
    validate_ev_spread,
    validate_move_name,
    validate_nature,
    validate_pokemon_name,
    validate_stat_boost,
    validate_terrain,
    validate_type_name,
    validate_weather,
)


def register_damage_tools(mcp: FastMCP) -> None:
    """Register damage calculation tools with the MCP server."""

    @mcp.tool()
    async def calculate_damage(
        attacker: str,
        attacker_evs: str,
        attacker_nature: str,
        defender: str,
        defender_evs: str,
        defender_nature: str,
        move: str,
        attacker_item: str | None = None,
        attacker_ability: str | None = None,
        defender_item: str | None = None,
        defender_ability: str | None = None,
        attacker_tera: str | None = None,
        weather: str | None = None,
        terrain: str | None = None,
        helping_hand: bool = False,
        reflect: bool = False,
        light_screen: bool = False,
        attacker_atk_boost: int = 0,
        attacker_spa_boost: int = 0,
        defender_def_boost: int = 0,
        defender_spd_boost: int = 0,
    ) -> dict:
        """Calculate damage dealt by one Pokemon attacking another with a specific move.

        Use this for single damage calculations with full modifier support (items, abilities,
        tera, weather, terrain, stat boosts, screens). For comparing all moves between two
        Pokemon, use analyze_matchup. For minimum EVs to OHKO, use find_minimum_ohko_evs.

        Returns: description, damage_range, percent_range, ko_chance (e.g., "Guaranteed OHKO"),
        defender_hp, attacker/defender/move details.

        Examples:
        - "How much does Urshifu Close Combat do to Incineroar?"
        - "Can Flutter Mane OHKO Amoonguss with Psychic in Psychic Terrain?"

        Args:
            attacker: Attacking Pokemon name.
            attacker_evs: Attacker EV spread (e.g., "0/252/0/0/4/252").
            attacker_nature: Attacker nature (e.g., "Jolly").
            defender: Defending Pokemon name.
            defender_evs: Defender EV spread.
            defender_nature: Defender nature.
            move: Move name (e.g., "Close Combat").
            attacker_item: Attacker's held item (e.g., "Choice Band").
            attacker_ability: Attacker's ability.
            defender_item: Defender's held item.
            defender_ability: Defender's ability (e.g., "Intimidate").
            attacker_tera: Attacker's active Tera type (e.g., "Fighting").
            weather: Active weather ("Sun", "Rain", "Sand", "Snow").
            terrain: Active terrain ("Grassy", "Electric", "Psychic", "Misty").
            helping_hand: Is Helping Hand boosting the attack?
            reflect: Is Reflect active?
            light_screen: Is Light Screen active?
            attacker_atk_boost: Attack stat stage (-6 to +6).
            attacker_spa_boost: Special Attack stat stage (-6 to +6).
            defender_def_boost: Defense stat stage (-6 to +6).
            defender_spd_boost: Special Defense stat stage (-6 to +6).
        """
        try:
            validate_pokemon_name(attacker)
            validate_ev_spread(attacker_evs)
            validate_nature(attacker_nature)
            validate_pokemon_name(defender)
            validate_ev_spread(defender_evs)
            validate_nature(defender_nature)
            move = validate_move_name(move)
            if attacker_tera:
                validate_type_name(attacker_tera)
            validate_weather(weather)
            validate_terrain(terrain)
            validate_stat_boost(attacker_atk_boost, "Attack")
            validate_stat_boost(attacker_spa_boost, "Special Attack")
            validate_stat_boost(defender_def_boost, "Defense")
            validate_stat_boost(defender_spd_boost, "Special Defense")
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        attacker_boosts = None
        if attacker_atk_boost != 0 or attacker_spa_boost != 0:
            attacker_boosts = {"atk": attacker_atk_boost, "spa": attacker_spa_boost}

        defender_boosts = None
        if defender_def_boost != 0 or defender_spd_boost != 0:
            defender_boosts = {"def": defender_def_boost, "spd": defender_spd_boost}

        result = calculate_damage_simple(
            attacker_name=attacker,
            attacker_evs=attacker_evs,
            attacker_nature=attacker_nature,
            defender_name=defender,
            defender_evs=defender_evs,
            defender_nature=defender_nature,
            move=move,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
            defender_item=defender_item,
            defender_ability=defender_ability,
            attacker_tera=attacker_tera,
            weather=weather,
            terrain=terrain,
            helping_hand=helping_hand,
            reflect=reflect,
            light_screen=light_screen,
            attacker_boosts=attacker_boosts,
            defender_boosts=defender_boosts,
        )

        if not result.get("success"):
            return make_error_response(result.get("error", "Calculation failed"))

        return {
            "description": result.get("description"),
            "damage_range": f"{result.get('minDamage')}-{result.get('maxDamage')}",
            "percent_range": f"{result.get('minPercent')}-{result.get('maxPercent')}%",
            "ko_chance": result.get("koChance"),
            "defender_hp": result.get("defenderMaxHP"),
            "attacker": result.get("attacker"),
            "defender": result.get("defender"),
            "move": result.get("move"),
        }

    @mcp.tool()
    async def analyze_matchup(
        pokemon1: str,
        pokemon1_evs: str,
        pokemon1_nature: str,
        pokemon1_moves: list[str],
        pokemon2: str,
        pokemon2_evs: str,
        pokemon2_nature: str,
        pokemon2_moves: list[str],
        pokemon1_item: str | None = None,
        pokemon1_ability: str | None = None,
        pokemon2_item: str | None = None,
        pokemon2_ability: str | None = None,
    ) -> dict:
        """Analyze full matchup between two Pokemon by calculating damage for all moves both ways.

        Use this to compare two Pokemon head-to-head with their full movesets. For a single
        damage calc, use calculate_damage. For EV spreads that survive attacks, use
        find_minimum_survival_evs.

        Returns: pokemon1{name, item, ability, attacks[]}, pokemon2{name, item, ability,
        attacks[]}, summary{pokemon1_best_attack, pokemon2_best_attack}.

        Examples:
        - "How does Urshifu match up against Incineroar?"
        - "Can Flutter Mane beat Amoonguss 1v1?"

        Args:
            pokemon1: First Pokemon name.
            pokemon1_evs: First Pokemon's EV spread.
            pokemon1_nature: First Pokemon's nature.
            pokemon1_moves: First Pokemon's moves (list of up to 4).
            pokemon2: Second Pokemon name.
            pokemon2_evs: Second Pokemon's EV spread.
            pokemon2_nature: Second Pokemon's nature.
            pokemon2_moves: Second Pokemon's moves (list of up to 4).
            pokemon1_item: First Pokemon's item.
            pokemon1_ability: First Pokemon's ability.
            pokemon2_item: Second Pokemon's item.
            pokemon2_ability: Second Pokemon's ability.
        """
        try:
            validate_pokemon_name(pokemon1)
            validate_ev_spread(pokemon1_evs)
            validate_nature(pokemon1_nature)
            validate_pokemon_name(pokemon2)
            validate_ev_spread(pokemon2_evs)
            validate_nature(pokemon2_nature)
            if not isinstance(pokemon1_moves, list) or len(pokemon1_moves) == 0:
                raise ValidationError("pokemon1_moves must be a non-empty list")
            if len(pokemon1_moves) > 4:
                raise ValidationError("pokemon1_moves cannot have more than 4 moves")
            for i, mv in enumerate(pokemon1_moves):
                if mv:
                    pokemon1_moves[i] = validate_move_name(mv)
            if not isinstance(pokemon2_moves, list) or len(pokemon2_moves) == 0:
                raise ValidationError("pokemon2_moves must be a non-empty list")
            if len(pokemon2_moves) > 4:
                raise ValidationError("pokemon2_moves cannot have more than 4 moves")
            for i, mv in enumerate(pokemon2_moves):
                if mv:
                    pokemon2_moves[i] = validate_move_name(mv)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        p1 = build_pokemon_dict(
            name=pokemon1,
            evs=pokemon1_evs,
            nature=pokemon1_nature,
            item=pokemon1_item,
            ability=pokemon1_ability,
        )

        p2 = build_pokemon_dict(
            name=pokemon2,
            evs=pokemon2_evs,
            nature=pokemon2_nature,
            item=pokemon2_item,
            ability=pokemon2_ability,
        )

        field = build_field_dict(game_type="Doubles")

        # Calculate Pokemon 1 attacking Pokemon 2
        p1_attacks = []
        for move in pokemon1_moves[:4]:
            if move:
                result = calc_damage_internal(p1, p2, move, field)
                if result.get("success"):
                    p1_attacks.append(
                        {
                            "move": move,
                            "damage": f"{result.get('minPercent')}-{result.get('maxPercent')}%",
                            "ko_chance": result.get("koChance"),
                        }
                    )

        # Calculate Pokemon 2 attacking Pokemon 1
        p2_attacks = []
        for move in pokemon2_moves[:4]:
            if move:
                result = calc_damage_internal(p2, p1, move, field)
                if result.get("success"):
                    p2_attacks.append(
                        {
                            "move": move,
                            "damage": f"{result.get('minPercent')}-{result.get('maxPercent')}%",
                            "ko_chance": result.get("koChance"),
                        }
                    )

        return {
            "pokemon1": {
                "name": pokemon1,
                "item": pokemon1_item,
                "ability": pokemon1_ability,
                "attacks": p1_attacks,
            },
            "pokemon2": {
                "name": pokemon2,
                "item": pokemon2_item,
                "ability": pokemon2_ability,
                "attacks": p2_attacks,
            },
            "summary": {
                "pokemon1_best_attack": p1_attacks[0] if p1_attacks else None,
                "pokemon2_best_attack": p2_attacks[0] if p2_attacks else None,
            },
        }

    @mcp.tool()
    async def calculate_damage_after_intimidate(
        attacker: str,
        attacker_evs: str,
        attacker_nature: str,
        defender: str,
        defender_evs: str,
        defender_nature: str,
        move: str,
        attacker_item: str | None = None,
        attacker_ability: str | None = None,
    ) -> dict:
        """Calculate physical damage before and after Intimidate (-1 Attack).

        Use this for the common VGC scenario of checking damage drop after Incineroar's
        Intimidate. For general stat boost calculations, use calculate_damage with
        attacker_atk_boost=-1.

        Returns: attacker, defender, move, normal{damage, ko_chance}, after_intimidate{damage,
        ko_chance}, damage_reduction percentage.

        Examples:
        - "How much does Intimidate reduce Urshifu's Close Combat damage?"
        - "Can Chien-Pao still OHKO after Intimidate?"

        Args:
            attacker: Attacking Pokemon name.
            attacker_evs: Attacker EV spread.
            attacker_nature: Attacker nature.
            defender: Defending Pokemon name.
            defender_evs: Defender EV spread.
            defender_nature: Defender nature.
            move: Physical move name.
            attacker_item: Attacker's item.
            attacker_ability: Attacker's ability.
        """
        try:
            validate_pokemon_name(attacker)
            validate_ev_spread(attacker_evs)
            validate_nature(attacker_nature)
            validate_pokemon_name(defender)
            validate_ev_spread(defender_evs)
            validate_nature(defender_nature)
            move = validate_move_name(move)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        field = build_field_dict(game_type="Doubles")

        attacker_pokemon = build_pokemon_dict(
            name=attacker,
            evs=attacker_evs,
            nature=attacker_nature,
            item=attacker_item,
            ability=attacker_ability,
        )

        attacker_intimidated = build_pokemon_dict(
            name=attacker,
            evs=attacker_evs,
            nature=attacker_nature,
            item=attacker_item,
            ability=attacker_ability,
            boosts={"atk": -1},
        )

        defender_pokemon = build_pokemon_dict(
            name=defender,
            evs=defender_evs,
            nature=defender_nature,
        )

        # Calculate normal damage
        normal_result = calc_damage_internal(attacker_pokemon, defender_pokemon, move, field)

        # Calculate after Intimidate
        intimidated_result = calc_damage_internal(
            attacker_intimidated, defender_pokemon, move, field
        )

        if not normal_result.get("success") or not intimidated_result.get("success"):
            return make_error_response("Calculation failed")

        normal_min = normal_result.get("minPercent", 0)
        normal_max = normal_result.get("maxPercent", 0)
        intim_min = intimidated_result.get("minPercent", 0)
        intim_max = intimidated_result.get("maxPercent", 0)

        return {
            "attacker": attacker,
            "defender": defender,
            "move": move,
            "normal": {
                "damage": f"{normal_min}-{normal_max}%",
                "ko_chance": normal_result.get("koChance"),
            },
            "after_intimidate": {
                "damage": f"{intim_min}-{intim_max}%",
                "ko_chance": intimidated_result.get("koChance"),
            },
            "damage_reduction": f"{normal_min - intim_min:.1f}%",
        }
