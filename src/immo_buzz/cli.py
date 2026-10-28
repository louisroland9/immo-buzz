"""Command line interface running the full workflow."""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace

from immo_buzz.config import Settings, load_settings
from immo_buzz.pipeline import Pipeline, build_bienici_source, format_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="immo-buzz",
        description=(
            "Scrape the Lille metropolitan area, keep the listings whose "
            "estimated gross yield reaches the threshold and store them."
        ),
    )
    parser.add_argument(
        "--min-yield",
        type=float,
        default=None,
        help="minimum gross yield in percent (default: IMMO_MIN_YIELD_PCT or 8)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="number of pages fetched per source (default: IMMO_MAX_PAGES or 5)",
    )
    parser.add_argument(
        "--commune",
        action="append",
        default=None,
        help=(
            "restrict the search to a commune, repeatable "
            "(default: all Lille metropolis zones)"
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=None,
        help="ads requested per page, capped at 100 (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="analyse and score listings without writing to the database",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable debug logs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # httpx logs every request at INFO, which drowns the pipeline output.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = load_settings()
    if args.min_yield is not None:
        settings = replace(settings, min_yield_pct=args.min_yield)
    if args.max_pages is not None:
        settings = replace(settings, max_pages=args.max_pages)
    if args.page_size is not None:
        settings = replace(settings, page_size=args.page_size)

    source = build_bienici_source(settings, args.commune)
    pipeline = Pipeline(source, settings)
    try:
        result = pipeline.run(max_pages=settings.max_pages, dry_run=args.dry_run)
    finally:
        source.close()

    print(format_result(result, settings.min_yield_pct))
    if args.dry_run:
        print("Mode dry-run : aucune ecriture en base.")
    return 0


def main_with_settings(settings: Settings, argv: list[str] | None = None) -> int:
    """Run the pipeline with pre-built settings."""
    args = build_parser().parse_args(argv)
    source = build_bienici_source(settings, args.commune)
    pipeline = Pipeline(source, settings)
    try:
        result = pipeline.run(max_pages=settings.max_pages, dry_run=args.dry_run)
    finally:
        source.close()
    print(format_result(result, settings.min_yield_pct))
    if args.dry_run:
        print("Mode dry-run : aucune ecriture en base.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
