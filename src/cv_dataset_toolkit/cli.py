"""Command-line entry point for cv-dataset-toolkit."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack
from itertools import islice
from pathlib import Path
from typing import Any

from cv_dataset_toolkit import __version__
from cv_dataset_toolkit.core.metadata import iter_metadata
from cv_dataset_toolkit.core.stats import running_stats
from cv_dataset_toolkit.io.export import MANIFEST_FIELDS
from cv_dataset_toolkit.io.walker import iter_image_paths
from cv_dataset_toolkit.utils.iterutils import batched


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
        "--out", type=str, default=None, help="Optional path to write a manifest CSV to."
    )

    return parser


def _tracked_records(
    records: Iterator[dict[str, Any]],
    stats: Any,
    label_counts: Counter[str],
) -> Iterator[dict[str, Any]]:
    """Pass each record through `stats.send()` and tally its label, unchanged."""
    for record in records:
        stats.send(record)
        label_counts[record["label"]] += 1
        yield record


def run_scan(path: str, limit: int | None, batch_size: int, out: str | None) -> int:
    """Single lazy pass: walk -> metadata -> stats/label-count -> optional CSV.

    Prints per-batch progress as it goes.
    """
    paths: Iterator[Path] = iter_image_paths(Path(path))
    if limit is not None:
        paths = islice(paths, limit)

    records = iter_metadata(paths)

    stats = running_stats()
    next(stats)  # prime: advance the coroutine to its first `yield`
    label_counts: Counter[str] = Counter()
    tracked = _tracked_records(records, stats, label_counts)

    total = 0
    with ExitStack() as stack:
        csv_writer = None
        if out is not None:
            csv_file = stack.enter_context(open(out, "w", newline="", encoding="utf-8"))
            csv_writer = csv.DictWriter(csv_file, fieldnames=MANIFEST_FIELDS)
            csv_writer.writeheader()

        try:
            for batch_num, batch in enumerate(batched(tracked, batch_size), start=1):
                if csv_writer is not None:
                    for record in batch:
                        csv_writer.writerow(record)
                total += len(batch)
                print(f"batch {batch_num}: {len(batch)} records (running total: {total})")
        finally:
            stats.close()

    print(f"\ntotal records: {total}")
    if iter_metadata.skipped:
        print(f"skipped (unreadable): {iter_metadata.skipped}")
    if out is not None:
        print(f"manifest written to: {out}")

    print("per-label counts:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")

    return total


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        run_scan(args.path, args.limit, args.batch_size, args.out)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
