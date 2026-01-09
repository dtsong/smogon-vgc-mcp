"""Pokedex tools for MCP server."""

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


def register_pokedex_tools(mcp: FastMCP) -> None:
    """Register Pokedex lookup tools with the MCP server."""

    @mcp.tool()
    async def dex_pokemon(pokemon: str) -> dict:
        """Get Pokedex info for a Pokemon (stats, types, abilities).

        Args:
            pokemon: Pokemon name or ID (e.g., "Flutter Mane", "fluttermane")

        Returns:
            Pokemon data including types, base stats, and abilities
        """
        result = await get_dex_pokemon(pokemon)

        if not result:
            return {
                "error": f"Pokemon '{pokemon}' not found in Pokedex",
                "hint": "Try using search_dex to find the correct name",
            }

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
        """Get info about a move (type, power, effect).

        Args:
            move: Move name or ID (e.g., "Moonblast", "moonblast")

        Returns:
            Move data including type, power, accuracy, and effect
        """
        result = await get_dex_move(move)

        if not result:
            return {
                "error": f"Move '{move}' not found in Pokedex",
                "hint": "Try using search_dex with category='moves' to find the correct name",
            }

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
        """Get info about an ability.

        Args:
            ability: Ability name or ID (e.g., "Protosynthesis", "protosynthesis")

        Returns:
            Ability data including effect description
        """
        result = await get_dex_ability(ability)

        if not result:
            return {
                "error": f"Ability '{ability}' not found in Pokedex",
                "hint": "Try using search_dex with category='abilities' to find the correct name",
            }

        return {
            "name": result.name,
            "effect": result.short_desc or result.description,
            "rating": result.rating,
        }

    @mcp.tool()
    async def dex_item(item: str) -> dict:
        """Get info about an item.

        Args:
            item: Item name or ID (e.g., "Booster Energy", "boosterenergy")

        Returns:
            Item data including effect description
        """
        result = await get_dex_item(item)

        if not result:
            return {
                "error": f"Item '{item}' not found in Pokedex",
                "hint": "Try using search_dex with category='items' to find the correct name",
            }

        return {
            "name": result.name,
            "effect": result.short_desc or result.description,
            "fling_power": result.fling_power,
            "gen": result.gen,
        }

    @mcp.tool()
    async def dex_learnset(pokemon: str) -> dict:
        """Get all moves a Pokemon can learn.

        Args:
            pokemon: Pokemon name or ID

        Returns:
            List of moves the Pokemon can learn, organized by type
        """
        moves = await get_pokemon_learnset(pokemon)

        if not moves:
            return {
                "error": f"No learnset found for '{pokemon}'",
                "hint": "Try using dex_pokemon first to verify the Pokemon name",
            }

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
        """Calculate type effectiveness (e.g., Fire vs Grass/Steel).

        Args:
            attacking_type: The attacking move's type (e.g., "Fire")
            defending_types: Comma-separated defending types (e.g., "Grass,Steel")

        Returns:
            Type effectiveness multiplier and details
        """
        # Parse defending types
        def_types = [t.strip() for t in defending_types.split(",")]

        result = await get_type_effectiveness(attacking_type, def_types)

        return result

    @mcp.tool()
    async def dex_pokemon_weaknesses(pokemon: str) -> dict:
        """Get a Pokemon's type weaknesses and resistances.

        Args:
            pokemon: Pokemon name or ID

        Returns:
            Type matchups including weaknesses (>1x), resistances (<1x), and immunities (0x)
        """
        result = await get_pokemon_type_matchups(pokemon)

        if not result:
            return {
                "error": f"Pokemon '{pokemon}' not found in Pokedex",
                "hint": "Try using dex_pokemon first to verify the Pokemon name",
            }

        return result

    @mcp.tool()
    async def search_dex(
        query: str,
        category: str = "pokemon",
        limit: int = 10,
    ) -> dict:
        """Search the Pokedex by name.

        Args:
            query: Search query (partial name match)
            category: What to search: "pokemon", "moves", "abilities", or "items"
            limit: Maximum results to return (default 10)

        Returns:
            List of matching entries
        """
        category = category.lower()

        if category == "pokemon":
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

        elif category == "moves":
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

        elif category == "abilities":
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

        elif category == "items":
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
            return {
                "error": f"Unknown category '{category}'",
                "valid_categories": ["pokemon", "moves", "abilities", "items"],
            }

    @mcp.tool()
    async def dex_pokemon_by_type(
        pokemon_type: str,
        limit: int = 20,
    ) -> dict:
        """Get Pokemon of a specific type.

        Args:
            pokemon_type: Type to filter by (e.g., "Fairy", "Ghost")
            limit: Maximum results to return (default 20)

        Returns:
            List of Pokemon with the specified type
        """
        results = await get_pokemon_by_type(pokemon_type, limit)

        if not results:
            return {
                "error": f"No Pokemon found with type '{pokemon_type}'",
                "hint": "Make sure the type name is capitalized (e.g., 'Fairy', not 'fairy')",
            }

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
        category: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Get moves of a specific type.

        Args:
            move_type: Type to filter by (e.g., "Fairy", "Ghost")
            category: Optional category filter ("Physical", "Special", "Status")
            limit: Maximum results to return (default 20)

        Returns:
            List of moves with the specified type, ordered by base power
        """
        results = await get_moves_by_type(move_type, category, limit)

        if not results:
            return {
                "error": f"No moves found with type '{move_type}'",
                "hint": "Make sure the type name is capitalized (e.g., 'Fairy', not 'fairy')",
            }

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
