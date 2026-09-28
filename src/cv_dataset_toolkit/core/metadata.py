"""Streaming extraction of per-image metadata records."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


def iter_metadata(paths: Iterable[Path]) -> Iterator[dict[str, Any]]:
    """Yield one metadata dict per readable image in `paths`.

    `Image.open` is lazy: it reads only the file header to determine
    format/size and does not decode pixel data, so this stays cheap even
    over thousands of large images. Files that fail to open (corrupt,
    truncated, or not actually images despite the extension) are skipped
    and counted on `iter_metadata.skipped` rather than raising — proper
    structured error handling arrives on Day 6.
    """
    skipped = 0
    for path in paths:
        try:
            with Image.open(path) as img:
                width, height = img.size
                image_format = img.format
        except (OSError, UnidentifiedImageError):
            skipped += 1
            continue

        yield {
            "path": str(path),
            "label": path.parent.name,
            "format": image_format,
            "size_bytes": path.stat().st_size,
            "width": width,
            "height": height,
        }

    iter_metadata.skipped = skipped


iter_metadata.skipped = 0
