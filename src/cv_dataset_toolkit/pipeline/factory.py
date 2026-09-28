"""Builds a `Pipeline` from a validated `PipelineConfig`.

Replaces the CLI's old by-hand transform wiring: once a `PipelineConfig` has
passed Pydantic validation, this is the single place that turns its fields
into concrete `Transform` steps.
"""

from __future__ import annotations

from cv_dataset_toolkit.config.models import PipelineConfig
from cv_dataset_toolkit.pipeline.pipeline import Pipeline
from cv_dataset_toolkit.pipeline.transforms import (
    DropDuplicates,
    FilterByFormat,
    FilterMinSize,
    Transform,
)


def build_pipeline(config: PipelineConfig) -> Pipeline:
    steps: list[Transform] = []
    if config.formats:
        steps.append(FilterByFormat(config.formats))
    if config.min_size is not None:
        steps.append(FilterMinSize(*config.min_size))
    if config.dedupe:
        steps.append(DropDuplicates())
    return Pipeline(steps)
