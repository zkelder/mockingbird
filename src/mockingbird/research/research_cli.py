"""CLI entry points for `python -m mockingbird export-research`,
`export-camtrap-dp`, and `conservation-report` (see "Conservation report
API/CLI" in the governing milestone brief and docs/research-conservation-
export-contract.md).

Mirrors the existing `python -m mockingbird <subcommand>` dispatch
convention in `__main__.py` -- a lazy import + `run(argv)` returning an int
exit code -- exactly like `mockingbird.observation.offline_ingest_cli`'s
precedent. No async bridge is needed here: every `ProductRepository` method
this CLI calls is already synchronous.

Operates on the real local product database by default (`ProductRepository()`
with no explicit `db_url`) -- ordinary local-tool usage, not a test; see
`mockingbird.storage.database`'s own pytest-only safety guard, which this
module never triggers because it is never imported under pytest.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from mockingbird.api.schemas import (
    CamtrapDpExportRequest,
    ConservationReportRequest,
    DarwinCoreExportRequest,
    ResearchExportFilters,
    ResearchExportRequest,
)
from mockingbird.repository.product_repository import ProductRepository


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-at", type=_parse_datetime, default=None, help="ISO-8601 period start (inclusive).")
    parser.add_argument("--end-at", type=_parse_datetime, default=None, help="ISO-8601 period end (exclusive).")
    parser.add_argument("--stream-id", action="append", dest="stream_ids", default=None)
    parser.add_argument("--source-id", action="append", dest="source_ids", default=None)
    parser.add_argument("--taxon", action="append", dest="taxon_labels", default=None)
    parser.add_argument("--acquisition-scope", choices=["live", "offline", "both"], default="both")
    parser.add_argument("--collection-id", default=None)


def _filters_from_args(args: argparse.Namespace) -> ResearchExportFilters:
    return ResearchExportFilters(
        start_at=args.start_at,
        end_at=args.end_at,
        stream_ids=args.stream_ids,
        source_ids=args.source_ids,
        taxon_labels=args.taxon_labels,
        acquisition_scope=args.acquisition_scope,
        collection_id=args.collection_id,
    )


def run_export_research(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mockingbird export-research",
        description=(
            "Export research-safe reviewed Observations as a generic CSV/JSON/manifest "
            "bundle. Always trusted-only: a provisional, unresolved, rejected, or "
            "superseded record never enters the export table."
        ),
    )
    _add_filter_arguments(parser)
    parser.add_argument("--include-media", action="store_true", help="Include media metadata rows (bytes are never duplicated).")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be written without writing files.")
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--json", action="store_true", help="Print the result as machine-readable JSON.")
    args = parser.parse_args(argv)

    repository = ProductRepository()
    try:
        result = repository.export_research_dataset(
            ResearchExportRequest(
                filters=_filters_from_args(args),
                include_media=args.include_media,
                dry_run=args.dry_run,
                output_name=args.output_name,
            )
        )
    finally:
        repository.close()

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"export_id: {result.export_id}")
        print(f"output_directory: {result.output_directory}")
        print(f"observations: {result.observation_count}")
        print(f"media: {result.media_count}")
        print(f"excluded: {result.excluded_count} {dict(result.excluded_reasons)}")
        print(f"dry_run: {result.dry_run}")
    return 0


def run_export_camtrap_dp(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mockingbird export-camtrap-dp",
        description=(
            "Export research-safe reviewed Observations as a Camtrap DP package "
            "(target spec v1.0.2, https://camtrap-dp.tdwg.org/)."
        ),
    )
    _add_filter_arguments(parser)
    parser.add_argument("--include-media", action="store_true")
    parser.add_argument("--site-name", default=None, help="Explicit site/location name (never inferred).")
    parser.add_argument("--latitude", type=float, default=None, help="Explicit site latitude (never inferred).")
    parser.add_argument("--longitude", type=float, default=None, help="Explicit site longitude (never inferred).")
    parser.add_argument(
        "--no-machine-classifications", action="store_true",
        help="Omit the separate classificationMethod=machine observation rows.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repository = ProductRepository()
    try:
        result = repository.export_camtrap_dp_package(
            CamtrapDpExportRequest(
                filters=_filters_from_args(args),
                include_media=args.include_media,
                site_name=args.site_name,
                latitude=args.latitude,
                longitude=args.longitude,
                include_machine_classifications=not args.no_machine_classifications,
                dry_run=args.dry_run,
                output_name=args.output_name,
            )
        )
    finally:
        repository.close()

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"export_id: {result.export_id}")
        print(f"output_directory: {result.output_directory}")
        print(f"profile_version: {result.profile_version}")
        print(
            f"deployments: {result.deployment_count}  media: {result.media_count}  "
            f"observations: {result.observation_count}"
        )
        print(
            f"validation: valid={result.validation.valid}  "
            f"errors={len(result.validation.errors)}  warnings={len(result.validation.warnings)}"
        )
        for warning in result.validation.warnings:
            print(f"  warning: {warning}")
        for error in result.validation.errors:
            print(f"  error: {error}")
    return 0 if result.validation.valid else 1


def run_export_darwin_core(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mockingbird export-darwin-core",
        description=(
            "Export research-safe reviewed Observations as a bounded Darwin Core "
            "Occurrence-core archive (https://dwc.tdwg.org/) -- additive to, never a "
            "replacement for, export-camtrap-dp."
        ),
    )
    _add_filter_arguments(parser)
    parser.add_argument("--site-name", default=None, help="Explicit site/location name (never inferred).")
    parser.add_argument("--latitude", type=float, default=None, help="Explicit site latitude (never inferred).")
    parser.add_argument("--longitude", type=float, default=None, help="Explicit site longitude (never inferred).")
    parser.add_argument("--coordinate-uncertainty-meters", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repository = ProductRepository()
    try:
        result = repository.export_darwin_core_package(
            DarwinCoreExportRequest(
                filters=_filters_from_args(args),
                site_name=args.site_name,
                latitude=args.latitude,
                longitude=args.longitude,
                coordinate_uncertainty_meters=args.coordinate_uncertainty_meters,
                dry_run=args.dry_run,
                output_name=args.output_name,
            )
        )
    finally:
        repository.close()

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"export_id: {result.export_id}")
        print(f"output_directory: {result.output_directory}")
        print(f"schema_version: {result.schema_version}")
        print(f"occurrences: {result.occurrence_count}")
        print(f"dry_run: {result.dry_run}")
    return 0


def run_conservation_report(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mockingbird conservation-report",
        description=(
            "Print a bounded conservation/natural-history report for an explicit period: "
            "what was recorded, under how much defensible observation effort. Never a "
            "population/abundance/occupancy/trend claim."
        ),
    )
    parser.add_argument("--start-at", type=_parse_datetime, required=True)
    parser.add_argument("--end-at", type=_parse_datetime, required=True)
    parser.add_argument("--stream-id", action="append", dest="stream_ids", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repository = ProductRepository()
    try:
        report = repository.conservation_report(
            ConservationReportRequest(start_at=args.start_at, end_at=args.end_at, stream_ids=args.stream_ids)
        )
    finally:
        repository.close()

    if args.json:
        print(report.model_dump_json(indent=2))
        return 0

    print(f"period: {report.period_start_at.isoformat()} to {report.period_end_at.isoformat()}")
    print(f"maturity: {report.maturity}")
    if report.live_monitoring_monitored_seconds is not None:
        print(
            f"live monitoring: {report.live_monitoring_monitored_seconds:.0f}s "
            f"(usable days: {report.live_monitoring_usable_day_count})"
        )
    else:
        print("live monitoring: no durable exposure history yet for this period")
    print(
        f"offline acquisition: {report.offline_recorded_video_count} recorded video(s) "
        f"({report.offline_recorded_video_analyzed_seconds:.0f}s analyzed, "
        f"{report.offline_recorded_video_unknown_duration_count} of unknown duration), "
        f"{report.offline_still_image_count} still image(s)"
    )
    print(
        f"reviewed wildlife visits: {report.reviewed_wildlife_visit_count} "
        f"(confirmed unidentified: {report.confirmed_unidentified_wildlife_visit_count})"
    )
    for species in report.confirmed_species:
        note = species.occurrence_note or f"{species.confirmed_visit_count} confirmed visit(s)"
        print(f"  - {species.display_name}: {note}")
    print(f"provisional (unreviewed) wildlife visits: {report.provisional_wildlife_visit_count}")
    print(f"unresolved visits (review backlog): {report.unresolved_visit_count}")
    return 0
