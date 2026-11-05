"""Editable financial grids for the Lille metropolitan area.

Every value in this module is a hypothesis that must be calibrated against
local market data (DVF, ANIL rent observatory, agency feedback). The numbers
below are conservative starting points for the MVP.

References used to build the grids:

- Rent levels: ANIL / DGALN "Carte des loyers" 2023 (indicateurs de loyers
  d'annonce, charges comprises), crossed with the local OLL (Observatoire
  Local des Loyers) of the Lille European Metropolis. Rents are expressed in
  euros per square metre per month, split by surface tier and typology.
- Property tax: effective rate applied to the *purchase price* (DGFiP local
  rates combined with the cadastral value ratio observed on the field).
  It is a simplification of the real "valeur locative cadastrale" mechanism.
- Condominium fees: non recoverable share (syndic fees, building insurance,
  works provision) of about 1.8 euros per square metre per month for flats.
"""

from __future__ import annotations

import unicodedata
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

# Renovation works budget, split into a fixed cost per dwelling (kitchen,
# bathroom, electrical panel...) and a variable cost per square metre (floors,
# paint, insulation...). Order of magnitudes inspired by FNAIM / ANIL renovation
# cost guides for the Lille area:
#   - rafraichissement : simple refresh, mostly paint and floor
#   - renovation : kitchen, bathroom, electricity
#   - lourd : structure, roof, networks
# GOOD has no works at all, REFRESH keeps a real (non zero) budget.
WORKS_FIXED_COST_EUR: dict[Condition, float] = {
    Condition.GOOD: 0.0,
    Condition.REFRESH: 1_000.0,
    Condition.RENOVATION: 6_000.0,
    Condition.HEAVY: 12_000.0,
}

WORKS_COST_EUR_PER_M2: dict[Condition, float] = {
    Condition.GOOD: 0.0,
    Condition.REFRESH: 100.0,
    Condition.RENOVATION: 400.0,
    Condition.HEAVY: 700.0,
}

# Average works intensity applied to a verified energy renovation (DPE F/G)
# that the listing text does not already describe as a heavy renovation.
WORKS_ENERGY_PREMIUM_EUR_PER_M2: float = 120.0

# Safety rails: the works budget cannot exceed this share of the asking price,
# and its per square metre value is capped to avoid runaway estimates on large
# or mistyped surfaces.
WORKS_COST_MAX_RATIO_OF_PRICE: float = 0.6
WORKS_COST_MAX_EUR_PER_M2: float = 1_200.0

# Monthly rent for a single parking spot: surface data is unreliable.
PARKING_MONTHLY_RENT: float = 70.0

# Tier boundaries in square metres: tier 0 is the smallest, tier 2 the largest.
RENT_TIER_UPPER_BOUNDS: tuple[float, float] = (30.0, 60.0)

# Theoretical rent expressed in euros per square metre per month, by typology
# and surface tier. These metro wide values are used when the commune is not
# part of COMMUNE_RENT_GRID below.
METROPOLE_FALLBACK_RENT: dict[PropertyType, tuple[float, float, float]] = {
    PropertyType.FLAT: (16.0, 12.5, 10.5),
    PropertyType.HOUSE: (14.0, 11.5, 10.0),
    PropertyType.BUILDING: (12.5, 10.5, 9.0),
    PropertyType.PARKING: (0.0, 0.0, 0.0),
}

# Rent grid per commune (normalized name -> rent per tier), split by typology.
# Values derived from the ANIL 2023 rent map and the Lille metropolis OLL.
COMMUNE_RENT_GRID: dict[str, dict[PropertyType, tuple[float, float, float]]] = {
    "lille": {
        PropertyType.FLAT: (18.0, 14.5, 12.5),
        PropertyType.HOUSE: (16.0, 13.5, 12.0),
        PropertyType.BUILDING: (14.5, 12.0, 10.5),
    },
    "lomme": {
        PropertyType.FLAT: (14.5, 11.5, 10.0),
        PropertyType.HOUSE: (13.0, 11.0, 9.5),
        PropertyType.BUILDING: (12.0, 10.0, 9.0),
    },
    "villeneuve d ascq": {
        PropertyType.FLAT: (16.5, 13.0, 11.5),
        PropertyType.HOUSE: (15.0, 12.5, 11.0),
        PropertyType.BUILDING: (13.5, 11.5, 10.0),
    },
    "roubaix": {
        PropertyType.FLAT: (12.5, 9.8, 8.5),
        PropertyType.HOUSE: (11.5, 9.5, 8.5),
        PropertyType.BUILDING: (10.5, 9.0, 8.0),
    },
    "tourcoing": {
        PropertyType.FLAT: (13.0, 10.2, 9.0),
        PropertyType.HOUSE: (12.0, 10.0, 9.0),
        PropertyType.BUILDING: (11.0, 9.5, 8.5),
    },
    "lambersart": {
        PropertyType.FLAT: (16.0, 13.0, 11.5),
        PropertyType.HOUSE: (15.0, 12.5, 11.0),
        PropertyType.BUILDING: (13.5, 11.5, 10.0),
    },
    "marcq en baroeul": {
        PropertyType.FLAT: (16.5, 13.5, 11.5),
        PropertyType.HOUSE: (15.5, 13.0, 11.5),
        PropertyType.BUILDING: (14.0, 12.0, 10.5),
    },
    "mons en baroeul": {
        PropertyType.FLAT: (15.0, 12.0, 10.5),
        PropertyType.HOUSE: (14.0, 11.5, 10.0),
        PropertyType.BUILDING: (12.5, 10.5, 9.5),
    },
    "loos": {
        PropertyType.FLAT: (14.5, 11.5, 10.0),
        PropertyType.HOUSE: (13.5, 11.0, 9.5),
        PropertyType.BUILDING: (12.0, 10.0, 9.0),
    },
    "faches thumesnil": {
        PropertyType.FLAT: (14.0, 11.2, 9.8),
        PropertyType.HOUSE: (13.0, 11.0, 9.5),
        PropertyType.BUILDING: (12.0, 10.0, 9.0),
    },
    "wattignies": {
        PropertyType.FLAT: (13.5, 11.0, 9.5),
        PropertyType.HOUSE: (12.5, 10.5, 9.2),
        PropertyType.BUILDING: (11.5, 9.8, 8.8),
    },
    "ronchin": {
        PropertyType.FLAT: (13.8, 11.0, 9.5),
        PropertyType.HOUSE: (12.8, 10.5, 9.2),
        PropertyType.BUILDING: (11.5, 9.8, 8.8),
    },
    "hem": {
        PropertyType.FLAT: (13.5, 10.8, 9.5),
        PropertyType.HOUSE: (12.5, 10.5, 9.2),
        PropertyType.BUILDING: (11.5, 9.8, 8.8),
    },
    "wasquehal": {
        PropertyType.FLAT: (15.0, 12.0, 10.5),
        PropertyType.HOUSE: (14.0, 11.5, 10.0),
        PropertyType.BUILDING: (12.5, 10.5, 9.5),
    },
    "croix": {
        PropertyType.FLAT: (13.5, 10.8, 9.5),
        PropertyType.HOUSE: (12.5, 10.5, 9.2),
        PropertyType.BUILDING: (11.5, 9.8, 8.8),
    },
    "armentieres": {
        PropertyType.FLAT: (13.0, 10.5, 9.2),
        PropertyType.HOUSE: (12.0, 10.0, 9.0),
        PropertyType.BUILDING: (11.0, 9.5, 8.5),
    },
}

# Effective property tax rate, expressed as a fraction of the purchase price.
# Derived from DGFiP communal rates and the observed ratio between the
# cadastral rental value (rebased) and market prices.
DEFAULT_PROPERTY_TAX_RATE: float = 0.0085

PROPERTY_TAX_RATE_BY_COMMUNE: dict[str, float] = {
    "lille": 0.0080,
    "lomme": 0.0085,
    "villeneuve d ascq": 0.0080,
    "roubaix": 0.0090,
    "tourcoing": 0.0095,
    "lambersart": 0.0080,
    "marcq en baroeul": 0.0075,
    "mons en baroeul": 0.0080,
    "loos": 0.0082,
    "faches thumesnil": 0.0085,
    "wattignies": 0.0085,
    "ronchin": 0.0085,
    "hem": 0.0088,
    "wasquehal": 0.0080,
    "croix": 0.0088,
    "armentieres": 0.0090,
}

# Non recoverable condominium fees in euros per square metre per month.
# Applied to flats and buildings only (houses and parkings have none).
CONDO_FEES_EUR_PER_M2_MONTH: float = 1.8

# Slight discount applied to theoretical rents when extra comfort exists.
CONDITION_RENT_FACTOR: dict[Condition, float] = {
    Condition.GOOD: 1.0,
    Condition.REFRESH: 0.98,
    Condition.RENOVATION: 0.95,
    Condition.HEAVY: 0.92,
}


def normalize_commune(city: str | None) -> str:
    """Lowercase, strip accents and collapse separators of a commune name."""
    if not city:
        return ""
    decomposed = unicodedata.normalize("NFKD", city.lower())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    cleaned = "".join(char if char.isalnum() else " " for char in without_accents)
    return " ".join(cleaned.split())


def _tier_index(surface: float) -> int:
    small, medium = RENT_TIER_UPPER_BOUNDS
    if surface <= small:
        return 0
    if surface <= medium:
        return 1
    return 2


def rent_grid_for(city: str | None) -> dict[PropertyType, tuple[float, float, float]]:
    """Return the rent grid to use for a commune, falling back to the metro."""
    return COMMUNE_RENT_GRID.get(normalize_commune(city), METROPOLE_FALLBACK_RENT)


def default_rent_per_m2(
    property_type: PropertyType, surface: float, city: str | None = None
) -> float:
    """Return the grid rent per square metre for a typology, surface and city."""
    if property_type is PropertyType.PARKING:
        return PARKING_MONTHLY_RENT
    tiers = rent_grid_for(city).get(
        property_type, METROPOLE_FALLBACK_RENT[property_type]
    )
    return tiers[_tier_index(surface)]


def estimate_monthly_rent(
    property_type: PropertyType, surface: float, city: str | None = None
) -> float:
    """Compute a theoretical monthly rent for a listing.

    Parkings use a flat monthly rate, other typologies use the commune rent
    grid (or the metro fallback when the commune is unknown).
    """
    if property_type is PropertyType.PARKING:
        return PARKING_MONTHLY_RENT
    per_m2 = default_rent_per_m2(property_type, surface, city)
    return per_m2 * surface


def property_tax_rate(city: str | None) -> float:
    """Return the effective property tax rate (fraction of the price)."""
    return PROPERTY_TAX_RATE_BY_COMMUNE.get(
        normalize_commune(city), DEFAULT_PROPERTY_TAX_RATE
    )


def condo_fees_eur_per_m2_month(property_type: PropertyType) -> float:
    """Return the non recoverable condominium fees for a typology."""
    if property_type in (PropertyType.FLAT, PropertyType.BUILDING):
        return CONDO_FEES_EUR_PER_M2_MONTH
    return 0.0


POOR_ENERGY_CLASSES: frozenset[str] = frozenset({"F", "G"})


def estimate_works_cost(
    condition: Condition,
    surface: float,
    *,
    energy_class: str | None = None,
    price: float = 0.0,
) -> float:
    """Estimate the renovation works budget of a listing.

    The budget combines a fixed cost per dwelling and a variable cost per
    square metre, both driven by the renovation intensity. A poor energy label
    adds an energy renovation premium unless the condition is already ``HEAVY``
    (the worst case already covers it). The result is capped by a per square
    metre ceiling and by a share of the asking price to keep estimates sane.
    """
    if condition is Condition.GOOD:
        return 0.0

    budget = (
        WORKS_FIXED_COST_EUR[condition] + WORKS_COST_EUR_PER_M2[condition] * surface
    )

    label = (energy_class or "").strip().upper()
    if label in POOR_ENERGY_CLASSES and condition is not Condition.HEAVY:
        budget += WORKS_ENERGY_PREMIUM_EUR_PER_M2 * surface

    if surface > 0:
        budget = min(budget, WORKS_COST_MAX_EUR_PER_M2 * surface)
    if price > 0:
        budget = min(budget, price * WORKS_COST_MAX_RATIO_OF_PRICE)
    return budget
