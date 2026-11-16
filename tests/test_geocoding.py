"""Tests for the geocoding helpers (city resolution and radius search)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from immo_buzz.scraper.geocoding import (
    COMMUNES_URL,
    SUGGEST_URL,
    GeoPoint,
    GeoResolver,
    haversine_km,
)

LILLE = GeoPoint(latitude=50.6310, longitude=3.0468)
PARIS = GeoPoint(latitude=48.8566, longitude=2.3522)


class StubResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, Any]]:
        return self._payload


class RouteClient:
    """Client returning a canned payload depending on the requested URL."""

    def __init__(
        self,
        *,
        suggest: list[dict[str, Any]] | None = None,
        communes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._suggest = suggest or []
        self._communes = communes or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> StubResponse:
        self.calls.append((url, params or {}))
        if url == SUGGEST_URL:
            return StubResponse(self._suggest)
        if url == COMMUNES_URL:
            return StubResponse(self._communes)
        raise AssertionError(f"unexpected url {url}")

    def close(self) -> None:
        return None


def make_resolver(client: RouteClient) -> GeoResolver:
    return GeoResolver(client=client, request_delay_s=0.0)  # type: ignore[arg-type]


def test_haversine_km_matches_a_known_distance() -> None:
    # Paris - Lille is about 205 km as the crow flies.
    distance = haversine_km(LILLE, PARIS)
    assert distance == pytest.approx(205.0, abs=3.0)
    assert haversine_km(LILLE, LILLE) == pytest.approx(0.0)


def test_resolve_city_uses_the_bounding_box_center() -> None:
    client = RouteClient(
        suggest=[
            {"type": "department", "name": "Nord"},
            {
                "type": "city",
                "name": "Lille",
                "insee_code": "59350",
                "boundingBox": {
                    "west": 2.967967672557516,
                    "south": 50.600826411633264,
                    "east": 3.125724951852052,
                    "north": 50.661259572323715,
                },
                "zoneIds": ["-58404"],
            },
        ]
    )
    resolver = make_resolver(client)

    center = resolver.resolve_city("Lille")

    assert center.latitude == pytest.approx(50.6310, abs=0.01)
    assert center.longitude == pytest.approx(3.0468, abs=0.01)
    assert client.calls[0][0] == SUGGEST_URL
    assert client.calls[0][1] == {"q": "Lille"}


def test_resolve_city_skips_entries_without_bounding_box() -> None:
    client = RouteClient(
        suggest=[
            {"type": "city", "name": "Broken", "zoneIds": ["-1"]},
            {
                "type": "city",
                "name": "Lille",
                "boundingBox": {"west": 3.0, "south": 50.6, "east": 3.1, "north": 50.7},
            },
        ]
    )

    center = make_resolver(client).resolve_city("Lille")

    assert center.latitude == pytest.approx(50.65)
    assert center.longitude == pytest.approx(3.05)


def test_resolve_city_raises_when_not_found() -> None:
    client = RouteClient(suggest=[{"type": "department", "name": "Nord"}])

    with pytest.raises(ValueError):
        make_resolver(client).resolve_city("inconnue")


def test_resolve_city_raises_on_empty_name() -> None:
    client = RouteClient(suggest=[])

    with pytest.raises(ValueError):
        make_resolver(client).resolve_city("   ")


def test_communes_in_radius_maps_the_center_point() -> None:
    client = RouteClient(
        communes=[
            {
                "nom": "Lille",
                "code": "59350",
                "centre": {"type": "Point", "coordinates": [3.0468, 50.6310]},
            },
            {"nom": "SansCentre", "code": "00000"},
        ]
    )

    communes = make_resolver(client).communes_in_radius(LILLE, 5.0)

    assert [commune.name for commune in communes] == ["Lille"]
    assert communes[0].insee_code == "59350"
    assert communes[0].center.latitude == pytest.approx(50.6310)
    assert communes[0].center.longitude == pytest.approx(3.0468)
    url, params = client.calls[0]
    assert url == COMMUNES_URL
    assert params["radius"] == 5000
    assert params["lat"] == pytest.approx(50.6310)
    assert params["lon"] == pytest.approx(3.0468)


def test_communes_in_radius_rejects_non_positive_radius() -> None:
    client = RouteClient(communes=[])

    with pytest.raises(ValueError):
        make_resolver(client).communes_in_radius(LILLE, 0)


def test_network_error_is_propagated() -> None:
    class FailingClient(RouteClient):
        def get(self, url: str, params: dict[str, Any] | None = None) -> StubResponse:
            del url, params
            raise httpx.ConnectError("network unavailable")

    with pytest.raises(httpx.ConnectError):
        make_resolver(FailingClient()).resolve_city("Lille")
