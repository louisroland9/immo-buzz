"""Tests for the Bien'ici source mapping and request building."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from immo_buzz.db.models import PropertyType
from immo_buzz.scraper.bienici import (
    AD_API_URL,
    API_URL,
    BieniciSource,
    _parse_monthly_rent,
    _parse_property_tax,
)


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
    assert flat.property_tax == 720.0
    assert flat.monthly_rent == 712.0

    parking = listings[2]
    assert parking.property_type is PropertyType.PARKING
    assert parking.surface is None
    assert parking.energy_class is None
    assert parking.property_tax is None
    assert parking.monthly_rent is None


def test_fetch_maps_work_to_do_and_energy_class(
    bienici_payload: dict[str, Any],
) -> None:
    source, _ = make_source(bienici_payload)
    listings = source.fetch(page=0, page_size=100)

    flat, house, parking = listings
    assert flat.works_signalled is False
    assert flat.energy_class == "C"
    assert house.works_signalled is True
    assert house.energy_class == "F"
    assert parking.works_signalled is None


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


class ZoneAwareClient:
    """Client returning one ad per zone, keyed by the requested zone id."""

    def __init__(self, ads_by_zone: dict[str, list[dict[str, Any]]]) -> None:
        self._ads_by_zone = ads_by_zone
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> StubResponse:
        del url
        filters = json.loads((params or {})["filters"])
        self.calls.append(filters)
        zone_ids = filters["zoneIdsByTypes"]["zoneIds"]
        ads: list[dict[str, Any]] = []
        for zone_id in zone_ids:
            ads.extend(self._ads_by_zone.get(zone_id, []))
        return StubResponse({"realEstateAds": ads})

    def close(self) -> None:
        return None


def _ad(source_id: str, zone: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "propertyType": "flat",
        "price": 100_000,
        "surfaceArea": 50,
        "city": zone,
        "postalCode": "59000",
        "description": "",
    }


def test_iter_listings_queries_one_zone_per_request() -> None:
    client = ZoneAwareClient(
        {"-58404": [_ad("a", "Lille")], "-59043": [_ad("b", "Roubaix")]}
    )
    source = BieniciSource(["-58404", "-59043"], client=client, request_delay_s=0.0)  # type: ignore[arg-type]

    listings = source.iter_listings(max_pages=1, page_size=100)

    assert [listing.source_id for listing in listings] == ["a", "b"]
    # One request per zone, each carrying a single zone id.
    assert len(client.calls) == 2
    assert client.calls[0]["zoneIdsByTypes"] == {"zoneIds": ["-58404"]}
    assert client.calls[1]["zoneIdsByTypes"] == {"zoneIds": ["-59043"]}


def test_iter_listings_deduplicates_across_zones() -> None:
    shared = _ad("dup", "Lille")
    client = ZoneAwareClient(
        {"-58404": [shared, _ad("a", "Lille")], "-59043": [shared, _ad("b", "Roubaix")]}
    )
    source = BieniciSource(["-58404", "-59043"], client=client, request_delay_s=0.0)  # type: ignore[arg-type]

    listings = source.iter_listings(max_pages=1, page_size=100)

    assert [listing.source_id for listing in listings] == ["dup", "a", "b"]


def test_iter_listings_paginates_each_zone_independently() -> None:
    client = ZoneAwareClient(
        {"-58404": [_ad("a", "Lille")], "-59043": [_ad("b", "Roubaix")]}
    )
    source = BieniciSource(["-58404", "-59043"], client=client, request_delay_s=0.0)  # type: ignore[arg-type]

    listings = source.iter_listings(max_pages=3, page_size=100)

    # Each zone is walked for up to max_pages before moving to the next one.
    assert len(listings) == 2
    assert client.calls[0]["zoneIdsByTypes"] == {"zoneIds": ["-58404"]}
    assert client.calls[1]["zoneIdsByTypes"] == {"zoneIds": ["-58404"]}
    assert client.calls[2]["zoneIdsByTypes"] == {"zoneIds": ["-58404"]}
    assert client.calls[3]["zoneIdsByTypes"] == {"zoneIds": ["-59043"]}


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Taxe fonciere : 436 EUR.", 436.0),
        ("Taxe foncière: 1 200 €.", 1200.0),
        ("taxe fonciere de 1.200 €", 1200.0),
        ("Taxe fonciere 890,50 euros", 890.5),
        (
            "Taxe"
            + chr(0xA0)
            + "foncière"
            + chr(0xA0)
            + ":"
            + chr(0xA0)
            + "436"
            + chr(0xA0)
            + "€",
            436.0,
        ),
        ("DPE : C.<br>Taxe fonciere : 720 EUR.<br>Chauffage gaz.", 720.0),
    ],
)
def test_parse_property_tax_reads_the_declared_amount(
    description: str, expected: float
) -> None:
    assert _parse_property_tax(description) == expected


@pytest.mark.parametrize(
    "description",
    [
        None,
        "",
        "Bel appartement sans mention fiscale.",
        "Taxe fonciere : 5 EUR",  # implausible low
        "Taxe fonciere : 999 999 EUR",  # implausible high
    ],
)
def test_parse_property_tax_returns_none_when_absent_or_implausible(
    description: str | None,
) -> None:
    assert _parse_property_tax(description) is None


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Loyer : 712€.", 712.0),
        ("Loyer : 712 €.", 712.0),
        ("Loyer actuel : 1 200 €.", 1200.0),
        ("loyers mensuels : 890,50 euros", 890.5),
        ("SPECIAL INVESTISSEUR<br>Loyer : 712€ (date du bail 13/06/2013).", 712.0),
        ("Loyer hors charges : 950 €", 950.0),
        ("Loyer charges comprises : 1.050 €", 1050.0),
    ],
)
def test_parse_monthly_rent_reads_the_declared_amount(
    description: str, expected: float
) -> None:
    assert _parse_monthly_rent(description) == expected


@pytest.mark.parametrize(
    "description",
    [
        None,
        "",
        "Bel appartement sans mention de loyer.",
        "Loyer : 5 €",  # implausible low
        "Loyer : 50 000 €",  # implausible high
    ],
)
def test_parse_monthly_rent_returns_none_when_absent_or_implausible(
    description: str | None,
) -> None:
    assert _parse_monthly_rent(description) is None
