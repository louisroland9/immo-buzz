"""Contracts shared by every listing source."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from immo_buzz.db.models import PropertyType


class RawListing(BaseModel):
    """Normalized listing produced by a scraper before any computation."""

    model_config = ConfigDict(extra="ignore")

    source: str
    source_id: str
    title: str
    property_type: PropertyType

    price: float
    surface: float | None = None
    city: str
    postal_code: str | None = None
    district: str | None = None
    url: str

    description: str | None = None
    rooms: int | None = None
    energy_class: str | None = None
    published_at: datetime | None = None


@runtime_checkable
class ListingSource(Protocol):
    """Minimal interface a scraping backend must implement."""

    name: str

    def fetch(
        self, *, page: int, page_size: int
    ) -> list[RawListing]:  # pragma: no cover - protocol definition
        """Return raw listings for the given page."""
        ...


@runtime_checkable
class ListingAvailabilityChecker(Protocol):
    """Optional capability used to detect listings removed from the source."""

    def is_available(
        self, source_id: str
    ) -> bool | None:  # pragma: no cover - protocol definition
        """Return ``False`` when the listing no longer exists.

        ``None`` means the availability could not be determined (network error,
        rate limiting, server error) and must not mark the listing as sold.
        """
        ...
