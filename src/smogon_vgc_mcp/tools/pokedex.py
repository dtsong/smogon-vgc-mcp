"""Pokedex tools for MCP server."""

from typing import Literal

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database.queries import (
    get_dex_ability,
    get_dex_item,
    get_dex_move,
    get_dex_pokemon,
    get_moves_by_type,
    get_pokemon_by_type,
    get_pokemon_learnset,
    get_pokemon_type_matchups,
    get_type_effectiveness,
    search_dex_abilities,
    search_dex_items,
    search_dex_moves,
    search_dex_pokemon,
)
from smogon_vgc_mcp.utils import (
    ValidationError,
    make_error_response,
    validate_ability_name,
    validate_item_name,
    validate_limit,
    validate_move_name,
    validate_query_string,
    validate_type_name,
)


def register_pokedex_tools(mcp: FastMCP) -> None:
    """Register Pokedex lookup tools with the MCP server."""

    @mcp.tool()
    async def dex_pokemon(pokemon: str) -> dict:
        """Get static Pokedex data for a Pokemon including base stats, types, and abilities.

        Use this for base stats and type information. For VGC usage statistics (common
        moves, items, teammates), use get_pokemon instead. For searching by partial name,
        use search_dex.

        Returns: name, types[], base_stats{hp/atk/def/spa/spd/spe}, bst, abilities[],
        hidden_ability, height_m, weight_kg, tier.

        Examples:
        - "What are Flutter Mane's base stats?"
        - "What type is Incineroar?"

        Args:
            pokemon: Pokemon name (e.g., "Flutter Mane", "Incineroar"). Case-insensitive.
        """
        result = await get_dex_pokemon(pokemon)

        if not result:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Pokedex",
                hint="Try using search_dex to find the correct name",
            )

        bst = sum(result.base_stats.values())

        return {
            "name": result.name,
            "types": result.types,
            "base_stats": result.base_stats,
            "bst": bst,
            "abilities": result.abilities,
            "hidden_ability": result.ability_hidden,
            "height_m": result.height_m,
            "weight_kg": result.weight_kg,
            "tier": result.tier,
            "prevo": result.prevo,
            "evo_level": result.evo_level,
        }

    @mcp.tool()
    async def dex_move(move: str) -> dict:
        """Get details about a move including type, power, accuracy, and effect description.

        Use this when you know the exact move name. For finding moves by partial name,
        use search_dex with category='moves'. For finding all moves a Pokemon learns,
        use dex_learnset.

        Returns: name, type, category (Physical/Special/Status), base_power, accuracy,
        pp, priority, target, effect.

        Examples:
        - "What does Moonblast do?"
        - "What type is Close Combat?"

        Args:
            move: Move name (e.g., "Moonblast", "Close Combat"). Case-insensitive.
        """
        try:
            move = validate_move_name(move)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        result = await get_dex_move(move)

        if not result:
            return make_error_response(
                f"Move '{move}' not found in Pokedex",
                hint="Try using search_dex with category='moves' to find the correct name",
            )

        return {
            "name": result.name,
            "type": result.type,
            "category": result.category,
            "base_power": result.base_power,
            "accuracy": result.accuracy,
            "pp": result.pp,
            "priority": result.priority,
            "target": result.target,
            "effect": result.short_desc or result.description,
        }

    @mcp.tool()
    async def dex_ability(ability: str) -> dict:
        """Get details about an ability including its effect description.

        Use this when you know the exact ability name. For finding abilities by partial
        name, use search_dex with category='abilities'.

        Returns: name, effect (description), rating.

        Examples:
        - "What does Protosynthesis do?"
        - "How does Intimidate work?"

        Args:
            ability: Ability name (e.g., "Protosynthesis", "Intimidate"). Case-insensitive.
        """
        try:
            ability = validate_ability_name(ability)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        result = await get_dex_ability(ability)

        if not result:
            return make_error_response(
                f"Ability '{ability}' not found in Pokedex",
                hint="Try using search_dex with category='abilities' to find the correct name",
            )

        return {
            "name": result.name,
            "effect": result.short_desc or result.description,
            "rating": result.rating,
        }

    @mcp.tool()
    async def dex_item(item: str) -> dict:
        """Get details about a held item including its effect description.

        Use this when you know the exact item name. For finding items by partial name,
        use search_dex with category='items'. For seeing which Pokemon commonly hold
        an item in VGC, use find_pokemon_by_item.

        Returns: name, effect (description), fling_power, gen.

        Examples:
        - "What does Booster Energy do?"
        - "What is the effect of Choice Scarf?"

        Args:
            item: Item name (e.g., "Booster Energy", "Choice Scarf"). Case-insensitive.
        """
        try:
            item = validate_item_name(item)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        result = await get_dex_item(item)

        if not result:
            return make_error_response(
                f"Item '{item}' not found in Pokedex",
                hint="Try using search_dex with category='items' to find the correct name",
            )

        return {
            "name": result.name,
            "effect": result.short_desc or result.description,
            "fling_power": result.fling_power,
            "gen": result.gen,
        }

    @mcp.tool()
    async def dex_learnset(pokemon: str) -> dict:
        """Get all moves a Pokemon can learn, organized by move type.

        Use this to see a Pokemon's full movepool when building sets. For details about
        a specific move, use dex_move. For seeing which moves are actually used in VGC,
        use get_pokemon instead.

        Returns: pokemon, total_moves, by_type{} with each type containing moves with
        name, category, power, accuracy.

        Examples:
        - "What moves can Incineroar learn?"
        - "Does Flutter Mane learn any Ground moves?"

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane"). Case-insensitive.
        """
        moves = await get_pokemon_learnset(pokemon)

        if not moves:
            return make_error_response(
                f"No learnset found for '{pokemon}'",
                hint="Try using dex_pokemon first to verify the Pokemon name",
            )

        # Organize by type
        by_type = {}
        for move in moves:
            if move.type not in by_type:
                by_type[move.type] = []
            by_type[move.type].append(
                {
                    "name": move.name,
                    "category": move.category,
                    "power": move.base_power,
                    "accuracy": move.accuracy,
                }
            )

        return {
            "pokemon": pokemon,
            "total_moves": len(moves),
            "by_type": by_type,
        }

    @mcp.tool()
    async def dex_type_effectiveness(
        attacking_type: str,
        defending_types: str,
    ) -> dict:
        """Calculate the type effectiveness multiplier for an attacking type vs defending types.

        Use this for raw type calculations (e.g., Fire vs Grass/Steel = 4x). For getting
        a Pokemon's full defensive type chart, use dex_pokemon_weaknesses instead.

        Returns: attacking_type, defending_types[], multiplier (0.25/0.5/1/2/4),
        effectiveness description.

        Examples:
        - "How effective is Fire against Grass/Steel?"
        - "What's the multiplier for Ghost vs Normal?"

        Args:
            attacking_type: Attacking move's type (e.g., "Fire", "Ghost"). Capitalize first letter.
            defending_types: Defending types, comma-separated no spaces (e.g., "Grass,Steel").
        """
        def_types = [t.strip() for t in defending_types.split(",")]

        try:
            validate_type_name(attacking_type)
            for def_type in def_types:
                validate_type_name(def_type)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        result = await get_type_effectiveness(attacking_type, def_types)

        return result

    @mcp.tool()
    async def dex_pokemon_weaknesses(pokemon: str) -> dict:
        """Get a Pokemon's defensive type chart (weaknesses, resistances, immunities).

        Use this to see what types a Pokemon is weak/resistant to. For calculating a specific
        type matchup, use dex_type_effectiveness. For analyzing a full team's shared weaknesses,
        use analyze_team_type_coverage.

        Returns: pokemon, types[], x4_weak[], x2_weak[], x0_5_resist[], x0_25_resist[], immune[].

        Examples:
        - "What is Incineroar weak to?"
        - "What types does Flutter Mane resist?"

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane"). Case-insensitive.
        """
        result = await get_pokemon_type_matchups(pokemon)

        if not result:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Pokedex",
                hint="Try using dex_pokemon first to verify the Pokemon name",
            )

        return result

    @mcp.tool()
    async def search_dex(
        query: str,
        category: Literal["pokemon", "moves", "abilities", "items"] = "pokemon",
        limit: int = 10,
    ) -> dict:
        """Search the Pokedex by partial name match across Pokemon, moves, abilities, or items.

        Use this when you don't know the exact name or want to find similar entries.
        For getting full details once you know the name, use dex_pokemon, dex_move,
        dex_ability, or dex_item.

        Returns: query, category, count, results[] with name and category-specific fields
        (types/bst for pokemon, type/power for moves, effect for abilities/items).

        Examples:
        - "Find Pokemon with 'flutter' in the name"
        - "Search for moves containing 'moon'"

        Args:
            query: Partial name to search (e.g., "flutter", "incin"). Case-insensitive.
            category: What to search - "pokemon", "moves", "abilities", or "items".
            limit: Max results (default 10, max 50).
        """
        try:
            query = validate_query_string(query, "Search query")
            limit = validate_limit(limit, max_limit=50)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        cat = category.lower()

        if cat == "pokemon":
            results = await search_dex_pokemon(query, limit)
            return {
                "query": query,
                "category": category,
                "count": len(results),
                "results": [
                    {
                        "name": p.name,
                        "types": p.types,
                        "bst": sum(p.base_stats.values()),
                    }
                    for p in results
                ],
            }

        elif cat == "moves":
            results = await search_dex_moves(query, limit)
            return {
                "query": query,
                "category": category,
                "count": len(results),
                "results": [
                    {
                        "name": m.name,
                        "type": m.type,
                        "category": m.category,
                        "power": m.base_power,
                    }
                    for m in results
                ],
            }

        elif cat == "abilities":
            results = await search_dex_abilities(query, limit)
            return {
                "query": query,
                "category": category,
                "count": len(results),
                "results": [
                    {
                        "name": a.name,
                        "effect": a.short_desc,
                    }
                    for a in results
                ],
            }

        elif cat == "items":
            results = await search_dex_items(query, limit)
            return {
                "query": query,
                "category": category,
                "count": len(results),
                "results": [
                    {
                        "name": i.name,
                        "effect": i.short_desc,
                    }
                    for i in results
                ],
            }

        else:
            return make_error_response(
                f"Unknown category '{cat}'",
                valid_categories=["pokemon", "moves", "abilities", "items"],
            )

    @mcp.tool()
    async def dex_pokemon_by_type(
        pokemon_type: str,
        limit: int = 20,
    ) -> dict:
        """Get a list of Pokemon that have a specific type.

        Use this to find Pokemon of a type (e.g., all Fairy types). For finding Pokemon
        that commonly use a specific Tera Type in VGC, use find_pokemon_by_tera instead.

        Returns: type, count, pokemon[] with name, types[], bst.

        Examples:
        - "List all Fairy type Pokemon"
        - "What Pokemon are Ghost type?"

        Args:
            pokemon_type: Type name (e.g., "Fairy", "Ghost"). Capitalize first letter.
            limit: Max results (default 20, max 100).
        """
        try:
            pokemon_type = validate_type_name(pokemon_type)
            limit = validate_limit(limit, max_limit=100)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        results = await get_pokemon_by_type(pokemon_type, limit)

        if not results:
            return make_error_response(
                f"No Pokemon found with type '{pokemon_type}'",
                hint="Make sure the type name is capitalized (e.g., 'Fairy', not 'fairy')",
            )

        return {
            "type": pokemon_type,
            "count": len(results),
            "pokemon": [
                {
                    "name": p.name,
                    "types": p.types,
                    "bst": sum(p.base_stats.values()),
                }
                for p in results
            ],
        }

    @mcp.tool()
    async def dex_moves_by_type(
        move_type: str,
        category: Literal["Physical", "Special", "Status"] | None = None,
        limit: int = 20,
    ) -> dict:
        """Get a list of moves of a specific type, optionally filtered by category.

        Use this to find strong moves of a type (e.g., best Fairy moves). Results are
        ordered by base power (highest first). For finding moves a specific Pokemon
        can learn, use dex_learnset instead.

        Returns: type, category_filter, count, moves[] with name, category, power,
        accuracy, effect. Sorted by power descending.

        Examples:
        - "What are the strongest Fairy moves?"
        - "List all Physical Fighting moves"

        Args:
            move_type: Type name (e.g., "Fairy", "Fighting"). Capitalize first letter.
            category: Optional filter - "Physical", "Special", or "Status".
            limit: Max results (default 20, max 100).
        """
        try:
            move_type = validate_type_name(move_type)
            limit = validate_limit(limit, max_limit=100)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        results = await get_moves_by_type(move_type, category, limit)

        if not results:
            return make_error_response(
                f"No moves found with type '{move_type}'",
                hint="Make sure the type name is capitalized (e.g., 'Fairy', not 'fairy')",
            )

        return {
            "type": move_type,
            "category_filter": category,
            "count": len(results),
            "moves": [
                {
                    "name": m.name,
                    "category": m.category,
                    "power": m.base_power,
                    "accuracy": m.accuracy,
                    "effect": m.short_desc,
                }
                for m in results
            ],
        }
