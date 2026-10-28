"""Tests for the SQLite persistence layer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine

from immo_buzz.db import (
    ListingCreate,
    count_listings,
    list_listings,
    list_unsold_listings,
    mark_listing_sold,
    upsert_listing,
)
from immo_buzz.db.models import PropertyType
from immo_buzz.db.session import init_db


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    init_db(engine)
    with Session(engine) as session:
        yield session


def make_payload(**overrides: object) -> ListingCreate:
    payload: dict[str, object] = {
        "source": "bienici",
        "source_id": "era-1",
        "title": "Appartement T2",
        "property_type": PropertyType.FLAT,
        "price": 60_000.0,
        "surface": 25.0,
        "city": "Lille",
        "url": "https://www.bienici.com/annonce/era-1",
        "estimated_yield": 9.5,
    }
    payload.update(overrides)
    return ListingCreate(**payload)  # type: ignore[arg-type]


def test_upsert_creates_then_updates(session: Session) -> None:
    listing, created = upsert_listing(session, make_payload())
    assert created is True
    assert listing.id is not None
    assert listing.sold is False
    discovered_at = listing.discovered_at

    same, created_again = upsert_listing(
        session, make_payload(price=55_000.0, estimated_yield=10.4)
    )
    assert created_again is False
    assert same.id == listing.id
    assert same.price == 55_000.0
    assert same.estimated_yield == 10.4
    assert same.discovered_at == discovered_at
    assert count_listings(session) == 1


def test_mark_listing_sold_and_reactivate_on_upsert(session: Session) -> None:
    listing, _ = upsert_listing(session, make_payload())

    assert mark_listing_sold(session, listing) is True
    assert listing.sold is True
    assert list_unsold_listings(session) == []

    reactivated, created = upsert_listing(session, make_payload())
    assert created is False
    assert reactivated.sold is False
    assert [item.source_id for item in list_unsold_listings(session)] == ["era-1"]


def test_list_unsold_listings_filters_by_source(session: Session) -> None:
    upsert_listing(session, make_payload(source_id="bienici-1"))
    upsert_listing(session, make_payload(source="seloger", source_id="seloger-1"))

    unsold = list_unsold_listings(session, source="bienici")
    assert [item.source_id for item in unsold] == ["bienici-1"]


def test_unique_constraint_on_source_and_source_id(session: Session) -> None:
    upsert_listing(session, make_payload())
    upsert_listing(session, make_payload(source="seloger", source_id="era-1"))
    assert count_listings(session) == 2


def test_list_listings_filters_and_orders(session: Session) -> None:
    upsert_listing(session, make_payload(source_id="a", estimated_yield=9.0))
    upsert_listing(session, make_payload(source_id="b", estimated_yield=12.0))
    upsert_listing(
        session, make_payload(source_id="c", city="Roubaix", estimated_yield=15.0)
    )

    lille_only = list_listings(session, city="Lille")
    assert [listing.source_id for listing in lille_only] == ["b", "a"]

    best_first = list_listings(session, min_yield=10.0)
    assert [listing.source_id for listing in best_first] == ["c", "b"]

    limited = list_listings(session, limit=1)
    assert len(limited) == 1
    assert limited[0].source_id == "c"
