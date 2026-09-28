"""Demonstrates composing Pipelines with `|` and `.then()`.

Also proves (by catching the TypeError) that `Transform` cannot be
instantiated directly — it's an ABC with an abstract `apply()`.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from cv_dataset_toolkit.core.metadata import iter_metadata
from cv_dataset_toolkit.io.walker import iter_image_paths
from cv_dataset_toolkit.pipeline.pipeline import Pipeline, PipelineStats
from cv_dataset_toolkit.pipeline.transforms import (
    AddAspectBucket,
    FilterByFormat,
    FilterMinSize,
    NormalizeLabel,
    Transform,
)

SAMPLE_ROOT = Path(__file__).resolve().parent.parent / "sample_data"


def main() -> None:
    if not SAMPLE_ROOT.exists():
        raise SystemExit(
            f"sample dataset not found at {SAMPLE_ROOT}; run make_sample_dataset.py first"
        )

    # Compose with the `|` operator (Transform | Transform | Transform).
    piped_pipeline = FilterByFormat({"JPEG", "PNG"}) | FilterMinSize(16, 16) | NormalizeLabel()
    print("piped_pipeline:", repr(piped_pipeline))
    print("len(piped_pipeline):", len(piped_pipeline))

    # Compose with the fluent, immutable `.then()` — each call returns a
    # NEW Pipeline, the original is untouched.
    base = Pipeline([FilterByFormat({"JPEG", "PNG"})])
    extended = base.then(FilterMinSize(16, 16)).then(AddAspectBucket())
    print("base:", repr(base), "len:", len(base))
    print("extended:", repr(extended), "len:", len(extended))
    assert len(base) == 1, "base must be unaffected by .then() on the derived pipeline"

    # Pipeline | Pipeline composition.
    combined = piped_pipeline | Pipeline([AddAspectBucket()])
    print("combined:", repr(combined))

    # Run it, lazily, over the sample dataset, tracking per-step stats.
    stats = PipelineStats()
    records = iter_metadata(iter_image_paths(SAMPLE_ROOT))
    results = combined.run(records, stats)
    assert inspect.isgenerator(results), "Pipeline.run must return a generator"

    count = sum(1 for _ in results)
    print(f"\nrecords surviving the pipeline: {count}")
    print("\npipeline stats:")
    print(stats.table())

    # Transform is an ABC; instantiating it directly must fail.
    try:
        Transform()  # type: ignore[abstract]
    except TypeError as exc:
        print(f"\nTransform() correctly raised TypeError: {exc}")
    else:
        raise AssertionError("Transform() should not be instantiable")


if __name__ == "__main__":
    main()
