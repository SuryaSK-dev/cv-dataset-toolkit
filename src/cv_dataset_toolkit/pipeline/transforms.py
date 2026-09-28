"""Transform hierarchy: every pipeline step is a `Transform`.

`Filter` and `Mapper` are template-method subclasses: they implement
`apply()` once (the wiring) and ask concrete subclasses for just the
decision (`keep`) or the change (`map`). This keeps concrete transforms
tiny and prevents each one from having to remember the None-means-drop
convention itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import replace
from typing import TYPE_CHECKING

from cv_dataset_toolkit.core.record import ImageRecord

if TYPE_CHECKING:
    from cv_dataset_toolkit.pipeline.pipeline import Pipeline


class Transform(ABC):
    """A single pipeline step. `apply` returns a (possibly new) record, or
    `None` to drop the record from the stream."""

    @abstractmethod
    def apply(self, record: ImageRecord) -> ImageRecord | None:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return type(self).__name__

    def __call__(self, record: ImageRecord) -> ImageRecord | None:
        return self.apply(record)

    def __repr__(self) -> str:
        return f"{self.name}()"

    def __or__(self, other: Transform) -> Pipeline:
        from cv_dataset_toolkit.pipeline.pipeline import Pipeline

        return Pipeline([self]) | other


class Filter(Transform):
    """Template method: subclasses decide `keep`; this handles the drop wiring."""

    @abstractmethod
    def keep(self, record: ImageRecord) -> bool:
        raise NotImplementedError

    def apply(self, record: ImageRecord) -> ImageRecord | None:
        return record if self.keep(record) else None


class Mapper(Transform):
    """Template method: subclasses build the replacement record via `map`."""

    @abstractmethod
    def map(self, record: ImageRecord) -> ImageRecord:
        raise NotImplementedError

    def apply(self, record: ImageRecord) -> ImageRecord | None:
        return self.map(record)


class FilterByFormat(Filter):
    """Keep only records whose `format` is in `formats` (case-insensitive)."""

    def __init__(self, formats: Iterable[str]) -> None:
        self.formats = frozenset(f.strip().upper() for f in formats)

    def keep(self, record: ImageRecord) -> bool:
        return record.format.upper() in self.formats

    def __repr__(self) -> str:
        return f"{self.name}({sorted(self.formats)})"


class FilterMinSize(Filter):
    """Keep only records at least `min_width` x `min_height`."""

    def __init__(self, min_width: int, min_height: int) -> None:
        self.min_width = min_width
        self.min_height = min_height

    def keep(self, record: ImageRecord) -> bool:
        return record.width >= self.min_width and record.height >= self.min_height

    def __repr__(self) -> str:
        return f"{self.name}(min_width={self.min_width}, min_height={self.min_height})"


class NormalizeLabel(Mapper):
    """Strip whitespace and lowercase the label."""

    def map(self, record: ImageRecord) -> ImageRecord:
        return replace(record, label=record.label.strip().lower())


class AddAspectBucket(Mapper):
    """Tag each record's `extras["aspect_bucket"]` as portrait/landscape/square."""

    def map(self, record: ImageRecord) -> ImageRecord:
        ratio = record.aspect_ratio
        if ratio > 1.05:
            bucket = "landscape"
        elif ratio < 0.95:
            bucket = "portrait"
        else:
            bucket = "square"
        return replace(record, extras={**record.extras, "aspect_bucket": bucket})


class DropDuplicates(Filter):
    """Drop records whose (size_bytes, width, height) was already seen.

    This transform is **stateful**: `_seen` accumulates across every call
    to `keep()` on this instance. That makes it order-sensitive and
    unsafe to reuse across independent passes over the same data — running
    the *same* `DropDuplicates()` instance a second time over a dataset it
    already scanned will treat every record as a repeat and drop it all.
    Construct a fresh instance per independent run/pipeline if you need
    each run's duplicate detection to start clean.
    """

    def __init__(self) -> None:
        self._seen: set[tuple[int, int, int]] = set()

    def keep(self, record: ImageRecord) -> bool:
        key = (record.size_bytes, record.width, record.height)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True
