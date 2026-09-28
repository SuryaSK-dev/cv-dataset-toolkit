"""Command-line entry point for cv-dataset-toolkit."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Generator, Iterable, Iterator
from itertools import islice
from pathlib import Path

from pydantic import ValidationError

from cv_dataset_toolkit import __version__
from cv_dataset_toolkit.config.loader import load_config
from cv_dataset_toolkit.config.models import PipelineConfig
from cv_dataset_toolkit.core.metadata import iter_metadata
from cv_dataset_toolkit.core.record import ImageRecord
from cv_dataset_toolkit.core.stats import StatsSnapshot, running_stats
from cv_dataset_toolkit.io.exporters import CSVExporter, Exporter, JSONLinesExporter
from cv_dataset_toolkit.io.manifest import validate_manifest_csv
from cv_dataset_toolkit.io.walker import iter_image_paths
from cv_dataset_toolkit.pipeline.factory import build_pipeline
from cv_dataset_toolkit.pipeline.pipeline import PipelineStats
from cv_dataset_toolkit.utils.iterutils import batched


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cv-dataset-toolkit",
        description="Scan an image dataset folder and export a metadata manifest.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Scan a dataset folder and export a manifest.")
    scan_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to the dataset root folder (overrides config's root).",
    )
    scan_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a YAML config file (e.g. configs/default.yaml).",
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many source files (lazy: the directory walk itself stops early).",
    )
    scan_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Number of records to process per reported batch (config/model default: 32).",
    )
    scan_parser.add_argument("--out", type=str, default=None, help="Path to write a manifest to.")
    scan_parser.add_argument(
        "--formats",
        type=_csv_list,
        default=None,
        metavar="FMT,FMT",
        help="Comma-separated list of formats to keep, e.g. JPEG,PNG.",
    )
    scan_parser.add_argument(
        "--min-size",
        type=int,
        nargs=2,
        default=None,
        metavar=("W", "H"),
        help="Drop images smaller than W x H.",
    )
    scan_parser.add_argument(
        "--dedupe", action="store_true", help="Drop records with duplicate (size, width, height)."
    )
    scan_parser.add_argument(
        "--format",
        choices=("csv", "jsonl"),
        default=None,
        help="Manifest format when writing output (config/model default: csv).",
    )

    validate_parser = subparsers.add_parser(
        "validate-manifest", help="Validate a manifest CSV row-by-row against ManifestRow."
    )
    validate_parser.add_argument("file", help="Path to the manifest CSV to validate.")

    return parser


def config_overrides_from_args(args: argparse.Namespace) -> dict[str, object]:
    """Collect only the CLI flags the user actually passed, as a config override mapping.

    Flags left at their argparse default (`None`/unset) are omitted entirely
    so they don't shadow values from the YAML file or environment layer —
    that's what makes "CLI flags > env vars > YAML file" a real precedence
    chain instead of the CLI always winning.
    """
    overrides: dict[str, object] = {}
    if args.path is not None:
        overrides["root"] = args.path
    if args.limit is not None:
        overrides["limit"] = args.limit
    if args.batch_size is not None:
        overrides["batch_size"] = args.batch_size
    if args.formats is not None:
        overrides["formats"] = args.formats
    if args.min_size is not None:
        overrides["min_size"] = tuple(args.min_size)
    if args.dedupe:
        overrides["dedupe"] = True

    output_overrides: dict[str, object] = {}
    if args.out is not None:
        output_overrides["path"] = args.out
    if args.format is not None:
        output_overrides["format"] = args.format
    if output_overrides:
        overrides["output"] = output_overrides

    return overrides


def _tracked_records(
    records: Iterator[ImageRecord],
    stats: Generator[StatsSnapshot, ImageRecord, None],
    label_counts: Counter[str],
) -> Iterator[ImageRecord]:
    """Pass each record through `stats.send()` and tally its label, unchanged."""
    for record in records:
        stats.send(record)
        label_counts[record.label] += 1
        yield record


def _with_progress(records: Iterable[ImageRecord], batch_size: int) -> Iterator[ImageRecord]:
    """Yield records unchanged, printing per-batch progress as they pass through."""
    total = 0
    for batch_num, batch in enumerate(batched(records, batch_size), start=1):
        total += len(batch)
        print(f"batch {batch_num}: {len(batch)} records (running total: {total})")
        yield from batch


def run_scan(config: PipelineConfig) -> int:
    """Single lazy pass: walk -> metadata -> pipeline -> stats/label-count -> optional export."""
    paths: Iterator[Path] = iter_image_paths(config.root)
    if config.limit is not None:
        paths = islice(paths, config.limit)

    records = iter_metadata(paths)

    pipeline = build_pipeline(config)
    pipeline_stats = PipelineStats()
    piped = pipeline.run(records, pipeline_stats)

    stats = running_stats()
    next(stats)  # prime: advance the coroutine to its first `yield`
    label_counts: Counter[str] = Counter()
    tracked = _tracked_records(piped, stats, label_counts)

    reported = _with_progress(tracked, config.batch_size)

    try:
        if config.output is not None:
            exporter: Exporter = (
                CSVExporter() if config.output.format == "csv" else JSONLinesExporter()
            )
            total = exporter.export(reported, config.output.path)
        else:
            total = sum(1 for _ in reported)
    finally:
        stats.close()

    print(f"\ntotal records: {total}")
    if iter_metadata.skipped:
        print(f"skipped (unreadable): {iter_metadata.skipped}")
    if config.output is not None:
        print(f"manifest written to: {config.output.path} ({config.output.format})")

    print("per-label counts:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")

    if len(pipeline):
        print("\npipeline stats:")
        print(pipeline_stats.table())

    return total


def run_validate_manifest(file: str) -> int:
    summary = validate_manifest_csv(file)
    print(f"valid rows: {summary.valid_count}")
    print(f"invalid rows: {len(summary.errors)}")
    shown = summary.errors[:5]
    for error in shown:
        print(f"  row {error.row_number}: {error.message}")
    remaining = len(summary.errors) - len(shown)
    if remaining > 0:
        print(f"  ... and {remaining} more")
    return 0 if not summary.errors else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        config_path = Path(args.config) if args.config else None
        overrides = config_overrides_from_args(args)
        try:
            config = load_config(config_path, overrides)
        except ValidationError as exc:
            print("invalid configuration:", file=sys.stderr)
            for error in exc.errors():
                loc = ".".join(str(part) for part in error["loc"])
                print(f"  {loc}: {error['msg']}", file=sys.stderr)
            return 2
        run_scan(config)
        return 0

    if args.command == "validate-manifest":
        return run_validate_manifest(args.file)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
