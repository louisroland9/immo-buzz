"""Tests for the city + radius search area resolution."""

from __future__ import annotations

from typing import Any

import pytest

from immo_buzz.scraper.areas import SearchArea, resolve_zone_ids
from immo_buzz.scraper.geocoding import Commune, GeoPoint

LILLE = GeoPoint(latitude=50.6310, longitude=3.0468)


class StubResolver:
    """Resolver returning canned communes and per-name suggest payloads."""

    def __init__(
        self,
        communes: list[Commune],
        suggestions: dict[str, list[dict[str, Any]]],
    ) -> None:
        self._communes = communes
        self._suggestions = suggestions
        self.queries: list[str] = []

    def communes_in_radius(self, center: GeoPoint, radius_km: float) -> list[Commune]:
        del center, radius_km
        return list(self._communes)

    def suggest(self, query: str) -> list[dict[str, Any]]:
        self.queries.append(query)
        return self._suggestions.get(query, [])


def _commune(name: str, insee: str) -> Commune:
    return Commune(name=name, insee_code=insee, center=LILLE)


def test_search_area_contains_uses_the_radius() -> None:
    area = SearchArea(center=LILLE, radius_km=5.0)
    near = GeoPoint(latitude=50.6400, longitude=3.0500)
    far = GeoPoint(latitude=50.8600, longitude=3.0500)

    assert area.contains(LILLE) is True
    assert area.contains(near) is True
    assert area.contains(far) is False


def test_search_area_rejects_non_positive_radius() -> None:
    with pytest.raises(ValueError):
        SearchArea(center=LILLE, radius_km=0)


def test_resolve_zone_ids_matches_on_insee_code() -> None:
    resolver = StubResolver(
        communes=[_commune("Lille", "59350"), _commune("Roubaix", "59512")],
        suggestions={
            "Lille": [
                {
                    "type": "city",
                    "name": "Lille",
                    "insee_code": "59350",
                    "zoneIds": ["-58404"],
                }
            ],
            "Roubaix": [
                {
                    "type": "city",
                    "name": "Roubaix",
                    "insee_code": "59512",
                    "zoneIds": ["-59043"],
                }
            ],
        },
    )
    area = SearchArea(center=LILLE, radius_km=10.0, label="Lille")

    zone_ids = resolve_zone_ids(area, resolver)  # type: ignore[arg-type]

    assert zone_ids == ["-58404", "-59043"]
    assert resolver.queries == ["Lille", "Roubaix"]


def test_resolve_zone_ids_deduplicates_shared_zones() -> None:
    shared: list[dict[str, Any]] = [
        {"type": "city", "name": "Lille", "insee_code": "59350", "zoneIds": ["-58404"]}
    ]
    resolver = StubResolver(
        communes=[_commune("Lille", "59350"), _commune("Hellemmes", "59350")],
        suggestions={"Lille": shared, "Hellemmes": shared},
    )
    area = SearchArea(center=LILLE, radius_km=10.0)

    zone_ids = resolve_zone_ids(area, resolver)  # type: ignore[arg-type]

    assert zone_ids == ["-58404"]


def test_resolve_zone_ids_prefers_the_insee_match_over_the_fallback() -> None:
    resolver = StubResolver(
        communes=[_commune("Sainte-Colombe", "59512")],
        suggestions={
            "Sainte-Colombe": [
                {
                    "type": "city",
                    "name": "Sainte-Colombe",
                    "insee_code": "00000",
                    "zoneIds": ["-1"],
                },
                {
                    "type": "city",
                    "name": "Sainte-Colombe",
                    "insee_code": "59512",
                    "zoneIds": ["-2"],
                },
            ]
        },
    )

    zone_ids = resolve_zone_ids(
        SearchArea(center=LILLE, radius_km=10.0),
        resolver,  # type: ignore[arg-type]
    )

    assert zone_ids == ["-2"]


def test_resolve_zone_ids_raises_without_communes() -> None:
    resolver = StubResolver(communes=[], suggestions={})

    with pytest.raises(ValueError):
        resolve_zone_ids(
            SearchArea(center=LILLE, radius_km=10.0),
            resolver,  # type: ignore[arg-type]
        )


def test_resolve_zone_ids_raises_when_no_zone_resolves() -> None:
    resolver = StubResolver(
        communes=[_commune("Lille", "59350")],
        suggestions={"Lille": [{"type": "department", "name": "Nord"}]},
    )

    with pytest.raises(ValueError):
        resolve_zone_ids(
            SearchArea(center=LILLE, radius_km=10.0),
            resolver,  # type: ignore[arg-type]
        )
