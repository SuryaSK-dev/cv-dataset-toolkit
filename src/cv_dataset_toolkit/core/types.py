"""Shared type aliases.

Declared with the explicit `Name: TypeAlias = ...` form rather than the 3.12
`type Name = ...` statement, since this project targets Python 3.11.
"""

from __future__ import annotations

import os
from typing import Literal, TypeAlias

PathLike: TypeAlias = str | os.PathLike[str]
"""Anything `open()`/`Path()` accepts as a filesystem path."""

OutputFormat: TypeAlias = Literal["csv", "jsonl"]
"""Manifest export formats supported by `Exporter` implementations."""

AspectBucket: TypeAlias = Literal["portrait", "landscape", "square"]
"""Buckets assigned by the `AddAspectBucket` transform."""
