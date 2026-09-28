"""Polymorphic manifest exporters. `scan --format csv|jsonl` picks one."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable

from cv_dataset_toolkit.core.record import ImageRecord
from cv_dataset_toolkit.io.export import write_manifest_csv


class Exporter(ABC):
    """Writes a stream of `ImageRecord`s to `out_path`, returning the row count."""

    @abstractmethod
    def export(self, records: Iterable[ImageRecord], out_path: str | os.PathLike[str]) -> int:
        raise NotImplementedError


class CSVExporter(Exporter):
    """Wraps Day 2's `write_manifest_csv`, adapting `ImageRecord` -> dict lazily."""

    def export(self, records: Iterable[ImageRecord], out_path: str | os.PathLike[str]) -> int:
        return write_manifest_csv((record.to_dict() for record in records), out_path)


class JSONLinesExporter(Exporter):
    """One JSON object per line, written and flushed one record at a time."""

    def export(self, records: Iterable[ImageRecord], out_path: str | os.PathLike[str]) -> int:
        row_count = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record.to_dict()))
                f.write("\n")
                row_count += 1
        return row_count
