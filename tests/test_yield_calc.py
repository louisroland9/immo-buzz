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
    assert result.estimated_monthly_rent == pytest.approx(725.0)
    assert result.notary_fees == pytest.approx(9_600.0)
    assert result.works_cost == 0.0
    assert result.total_cost == pytest.approx(129_600.0)
    assert result.gross_yield_pct == pytest.approx(725 * 12 / 129_600 * 100)
    # Condo fees 1.8 EUR/m2/month for a flat, Lille property tax 0.80%.
    assert result.condo_fees_annual == pytest.approx(1.8 * 50 * 12)
    assert result.property_tax == pytest.approx(120_000 * 0.0080)
    assert result.estimated_property_tax == pytest.approx(120_000 * 0.0080)
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


def test_declared_property_tax_overrides_the_estimate() -> None:
    listing = make_listing(price=120_000.0, surface=50.0, property_tax=436.0)
    result = evaluate(listing)
    # The declared amount is used as is, the estimate stays available.
    assert result.property_tax == pytest.approx(436.0)
    assert result.estimated_property_tax == pytest.approx(120_000 * 0.0080)


def test_property_tax_falls_back_to_the_estimate_when_absent() -> None:
    listing = make_listing(price=120_000.0, surface=50.0, property_tax=None)
    result = evaluate(listing)
    assert result.property_tax == pytest.approx(120_000 * 0.0080)
    assert result.estimated_property_tax == pytest.approx(120_000 * 0.0080)


def test_declared_monthly_rent_overrides_the_estimate() -> None:
    listing = make_listing(price=120_000.0, surface=50.0, monthly_rent=712.0)
    result = evaluate(listing)
    # The declared rent is used as is, the estimate stays available.
    assert result.monthly_rent == pytest.approx(712.0)
    assert result.annual_rent == pytest.approx(712.0 * 12)
    assert result.estimated_monthly_rent == pytest.approx(725.0)


def test_monthly_rent_falls_back_to_the_estimate_when_absent() -> None:
    listing = make_listing(price=120_000.0, surface=50.0, monthly_rent=None)
    result = evaluate(listing)
    assert result.monthly_rent == pytest.approx(725.0)
    assert result.estimated_monthly_rent == pytest.approx(725.0)


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
    # Fixed 12 000 EUR + 700 EUR/m2 * 200 m2 = 152 000, capped to 60% of price.
    assert result.works_cost == pytest.approx(200_000 * 0.6)
    assert result.total_cost == pytest.approx(200_000 + 16_000 + 120_000)
    assert result.gross_yield_pct < 8.0


def test_refresh_condition_applies_a_non_zero_works_budget() -> None:
    listing = make_listing(title="Studio a rafraichir", price=80_000.0, surface=30.0)
    result = evaluate(listing)
    assert result.condition is Condition.REFRESH
    # Fixed 1 000 EUR + 100 EUR/m2 * 30 m2 = 4 000, below the price cap.
    assert result.works_cost == pytest.approx(1_000.0 + 100.0 * 30.0)


def test_works_cost_uses_fixed_and_variable_parts() -> None:
    small = make_listing(
        title="Appartement a renover",
        price=150_000.0,
        surface=20.0,
        energy_class="C",
    )
    large = make_listing(
        title="Appartement a renover",
        price=150_000.0,
        surface=100.0,
        energy_class="C",
    )
    small_cost = evaluate(small).works_cost
    large_cost = evaluate(large).works_cost
    assert small_cost == pytest.approx(6_000.0 + 400.0 * 20.0)
    assert large_cost == pytest.approx(6_000.0 + 400.0 * 100.0)
    # The fixed part makes the small dwelling relatively more expensive per m2.
    assert small_cost / 20.0 > large_cost / 100.0


def test_poor_energy_class_adds_a_works_premium() -> None:
    base = make_listing(
        title="Appartement lumineux",
        price=150_000.0,
        surface=40.0,
        energy_class="D",
    )
    poor = make_listing(
        title="Appartement lumineux",
        price=150_000.0,
        surface=40.0,
        energy_class="G",
    )
    # A poor label alone triggers RENOVATION and adds the energy premium.
    base_result = evaluate(base)
    poor_result = evaluate(poor)
    assert base_result.condition is Condition.GOOD
    assert poor_result.condition is Condition.RENOVATION
    assert poor_result.works_cost > base_result.works_cost


def test_works_cost_is_capped_by_price_ratio() -> None:
    listing = make_listing(
        title="Immeuble a restaurer",
        property_type=PropertyType.BUILDING,
        price=50_000.0,
        surface=300.0,
    )
    result = evaluate(listing)
    assert result.works_cost == pytest.approx(50_000 * 0.6)


def test_good_condition_has_no_works() -> None:
    listing = make_listing(price=120_000.0, surface=50.0, energy_class="C")
    result = evaluate(listing)
    assert result.condition is Condition.GOOD
    assert result.works_cost == 0.0


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
    assert "prix trop bas" in result.rejection_reason


def test_implausible_yield_is_rejected() -> None:
    # A price below the floor would be caught earlier, so the max yield guard
    # is exercised with a plausible price, a disabled price floor and a very
    # high rent per square metre to push the gross yield above the ceiling.
    listing = make_listing(price=5_000.0, surface=8.0, monthly_rent=3_000.0)
    result = evaluate(listing, max_yield_pct=20.0, min_plausible_price=0.0)
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


def test_viager_listing_is_rejected() -> None:
    listing = make_listing(
        title="Appartement en viager occupe",
        description="Vente en viager, bouquet 50 000 EUR.",
        price=60_000.0,
        surface=25.0,
    )
    result = evaluate(listing)
    assert result.is_high_potential is False
    assert result.rejection_reason is not None
    assert "viager" in result.rejection_reason


def test_bare_ownership_listing_is_rejected() -> None:
    listing = make_listing(
        title="Appartement en nue propriete",
        price=60_000.0,
        surface=25.0,
    )
    result = evaluate(listing)
    assert result.is_high_potential is False
    assert result.rejection_reason is not None
    assert "demembrement" in result.rejection_reason


def test_low_price_is_rejected() -> None:
    listing = make_listing(price=3_000.0, surface=50.0)
    result = evaluate(listing, min_plausible_price=5_000.0)
    assert result.is_high_potential is False
    assert result.rejection_reason is not None
    assert "prix trop bas" in result.rejection_reason


def test_low_price_per_m2_is_rejected() -> None:
    # 60 000 EUR for 500 m2 -> 120 EUR/m2, below the floor.
    listing = make_listing(price=60_000.0, surface=500.0)
    result = evaluate(listing, min_price_per_m2=150.0)
    assert result.is_high_potential is False
    assert result.rejection_reason is not None
    assert "prix au m2" in result.rejection_reason


def test_price_per_m2_floor_does_not_apply_to_parkings() -> None:
    listing = make_listing(
        property_type=PropertyType.PARKING,
        title="Place de parking",
        price=9_000.0,
        surface=None,
    )
    result = evaluate(listing, min_price_per_m2=150.0)
    assert result.rejection_reason is None


def test_heavy_renovation_is_still_accepted() -> None:
    listing = make_listing(
        title="Immeuble a restaurer",
        property_type=PropertyType.BUILDING,
        price=200_000.0,
        surface=300.0,
    )
    result = evaluate(listing, min_price_per_m2=150.0)
    assert result.condition is Condition.HEAVY
    assert result.rejection_reason is None
