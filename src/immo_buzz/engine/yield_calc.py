"""Gross yield computation and high-potential filtering."""

from __future__ import annotations

from dataclasses import dataclass

from immo_buzz.config import (
    DEFAULT_MAX_YIELD_PCT,
    DEFAULT_MIN_YIELD_PCT,
    DEFAULT_NOTARY_FEE_RATE,
)
from immo_buzz.db.models import PropertyType
from immo_buzz.engine.condition import detect_condition
from immo_buzz.engine.grids import (
    CONDITION_LABELS,
    CONDITION_RENT_FACTOR,
    WORKS_COST_EUR_PER_M2,
    Condition,
    estimate_monthly_rent,
)
from immo_buzz.scraper.base import RawListing

# Guards against unusable listings.
MIN_SURFACE_M2 = 8.0
PARKING_TYPOLOGIES = (PropertyType.PARKING,)


@dataclass(frozen=True)
class Evaluation:
    """Result of the financial assessment of a single listing."""

    condition: Condition
    condition_label: str
    monthly_rent: float
    annual_rent: float
    notary_fees: float
    works_cost: float
    total_cost: float
    gross_yield_pct: float
    is_high_potential: bool
    rejection_reason: str | None = None


def _estimate_works_cost(condition: Condition, surface: float) -> float:
    if condition in (Condition.GOOD, Condition.REFRESH):
        return 0.0
    return WORKS_COST_EUR_PER_M2[condition] * surface


def evaluate(
    listing: RawListing,
    *,
    min_yield_pct: float = DEFAULT_MIN_YIELD_PCT,
    max_yield_pct: float = DEFAULT_MAX_YIELD_PCT,
    notary_fee_rate: float = DEFAULT_NOTARY_FEE_RATE,
) -> Evaluation:
    """Assess a raw listing and decide whether it is worth storing.

    Total purchase cost is the asking price plus notary fees plus the works
    budget. The gross yield is the annual rent divided by that total cost.
    """
    text = f"{listing.title} {listing.description or ''}"
    condition = detect_condition(text, listing.energy_class)
    factor = CONDITION_RENT_FACTOR[condition]

    if listing.property_type is PropertyType.PARKING:
        surface = 0.0
    else:
        surface = listing.surface or 0.0
        if surface < MIN_SURFACE_M2:
            return _rejected(listing, condition, "surface manquante ou trop faible")

    if listing.price <= 0:
        return _rejected(listing, condition, "prix manquant ou nul")

    monthly_rent = estimate_monthly_rent(listing.property_type, surface) * factor
    annual_rent = monthly_rent * 12
    notary_fees = listing.price * notary_fee_rate
    works_cost = _estimate_works_cost(condition, surface)
    total_cost = listing.price + notary_fees + works_cost
    gross_yield = annual_rent / total_cost * 100

    if gross_yield > max_yield_pct:
        return _rejected(
            listing,
            condition,
            f"rendement invraisemblable ({gross_yield:.1f}%) - donnees suspectes",
            monthly_rent=monthly_rent,
            notary_fees=notary_fees,
            works_cost=works_cost,
            total_cost=total_cost,
            gross_yield=gross_yield,
        )

    return Evaluation(
        condition=condition,
        condition_label=CONDITION_LABELS[condition],
        monthly_rent=monthly_rent,
        annual_rent=annual_rent,
        notary_fees=notary_fees,
        works_cost=works_cost,
        total_cost=total_cost,
        gross_yield_pct=gross_yield,
        is_high_potential=gross_yield >= min_yield_pct,
    )


def _rejected(
    listing: RawListing,
    condition: Condition,
    reason: str,
    *,
    monthly_rent: float = 0.0,
    notary_fees: float = 0.0,
    works_cost: float = 0.0,
    total_cost: float = 0.0,
    gross_yield: float = 0.0,
) -> Evaluation:
    del listing  # only kept for call site symmetry
    return Evaluation(
        condition=condition,
        condition_label=CONDITION_LABELS[condition],
        monthly_rent=monthly_rent,
        annual_rent=monthly_rent * 12,
        notary_fees=notary_fees,
        works_cost=works_cost,
        total_cost=total_cost,
        gross_yield_pct=gross_yield,
        is_high_potential=False,
        rejection_reason=reason,
    )


def is_high_potential(
    evaluation: Evaluation, *, min_yield_pct: float = DEFAULT_MIN_YIELD_PCT
) -> bool:
    """Convenience wrapper kept for callers that only hold an evaluation."""
    return evaluation.is_high_potential and evaluation.gross_yield_pct >= min_yield_pct
