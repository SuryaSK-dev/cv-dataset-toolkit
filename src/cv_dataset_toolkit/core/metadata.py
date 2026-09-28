"""Streaming extraction of per-image metadata records."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from PIL import UnidentifiedImageError

from cv_dataset_toolkit.core.record import ImageRecord


class _MetadataReader:
    """Callable standing in for a plain generator function.

    A bare function can't carry a properly-typed `.skipped` counter —
    dynamically assigning an attribute to a function object (as the Day 2/3
    version of this module did) is exactly what `mypy --strict` rejects. A
    small callable class gives `skipped` a real, typed instance attribute
    while keeping the `iter_metadata(paths)` call syntax unchanged.
    """

    def __init__(self) -> None:
        self.skipped: int = 0

    def __call__(self, paths: Iterable[Path]) -> Iterator[ImageRecord]:
        """Yield one `ImageRecord` per readable image in `paths`.

        `ImageRecord.from_path` reads only the file header (no pixel
        decode), so this stays cheap even over thousands of large images.
        Files that fail to open (corrupt, truncated, or not actually images
        despite the extension) are skipped and counted on `self.skipped`
        rather than raising — proper structured error handling arrives on
        Day 6.
        """
        self.skipped = 0
        for path in paths:
            try:
                record = ImageRecord.from_path(path)
            except (OSError, UnidentifiedImageError):
                self.skipped += 1
                continue

            yield record


iter_metadata = _MetadataReader()
