"""Streaming Pydantic validation of exported manifest rows — untrusted, read back from disk.

Unlike `ImageRecord` (a trusted dataclass this codebase builds itself),
a manifest CSV on disk could have been hand-edited, produced by another
tool, or corrupted in transit. `ManifestRow` re-validates every row against
the same constraints `ImageRecord` is meant to uphold before anything
downstream trusts it.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from cv_dataset_toolkit.config.models import ALLOWED_FORMATS
from cv_dataset_toolkit.core.types import PathLike


class ManifestRow(BaseModel):
    """A single validated manifest row."""

    model_config = ConfigDict(extra="forbid")

    path: str
    label: str
    format: str
    size_bytes: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @field_validator("format")
    @classmethod
    def _known_format(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ALLOWED_FORMATS:
            raise ValueError(f"unknown format {value!r}; allowed: {sorted(ALLOWED_FORMATS)}")
        return normalized


class RowError(NamedTuple):
    row_number: int
    message: str


class ValidationSummary(NamedTuple):
    valid_count: int
    errors: list[RowError]


def _first_error_line(exc: ValidationError) -> str:
    """Collapse a (possibly multi-field) ValidationError to one readable line."""
    parts = [f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return "; ".join(parts)


def iter_validated_rows(
    rows: Iterator[dict[str, str | None]],
) -> Iterator[tuple[int, ManifestRow | RowError]]:
    """Yield `(row_number, ManifestRow | RowError)` for each row, lazily, starting at 1."""
    for row_number, row in enumerate(rows, start=1):
        try:
            yield row_number, ManifestRow.model_validate(row)
        except ValidationError as exc:
            yield row_number, RowError(row_number, _first_error_line(exc))


def validate_manifest_csv(path: PathLike) -> ValidationSummary:
    """Stream-validate a manifest CSV, never loading the whole file into memory.

    Only the running valid count and the list of row-level errors are kept;
    valid rows are validated and discarded one at a time.
    """
    valid_count = 0
    errors: list[RowError] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for _row_number, result in iter_validated_rows(reader):
            if isinstance(result, RowError):
                errors.append(result)
            else:
                valid_count += 1

    return ValidationSummary(valid_count, errors)
