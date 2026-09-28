"""Small lazy iterator utilities built on `itertools`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from itertools import chain, islice
from typing import Any, TypeVar

T = TypeVar("T")


def batched(iterable: Iterable[T], n: int) -> Iterator[tuple[T, ...]]:
    """Yield successive `n`-sized tuples from `iterable`, last one possibly shorter.

    Own implementation via `itertools.islice` over a shared iterator: each
    call to `next(it)` inside the inner loop resumes the *same* underlying
    iterator, so no item is consumed twice and nothing upstream is buffered
    into a list. (Python 3.12+ ships this as `itertools.batched` directly;
    reimplemented here since this project targets 3.11.)
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


def take(iterable: Iterable[T], n: int) -> list[T]:
    """Return the first `n` items of `iterable` without consuming the rest."""
    return list(islice(iterable, n))


def count_by_label(records: Iterable[dict[str, Any]]) -> Counter[str]:
    """Stream through metadata records, tallying counts per `label`.

    A single `Counter` accumulates as records are consumed one at a time —
    no intermediate list of labels is built, so this scales to a manifest
    generator of any length.
    """
    counts: Counter[str] = Counter()
    for record in records:
        counts[record["label"]] += 1
    return counts


def chain_iterables(*iterables: Iterable[T]) -> Iterator[T]:
    """Thin wrapper documenting the `chain` usage point for multi-root streams."""
    return chain(*iterables)
