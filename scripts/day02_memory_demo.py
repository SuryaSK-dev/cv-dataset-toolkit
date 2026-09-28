"""Compare peak memory of a list-based scan vs the lazy generator pipeline.

Uses `tracemalloc` to measure peak memory while walking the *same* stream
of paths two ways:
  1. list-based: `list(iter_image_paths(root))` materializes every path
     up front before any processing happens.
  2. generator-based: `iter_image_paths(root)` is consumed one path at a
     time and immediately discarded.

To make the difference visible on a tiny sample dataset, the walk is
repeated `DUPLICATE_FACTOR` times over synthetic extra roots pointing at
the same folder, simulating a much larger dataset without touching disk
generation code.
"""

from __future__ import annotations

import tracemalloc
from itertools import chain
from pathlib import Path

from cv_dataset_toolkit.io.walker import iter_image_paths

SAMPLE_ROOT = Path(__file__).resolve().parent.parent / "sample_data"
DUPLICATE_FACTOR = 200  # simulates a dataset ~200x larger than the tiny sample


def list_based_peak() -> int:
    tracemalloc.start()
    tracemalloc.clear_traces()

    all_paths = list(
        chain.from_iterable(iter_image_paths(SAMPLE_ROOT) for _ in range(DUPLICATE_FACTOR))
    )
    _ = len(all_paths)  # force materialization to stay referenced

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def generator_based_peak() -> tuple[int, int]:
    tracemalloc.start()
    tracemalloc.clear_traces()

    count = 0
    for _ in chain.from_iterable(iter_image_paths(SAMPLE_ROOT) for _ in range(DUPLICATE_FACTOR)):
        count += 1  # each path is discarded immediately after counting

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak, count


def main() -> None:
    if not SAMPLE_ROOT.exists():
        raise SystemExit(
            f"sample dataset not found at {SAMPLE_ROOT}; run make_sample_dataset.py first"
        )

    list_peak = list_based_peak()
    gen_peak, gen_count = generator_based_peak()

    print(f"paths processed per approach: {gen_count}")
    print(f"list-based peak memory:      {list_peak:,} bytes")
    print(f"generator-based peak memory: {gen_peak:,} bytes")
    reduction_pct = (1 - gen_peak / list_peak) * 100
    print(f"reduction: {list_peak - gen_peak:,} bytes ({reduction_pct:.1f}% less)")


if __name__ == "__main__":
    main()
