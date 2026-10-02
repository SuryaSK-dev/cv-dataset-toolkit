"""Context managers for resource management, timing, atomic writes, and environment isolation.

Provides both generator-based (`@contextlib.contextmanager`) and class-based
(`__enter__` / `__exit__`) context managers:
1. `timer(label)`: lightweight `@contextlib.contextmanager` that prints/logs elapsed time.
2. `Stopwatch`: class-based context manager exposing live and post-exit `.elapsed`.
3. `atomic_write(path)`: writes to a staging file in the same directory, replacing the
   target on success and unlinking on error.
4. `temporary_env(**vars)`: safely sets or unsets env vars, restoring them on exit.
5. `multi_atomic_write(paths)`: uses `ExitStack` to manage multiple atomic writes at once.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from types import TracebackType
from typing import Self, TextIO, cast

from cv_dataset_toolkit.core.types import PathLike

# --------------------------------------------------------------------------
# 1. Generator-based context manager: timer(label)
# --------------------------------------------------------------------------


@contextlib.contextmanager
def timer(label: str = "timer") -> Iterator[None]:
    """Measure and print elapsed wall time for the enclosed block.

    Always reports elapsed time in a `try/finally` block even if the enclosed
    code raises an exception.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"[{label}] elapsed: {elapsed:.4f}s")


# --------------------------------------------------------------------------
# 2. Class-based context manager: Stopwatch
# --------------------------------------------------------------------------


class Stopwatch:
    """Class-based context manager tracking elapsed time with live inspection.

    Unlike `timer()`, `Stopwatch` exposes an `.elapsed` property that can be
    read both *during* the `with` block (running time) and *after* exit (total time).
    """

    def __init__(self, label: str | None = None) -> None:
        self.label = label
        self._start: float | None = None
        self._end: float | None = None

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds.

        Returns 0.0 before entering, live elapsed time while inside the block,
        or the final duration once the block exits.
        """
        if self._start is None:
            return 0.0
        if self._end is None:
            return time.perf_counter() - self._start
        return self._end - self._start

    def __enter__(self) -> Self:
        self._start = time.perf_counter()
        self._end = None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._end = time.perf_counter()


# --------------------------------------------------------------------------
# 3. atomic_write
# --------------------------------------------------------------------------


@contextlib.contextmanager
def atomic_write(
    path: PathLike,
    mode: str = "w",
    encoding: str | None = "utf-8",
    newline: str | None = None,
) -> Iterator[TextIO]:
    """Atomically write to `path` using a temporary staging file.

    Writes to a temporary file in the same directory as `path` (ensuring same-filesystem
    semantics for atomic renaming). Upon successful completion, the staging file is
    closed and atomically moved into place with `os.replace`.

    If an exception occurs within the block, the staging file is closed and unlinked,
    leaving the original destination file (if any) untouched and preventing partial
    or corrupted writes.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Place temp file in same directory so os.replace is an atomic rename.
    # Note: Closed explicitly before os.replace to prevent Windows sharing violations.
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
        dir=dest.parent,
        prefix=f".{dest.name}.",
        suffix=".tmp",
        mode=mode,
        encoding=encoding,
        newline=newline,
        delete=False,
    )
    tmp_path = Path(tmp.name)
    try:
        yield cast(TextIO, tmp)
        tmp.flush()
        tmp.close()
        os.replace(tmp_path, dest)
    except BaseException:
        tmp.close()
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise


# --------------------------------------------------------------------------
# 4. temporary_env
# --------------------------------------------------------------------------


@contextlib.contextmanager
def temporary_env(**vars: str | None) -> Iterator[None]:
    """Temporarily set or unset environment variables within a `with` block.

    Restores previous values upon exit (or deletes keys that were originally unset),
    even if an exception occurs.
    """
    previous: dict[str, str | None] = {key: os.environ.get(key) for key in vars}
    try:
        for key, val in vars.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(val)
        yield
    finally:
        for key, old_val in previous.items():
            if old_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_val


# --------------------------------------------------------------------------
# 5. multi_atomic_write (ExitStack usage)
# --------------------------------------------------------------------------


@contextlib.contextmanager
def multi_atomic_write(
    paths: Iterable[PathLike],
    mode: str = "w",
    encoding: str | None = "utf-8",
    newline: str | None = None,
) -> Iterator[list[TextIO]]:
    """Open multiple atomic write file handles concurrently using `contextlib.ExitStack`.

    Ensures that if any file fails to open or write, all already-opened temporary files
    are closed and cleaned up safely.
    """
    with contextlib.ExitStack() as stack:
        handles = [
            stack.enter_context(atomic_write(p, mode=mode, encoding=encoding, newline=newline))
            for p in paths
        ]
        yield handles
