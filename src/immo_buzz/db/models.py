"""SQLModel entities storing qualified real estate opportunities."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel, UniqueConstraint


class PropertyType(StrEnum):
    """Property categories tracked by the MVP."""

    FLAT = "flat"
    HOUSE = "house"
    BUILDING = "building"
    PARKING = "parking"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ListingBase(SQLModel):
    """Fields shared by every API schema and the database table."""

    source: str = Field(index=True)
    source_id: str
    title: str
    property_type: PropertyType = Field(index=True)

    price: float
    surface: float | None = None
    city: str = Field(index=True)
    postal_code: str | None = None
    district: str | None = None
    url: str

    detected_condition: str | None = None
    estimated_monthly_rent: float | None = None
    estimated_works_cost: float | None = None
    total_cost: float | None = None
    estimated_yield: float | None = Field(default=None, index=True)

    published_at: datetime | None = None


class ListingCreate(ListingBase):
    """Payload used when persisting a newly qualified opportunity."""


class ListingRead(ListingBase):
    """Shape returned by future API endpoints."""

    id: int
    discovered_at: datetime
    updated_at: datetime


class Listing(ListingBase, table=True):
    """Physical table of high-potential opportunities."""

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listing_source_source_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    discovered_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
