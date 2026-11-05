"""Unit tests for the financial engine."""

from __future__ import annotations

import pytest

from immo_buzz.db.models import PropertyType
from immo_buzz.engine.grids import Condition, estimate_monthly_rent
from immo_buzz.engine.yield_calc import evaluate
from immo_buzz.scraper.base import RawListing


def make_listing(**overrides: object) -> RawListing:
    payload: dict[str, object] = {
        "source": "test",
        "source_id": "1",
        "title": "Appartement",
        "property_type": PropertyType.FLAT,
        "price": 100_000.0,
        "surface": 50.0,
        "city": "Lille",
        "url": "https://example.test/1",
        "description": "",
        "energy_class": "C",
    }
    payload.update(overrides)
    return RawListing(**payload)  # type: ignore[arg-type]


def test_rent_grid_uses_smaller_surface_premium() -> None:
    small = estimate_monthly_rent(PropertyType.FLAT, 25.0, "Lille")
    large = estimate_monthly_rent(PropertyType.FLAT, 100.0, "Lille")
    assert small == pytest.approx(18.0 * 25)
    assert large == pytest.approx(12.5 * 100)
    assert small / 25 > large / 100


def test_rent_grid_varies_by_commune() -> None:
    lille = estimate_monthly_rent(PropertyType.FLAT, 50.0, "Lille")
    roubaix = estimate_monthly_rent(PropertyType.FLAT, 50.0, "Roubaix")
    assert lille == pytest.approx(14.5 * 50)
    assert roubaix == pytest.approx(9.8 * 50)
    assert lille > roubaix


def test_rent_grid_falls_back_to_metropole_for_unknown_commune() -> None:
    unknown = estimate_monthly_rent(PropertyType.FLAT, 50.0, "Atlantis")
    assert unknown == pytest.approx(12.5 * 50)


def test_parking_uses_flat_rate_regardless_of_surface() -> None:
    assert estimate_monthly_rent(PropertyType.PARKING, 0.0) == pytest.approx(70.0)
    assert estimate_monthly_rent(PropertyType.PARKING, 14.0) == pytest.approx(70.0)


def test_evaluation_math_is_consistent() -> None:
    listing = make_listing(price=120_000.0, surface=50.0)
    result = evaluate(listing)
    assert result.condition is Condition.GOOD
    # Lille flat 50 m2 -> tier 2, 14.5 EUR/m2.
    assert result.monthly_rent == pytest.approx(725.0)
    assert result.notary_fees == pytest.approx(9_600.0)
    assert result.works_cost == 0.0
    assert result.total_cost == pytest.approx(129_600.0)
    assert result.gross_yield_pct == pytest.approx(725 * 12 / 129_600 * 100)
    # Condo fees 1.8 EUR/m2/month for a flat, Lille property tax 0.80%.
    assert result.condo_fees_annual == pytest.approx(1.8 * 50 * 12)
    assert result.property_tax == pytest.approx(120_000 * 0.0080)
    assert result.management_fees == pytest.approx(725 * 12 * 0.07)
    assert result.vacancy_cost == pytest.approx(725 * 12 * 0.04)
    assert result.net_yield_pct < result.gross_yield_pct
    assert result.is_high_potential is False
    assert result.rejection_reason is None


def test_house_has_no_condominium_fees() -> None:
    listing = make_listing(
        property_type=PropertyType.HOUSE,
        price=150_000.0,
        surface=90.0,
    )
    result = evaluate(listing)
    assert result.condo_fees_annual == 0.0
    assert result.property_tax > 0
    assert result.net_yield_pct < result.gross_yield_pct


def test_parking_has_no_condominium_fees_and_tax_applies() -> None:
    listing = make_listing(
        property_type=PropertyType.PARKING,
        title="Place de parking",
        price=9_000.0,
        surface=None,
    )
    result = evaluate(listing)
    assert result.condo_fees_annual == 0.0
    assert result.property_tax == pytest.approx(9_000 * 0.0080)
    assert result.net_yield_pct < result.gross_yield_pct


def test_heavy_renovation_income_tax_on_yield() -> None:
    listing = make_listing(
        title="Immeuble à restaurer",
        property_type=PropertyType.BUILDING,
        price=200_000.0,
        surface=200.0,
    )
    result = evaluate(listing)
    assert result.condition is Condition.HEAVY
    assert result.works_cost == pytest.approx(800.0 * 200)
    assert result.total_cost == pytest.approx(200_000 + 16_000 + 160_000)
    assert result.gross_yield_pct < 8.0


def test_high_potential_above_threshold() -> None:
    listing = make_listing(
        property_type=PropertyType.FLAT, price=60_000.0, surface=25.0
    )
    # Lille flat 25 m2 -> tier 0, 18.0 EUR/m2 -> 450 EUR/month, ~8.33% gross.
    result = evaluate(listing, min_yield_pct=8.0)
    assert result.gross_yield_pct >= 8.0
    assert result.is_high_potential is True

    below = evaluate(listing, min_yield_pct=9.0)
    assert below.is_high_potential is False


def test_configurable_threshold_rejects_borderline_deal() -> None:
    listing = make_listing(
        property_type=PropertyType.FLAT, price=60_000.0, surface=25.0
    )
    assert evaluate(listing, min_yield_pct=8.0).is_high_potential is True
    assert evaluate(listing, min_yield_pct=12.0).is_high_potential is False


def test_price_of_one_euro_is_rejected_as_suspicious() -> None:
    listing = make_listing(price=1.0, surface=50.0)
    result = evaluate(listing, max_yield_pct=20.0)
    assert result.is_high_potential is False
    assert result.rejection_reason is not None
    assert "invraisemblable" in result.rejection_reason


def test_missing_surface_is_rejected_for_flat() -> None:
    listing = make_listing(surface=None)
    result = evaluate(listing)
    assert result.is_high_potential is False
    assert result.rejection_reason is not None


def test_zero_price_is_rejected() -> None:
    listing = make_listing(price=0.0)
    result = evaluate(listing)
    assert result.rejection_reason is not None
    assert "prix" in result.rejection_reason


def test_parking_is_accepted_without_surface() -> None:
    listing = make_listing(
        property_type=PropertyType.PARKING,
        title="Place de parking",
        price=9_000.0,
        surface=None,
    )
    result = evaluate(listing)
    assert result.rejection_reason is None
    assert result.gross_yield_pct == pytest.approx(70 * 12 / (9_000 * 1.08) * 100)
    assert result.is_high_potential is True
    assert result.monthly_rent == pytest.approx(70.0)
