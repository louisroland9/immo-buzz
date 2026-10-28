"""Tests for the Bien'ici source mapping and request building."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from immo_buzz.db.models import PropertyType
from immo_buzz.scraper.bienici import AD_API_URL, API_URL, BieniciSource


class StubResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class StubClient:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> StubResponse:
        self.calls.append((url, params or {}))
        return StubResponse(self.payload, self.status_code)

    def close(self) -> None:
        return None


class FailingClient(StubClient):
    def get(self, url: str, params: dict[str, Any] | None = None) -> StubResponse:
        del url, params
        raise httpx.ConnectError("network unavailable")


def make_source(
    payload: dict[str, Any], *, status_code: int = 200
) -> tuple[BieniciSource, StubClient]:
    client = StubClient(payload, status_code=status_code)
    source = BieniciSource(["-58404"], client=client, request_delay_s=0.0)  # type: ignore[arg-type]
    return source, client


def test_fetch_maps_listings_and_skips_unknown_types(
    bienici_payload: dict[str, Any],
) -> None:
    source, client = make_source(bienici_payload)
    listings = source.fetch(page=0, page_size=100)

    assert len(listings) == 3
    assert client.calls[0][0] == API_URL

    flat = listings[0]
    assert flat.property_type is PropertyType.FLAT
    assert flat.source == "bienici"
    assert flat.source_id == "era-1565943"
    assert flat.price == 159_430
    assert flat.surface == 47.26
    assert flat.district == "Lille - Fives"
    assert flat.postal_code == "59000"
    assert flat.url == "https://www.bienici.com/annonce/era-1565943"
    assert flat.title == "Appartement T2 47 m2 Lille"
    assert flat.published_at is not None

    parking = listings[2]
    assert parking.property_type is PropertyType.PARKING
    assert parking.surface is None
    assert parking.energy_class is None


def test_is_available_uses_the_ad_detail_api(bienici_payload: dict[str, Any]) -> None:
    source, client = make_source(bienici_payload)

    assert source.is_available("era-1565943") is True
    assert client.calls == [(AD_API_URL, {"id": "era-1565943"})]


@pytest.mark.parametrize("status_code", [404, 410])
def test_is_available_detects_removed_ads(
    bienici_payload: dict[str, Any], status_code: int
) -> None:
    source, _ = make_source(bienici_payload, status_code=status_code)

    assert source.is_available("era-missing") is False


def test_is_available_returns_unknown_on_server_error(
    bienici_payload: dict[str, Any],
) -> None:
    source, _ = make_source(bienici_payload, status_code=503)

    assert source.is_available("era-1") is None


def test_is_available_returns_unknown_on_network_error(
    bienici_payload: dict[str, Any],
) -> None:
    client = FailingClient(bienici_payload)
    source = BieniciSource(["-58404"], client=client, request_delay_s=0.0)  # type: ignore[arg-type]

    assert source.is_available("era-1") is None


def test_filters_encode_types_zones_and_offset(
    bienici_payload: dict[str, Any],
) -> None:
    source, client = make_source(bienici_payload)
    source.fetch(page=2, page_size=100)

    filters = json.loads(client.calls[0][1]["filters"])
    assert filters["from"] == 200
    assert filters["size"] == 100
    assert filters["filterType"] == "buy"
    assert filters["zoneIdsByTypes"] == {"zoneIds": ["-58404"]}
    assert set(filters["propertyType"]) == {"flat", "house", "building", "parking"}


def test_page_size_is_capped_at_one_hundred(
    bienici_payload: dict[str, Any],
) -> None:
    source, client = make_source(bienici_payload)
    source.fetch(page=0, page_size=500)

    filters = json.loads(client.calls[0][1]["filters"])
    assert filters["size"] == 100


def test_offset_guard_rail_stops_requests(bienici_payload: dict[str, Any]) -> None:
    source, client = make_source(bienici_payload)
    assert source.fetch(page=60, page_size=100) == []
    assert client.calls == []


def test_empty_zone_list_is_rejected() -> None:
    with pytest.raises(ValueError):
        BieniciSource([])
