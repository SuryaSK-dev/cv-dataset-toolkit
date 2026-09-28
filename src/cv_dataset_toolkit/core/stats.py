"""Generator-based coroutine for streaming statistics.

`running_stats()` is a generator used as a *coroutine*: instead of pulling
values out with `next()`, the caller pushes values in with `.send(value)`.
Each `.send()` resumes the generator right after its `yield` expression,
lets it update running totals, and then blocks again at the next `yield`
until the caller sends the next value (or closes it).

Usage:
    stats = running_stats()
    next(stats)               # priming: advances to the first `yield`,
                               # required before the first real .send()
    stats.send(record)        # returns a live snapshot
    ...
    stats.close()             # ends the coroutine; further .send() raises
                               # StopIteration
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TypedDict

from cv_dataset_toolkit.core.record import ImageRecord


class StatsSnapshot(TypedDict):
    count: int
    mean_width: float
    mean_height: float
    min_size_bytes: int | None
    max_size_bytes: int | None


def running_stats() -> Generator[StatsSnapshot, ImageRecord, None]:
    count = 0
    width_sum = 0
    height_sum = 0
    min_size: int | None = None
    max_size: int | None = None

    snapshot: StatsSnapshot = {
        "count": 0,
        "mean_width": 0.0,
        "mean_height": 0.0,
        "min_size_bytes": None,
        "max_size_bytes": None,
    }

    try:
        while True:
            record = yield snapshot
            count += 1
            width_sum += record.width
            height_sum += record.height
            size = record.size_bytes
            min_size = size if min_size is None else min(min_size, size)
            max_size = size if max_size is None else max(max_size, size)

            snapshot = {
                "count": count,
                "mean_width": width_sum / count,
                "mean_height": height_sum / count,
                "min_size_bytes": min_size,
                "max_size_bytes": max_size,
            }
    except GeneratorExit:
        # Raised inside the generator when .close() is called; no cleanup
        # needed here, but the handler documents that this is the hook
        # point for it (e.g. flushing a file, releasing a lock).
        return
