"""Streaming manifest export."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from typing import Final

from cv_dataset_toolkit.core.types import PathLike
from cv_dataset_toolkit.utils.contexts import atomic_write
from cv_dataset_toolkit.utils.decorators import deprecated

MANIFEST_FIELDS: Final[tuple[str, ...]] = (
    "path",
    "label",
    "format",
    "size_bytes",
    "width",
    "height",
)


@deprecated("write_manifest_csv is superseded by CSVExporter; use CSVExporter instead")
def write_manifest_csv(records: Iterable[Mapping[str, object]], out_path: PathLike) -> int:
    """Write `records` to `out_path` as CSV, one row at a time.

    Consumes `records` (a generator) lazily via `csv.DictWriter.writerow`
    inside the loop, so at most one record is held in memory regardless of
    how many rows the manifest ends up with. Returns the row count.
    Writes atomically via `atomic_write`.
    """
    row_count = 0
    with atomic_write(out_path, mode="w", newline="", encoding="utf-8") as f:
        # extrasaction="ignore": records may carry extra keys (e.g. a
        # transform's `extras`, like Day 3's aspect_bucket) that this fixed
        # column set doesn't export.
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)
            row_count += 1
    return row_count
