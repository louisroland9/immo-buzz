"""Financial engine: rent grids, works estimation and yield filtering."""

from immo_buzz.engine.grids import (
    COMMUNE_RENT_GRID,
    CONDITION_LABELS,
    CONDITION_RENT_FACTOR,
    CONDO_FEES_EUR_PER_M2_MONTH,
    DEFAULT_PROPERTY_TAX_RATE,
    METROPOLE_FALLBACK_RENT,
    PROPERTY_TAX_RATE_BY_COMMUNE,
    RENT_TIER_UPPER_BOUNDS,
    WORKS_COST_EUR_PER_M2,
    Condition,
    condo_fees_eur_per_m2_month,
    default_rent_per_m2,
    estimate_monthly_rent,
    normalize_commune,
    property_tax_rate,
)
from immo_buzz.engine.yield_calc import Evaluation, evaluate, is_high_potential

__all__ = [
    "COMMUNE_RENT_GRID",
    "CONDO_FEES_EUR_PER_M2_MONTH",
    "CONDITION_LABELS",
    "CONDITION_RENT_FACTOR",
    "DEFAULT_PROPERTY_TAX_RATE",
    "METROPOLE_FALLBACK_RENT",
    "PROPERTY_TAX_RATE_BY_COMMUNE",
    "RENT_TIER_UPPER_BOUNDS",
    "WORKS_COST_EUR_PER_M2",
    "Condition",
    "Evaluation",
    "condo_fees_eur_per_m2_month",
    "default_rent_per_m2",
    "estimate_monthly_rent",
    "evaluate",
    "is_high_potential",
    "normalize_commune",
    "property_tax_rate",
]
