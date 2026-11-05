"""Centralized configuration for the immo-buzz MVP.

All financial hypotheses are exposed as editable constants. They can be
overridden through environment variables without touching the code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields

# --- Database ------------------------------------------------------------
DEFAULT_DATABASE_URL = "sqlite:///data/app.db"

# --- Financial hypotheses (editable) -------------------------------------
# Purchase price + notary fees + works budget.
DEFAULT_NOTARY_FEE_RATE = 0.08

# A listing is kept only when its estimated gross yield reaches this floor.
DEFAULT_MIN_YIELD_PCT = 8.0

# Above this value the data is almost always wrong (viager, bare ownership,
# parking bundle, mistyped surface...), so the listing is rejected.
DEFAULT_MAX_YIELD_PCT = 40.0

# --- Operating costs (used to derive the net yield) ----------------------
# Condominium fees (non recoverable), property tax rate and management fees
# are defined per commune in ``engine/grids.py``. The settings below tune the
# remaining hypotheses.
# Management fee as a fraction of the annual gross rent.
DEFAULT_MANAGEMENT_FEE_RATE = 0.07

# Vacancy allowance as a fraction of the annual gross rent.
DEFAULT_VACANCY_RATE = 0.04

# Annual mortgage rate used for the indicative cash-flow estimate
# (full financing, constant monthly payment model).
DEFAULT_MORTGAGE_ANNUAL_RATE = 0.035

# --- Scraping ------------------------------------------------------------
DEFAULT_REQUEST_DELAY_S = 1.0
DEFAULT_MAX_PAGES = 5
DEFAULT_PAGE_SIZE = 100

_ENV_PREFIX = "IMMO_"


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from environment variables."""

    database_url: str = DEFAULT_DATABASE_URL
    min_yield_pct: float = DEFAULT_MIN_YIELD_PCT
    max_yield_pct: float = DEFAULT_MAX_YIELD_PCT
    notary_fee_rate: float = DEFAULT_NOTARY_FEE_RATE
    management_fee_rate: float = DEFAULT_MANAGEMENT_FEE_RATE
    vacancy_rate: float = DEFAULT_VACANCY_RATE
    mortgage_annual_rate: float = DEFAULT_MORTGAGE_ANNUAL_RATE
    request_delay_s: float = DEFAULT_REQUEST_DELAY_S
    max_pages: int = DEFAULT_MAX_PAGES
    page_size: int = DEFAULT_PAGE_SIZE


def _env(name: str, default: str) -> str:
    return os.getenv(f"{_ENV_PREFIX}{name}", default)


def load_settings() -> Settings:
    """Build a :class:`Settings` instance from ``IMMO_*`` environment vars."""
    values: dict[str, object] = {
        "database_url": _env("DATABASE_URL", DEFAULT_DATABASE_URL),
        "min_yield_pct": float(_env("MIN_YIELD_PCT", str(DEFAULT_MIN_YIELD_PCT))),
        "max_yield_pct": float(_env("MAX_YIELD_PCT", str(DEFAULT_MAX_YIELD_PCT))),
        "notary_fee_rate": float(_env("NOTARY_FEE_RATE", str(DEFAULT_NOTARY_FEE_RATE))),
        "management_fee_rate": float(
            _env("MANAGEMENT_FEE_RATE", str(DEFAULT_MANAGEMENT_FEE_RATE))
        ),
        "vacancy_rate": float(_env("VACANCY_RATE", str(DEFAULT_VACANCY_RATE))),
        "mortgage_annual_rate": float(
            _env("MORTGAGE_ANNUAL_RATE", str(DEFAULT_MORTGAGE_ANNUAL_RATE))
        ),
        "request_delay_s": float(_env("REQUEST_DELAY_S", str(DEFAULT_REQUEST_DELAY_S))),
        "max_pages": int(_env("MAX_PAGES", str(DEFAULT_MAX_PAGES))),
        "page_size": int(_env("PAGE_SIZE", str(DEFAULT_PAGE_SIZE))),
    }
    known = {f.name for f in fields(Settings)}
    return Settings(**{key: value for key, value in values.items() if key in known})
