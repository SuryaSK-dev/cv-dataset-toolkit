"""Pydantic v2 models validating everything that enters from outside the process.

Dataclasses inside, Pydantic at the boundaries: `ImageRecord` (core/record.py)
is a frozen dataclass because it represents data this codebase already
trusts (it built the record itself, from a file it just opened). The models
here validate data that arrives from *outside* — a YAML file, environment
variables, CLI flags — where a typo or a hand-edited config file can put
anything in front of the program.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    DirectoryPath,
    PositiveInt,
    field_validator,
    model_validator,
)

from cv_dataset_toolkit.core.types import OutputFormat

ALLOWED_FORMATS: Final[frozenset[str]] = frozenset({"JPEG", "PNG", "BMP", "GIF", "WEBP"})
"""Image formats the toolkit's transforms and manifest validation recognize."""

_SUFFIX_BY_FORMAT: Final[dict[OutputFormat, str]] = {"csv": ".csv", "jsonl": ".jsonl"}


class OutputConfig(BaseModel):
    """Where and how a scan's manifest is written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    format: OutputFormat = "csv"


class PipelineConfig(BaseModel):
    """The full, validated configuration for a `scan` run.

    Frozen so a loaded config can't be accidentally mutated after
    validation; `extra="forbid"` so a typo'd key in a YAML file (or an
    unexpected CLI override key) fails loudly instead of being silently
    ignored.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    root: DirectoryPath
    formats: frozenset[str] = frozenset()
    min_size: tuple[PositiveInt, PositiveInt] | None = None
    dedupe: bool = False
    batch_size: PositiveInt = 32
    limit: PositiveInt | None = None
    output: OutputConfig | None = None

    @field_validator("formats", mode="before")
    @classmethod
    def _normalize_formats(cls, value: object) -> frozenset[str]:
        """Uppercase every format and reject anything the toolkit doesn't recognize."""
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise TypeError(f"formats must be a list of strings, got {type(value).__name__}")
        normalized = frozenset(str(item).strip().upper() for item in value)
        unknown = normalized - ALLOWED_FORMATS
        if unknown:
            raise ValueError(
                f"unknown image format(s) {sorted(unknown)}; allowed: {sorted(ALLOWED_FORMATS)}"
            )
        return normalized

    @model_validator(mode="after")
    def _sync_output_suffix(self) -> Self:
        """Auto-correct `output.path`'s suffix to match `output.format`.

        Chosen over raising: a mismatched extension (e.g. `--out manifest`
        with `--format jsonl`) is a cosmetic slip, not a semantic error —
        the intent (write JSON Lines) is unambiguous. Raising here would
        force users to spell out `.jsonl` by hand every time; silently
        fixing it is friendlier and loses no information.
        """
        if self.output is None:
            return self
        expected_suffix = _SUFFIX_BY_FORMAT[self.output.format]
        if self.output.path.suffix.lower() == expected_suffix:
            return self
        fixed_path = self.output.path.with_suffix(expected_suffix)
        corrected = self.output.model_copy(update={"path": fixed_path})
        return self.model_copy(update={"output": corrected})
