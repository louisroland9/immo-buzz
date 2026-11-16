"""Search areas: a city center plus a radius, expanded to Bien'ici zones.

The scraper paginates one zone at a time, so a geo search is turned into the
list of Bien'ici ``zoneId`` values covering the communes inside the radius.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from immo_buzz.scraper.geocoding import (
    GeoPoint,
    GeoResolver,
    haversine_km,
)

logger = logging.getLogger(__name__)

# Guard rail: a very large radius would resolve hundreds of communes and
# trigger one paginated walk per commune, which is abusive.
MAX_COMMUNES = 200


@dataclass(frozen=True)
class SearchArea:
    """A geographic search: a center point and a radius in kilometers."""

    center: GeoPoint
    radius_km: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.radius_km <= 0:
            raise ValueError("radius must be positive")

    def contains(self, point: GeoPoint) -> bool:
        """Return ``True`` when ``point`` lies within the radius."""
        return haversine_km(self.center, point) <= self.radius_km


def resolve_zone_ids(area: SearchArea, resolver: GeoResolver) -> list[str]:
    """Return the Bien'ici zone ids covering the communes inside ``area``.

    The communes in the radius are listed through ``geo.api.gouv.fr`` and each
    one is mapped to its Bien'ici ``zoneId`` with the suggest endpoint. The
    result is deduplicated and raises :class:`ValueError` when nothing is found.
    """
    communes = resolver.communes_in_radius(area.center, area.radius_km)
    if len(communes) > MAX_COMMUNES:
        logger.warning(
            "area %s covers %s communes, capped at %s",
            area.label or "unnamed",
            len(communes),
            MAX_COMMUNES,
        )
        communes = communes[:MAX_COMMUNES]

    if not communes:
        raise ValueError("no commune found in the search radius")

    zone_ids: list[str] = []
    seen: set[str] = set()
    for commune in communes:
        zone_id = _resolve_zone_id(commune.name, commune.insee_code, resolver)
        if zone_id and zone_id not in seen:
            seen.add(zone_id)
            zone_ids.append(zone_id)

    if not zone_ids:
        raise ValueError("no Bien'ici zone resolved for the search radius")
    return zone_ids


def _resolve_zone_id(name: str, insee_code: str, resolver: GeoResolver) -> str | None:
    """Resolve a commune to a Bien'ici zone id, matched on the INSEE code.

    The suggest endpoint returns homonyms from other departments, so the INSEE
    code is the reliable discriminator. Falls back to the first ``city`` entry
    when no INSEE code matches (older delegated cities have no code).
    """
    suggestions = resolver.suggest(name)

    fallback: str | None = None
    for suggestion in suggestions:
        if str(suggestion.get("type")) != "city":
            continue
        zone_ids = suggestion.get("zoneIds") or []
        if not zone_ids:
            continue
        if str(suggestion.get("insee_code")) == insee_code:
            return str(zone_ids[0])
        if fallback is None:
            fallback = str(zone_ids[0])

    if fallback is None:
        logger.info("no Bien'ici zone found for %s (%s)", name, insee_code)
    return fallback
