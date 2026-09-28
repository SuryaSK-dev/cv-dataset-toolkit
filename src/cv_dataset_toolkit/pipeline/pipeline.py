"""`Pipeline`: an ordered, composable, lazily-run sequence of `Transform` steps."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Self, overload

from cv_dataset_toolkit.core.protocols import RecordSource
from cv_dataset_toolkit.core.record import ImageRecord
from cv_dataset_toolkit.pipeline.transforms import Transform


@dataclass
class PipelineStats:
    """Per-step counters, filled in as records stream through `Pipeline.run`."""

    seen: dict[str, int] = field(default_factory=dict)
    passed: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, int] = field(default_factory=dict)

    def record(self, step_name: str, kept: bool) -> None:
        self.seen[step_name] = self.seen.get(step_name, 0) + 1
        bucket = self.passed if kept else self.dropped
        bucket[step_name] = bucket.get(step_name, 0) + 1

    def table(self) -> str:
        if not self.seen:
            return "(no records reached any step)"
        header = f"{'step':<20}{'seen':>8}{'passed':>8}{'dropped':>9}"
        lines = [header, "-" * len(header)]
        for step_name, seen in self.seen.items():
            passed = self.passed.get(step_name, 0)
            dropped = self.dropped.get(step_name, 0)
            lines.append(f"{step_name:<20}{seen:>8}{passed:>8}{dropped:>9}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.table()


class Pipeline:
    """A composable chain of `Transform` steps, run lazily over a record stream."""

    def __init__(self, steps: Iterable[Transform] = ()) -> None:
        self._steps: tuple[Transform, ...] = tuple(steps)

    def then(self, step: Transform) -> Self:
        """Return a *new* Pipeline with `step` appended. Does not mutate `self`."""
        return type(self)((*self._steps, step))

    def run(
        self,
        records: RecordSource,
        stats: PipelineStats | None = None,
    ) -> Iterator[ImageRecord]:
        """Yield records that survive every step, in order.

        A generator: nothing is buffered. Each record is pulled from
        `records`, pushed through the steps one at a time, and dropped
        (via `None`) or yielded immediately — the stream never
        materializes as a list, preserving Day 2's memory guarantees.
        """
        for record in records:
            current: ImageRecord | None = record
            for step in self._steps:
                if current is None:
                    break
                result = step(current)
                if stats is not None:
                    stats.record(step.name, kept=result is not None)
                current = result
            if current is not None:
                yield current

    def __len__(self) -> int:
        return len(self._steps)

    def __iter__(self) -> Iterator[Transform]:
        return iter(self._steps)

    def __getitem__(self, index: int) -> Transform:
        return self._steps[index]

    def __repr__(self) -> str:
        steps_repr = " | ".join(repr(step) for step in self._steps)
        return f"Pipeline({steps_repr})" if steps_repr else "Pipeline()"

    @overload
    def __or__(self, other: Transform) -> Pipeline: ...
    @overload
    def __or__(self, other: Pipeline) -> Pipeline: ...
    def __or__(self, other: Transform | Pipeline) -> Pipeline:
        if isinstance(other, Pipeline):
            return Pipeline((*self._steps, *other._steps))
        if isinstance(other, Transform):
            return Pipeline((*self._steps, other))
        return NotImplemented
