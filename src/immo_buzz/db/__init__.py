"""Data access layer (SQLite / SQLModel)."""

from immo_buzz.db.models import (
    Listing,
    ListingBase,
    ListingCreate,
    ListingRead,
    PropertyType,
)
from immo_buzz.db.repository import (
    count_listings,
    list_listings,
    upsert_listing,
)
from immo_buzz.db.session import get_session, init_db, make_engine

__all__ = [
    "Listing",
    "ListingBase",
    "ListingCreate",
    "ListingRead",
    "PropertyType",
    "count_listings",
    "get_session",
    "init_db",
    "list_listings",
    "make_engine",
    "upsert_listing",
]
