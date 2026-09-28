"""Structural typing (`Protocol`) for anything that can act as a record source.

Protocol vs ABC
----------------
- An ABC (like `Transform` in `pipeline/transforms.py`) is *nominal*: a class
  must explicitly inherit from it to count as a subtype, and `isinstance()`
  checks walk the MRO. It's the right tool when you also want to share
  implementation (template methods, `__call__`, etc.) or enforce a specific
  lineage.
- A `Protocol` is *structural*: any object with a matching `__iter__`
  signature satisfies `RecordSource`, whether or not it ever imports this
  module. `ImageFolder` (`io/dataset.py`) satisfies it "for free" — it was
  written before this Protocol existed and needs no changes.

`RecordSource` suits this case because "produces an iterator of
`ImageRecord`" is a *shape*, not an identity: plain generators, dataclasses,
and test doubles can all satisfy it without inheriting from anything.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from cv_dataset_toolkit.core.record import ImageRecord


@runtime_checkable
class RecordSource(Protocol):
    def __iter__(self) -> Iterator[ImageRecord]: ...
