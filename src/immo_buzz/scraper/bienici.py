"""Bien'ici listing source.

Bien'ici exposes the JSON endpoint ``/realEstateAds.json`` without any
authentication. Returned fields are mapped to the internal ``RawListing``
contract so the financial engine stays source agnostic.

The endpoint is undocumented and may change without notice: keep the mapping
isolated in this module.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from immo_buzz.config import DEFAULT_PAGE_SIZE, DEFAULT_REQUEST_DELAY_S
from immo_buzz.db.models import PropertyType
from immo_buzz.scraper.base import RawListing

logger = logging.getLogger(__name__)

API_URL = "https://www.bienici.com/realEstateAds.json"
AD_API_URL = "https://www.bienici.com/realEstateAd.json"
AD_BASE_URL = "https://www.bienici.com/annonce"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Bien'ici typology mapped to the internal typology.
PROPERTY_TYPE_MAPPING: dict[str, PropertyType] = {
    "flat": PropertyType.FLAT,
    "apartment": PropertyType.FLAT,
    "house": PropertyType.HOUSE,
    "building": PropertyType.BUILDING,
    "parking": PropertyType.PARKING,
    "garage": PropertyType.PARKING,
    "box": PropertyType.PARKING,
}

# Labels used when the source leaves the title empty.
PROPERTY_TYPE_LABELS: dict[PropertyType, str] = {
    PropertyType.FLAT: "Appartement",
    PropertyType.HOUSE: "Maison",
    PropertyType.BUILDING: "Immeuble",
    PropertyType.PARKING: "Parking",
}

# Guard rail: the API refuses requests beyond this offset.
MAX_OFFSET = 4900


class BieniciSource:
    """Fetch raw listings for the Lille metropolitan area."""

    name = "bienici"

    def __init__(
        self,
        zone_ids: list[str],
        *,
        property_types: tuple[PropertyType, ...] = tuple(PropertyType),
        client: httpx.Client | None = None,
        request_delay_s: float = DEFAULT_REQUEST_DELAY_S,
    ) -> None:
        if not zone_ids:
            raise ValueError("at least one zone id is required")
        self._zone_ids = zone_ids
        self._property_types = property_types
        self._delay = request_delay_s
        self._client = client or self._build_client()

    @staticmethod
    def _build_client() -> httpx.Client:
        transport = httpx.HTTPTransport(retries=3)
        return httpx.Client(
            timeout=30.0,
            transport=transport,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def _build_filters(self, page: int, page_size: int) -> str:
        payload = {
            "size": min(page_size, DEFAULT_PAGE_SIZE),
            "from": max(page, 0) * page_size,
            "filterType": "buy",
            "propertyType": [pt.value for pt in self._property_types],
            "zoneIdsByTypes": {"zoneIds": list(self._zone_ids)},
            "sortBy": "publicationDate",
            "sortOrder": "desc",
            "onTheMarket": [True],
        }
        return json.dumps(payload, separators=(",", ":"))

    def fetch(
        self, *, page: int = 0, page_size: int = DEFAULT_PAGE_SIZE
    ) -> list[RawListing]:
        """Return the raw listings of a single page."""
        offset = max(page, 0) * page_size
        if offset > MAX_OFFSET:
            logger.info("bienici: offset %s beyond guard rail, stopping", offset)
            return []

        response = self._client.get(
            API_URL,
            params={"filters": self._build_filters(page, page_size)},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        ads = payload.get("realEstateAds") or []

        if self._delay > 0:
            time.sleep(self._delay)

        return [listing for ad in ads if (listing := self._map_ad(ad)) is not None]

    def is_available(self, source_id: str) -> bool | None:
        """Check whether an ad still exists on Bien'ici.

        The public listing page is a single-page application that always
        answers ``200``, even for unknown ids. Its detail API does return
        ``404`` for removed ads, so it is the reliable availability signal.
        """
        try:
            response = self._client.get(AD_API_URL, params={"id": source_id})
        except httpx.HTTPError as exc:
            logger.warning(
                "bienici: availability check failed for %s: %s", source_id, exc
            )
            return None

        if self._delay > 0:
            time.sleep(self._delay)

        if response.status_code in (404, 410):
            return False
        if 200 <= response.status_code < 300:
            return True

        logger.warning(
            "bienici: unexpected status %s while checking %s",
            response.status_code,
            source_id,
        )
        return None

    def _map_ad(self, ad: dict[str, Any]) -> RawListing | None:
        raw_type = str(ad.get("propertyType", "")).lower()
        property_type = PROPERTY_TYPE_MAPPING.get(raw_type)
        price = _as_float(ad.get("price"))
        if property_type is None or price is None:
            return None

        surface = _as_float(ad.get("surfaceArea"))
        district = ad.get("district") or {}
        postal_code = ad.get("postalCode") or district.get("postal_code")
        city = _as_text(ad.get("city")) or _as_text(district.get("libelle")) or ""
        district_name = _as_text(ad.get("displayDistrictName")) or _as_text(
            district.get("name")
        )

        if surface is not None:
            surface = round(surface, 2)

        return RawListing(
            source=self.name,
            source_id=str(ad.get("id")),
            title=_build_title(ad, property_type, city),
            property_type=property_type,
            price=price,
            surface=surface,
            city=city,
            postal_code=str(postal_code) if postal_code else None,
            district=district_name,
            url=f"{AD_BASE_URL}/{ad.get('id')}",
            description=ad.get("description") or None,
            rooms=_as_int(ad.get("roomsQuantity")),
            energy_class=_as_energy_class(ad.get("energyClassification")),
            published_at=_parse_datetime(ad.get("publicationDate")),
        )


def _build_title(ad: dict[str, Any], property_type: PropertyType, city: str) -> str:
    title = (ad.get("title") or "").strip()
    if title:
        return title
    label = PROPERTY_TYPE_LABELS[property_type]
    rooms = _as_int(ad.get("roomsQuantity"))
    surface = _as_float(ad.get("surfaceArea"))
    parts = [label]
    if rooms:
        parts.append(f"T{rooms}")
    if surface:
        parts.append(f"{surface:.0f} m2")
    if city:
        parts.append(city)
    return " ".join(parts)


def _as_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def _as_energy_class(value: Any) -> str | None:
    if not value:
        return None
    return str(value).strip().upper()


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
