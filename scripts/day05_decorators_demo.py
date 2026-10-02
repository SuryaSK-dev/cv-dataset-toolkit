"""Demonstrates Day 5: decorators, context managers, failure paths, and resource safety.

Covers:
  1. @timed and TimingRegistry (functions + generator functions)
  2. @retry with exponential backoff, success recovery, exhaustion, and non-matching exceptions
  3. @memoize LRU cache (hits, misses, evictions, cache_clear, unhashable args handling)
  4. @deprecated emitting DeprecationWarning with stacklevel pointing to caller
  5. timer() context manager (success & exception paths)
  6. Stopwatch class-based context manager (.elapsed live and post-exit)
  7. atomic_write staging + atomic rename (crash leaves no partial or corrupted file)
  8. temporary_env environment isolation and restoration
  9. multi_atomic_write and ExitStack (opening multiple atomic files at once)
"""

from __future__ import annotations

import tempfile
import time
import warnings
from collections.abc import Iterator
from pathlib import Path

from cv_dataset_toolkit.core.record import ImageRecord
from cv_dataset_toolkit.io.exporters import MultiExporter
from cv_dataset_toolkit.utils.contexts import (
    Stopwatch,
    atomic_write,
    multi_atomic_write,
    temporary_env,
    timer,
)
from cv_dataset_toolkit.utils.decorators import (
    DEFAULT_TIMING_REGISTRY,
    TimingRegistry,
    deprecated,
    memoize,
    retry,
    timed,
)


def demo_timed_and_registry() -> None:
    print("=== 1. @timed and TimingRegistry ===")
    assert isinstance(DEFAULT_TIMING_REGISTRY, TimingRegistry)
    custom_reg = TimingRegistry()
    custom_reg.record("custom_task", 0.042)
    assert custom_reg.get("custom_task") is not None
    DEFAULT_TIMING_REGISTRY.clear()

    @timed
    def compute_squares(n: int) -> int:
        """Standard function timing."""
        time.sleep(0.01)
        return sum(i * i for i in range(n))

    @timed
    def stream_items(count: int) -> Iterator[int]:
        """Generator function: clock runs during iteration, not generator creation."""
        for i in range(count):
            time.sleep(0.005)
            yield i

    # Call regular function
    ans = compute_squares(100)
    print(f"compute_squares result: {ans}")

    # Call generator function and consume lazily
    items = list(stream_items(4))
    print(f"stream_items result: {items}")

    table = DEFAULT_TIMING_REGISTRY.table()
    print("\nTiming Registry Table:")
    print(table)

    assert "compute_squares" in table
    assert "stream_items" in table
    print("[OK] @timed successfully measured function and lazy generator execution")


def demo_retry_decorator() -> None:
    print("\n=== 2. @retry Decorator & Exponential Backoff ===")

    # Path A: Recovers after 2 failures on attempt 3
    calls = 0

    @retry(attempts=3, delay=0.01, backoff=2.0, exceptions=(IOError,))
    def flaky_network_read() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError(f"Transient socket timeout (attempt {calls})")
        return "payload-data"

    result = flaky_network_read()
    print(f"flaky_network_read succeeded: '{result}' after {calls} attempts")
    assert result == "payload-data"
    assert calls == 3

    # Path B: Exhausting all attempts raises the final exception
    exhaust_calls = 0

    @retry(attempts=3, delay=0.01, backoff=2.0, exceptions=(ValueError,))
    def always_failing() -> None:
        nonlocal exhaust_calls
        exhaust_calls += 1
        raise ValueError(f"Permanent failure at attempt {exhaust_calls}")

    try:
        always_failing()
    except ValueError as exc:
        print(f"Expected exhausted retry caught: '{exc}' (attempts made: {exhaust_calls})")
        assert exhaust_calls == 3
        assert "Permanent failure at attempt 3" in str(exc)
    else:
        raise AssertionError("Expected always_failing to raise ValueError")

    # Path C: Unlisted exception raises immediately without retry
    unlisted_calls = 0

    @retry(attempts=3, delay=0.01, backoff=2.0, exceptions=(OSError,))
    def wrong_exception() -> None:
        nonlocal unlisted_calls
        unlisted_calls += 1
        raise KeyError("Unlisted exception type")

    try:
        wrong_exception()
    except KeyError:
        print(f"Unlisted exception propagated immediately on attempt {unlisted_calls}")
        assert unlisted_calls == 1
    else:
        raise AssertionError("Expected wrong_exception to propagate KeyError")

    print("[OK] @retry verified: transient recovery, exhaustion re-raise, unlisted propagation")


def demo_memoize_decorator() -> None:
    print("\n=== 3. @memoize LRU Cache ===")

    evaluations = 0

    @memoize(maxsize=3)
    def compute_expensive(a: int, b: int) -> int:
        nonlocal evaluations
        evaluations += 1
        return a * 10 + b

    # Misses
    assert compute_expensive(1, 2) == 12  # miss 1
    assert compute_expensive(2, 3) == 23  # miss 2
    assert compute_expensive(3, 4) == 34  # miss 3
    assert evaluations == 3

    # Hits
    assert compute_expensive(1, 2) == 12  # hit 1
    assert compute_expensive(2, 3) == 23  # hit 2
    assert evaluations == 3

    info = compute_expensive.cache_info()
    print(f"CacheInfo after hits/misses: {info}")
    assert info.hits == 2
    assert info.misses == 3
    assert info.size == 3
    assert info.maxsize == 3

    # LRU Eviction: calling with key 4 evicts key (3, 4) because (1, 2) and (2, 3) were accessed
    compute_expensive(4, 5)  # miss 4, evicts (3, 4)
    info2 = compute_expensive.cache_info()
    assert info2.size == 3
    assert info2.misses == 4

    # Calling (3, 4) again causes a miss
    compute_expensive(3, 4)
    assert compute_expensive.cache_info().misses == 5

    # cache_clear()
    compute_expensive.cache_clear()
    cleared_info = compute_expensive.cache_info()
    print(f"CacheInfo after cache_clear: {cleared_info}")
    assert cleared_info.hits == 0
    assert cleared_info.misses == 0
    assert cleared_info.size == 0

    # Unhashable argument error handling
    @memoize(maxsize=4)
    def process_data(data: object) -> str:
        return str(data)

    try:
        process_data([1, 2, 3])  # list is unhashable
    except TypeError as exc:
        print(f"Caught expected unhashable argument error: {exc}")
        assert "all arguments must be hashable" in str(exc)
    else:
        raise AssertionError("Expected TypeError for unhashable argument")

    print("[OK] @memoize verified: hit/miss accounting, LRU eviction, clear, unhashable handling")


def demo_deprecated_decorator() -> None:
    print("\n=== 4. @deprecated Warning ===")

    @deprecated("use compute_v2() instead")
    def old_compute(x: int) -> int:
        return x * 2

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", DeprecationWarning)
        ans = old_compute(21)
        assert ans == 42
        assert len(captured) == 1
        w = captured[0]
        assert issubclass(w.category, DeprecationWarning)
        assert "old_compute is deprecated: use compute_v2() instead" in str(w.message)
        # Verify stacklevel=2 points to this caller file, not inside decorators.py
        assert Path(w.filename).name == "day05_decorators_demo.py"
        print(f"Captured DeprecationWarning: {w.message} (from {Path(w.filename).name}:{w.lineno})")

    print("[OK] @deprecated verified with stacklevel attribution")


def demo_timer_context() -> None:
    print("\n=== 5. timer() Context Manager ===")
    print("Normal run:")
    with timer("sample_step"):
        time.sleep(0.01)

    print("Exception run (timer still prints elapsed in finally block):")
    try:
        with timer("failing_step"):
            time.sleep(0.005)
            raise RuntimeError("Deliberate failure inside timer")
    except RuntimeError as exc:
        print(f"Caught error as expected: {exc}")

    print("[OK] timer() executed try/finally reporting on success and error")


def demo_stopwatch_context() -> None:
    print("\n=== 6. Stopwatch Class-Based Context Manager ===")
    sw = Stopwatch("bench")
    assert sw.elapsed == 0.0

    with sw:
        time.sleep(0.02)
        live = sw.elapsed
        assert live > 0.0
        print(f"Stopwatch live reading during execution: {live:.4f}s")
        time.sleep(0.01)

    final = sw.elapsed
    print(f"Stopwatch post-exit elapsed reading:     {final:.4f}s")
    assert final >= live
    assert final > 0.02

    print("[OK] Stopwatch verified: .elapsed accessible during and after context")


def demo_atomic_write() -> None:
    print("\n=== 7. atomic_write Resource Safety ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "output_manifest.csv"

        # Path A: Successful atomic write
        with atomic_write(target_path) as f:
            f.write("id,name\n1,cat\n")
        assert target_path.exists()
        assert target_path.read_text(encoding="utf-8") == "id,name\n1,cat\n"
        print(f"Successful write created: {target_path.name}")

        # Path B: Crashed write on a non-existent file leaves no partial file
        crashed_new_path = Path(tmp_dir) / "crashed_new.csv"
        try:
            with atomic_write(crashed_new_path) as f:
                f.write("half-written garbage that should be aborted")
                raise RuntimeError("Disk error / scan crash midway!")
        except RuntimeError:
            pass

        assert not crashed_new_path.exists(), "Target file must NOT exist after crash!"
        tmp_files = list(Path(tmp_dir).glob(".*.tmp"))
        assert len(tmp_files) == 0, "No staging .tmp files should linger after crash!"
        print("Crashed write on new file: target and temp staging file cleaned up")

        # Path C: Crashed write over an existing file leaves original file intact
        try:
            with atomic_write(target_path) as f:
                f.write("corrupt replacement that crashes before completing")
                raise RuntimeError("Crash during overwrite")
        except RuntimeError:
            pass

        assert target_path.read_text(encoding="utf-8") == "id,name\n1,cat\n"
        print("Crashed overwrite on existing file: original contents remained completely intact")

    print("[OK] atomic_write verified for atomic replacement and crash safety")


def demo_temporary_env() -> None:
    print("\n=== 8. temporary_env Isolation ===")
    import os

    os.environ["CVTK_TEST_VAR"] = "original_val"
    os.environ.pop("CVTK_TEMP_NEW", None)

    with temporary_env(CVTK_TEST_VAR="overridden", CVTK_TEMP_NEW="brand_new"):
        assert os.environ["CVTK_TEST_VAR"] == "overridden"
        assert os.environ["CVTK_TEMP_NEW"] == "brand_new"
        print(f"Inside temporary_env: CVTK_TEST_VAR={os.environ['CVTK_TEST_VAR']}")

    assert os.environ["CVTK_TEST_VAR"] == "original_val"
    assert "CVTK_TEMP_NEW" not in os.environ
    print(f"After temporary_env:  CVTK_TEST_VAR={os.environ['CVTK_TEST_VAR']}")

    # Exception safety
    try:
        with temporary_env(CVTK_TEST_VAR="exception_val"):
            raise ValueError("Crash inside env block")
    except ValueError:
        pass

    assert os.environ["CVTK_TEST_VAR"] == "original_val"
    del os.environ["CVTK_TEST_VAR"]

    print("[OK] temporary_env restored environment variables on exit and error")


def demo_exitstack_and_multi_exporter() -> None:
    print("\n=== 9. contextlib.ExitStack & MultiExporter ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "multi.csv"
        jsonl_path = Path(tmp_dir) / "multi.jsonl"

        records = [
            ImageRecord(
                path="sample/cat_01.jpg",
                label="cat",
                format="JPEG",
                size_bytes=1200,
                width=32,
                height=32,
            ),
            ImageRecord(
                path="sample/dog_01.png",
                label="dog",
                format="PNG",
                size_bytes=2400,
                width=64,
                height=64,
            ),
        ]

        # MultiExporter uses ExitStack internally to open both atomic_write destinations
        multi_exporter = MultiExporter([("csv", csv_path), ("jsonl", jsonl_path)])
        count = multi_exporter.export(records)
        assert count == 2
        assert csv_path.exists()
        assert jsonl_path.exists()
        print(f"MultiExporter wrote {count} records across CSV and JSONL using ExitStack")

        # multi_atomic_write direct ExitStack test
        file1 = Path(tmp_dir) / "f1.txt"
        file2 = Path(tmp_dir) / "f2.txt"
        with multi_atomic_write([file1, file2]) as handles:
            assert len(handles) == 2
            handles[0].write("hello file 1")
            handles[1].write("hello file 2")

        assert file1.read_text(encoding="utf-8") == "hello file 1"
        assert file2.read_text(encoding="utf-8") == "hello file 2"
        print("multi_atomic_write opened and committed multiple handles with ExitStack")

    print("[OK] ExitStack resource management verified")


def main() -> None:
    print("=" * 60)
    print(" DAY 5 DEMO: Decorators & Context Managers Verification")
    print("=" * 60)
    demo_timed_and_registry()
    demo_retry_decorator()
    demo_memoize_decorator()
    demo_deprecated_decorator()
    demo_timer_context()
    demo_stopwatch_context()
    demo_atomic_write()
    demo_temporary_env()
    demo_exitstack_and_multi_exporter()
    print("\n" + "=" * 60)
    print(" ALL DAY 5 DEMOS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
