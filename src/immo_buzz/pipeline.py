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
    make_engine,
    upsert_listing,
)
from immo_buzz.engine import Evaluation, evaluate
from immo_buzz.scraper.base import ListingSource, RawListing
from immo_buzz.scraper.bienici import BieniciSource
from immo_buzz.scraper.zones import LILLE_METROPOLE_ZONES, zones_by_name

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
    created_listings: list[ListingRead] = field(default_factory=list)


def collect_raw_listings(
    source: ListingSource, max_pages: int, page_size: int
) -> list[RawListing]:
    """Fetch several pages and drop listings already seen."""
    seen: set[str] = set()
    collected: list[RawListing] = []
    for page in range(max_pages):
        batch = source.fetch(page=page, page_size=page_size)
        if not batch:
            break
        for raw in batch:
            if raw.source_id in seen:
                continue
            seen.add(raw.source_id)
            collected.append(raw)
    return collected


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
                notary_fee_rate=self.settings.notary_fee_rate,
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
        detected_condition=evaluation.condition.value,
        estimated_monthly_rent=round(evaluation.monthly_rent, 2),
        estimated_works_cost=round(evaluation.works_cost, 2),
        total_cost=round(evaluation.total_cost, 2),
        estimated_yield=round(evaluation.gross_yield_pct, 2),
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
    ]
    for listing in result.created_listings[:10]:
        lines.append(
            f"  - {listing.estimated_yield:.1f}% | {listing.city} | "
            f"{listing.price:.0f} EUR | {listing.title[:60]} | {listing.url}"
        )
    return "\n".join(lines)


def build_bienici_source(
    settings: Settings, commune_names: list[str] | None = None
) -> BieniciSource:
    """Create the default Bien'ici source for the Lille metropolitan area."""
    zones = (
        zones_by_name(commune_names) if commune_names else list(LILLE_METROPOLE_ZONES)
    )
    return BieniciSource(
        [zone.bienici_zone_id for zone in zones],
        request_delay_s=settings.request_delay_s,
    )
