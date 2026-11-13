"""End-to-end workflow: fetch, evaluate, filter and persist."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlmodel import Session

from immo_buzz.config import Settings, load_settings
from immo_buzz.db import (
    ListingCreate,
    ListingRead,
    init_db,
    list_unsold_listings,
    make_engine,
    mark_listing_sold,
    upsert_listing,
)
from immo_buzz.engine import Evaluation, evaluate
from immo_buzz.scraper.areas import SearchArea, resolve_zone_ids
from immo_buzz.scraper.base import (
    ListingAvailabilityChecker,
    ListingSource,
    RawListing,
)
from immo_buzz.scraper.bienici import BieniciSource
from immo_buzz.scraper.geocoding import GeoResolver

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Aggregated counters produced by a pipeline run."""

    fetched: int = 0
    evaluated: int = 0
    kept: int = 0
    created: int = 0
    updated: int = 0
    rejected: int = 0
    marked_sold: int = 0
    created_listings: list[ListingRead] = field(default_factory=list)


def collect_raw_listings(
    source: ListingSource, max_pages: int, page_size: int
) -> list[RawListing]:
    """Collect listings across the source search areas, deduplicated.

    ``max_pages`` is the number of pages walked *per search area* (e.g. per
    commune), not a global budget, so a commune is never hidden by the recent
    ads of another one.
    """
    return source.iter_listings(max_pages=max_pages, page_size=page_size)


class Pipeline:
    """Orchestrate the scraping, scoring and storage steps."""

    def __init__(
        self,
        source: ListingSource,
        settings: Settings | None = None,
    ) -> None:
        self.source = source
        self.settings = settings or load_settings()

    def _iter_raw_listings(self, max_pages: int) -> list[RawListing]:
        return collect_raw_listings(self.source, max_pages, self.settings.page_size)

    def _mark_sold_listings(self, session: Session) -> int:
        """Mark known listings whose source URL no longer exists as sold."""
        if not isinstance(self.source, ListingAvailabilityChecker):
            return 0

        marked = 0
        for listing in list_unsold_listings(session, source=self.source.name):
            if self.source.is_available(listing.source_id) is False:
                marked += int(mark_listing_sold(session, listing))
                logger.info("listing %s is no longer available", listing.source_id)
        return marked

    def run(
        self, *, max_pages: int | None = None, dry_run: bool = False
    ) -> PipelineResult:
        """Execute the whole workflow and return aggregated counters."""
        pages = max_pages if max_pages is not None else self.settings.max_pages
        raw_listings = self._iter_raw_listings(pages)
        result = PipelineResult(fetched=len(raw_listings))
        logger.info("fetched %s raw listings", result.fetched)

        high_potential: list[tuple[RawListing, Evaluation]] = []
        for raw in raw_listings:
            evaluation = evaluate(
                raw,
                min_yield_pct=self.settings.min_yield_pct,
                max_yield_pct=self.settings.max_yield_pct,
                min_plausible_price=self.settings.min_plausible_price,
                min_price_per_m2=self.settings.min_price_per_m2,
                notary_fee_rate=self.settings.notary_fee_rate,
                management_fee_rate=self.settings.management_fee_rate,
                vacancy_rate=self.settings.vacancy_rate,
            )
            result.evaluated += 1
            if evaluation.rejection_reason is not None:
                result.rejected += 1
            if evaluation.is_high_potential:
                high_potential.append((raw, evaluation))

        result.kept = len(high_potential)
        logger.info(
            "kept %s listings with a yield >= %.1f%%",
            result.kept,
            self.settings.min_yield_pct,
        )

        if dry_run:
            return result

        engine = make_engine(self.settings.database_url)
        init_db(engine)
        with Session(engine) as session:
            for raw, evaluation in high_potential:
                listing, created = upsert_listing(
                    session, build_listing_create(raw, evaluation)
                )
                result.created += int(created)
                result.updated += int(not created)
                if created:
                    # Snapshot the row while the session is still open, so the
                    # result can be rendered after the session is closed.
                    result.created_listings.append(ListingRead.model_validate(listing))
            result.marked_sold = self._mark_sold_listings(session)
        return result


def build_listing_create(raw: RawListing, evaluation: Evaluation) -> ListingCreate:
    """Turn a raw listing and its evaluation into a persistence payload."""
    return ListingCreate(
        source=raw.source,
        source_id=raw.source_id,
        title=raw.title,
        property_type=raw.property_type,
        price=raw.price,
        surface=raw.surface,
        city=raw.city,
        postal_code=raw.postal_code,
        district=raw.district,
        url=raw.url,
        latitude=raw.latitude,
        longitude=raw.longitude,
        description=raw.description,
        energy_class=raw.energy_class,
        works_signalled=raw.works_signalled,
        detected_condition=evaluation.condition.value,
        estimated_monthly_rent=round(evaluation.estimated_monthly_rent, 2),
        monthly_rent=raw.monthly_rent,
        estimated_works_cost=round(evaluation.works_cost, 2),
        total_cost=round(evaluation.total_cost, 2),
        estimated_gross_yield=round(evaluation.gross_yield_pct, 2),
        estimated_net_yield=round(evaluation.net_yield_pct, 2),
        estimated_property_tax=round(evaluation.estimated_property_tax, 2),
        property_tax=raw.property_tax,
        estimated_condo_fees=round(evaluation.condo_fees_annual, 2),
        published_at=raw.published_at,
    )


def format_result(result: PipelineResult, min_yield_pct: float) -> str:
    """Render a short human readable summary."""
    lines = [
        f"Annonces analysees : {result.evaluated}",
        f"Rejetees (donnees inexploitables) : {result.rejected}",
        f"Retenues (rendement >= {min_yield_pct:.1f}%) : {result.kept}",
        f"Nouvelles en base : {result.created}",
        f"Mises a jour : {result.updated}",
        f"Marquees vendues : {result.marked_sold}",
    ]
    for listing in result.created_listings[:10]:
        lines.append(
            f"  - {listing.estimated_gross_yield:.1f}% brut / "
            f"{listing.estimated_net_yield:.1f}% net | {listing.city} | "
            f"{listing.price:.0f} EUR | {listing.title[:60]} | {listing.url}"
        )
    return "\n".join(lines)


def build_bienici_source(
    settings: Settings,
    city: str | None = None,
    radius_km: float | None = None,
) -> BieniciSource:
    """Create the Bien'ici source for a city and a search radius.

    The city is geocoded through Bien'ici's suggest endpoint, the communes
    inside the radius are resolved to their Bien'ici zone ids, and the source
    filters out the listings sitting outside the radius.
    """
    city_name = city or settings.city
    radius = radius_km if radius_km is not None else settings.radius_km

    resolver = GeoResolver(request_delay_s=settings.request_delay_s)
    try:
        center = resolver.resolve_city(city_name)
        area = SearchArea(center=center, radius_km=radius, label=city_name)
        zone_ids = resolve_zone_ids(area, resolver)
    finally:
        resolver.close()

    logger.info(
        "resolved %s (%s km) to %s Bien'ici zones",
        city_name,
        radius,
        len(zone_ids),
    )
    return BieniciSource(
        zone_ids,
        request_delay_s=settings.request_delay_s,
        area=area,
    )
