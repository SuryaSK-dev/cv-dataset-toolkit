"""Typed, reusable decorators: timing, retry, memoization, deprecation.

Decorator Architecture
----------------------
1. Plain Function Decorator:
   Takes a callable and returns a callable (`Callable[P, R] -> Callable[P, R]`).
   Used without arguments:
       @timed
       def func(...) -> ...: ...

2. Decorator Factory:
   A function that accepts configuration arguments and returns an actual decorator:
       def retry(attempts=3, ...) -> Callable[[Callable[P, R]], Callable[P, R]]: ...
   Applied with parentheses:
       @retry(attempts=3)
       def flaky(...) -> ...: ...

3. Class-Based Decorator:
   A class defining `__call__` (or `__init__` + `__call__`). It can cleanly store state
   on `self`, but if applied to methods it must implement the descriptor protocol
   (`__get__`) to bind the instance (`self`) correctly upon invocation.

Why `functools.wraps` Matters
-----------------------------
A naive decorator replaces the target function with an inner `wrapper` closure.
Without `functools.wraps`, standard attributes like `__name__`, `__doc__`, `__module__`,
`__qualname__`, and `__annotations__` are overwritten with the wrapper's own metadata.
`functools.wraps` copies these attributes and assigns `__wrapped__`, preserving function
identity for debugging, logging, documentation generators, and inspection utilities like
`inspect.isgeneratorfunction`.

Stacking Order
--------------
Decorators apply bottom-up (closest to `def` first) but execute outside-in:
    @classmethod
    @retry(attempts=3, exceptions=(OSError,))
    def from_path(cls, path): ...

Here, `@retry(...)` wraps the raw function first, and `@classmethod` then wraps the
retrying callable. When called, `@retry` catches transient errors and retries before
returning.
"""

from __future__ import annotations

import functools
import inspect
import time
import warnings
from collections import OrderedDict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Final, NamedTuple, ParamSpec, Protocol, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")
R_co = TypeVar("R_co", covariant=True)


# --------------------------------------------------------------------------
# @timed
# --------------------------------------------------------------------------


@dataclass
class _FunctionTiming:
    call_count: int = 0
    total_time: float = 0.0
    max_time: float = 0.0

    def record(self, elapsed: float) -> None:
        self.call_count += 1
        self.total_time += elapsed
        self.max_time = max(self.max_time, elapsed)

    @property
    def mean_time(self) -> float:
        return self.total_time / self.call_count if self.call_count else 0.0


class TimingRegistry:
    """Per-function call count / total / mean / max wall time, keyed by `__qualname__`."""

    def __init__(self) -> None:
        self._timings: dict[str, _FunctionTiming] = {}

    def record(self, name: str, elapsed: float) -> None:
        self._timings.setdefault(name, _FunctionTiming()).record(elapsed)

    def clear(self) -> None:
        self._timings.clear()

    def get(self, name: str) -> _FunctionTiming | None:
        return self._timings.get(name)

    def table(self) -> str:
        if not self._timings:
            return "(no timed calls)"
        header = f"{'function':<32}{'calls':>7}{'total(s)':>10}{'mean(s)':>10}{'max(s)':>10}"
        lines = [header, "-" * len(header)]
        for name, timing in sorted(self._timings.items()):
            lines.append(
                f"{name:<32}{timing.call_count:>7}{timing.total_time:>10.4f}"
                f"{timing.mean_time:>10.4f}{timing.max_time:>10.4f}"
            )
        return "\n".join(lines)


DEFAULT_TIMING_REGISTRY: Final[TimingRegistry] = TimingRegistry()


def timed(func: Callable[P, R]) -> Callable[P, R]:
    """Record `func`'s wall time into `DEFAULT_TIMING_REGISTRY`.

    Pitfall this handles: a generator *function* returns its generator
    object immediately, without running any of its body — a naive
    `start = perf_counter(); func(...); record(perf_counter() - start)`
    around a generator function would only time object creation (near
    zero), not the actual work, which happens lazily as the caller
    iterates. We detect this with `inspect.isgeneratorfunction` and instead
    wrap the *iteration*: the clock starts when the first item is pulled
    and stops once the generator is exhausted (or closed/GC'd early).
    """
    name = func.__qualname__

    if inspect.isgeneratorfunction(func):

        @functools.wraps(func)
        def gen_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            def timed_iteration() -> Iterator[object]:
                start = time.perf_counter()
                try:
                    gen = cast(Iterable[object], func(*args, **kwargs))
                    yield from gen
                finally:
                    DEFAULT_TIMING_REGISTRY.record(name, time.perf_counter() - start)

            return cast(R, timed_iteration())

        return gen_wrapper

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            DEFAULT_TIMING_REGISTRY.record(name, time.perf_counter() - start)

    return wrapper


# --------------------------------------------------------------------------
# @retry(...)
# --------------------------------------------------------------------------


def retry(
    attempts: int = 3,
    delay: float = 0.05,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    *,
    times: int | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator factory: retry `func` up to `attempts` with exponential backoff.

    Re-raises the *last* exception once attempts are exhausted (the caller
    sees the final failure, not the first). `.attempts` on the wrapped
    function reports how many attempts the most recent call took.
    Only retries exceptions listed in `exceptions`.
    """
    total_attempts = times if times is not None else attempts
    if total_attempts < 1:
        raise ValueError("attempts must be >= 1")

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            current_delay = delay
            last_exc: BaseException | None = None
            for attempt in range(1, total_attempts + 1):
                wrapper.attempts = attempt  # type: ignore[attr-defined]
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == total_attempts:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff
            assert last_exc is not None
            raise last_exc

        wrapper.attempts = 0  # type: ignore[attr-defined]
        return wrapper

    return decorator


# --------------------------------------------------------------------------
# @memoize(...)
# --------------------------------------------------------------------------


class CacheInfo(NamedTuple):
    hits: int
    misses: int
    size: int
    maxsize: int


class _MemoizedCallable(Protocol[P, R_co]):
    """A callable that also exposes LRU cache introspection, like `functools.lru_cache`."""

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R_co: ...

    def cache_info(self) -> CacheInfo: ...

    def cache_clear(self) -> None: ...


def memoize(maxsize: int = 128) -> Callable[[Callable[P, R]], _MemoizedCallable[P, R]]:
    """Own least-recently-used cache, via `OrderedDict.move_to_end`.

    Compared to `functools.lru_cache`/`functools.cache`: those are
    C-accelerated, thread-safe, and battle-tested — use them in real
    production code. This hand-rolled version exists to show the mechanism
    `lru_cache` hides behind its C implementation: an ordered mapping where
    a cache hit moves its key to the "most recently used" end, and a full
    cache evicts from the "least recently used" end.

    Unhashable arguments trigger a clear `TypeError` explaining that the arguments
    cannot be hashed for caching.
    """
    if maxsize < 1:
        raise ValueError("maxsize must be >= 1")

    def decorator(func: Callable[P, R]) -> _MemoizedCallable[P, R]:
        cache: OrderedDict[tuple[object, ...], R] = OrderedDict()
        hits = 0
        misses = 0

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal hits, misses
            key = (args, tuple(sorted(kwargs.items())))
            try:
                hash(key)
            except TypeError as exc:
                raise TypeError(
                    f"Cannot memoize call to '{func.__qualname__}': "
                    f"all arguments must be hashable. Cause: {exc}"
                ) from exc

            if key in cache:
                cache.move_to_end(key)
                hits += 1
                return cache[key]
            misses += 1
            result = func(*args, **kwargs)
            cache[key] = result
            if len(cache) > maxsize:
                cache.popitem(last=False)
            return result

        def cache_info() -> CacheInfo:
            return CacheInfo(hits=hits, misses=misses, size=len(cache), maxsize=maxsize)

        def cache_clear() -> None:
            nonlocal hits, misses
            cache.clear()
            hits = 0
            misses = 0

        wrapper.cache_info = cache_info  # type: ignore[attr-defined]
        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return cast("_MemoizedCallable[P, R]", wrapper)

    return decorator


# --------------------------------------------------------------------------
# @deprecated(...)
# --------------------------------------------------------------------------


def deprecated(reason: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Emit a `DeprecationWarning` naming `reason` every time the function is called.

    Python 3.13 adds `warnings.deprecated` (PEP 702), which does this plus
    lets static checkers flag call sites directly. This project targets
    3.11, so this implements just the runtime-warning half by hand.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        message = f"{func.__qualname__} is deprecated: {reason}"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            warnings.warn(message, category=DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper

    return decorator
