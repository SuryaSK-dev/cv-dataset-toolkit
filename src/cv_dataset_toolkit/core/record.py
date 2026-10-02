"""`ImageRecord`: the immutable unit of data flowing through the pipeline.

Frozen because a record represents a *fact* about a file at scan time — once
built it shouldn't drift out of sync with what was actually read. Transforms
that need to "change" a record (e.g. normalizing a label) never mutate it in
place; they build a new record with `dataclasses.replace(record, **changes)`,
leaving the original untouched. This makes records safe to share across
pipeline steps, batches, and threads without defensive copying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from cv_dataset_toolkit.core.types import PathLike
from cv_dataset_toolkit.utils.decorators import retry


@dataclass(frozen=True, slots=True)
class ImageRecord:
    path: str
    label: str
    format: str
    size_bytes: int
    width: int
    height: int
    # `object`, not `Any`: transforms attach heterogeneous derived values here
    # (Day 3's aspect_bucket is a str, a future one might add a float or
    # bool). `object` still forces callers to narrow the type before using a
    # value, unlike `Any`, which would silently allow anything.
    extras: dict[str, object] = field(default_factory=dict)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000

    @classmethod
    @retry(attempts=3, delay=0.01, backoff=2.0, exceptions=(OSError,))
    def from_path(cls, path: PathLike) -> ImageRecord:
        """Build a record by reading only the image header (no pixel decode).

        Retries transient `OSError` failures up to 3 times with exponential backoff.
        Transient filesystem locks, network storage contention (NFS/SMB), or sync
        services (OneDrive/Dropbox) can momentarily block file descriptors during
        rapid scanning; retrying handles transient sharing violations gracefully.
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

    def to_dict(self) -> dict[str, object]:
        base: dict[str, object] = {
            "path": self.path,
            "label": self.label,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
        }
        base.update(self.extras)
        return base
