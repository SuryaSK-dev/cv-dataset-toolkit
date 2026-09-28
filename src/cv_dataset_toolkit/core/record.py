"""`ImageRecord`: the immutable unit of data flowing through the pipeline.

Frozen because a record represents a *fact* about a file at scan time — once
built it shouldn't drift out of sync with what was actually read. Transforms
that need to "change" a record (e.g. normalizing a label) never mutate it in
place; they build a new record with `dataclasses.replace(record, **changes)`,
leaving the original untouched. This makes records safe to share across
pipeline steps, batches, and threads without defensive copying.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass(frozen=True, slots=True)
class ImageRecord:
    path: str
    label: str
    format: str
    size_bytes: int
    width: int
    height: int
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000

    @classmethod
    def from_path(cls, path: str | os.PathLike[str]) -> ImageRecord:
        """Build a record by reading only the image header (no pixel decode).

        Propagates `OSError`/`PIL.UnidentifiedImageError` for unreadable
        files — callers that want to skip-and-count (like `iter_metadata`)
        catch those around this call.
        """
        path = Path(path)
        with Image.open(path) as img:
            width, height = img.size
            image_format = img.format or "UNKNOWN"
        return cls(
            path=str(path),
            label=path.parent.name,
            format=image_format,
            size_bytes=path.stat().st_size,
            width=width,
            height=height,
        )

    def to_dict(self) -> dict[str, Any]:
        base = {
            "path": self.path,
            "label": self.label,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
        }
        base.update(self.extras)
        return base
