"""Polymorphic manifest exporters. `scan --format csv|jsonl` picks one."""

from __future__ import annotations

import contextlib
import csv
import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TextIO, cast

from cv_dataset_toolkit.core.record import ImageRecord
from cv_dataset_toolkit.core.types import PathLike
from cv_dataset_toolkit.io.export import MANIFEST_FIELDS
from cv_dataset_toolkit.utils.contexts import atomic_write
from cv_dataset_toolkit.utils.decorators import timed


class Exporter(ABC):
    """Writes a stream of `ImageRecord`s to `out_path`, returning the row count."""

    @abstractmethod
    def export(self, records: Iterable[ImageRecord], out_path: PathLike) -> int:
        raise NotImplementedError


class CSVExporter(Exporter):
    """Streams records to a CSV file atomically via `atomic_write`."""

    @timed
    def export(self, records: Iterable[ImageRecord], out_path: PathLike) -> int:
        row_count = 0
        with atomic_write(out_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow(record.to_dict())
                row_count += 1
        return row_count


class JSONLinesExporter(Exporter):
    """One JSON object per line, written atomically via `atomic_write`."""

    @timed
    def export(self, records: Iterable[ImageRecord], out_path: PathLike) -> int:
        row_count = 0
        with atomic_write(out_path, mode="w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record.to_dict()))
                f.write("\n")
                row_count += 1
        return row_count


class MultiExporter:
    """Exports records to multiple destinations simultaneously in a single pass.

    Uses `contextlib.ExitStack` to manage multiple `atomic_write` contexts concurrently,
    guaranteeing that either all target manifests succeed or none leave partial files.
    """

    def __init__(self, targets: Iterable[tuple[str, PathLike]]) -> None:
        self.targets = list(targets)

    @timed
    def export(self, records: Iterable[ImageRecord]) -> int:
        if not self.targets:
            return 0

        with contextlib.ExitStack() as stack:
            writers: list[tuple[str, object]] = []
            for fmt, path in self.targets:
                if fmt == "csv":
                    f = stack.enter_context(
                        atomic_write(path, mode="w", newline="", encoding="utf-8")
                    )
                    writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
                    writer.writeheader()
                    writers.append(("csv", writer))
                elif fmt == "jsonl":
                    f = stack.enter_context(atomic_write(path, mode="w", encoding="utf-8"))
                    writers.append(("jsonl", f))
                else:
                    raise ValueError(f"Unsupported format: {fmt}")

            row_count = 0
            for record in records:
                row_dict = record.to_dict()
                for fmt, handle in writers:
                    if fmt == "csv":
                        cast("csv.DictWriter[str]", handle).writerow(row_dict)
                    else:
                        f_handle = cast(TextIO, handle)
                        f_handle.write(json.dumps(row_dict))
                        f_handle.write("\n")
                row_count += 1

        return row_count
