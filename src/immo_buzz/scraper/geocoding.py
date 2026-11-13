"""Geographic helpers used to resolve a city and a search radius.

Two public, keyless services are used:

* ``res.bienici.com/suggest.json`` resolves a city name into a center point and
  the Bien'ici zone identifiers used by the listing endpoint.
* ``geo.api.gouv.fr`` (Etalab) lists the French communes whose center falls
  inside a radius, which is the ground truth for a geo search.

The endpoints are undocumented and may change without notice: keep the mapping
isolated in this module.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import httpx

from immo_buzz.config import DEFAULT_REQUEST_DELAY_S

logger = logging.getLogger(__name__)

SUGGEST_URL = "https://res.bienici.com/suggest.json"
COMMUNES_URL = "https://geo.api.gouv.fr/communes"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Mean Earth radius, used by the haversine formula.
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class GeoPoint:
    """A WGS84 coordinate."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class Commune:
    """A French commune with its center point."""

    name: str
    insee_code: str
    center: GeoPoint


def haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    """Return the great-circle distance between two points, in kilometers."""
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _build_client() -> httpx.Client:
    transport = httpx.HTTPTransport(retries=3)
    return httpx.Client(
        timeout=30.0,
        transport=transport,
        headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )


class GeoResolver:
    """Resolve a city name and the communes around a point."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        request_delay_s: float = DEFAULT_REQUEST_DELAY_S,
    ) -> None:
        self._delay = request_delay_s
        self._client = client or _build_client()

    def close(self) -> None:
        self._client.close()

    def _sleep(self) -> None:
        if self._delay > 0:
            import time

            time.sleep(self._delay)

    def suggest(self, query: str) -> list[dict[str, Any]]:
        """Return the raw suggest candidates for a free-text query."""
        text = query.strip()
        if not text:
            return []
        response = self._client.get(SUGGEST_URL, params={"q": text})
        response.raise_for_status()
        self._sleep()
        return response.json()

    def resolve_city(self, name: str) -> GeoPoint:
        """Resolve a city name to its center point.

        The suggest endpoint returns several candidates ordered by relevance,
        including homonyms from other departments. The first ``city`` entry is
        kept, which is the most populated (hence the best scored) match.
        Raises :class:`ValueError` when the city cannot be resolved.
        """
        suggestions = self.suggest(name)
        if not name.strip():
            raise ValueError("a city name is required")

        for suggestion in suggestions:
            if str(suggestion.get("type")) != "city":
                continue
            point = _bounding_box_center(suggestion.get("boundingBox"))
            if point is not None:
                return point

        raise ValueError(f"city not found: {name!r}")

    def communes_in_radius(self, center: GeoPoint, radius_km: float) -> list[Commune]:
        """Return the communes whose center falls within ``radius_km``."""
        if radius_km <= 0:
            raise ValueError("radius must be positive")

        response = self._client.get(
            COMMUNES_URL,
            params={
                "lat": center.latitude,
                "lon": center.longitude,
                "radius": int(radius_km * 1000),
                "fields": "nom,code,centre",
                "limit": 1000,
            },
        )
        response.raise_for_status()
        self._sleep()
        payload: list[dict[str, Any]] = response.json()

        communes: list[Commune] = []
        for item in payload:
            point = _center_from_commune(item.get("centre"))
            insee_code = item.get("code")
            if point is None or not insee_code:
                continue
            communes.append(
                Commune(
                    name=str(item.get("nom") or "").strip(),
                    insee_code=str(insee_code),
                    center=point,
                )
            )
        return communes


def _bounding_box_center(bounding_box: Any) -> GeoPoint | None:
    if not isinstance(bounding_box, dict):
        return None
    west = _as_float(bounding_box.get("west"))
    south = _as_float(bounding_box.get("south"))
    east = _as_float(bounding_box.get("east"))
    north = _as_float(bounding_box.get("north"))
    if None in (west, south, east, north):
        return None
    return GeoPoint(latitude=(south + north) / 2, longitude=(west + east) / 2)


def _center_from_commune(center: Any) -> GeoPoint | None:
    if not isinstance(center, dict):
        return None
    coordinates = center.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
        return None
    longitude = _as_float(coordinates[0])
    latitude = _as_float(coordinates[1])
    if longitude is None or latitude is None:
        return None
    return GeoPoint(latitude=latitude, longitude=longitude)


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
