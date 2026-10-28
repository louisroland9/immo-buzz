"""Persistence helpers for qualified opportunities."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, col, select

from immo_buzz.db.models import Listing, ListingCreate


def upsert_listing(session: Session, payload: ListingCreate) -> tuple[Listing, bool]:
    """Insert a listing or refresh it when it already exists.

    Returns the stored entity and a flag telling whether it was created.
    A known listing keeps its original ``discovered_at`` while its financial
    estimates are recomputed.
    """
    existing = session.exec(
        select(Listing)
        .where(Listing.source == payload.source)
        .where(Listing.source_id == payload.source_id)
    ).first()

    if existing is None:
        listing = Listing.model_validate(payload)
        session.add(listing)
        session.commit()
        session.refresh(listing)
        return listing, True

    existing.sqlmodel_update(payload.model_dump(exclude={"source", "source_id"}))
    # Seeing the ad again means it is back on the market.
    existing.sold = False
    existing.updated_at = datetime.now(UTC)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing, False


def list_unsold_listings(
    session: Session, *, source: str | None = None
) -> list[Listing]:
    """Return active listings, optionally restricted to one source."""
    statement = select(Listing).where(col(Listing.sold).is_(False))
    if source is not None:
        statement = statement.where(Listing.source == source)
    return list(session.exec(statement).all())


def mark_listing_sold(session: Session, listing: Listing) -> bool:
    """Mark an unavailable listing as sold.

    Returns ``True`` only when the state actually changed.
    """
    if listing.sold:
        return False
    listing.sold = True
    listing.updated_at = datetime.now(UTC)
    session.add(listing)
    session.commit()
    session.refresh(listing)
    return True


def list_listings(
    session: Session,
    *,
    min_yield: float | None = None,
    city: str | None = None,
    limit: int | None = None,
) -> list[Listing]:
    """Return stored listings, best yield first."""
    statement = select(Listing)
    if min_yield is not None:
        statement = statement.where(col(Listing.estimated_yield) >= min_yield)
    if city is not None:
        statement = statement.where(Listing.city == city)
    statement = statement.order_by(col(Listing.estimated_yield).desc())
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.exec(statement).all())


def count_listings(session: Session) -> int:
    """Return the total number of stored listings."""
    return len(session.exec(select(Listing)).all())
