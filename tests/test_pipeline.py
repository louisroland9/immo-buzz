"""Integration tests for the pipeline workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session

from immo_buzz.config import Settings
from immo_buzz.db import count_listings, make_engine
from immo_buzz.db.models import PropertyType
from immo_buzz.engine import evaluate
from immo_buzz.pipeline import Pipeline, build_listing_create, collect_raw_listings
from immo_buzz.scraper.base import RawListing


class StubSource:
    """In-memory source returning two pages then stopping."""

    name = "stub"

    def __init__(self, pages: list[list[RawListing]]) -> None:
        self._pages = pages
        self.calls = 0

    def fetch(self, *, page: int, page_size: int) -> list[RawListing]:
        del page_size  # unused by the stub, kept for protocol compatibility
        self.calls += 1
        if page >= len(self._pages):
            return []
        return self._pages[page]


def raw_flat(source_id: str, price: float, surface: float) -> RawListing:
    return RawListing(
        source="stub",
        source_id=source_id,
        title="Appartement T2",
        property_type=PropertyType.FLAT,
        price=price,
        surface=surface,
        city="Lille",
        url=f"https://example.test/{source_id}",
        description="Appartement refait a neuf.",
        energy_class="C",
    )


def raw_parking(source_id: str, price: float = 9_000.0) -> RawListing:
    return RawListing(
        source="stub",
        source_id=source_id,
        title="Place de parking",
        property_type=PropertyType.PARKING,
        price=price,
        surface=None,
        city="Lille",
        url=f"https://example.test/{source_id}",
        description="Place de parking securisee.",
    )


def test_pipeline_keeps_only_high_yield_and_persists(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'pipeline.db'}",
        min_yield_pct=8.0,
        max_yield_pct=20.0,
        page_size=100,
        max_pages=2,
        request_delay_s=0.0,
    )
    source = StubSource(
        pages=[
            [
                raw_parking("cheap"),
                raw_flat("expensive", 200_000.0, 50.0),
            ],
            [raw_parking("cheap")],
        ]
    )
    pipeline = Pipeline(source, settings)
    result = pipeline.run()

    assert result.fetched == 2
    assert result.evaluated == 2
    assert result.kept == 1
    assert result.created == 1
    assert result.created_listings[0].source_id == "cheap"

    engine = make_engine(settings.database_url)
    with Session(engine) as session:
        assert count_listings(session) == 1


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'dry.db'}"
    settings = Settings(database_url=database_url, min_yield_pct=8.0)
    source = StubSource(pages=[[raw_parking("cheap")]])
    result = Pipeline(source, settings).run(dry_run=True)

    assert result.kept == 1
    assert result.created == 0
    assert not Path(tmp_path / "dry.db").exists()


def test_pipeline_deduplicates_across_pages(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'dedupe.db'}",
        min_yield_pct=8.0,
        max_pages=2,
    )
    source = StubSource(
        pages=[
            [raw_parking("a"), raw_parking("b")],
            [raw_parking("a")],
        ]
    )
    collected = collect_raw_listings(source, max_pages=2, page_size=100)
    assert [listing.source_id for listing in collected] == ["a", "b"]

    result = Pipeline(source, settings).run(dry_run=True)
    assert result.fetched == 2


def test_build_listing_create_projects_evaluation() -> None:
    listing = raw_flat("x", 60_000.0, 25.0)
    payload = build_listing_create(listing, evaluate(listing))
    assert payload.estimated_yield == pytest.approx(7.87)
    assert payload.detected_condition == "bon"
    assert payload.source_id == "x"
    assert payload.total_cost == pytest.approx(64_800.0)
