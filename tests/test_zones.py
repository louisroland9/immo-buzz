"""Tests for the search zone catalogue."""

from __future__ import annotations

from immo_buzz.scraper.zones import LILLE_METROPOLE_ZONES, zones_by_name


def test_zone_ids_have_the_bienici_format() -> None:
    assert LILLE_METROPOLE_ZONES
    for zone in LILLE_METROPOLE_ZONES:
        assert zone.bienici_zone_id.startswith("-")
        assert zone.bienici_zone_id[1:].isdigit()
        assert len(zone.insee_code) == 5


def test_zones_are_unique() -> None:
    names = [zone.name for zone in LILLE_METROPOLE_ZONES]
    zone_ids = [zone.bienici_zone_id for zone in LILLE_METROPOLE_ZONES]
    assert len(set(names)) == len(names)
    assert len(set(zone_ids)) == len(zone_ids)


def test_zones_by_name_is_case_insensitive() -> None:
    selected = zones_by_name(["lille", "ROUBAIX"])
    assert {zone.name for zone in selected} == {"Lille", "Roubaix"}


def test_zones_by_name_falls_back_to_everything() -> None:
    assert len(zones_by_name(None)) == len(LILLE_METROPOLE_ZONES)
    assert len(zones_by_name(["inconnue"])) == len(LILLE_METROPOLE_ZONES)
