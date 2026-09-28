"""Streaming manifest export."""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from typing import Any

MANIFEST_FIELDS = ("path", "label", "format", "size_bytes", "width", "height")


def write_manifest_csv(records: Iterable[dict[str, Any]], out_path: str | os.PathLike[str]) -> int:
    """Write `records` to `out_path` as CSV, one row at a time.

    Consumes `records` (a generator) lazily via `csv.DictWriter.writerow`
    inside the loop, so at most one record is held in memory regardless of
    how many rows the manifest ends up with. Returns the row count.
    """
    row_count = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        # extrasaction="ignore": records may carry extra keys (e.g. a
        # transform's `extras`, like Day 3's aspect_bucket) that this fixed
        # column set doesn't export.
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)
            row_count += 1
    return row_count
