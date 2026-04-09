"""Tests for fetcher/champions_pokemon_list.py — static Champions Pokemon list."""

import pytest

from smogon_vgc_mcp.fetcher.champions_pokemon_list import (
    ALL_POKEMON,
    BASE_POKEMON,
    MEGA_FORMS,
    MEGA_POKEMON,
)


class TestBasePokemonList:
    """Structural invariants for BASE_POKEMON."""

    def test_has_entries(self):
        assert len(BASE_POKEMON) > 0

    def test_all_slugs_lowercase(self):
        for slug, _ in BASE_POKEMON:
            assert slug == slug.lower(), f"Slug not lowercase: {slug}"

    def test_all_dex_numbers_positive(self):
        for slug, num in BASE_POKEMON:
            assert num > 0, f"{slug} has invalid dex number {num}"

    def test_no_duplicate_slugs(self):
        slugs = [slug for slug, _ in BASE_POKEMON]
        assert len(slugs) == len(set(slugs)), "Duplicate slug in BASE_POKEMON"

    def test_known_pokemon_present(self):
        slugs = {slug for slug, _ in BASE_POKEMON}
        for expected in ("charizard", "mewtwo", "incineroar", "rayquaza"):
            assert expected in slugs, f"Expected {expected} in BASE_POKEMON"

    def test_charizard_dex_number(self):
        mapping = dict(BASE_POKEMON)
        assert mapping["charizard"] == 6

    def test_mewtwo_dex_number(self):
        mapping = dict(BASE_POKEMON)
        assert mapping["mewtwo"] == 150


class TestMegaPokemonList:
    """Structural invariants for MEGA_POKEMON."""

    def test_has_mega_entries(self):
        assert len(MEGA_POKEMON) > 0

    def test_all_mega_slugs_contain_mega(self):
        for slug, _, _ in MEGA_POKEMON:
            assert "mega" in slug, f"Mega slug missing 'mega': {slug}"

    def test_all_base_slugs_in_base_list(self):
        base_slugs = {slug for slug, _ in BASE_POKEMON}
        for mega_slug, _, base_slug in MEGA_POKEMON:
            assert base_slug in base_slugs, (
                f"Mega form '{mega_slug}' has base_slug '{base_slug}' "
                f"not found in BASE_POKEMON"
            )

    def test_no_duplicate_mega_slugs(self):
        slugs = [slug for slug, _, _ in MEGA_POKEMON]
        assert len(slugs) == len(set(slugs)), "Duplicate slug in MEGA_POKEMON"

    def test_charizard_has_two_megas(self):
        charizard_megas = [slug for slug, _, base in MEGA_POKEMON if base == "charizard"]
        assert len(charizard_megas) == 2
        assert "charizard-mega-x" in charizard_megas
        assert "charizard-mega-y" in charizard_megas

    def test_mewtwo_has_two_megas(self):
        mewtwo_megas = [slug for slug, _, base in MEGA_POKEMON if base == "mewtwo"]
        assert len(mewtwo_megas) == 2

    def test_venusaur_mega_present(self):
        mega_slugs = {slug for slug, _, _ in MEGA_POKEMON}
        assert "venusaur-mega" in mega_slugs


class TestAllPokemon:
    """Tests for the combined ALL_POKEMON list."""

    def test_all_pokemon_superset_of_base(self):
        base_slugs = {slug for slug, _ in BASE_POKEMON}
        all_slugs = {slug for slug, _ in ALL_POKEMON}
        assert base_slugs <= all_slugs

    def test_all_pokemon_superset_of_mega(self):
        mega_slugs = {slug for slug, _, _ in MEGA_POKEMON}
        all_slugs = {slug for slug, _ in ALL_POKEMON}
        assert mega_slugs <= all_slugs

    def test_no_duplicate_slugs_in_all(self):
        slugs = [slug for slug, _ in ALL_POKEMON]
        assert len(slugs) == len(set(slugs)), "Duplicate slug in ALL_POKEMON"


class TestMegaFormsLookup:
    """Tests for the MEGA_FORMS lookup dict."""

    def test_charizard_megas_in_lookup(self):
        assert "charizard" in MEGA_FORMS
        assert "charizard-mega-x" in MEGA_FORMS["charizard"]
        assert "charizard-mega-y" in MEGA_FORMS["charizard"]

    def test_single_mega_base_has_one_entry(self):
        # Venusaur has only one Mega
        assert "venusaur" in MEGA_FORMS
        assert len(MEGA_FORMS["venusaur"]) == 1
        assert MEGA_FORMS["venusaur"][0] == "venusaur-mega"

    def test_non_mega_pokemon_not_in_lookup(self):
        # Snorlax has no Mega
        assert "snorlax" not in MEGA_FORMS

    def test_all_mega_slugs_in_lookup_values(self):
        all_lookup_megas = {slug for megas in MEGA_FORMS.values() for slug in megas}
        mega_slugs = {slug for slug, _, _ in MEGA_POKEMON}
        assert all_lookup_megas == mega_slugs
