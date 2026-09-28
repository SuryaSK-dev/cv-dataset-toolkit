"""Streaming extraction of per-image metadata records."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from PIL import UnidentifiedImageError

from cv_dataset_toolkit.core.record import ImageRecord


def iter_metadata(paths: Iterable[Path]) -> Iterator[ImageRecord]:
    """Yield one `ImageRecord` per readable image in `paths`.

    `ImageRecord.from_path` reads only the file header (no pixel decode),
    so this stays cheap even over thousands of large images. Files that
    fail to open (corrupt, truncated, or not actually images despite the
    extension) are skipped and counted on `iter_metadata.skipped` rather
    than raising — proper structured error handling arrives on Day 6.
    """
    skipped = 0
    for path in paths:
        try:
            record = ImageRecord.from_path(path)
        except (OSError, UnidentifiedImageError):
            skipped += 1
            continue

        yield record

    iter_metadata.skipped = skipped


iter_metadata.skipped = 0
