"""Gross yield computation and high-potential filtering."""

from __future__ import annotations

from dataclasses import dataclass

from immo_buzz.config import (
    DEFAULT_MANAGEMENT_FEE_RATE,
    DEFAULT_MAX_YIELD_PCT,
    DEFAULT_MIN_PLAUSIBLE_PRICE,
    DEFAULT_MIN_PRICE_PER_M2,
    DEFAULT_MIN_YIELD_PCT,
    DEFAULT_MORTGAGE_ANNUAL_RATE,
    DEFAULT_NOTARY_FEE_RATE,
    DEFAULT_VACANCY_RATE,
)
from immo_buzz.db.models import PropertyType
from immo_buzz.engine.condition import detect_condition
from immo_buzz.engine.exclusion import detect_exclusion
from immo_buzz.engine.grids import (
    CONDITION_LABELS,
    CONDITION_RENT_FACTOR,
    Condition,
    condo_fees_eur_per_m2_month,
    estimate_monthly_rent,
    estimate_works_cost,
    property_tax_rate,
)
from immo_buzz.scraper.base import RawListing

# Guards against unusable listings.
MIN_SURFACE_M2 = 8.0
PARKING_TYPOLOGIES = (PropertyType.PARKING,)


@dataclass(frozen=True)
class Evaluation:
    """Result of the financial assessment of a single listing.

    Acquisition cost is the price plus notary fees plus the works budget.
    ``annual_rent`` is the gross rental income, while the operating costs
    (condominium fees, property tax, management fees and vacancy) are
    subtracted to derive the net income.
    """

    condition: Condition
    condition_label: str
    monthly_rent: float
    estimated_monthly_rent: float
    annual_rent: float
    notary_fees: float
    works_cost: float
    total_cost: float
    condo_fees_annual: float
    property_tax: float
    estimated_property_tax: float
    management_fees: float
    vacancy_cost: float
    net_annual_income: float
    gross_yield_pct: float
    net_yield_pct: float
    cash_flow_monthly: float
    is_high_potential: bool
    rejection_reason: str | None = None


def _estimate_monthly_mortgage(price: float) -> float:
    """Proxy of the monthly loan payment used for the cash flow estimate.

    A fixed rate, full financing and a constant monthly payment model keeps
    the cash flow a transparent, editable hypothesis.
    """
    return price * DEFAULT_MORTGAGE_ANNUAL_RATE / 12


def evaluate(
    listing: RawListing,
    *,
    min_yield_pct: float = DEFAULT_MIN_YIELD_PCT,
    max_yield_pct: float = DEFAULT_MAX_YIELD_PCT,
    min_plausible_price: float = DEFAULT_MIN_PLAUSIBLE_PRICE,
    min_price_per_m2: float = DEFAULT_MIN_PRICE_PER_M2,
    notary_fee_rate: float = DEFAULT_NOTARY_FEE_RATE,
    management_fee_rate: float = DEFAULT_MANAGEMENT_FEE_RATE,
    vacancy_rate: float = DEFAULT_VACANCY_RATE,
) -> Evaluation:
    """Assess a raw listing and decide whether it is worth storing.

    Total purchase cost is the asking price plus notary fees plus the works
    budget. The gross yield is the annual rent divided by that total cost;
    the net yield subtracts the operating costs (condo fees, property tax,
    management fees and vacancy). The property tax uses the amount declared in
    the listing when available, otherwise a commune-rate estimate. The monthly
    rent uses the current rent declared in the listing when available,
    otherwise a grid estimate. Filtering stays based on the gross yield, after
    rejecting fake high yields: viager / split ownership sales and implausible
    prices (below a floor, or below a floor per square metre).
    """
    text = f"{listing.title} {listing.description or ''}"
    condition = detect_condition(text, listing.energy_class, listing.works_signalled)
    factor = CONDITION_RENT_FACTOR[condition]

    exclusion = detect_exclusion(text)
    if exclusion is not None:
        return _rejected(listing, condition, exclusion)

    if listing.property_type is PropertyType.PARKING:
        surface = 0.0
    else:
        surface = listing.surface or 0.0
        if surface < MIN_SURFACE_M2:
            return _rejected(listing, condition, "surface manquante ou trop faible")

    if listing.price <= 0:
        return _rejected(listing, condition, "prix manquant ou nul")

    if listing.price < min_plausible_price:
        return _rejected(
            listing,
            condition,
            f"prix trop bas ({listing.price:.0f} EUR) - erreur de prix probable",
        )

    if (
        listing.property_type is not PropertyType.PARKING
        and surface > 0
        and listing.price / surface < min_price_per_m2
    ):
        return _rejected(
            listing,
            condition,
            f"prix au m2 trop bas ({listing.price / surface:.0f} EUR/m2) - "
            "erreur de prix probable",
        )

    # The rent grid always yields an estimate; the current rent declared in the
    # listing, when available, takes precedence for the yield computation.
    estimated_monthly_rent = (
        estimate_monthly_rent(listing.property_type, surface, listing.city) * factor
    )
    monthly_rent = (
        listing.monthly_rent
        if listing.monthly_rent is not None
        else estimated_monthly_rent
    )
    annual_rent = monthly_rent * 12
    notary_fees = listing.price * notary_fee_rate
    works_cost = estimate_works_cost(
        condition,
        surface,
        energy_class=listing.energy_class,
        price=listing.price,
    )
    total_cost = listing.price + notary_fees + works_cost
    gross_yield = annual_rent / total_cost * 100

    condo_fees_annual = (
        condo_fees_eur_per_m2_month(listing.property_type) * surface * 12
    )
    # The commune rate always yields an estimate; the amount declared in the
    # listing, when available, takes precedence for the net yield computation.
    estimated_property_tax = listing.price * property_tax_rate(listing.city)
    property_tax = (
        listing.property_tax
        if listing.property_tax is not None
        else estimated_property_tax
    )
    management_fees = annual_rent * management_fee_rate
    vacancy_cost = annual_rent * vacancy_rate
    net_annual_income = (
        annual_rent - condo_fees_annual - property_tax - management_fees - vacancy_cost
    )
    net_yield = net_annual_income / total_cost * 100
    cash_flow_monthly = net_annual_income / 12 - _estimate_monthly_mortgage(
        listing.price
    )

    breakdown = {
        "monthly_rent": monthly_rent,
        "estimated_monthly_rent": estimated_monthly_rent,
        "notary_fees": notary_fees,
        "works_cost": works_cost,
        "total_cost": total_cost,
        "condo_fees_annual": condo_fees_annual,
        "property_tax": property_tax,
        "estimated_property_tax": estimated_property_tax,
        "management_fees": management_fees,
        "vacancy_cost": vacancy_cost,
        "net_annual_income": net_annual_income,
        "gross_yield_pct": gross_yield,
        "net_yield_pct": net_yield,
        "cash_flow_monthly": cash_flow_monthly,
    }

    if gross_yield > max_yield_pct:
        return _rejected(
            listing,
            condition,
            f"rendement invraisemblable ({gross_yield:.1f}%) - donnees suspectes",
            **breakdown,
        )

    return Evaluation(
        condition=condition,
        condition_label=CONDITION_LABELS[condition],
        annual_rent=annual_rent,
        is_high_potential=gross_yield >= min_yield_pct,
        **breakdown,
    )


def _rejected(
    listing: RawListing,
    condition: Condition,
    reason: str,
    *,
    monthly_rent: float = 0.0,
    estimated_monthly_rent: float = 0.0,
    notary_fees: float = 0.0,
    works_cost: float = 0.0,
    total_cost: float = 0.0,
    condo_fees_annual: float = 0.0,
    property_tax: float = 0.0,
    estimated_property_tax: float = 0.0,
    management_fees: float = 0.0,
    vacancy_cost: float = 0.0,
    net_annual_income: float = 0.0,
    gross_yield_pct: float = 0.0,
    net_yield_pct: float = 0.0,
    cash_flow_monthly: float = 0.0,
) -> Evaluation:
    del listing  # only kept for call site symmetry
    return Evaluation(
        condition=condition,
        condition_label=CONDITION_LABELS[condition],
        monthly_rent=monthly_rent,
        estimated_monthly_rent=estimated_monthly_rent,
        annual_rent=monthly_rent * 12,
        notary_fees=notary_fees,
        works_cost=works_cost,
        total_cost=total_cost,
        condo_fees_annual=condo_fees_annual,
        property_tax=property_tax,
        estimated_property_tax=estimated_property_tax,
        management_fees=management_fees,
        vacancy_cost=vacancy_cost,
        net_annual_income=net_annual_income,
        gross_yield_pct=gross_yield_pct,
        net_yield_pct=net_yield_pct,
        cash_flow_monthly=cash_flow_monthly,
        is_high_potential=False,
        rejection_reason=reason,
    )


def is_high_potential(
    evaluation: Evaluation, *, min_yield_pct: float = DEFAULT_MIN_YIELD_PCT
) -> bool:
    """Convenience wrapper kept for callers that only hold an evaluation."""
    return evaluation.is_high_potential and evaluation.gross_yield_pct >= min_yield_pct
