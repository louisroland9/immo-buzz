"""Search zones: communes of the Lille European Metropolis.

Each entry maps a commune to its Bien'ici ``zoneId``. The identifiers were
resolved through ``https://res.bienici.com/suggest.json`` and can be extended
to cover the whole 95 communes of the MEL.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Zone:
    """A search area."""

    name: str
    insee_code: str
    bienici_zone_id: str


LILLE_METROPOLE_ZONES: tuple[Zone, ...] = (
    Zone("Lille", "59350", "-58404"),
    Zone("Roubaix", "59512", "-59043"),
    Zone("Tourcoing", "59599", "-59551"),
    Zone("Villeneuve-d'Ascq", "59009", "-58213"),
    Zone("Lambersart", "59328", "-58897"),
    Zone("Marcq-en-Baroeul", "59378", "-58686"),
    Zone("Mons-en-Baroeul", "59410", "-58583"),
    Zone("Loos", "59360", "-58402"),
    Zone("Faches-Thumesnil", "59220", "-58173"),
    Zone("Wattignies", "59648", "-58169"),
    Zone("Ronchin", "59507", "-58207"),
    Zone("Hem", "59299", "-58644"),
    Zone("Wasquehal", "59646", "-59041"),
    Zone("Croix", "59163", "-58677"),
    Zone("Armentieres", "59017", "-68000"),
)


def zones_by_name(names: list[str] | None = None) -> list[Zone]:
    """Return zones filtered by name, case insensitively."""
    if not names:
        return list(LILLE_METROPOLE_ZONES)
    wanted = {name.strip().lower() for name in names}
    selected = [zone for zone in LILLE_METROPOLE_ZONES if zone.name.lower() in wanted]
    return selected or list(LILLE_METROPOLE_ZONES)
