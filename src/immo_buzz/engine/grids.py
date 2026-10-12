"""Editable financial grids for the Lille metropolitan area.

Every value in this module is a hypothesis that must be calibrated against
local market data (DVF, ANIL rent observatory, agency feedback). The numbers
below are conservative starting points for the MVP.
"""

from __future__ import annotations

from enum import StrEnum

from immo_buzz.db.models import PropertyType


class Condition(StrEnum):
    """Renovation intensity inferred from the listing text and DPE."""

    GOOD = "bon"
    REFRESH = "rafraichissement"
    RENOVATION = "renovation"
    HEAVY = "lourd"


CONDITION_LABELS: dict[Condition, str] = {
    Condition.GOOD: "Bon état apparent",
    Condition.REFRESH: "Rafraîchissement (peintures, sols)",
    Condition.RENOVATION: "Rénovation (cuisine, salle d'eau, électricité)",
    Condition.HEAVY: "Rénovation lourde (structure, toiture, réseaux)",
}

# Works budget in euros per square metre, by renovation intensity.
WORKS_COST_EUR_PER_M2: dict[Condition, float] = {
    Condition.GOOD: 0.0,
    Condition.REFRESH: 150.0,
    Condition.RENOVATION: 450.0,
    Condition.HEAVY: 800.0,
}

# Theoretical rent expressed in euros per square metre per month.
# Tier boundaries in square metres: tier 0 is the smallest.
RENT_TIER_UPPER_BOUNDS: tuple[float, float] = (30.0, 60.0)

RENT_GRID_EUR_PER_M2: dict[PropertyType, tuple[float, float, float]] = {
    PropertyType.FLAT: (17.0, 13.5, 11.5),
    PropertyType.HOUSE: (15.0, 12.5, 11.0),
    PropertyType.BUILDING: (13.5, 11.5, 10.0),
    PropertyType.PARKING: (0.0, 0.0, 0.0),
}

# Representative surface used when the tier is open ended.
RENT_GRID_MIDPOINTS: tuple[float, float, float] = (22.0, 45.0, 80.0)

# Monthly rent for a single parking spot: surface data is unreliable.
PARKING_MONTHLY_RENT: float = 70.0

# Slight discount applied to theoretical rents when extra comfort exists.
CONDITION_RENT_FACTOR: dict[Condition, float] = {
    Condition.GOOD: 1.0,
    Condition.REFRESH: 0.98,
    Condition.RENOVATION: 0.95,
    Condition.HEAVY: 0.92,
}


def _tier_index(surface: float) -> int:
    small, medium = RENT_TIER_UPPER_BOUNDS
    if surface <= small:
        return 0
    if surface <= medium:
        return 1
    return 2


def default_rent_per_m2(property_type: PropertyType, surface: float) -> float:
    """Return the grid rent per square metre for a typology and a surface."""
    if property_type is PropertyType.PARKING:
        return PARKING_MONTHLY_RENT
    tiers = RENT_GRID_EUR_PER_M2[property_type]
    return tiers[_tier_index(surface)]


def estimate_monthly_rent(property_type: PropertyType, surface: float) -> float:
    """Compute a theoretical monthly rent for a listing.

    Parkings use a flat monthly rate, other typologies use the grid above.
    """
    if property_type is PropertyType.PARKING:
        return PARKING_MONTHLY_RENT
    per_m2 = default_rent_per_m2(property_type, surface)
    return per_m2 * surface
