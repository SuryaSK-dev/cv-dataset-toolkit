"""Command-line entry point for cv-dataset-toolkit."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from itertools import islice
from pathlib import Path
from typing import Any

from cv_dataset_toolkit import __version__
from cv_dataset_toolkit.core.metadata import iter_metadata
from cv_dataset_toolkit.core.record import ImageRecord
from cv_dataset_toolkit.core.stats import running_stats
from cv_dataset_toolkit.io.exporters import CSVExporter, Exporter, JSONLinesExporter
from cv_dataset_toolkit.io.walker import iter_image_paths
from cv_dataset_toolkit.pipeline.pipeline import Pipeline, PipelineStats
from cv_dataset_toolkit.pipeline.transforms import (
    DropDuplicates,
    FilterByFormat,
    FilterMinSize,
    Transform,
)
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
    scan_parser.add_argument("path", help="Path to the dataset root folder.")
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many source files (lazy: the directory walk itself stops early).",
    )
    scan_parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Number of records to process per reported batch.",
    )
    scan_parser.add_argument(
        "--out", type=str, default=None, help="Optional path to write a manifest to."
    )
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
        default="csv",
        help="Manifest format when --out is given (default: csv).",
    )

    return parser


def build_pipeline(
    formats: list[str] | None,
    min_size: tuple[int, int] | None,
    dedupe: bool,
) -> Pipeline:
    """Build a Pipeline from CLI flags. No flags set -> empty pipeline (pure passthrough)."""
    steps: list[Transform] = []
    if formats:
        steps.append(FilterByFormat(formats))
    if min_size is not None:
        steps.append(FilterMinSize(*min_size))
    if dedupe:
        steps.append(DropDuplicates())
    return Pipeline(steps)


def _tracked_records(
    records: Iterator[ImageRecord],
    stats: Any,
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


def run_scan(
    path: str,
    limit: int | None,
    batch_size: int,
    out: str | None,
    formats: list[str] | None,
    min_size: list[int] | None,
    dedupe: bool,
    out_format: str,
) -> int:
    """Single lazy pass: walk -> metadata -> pipeline -> stats/label-count -> optional export."""
    paths: Iterator[Path] = iter_image_paths(Path(path))
    if limit is not None:
        paths = islice(paths, limit)

    records = iter_metadata(paths)

    pipeline = build_pipeline(formats, tuple(min_size) if min_size else None, dedupe)
    pipeline_stats = PipelineStats()
    piped = pipeline.run(records, pipeline_stats)

    stats = running_stats()
    next(stats)  # prime: advance the coroutine to its first `yield`
    label_counts: Counter[str] = Counter()
    tracked = _tracked_records(piped, stats, label_counts)

    reported = _with_progress(tracked, batch_size)

    try:
        if out is not None:
            exporter: Exporter = CSVExporter() if out_format == "csv" else JSONLinesExporter()
            total = exporter.export(reported, out)
        else:
            total = sum(1 for _ in reported)
    finally:
        stats.close()

    print(f"\ntotal records: {total}")
    if iter_metadata.skipped:
        print(f"skipped (unreadable): {iter_metadata.skipped}")
    if out is not None:
        print(f"manifest written to: {out} ({out_format})")

    print("per-label counts:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")

    if len(pipeline):
        print("\npipeline stats:")
        print(pipeline_stats.table())

    return total


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        run_scan(
            args.path,
            args.limit,
            args.batch_size,
            args.out,
            args.formats,
            args.min_size,
            args.dedupe,
            args.format,
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
