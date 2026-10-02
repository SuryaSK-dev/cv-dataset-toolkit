# cv-dataset-toolkit

A small, well-engineered Python package that scans an image dataset folder,
extracts metadata (path, size, dimensions, format, label from folder name),
validates it, runs configurable transform steps, and exports a clean CSV/JSON
manifest. Built incrementally as a 15-day pre-internship engineering tracker.

## Quick Start

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
cv-dataset-toolkit --version
cv-dataset-toolkit scan ./datasets/sample
```

## Progress

| Day | Topic                        | Status | Tag     |
|-----|-------------------------------|--------|---------|
| 1   | Env Setup                     | ✅     | day-01  |
| 2   | Iterators & Generators        | ✅     | day-02  |
| 3   | OOP / Pipeline                | ✅     | day-03  |
| 4   | Type Hints / Pydantic         | ✅     | day-04  |
| 5   | Decorators / Context Managers | ✅     | day-05  |
| 6   | Exceptions                    | ⬜     |         |
| 7   | Logging                       | ⬜     |         |
| 8   | SOLID Refactor                | ⬜     |         |
| 9   | Testing                       | ⬜     |         |

## Project Structure

```
cv-dataset-toolkit/
├── src/
│   └── cv_dataset_toolkit/
│       ├── __init__.py
│       ├── py.typed             # PEP 561 marker: this package ships type hints
│       ├── cli.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── record.py        # ImageRecord: frozen, slotted dataclass
│       │   ├── metadata.py      # iter_metadata: streaming metadata extraction
│       │   ├── stats.py         # running_stats: send()-based coroutine, StatsSnapshot
│       │   ├── types.py         # TypeAlias: PathLike, OutputFormat, AspectBucket
│       │   └── protocols.py     # RecordSource (Protocol)
│       ├── config/
│       │   ├── __init__.py
│       │   ├── models.py        # OutputConfig, PipelineConfig (Pydantic v2)
│       │   └── loader.py        # load_config: YAML + env + CLI precedence
│       ├── io/
│       │   ├── __init__.py
│       │   ├── walker.py        # iter_image_paths, iter_many_roots
│       │   ├── dataset.py       # ImageFolder, ImageFolderIterator
│       │   ├── export.py        # write_manifest_csv
│       │   ├── exporters.py     # Exporter ABC: CSVExporter, JSONLinesExporter, MultiExporter
│       │   └── manifest.py      # ManifestRow (Pydantic), validate_manifest_csv
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── transforms.py    # Transform/Filter/Mapper ABCs + concrete transforms
│       │   ├── pipeline.py      # Pipeline (composable via | and .then()), PipelineStats
│       │   └── factory.py       # build_pipeline(config) -> Pipeline
│       └── utils/
│           ├── __init__.py
│           ├── contexts.py      # timer, Stopwatch, atomic_write, temporary_env, multi_atomic_write
│           ├── decorators.py    # @timed, @retry, @memoize, @deprecated, TimingRegistry
│           └── iterutils.py     # batched, take, count_by_label
├── configs/
│   └── default.yaml             # committed default scan configuration
├── docs/
│   └── config.schema.json       # PipelineConfig.model_json_schema()
├── scripts/
│   ├── make_sample_dataset.py
│   ├── day02_memory_demo.py
│   ├── day03_pipeline_demo.py
│   ├── day04_types_demo.py
│   ├── day05_decorators_demo.py
│   └── export_schema.py
├── pyproject.toml
├── Makefile
├── .pre-commit-config.yaml
├── .gitignore
└── README.md
```

## Configuration

`scan` is driven by a `PipelineConfig` (validated with Pydantic v2), merged in
increasing priority:

```
model defaults  <  YAML file (--config)  <  CVTK_* env vars  <  CLI flags
```

Example (`configs/default.yaml`):

```yaml
root: sample_data
formats: [JPEG, PNG]
min_size: [16, 16]
dedupe: false
batch_size: 8
limit: null
output:
  path: manifest.csv
  format: csv
```

Supported environment variables (scalar fields only — `formats`, `min_size`,
and `output` stay YAML/CLI-only): `CVTK_ROOT`, `CVTK_BATCH_SIZE`,
`CVTK_LIMIT`, `CVTK_DEDUPE`. The full schema is in
[`docs/config.schema.json`](docs/config.schema.json), regenerated with
`make schema`.

## Day-by-Day Log

### Day 1 — Env Setup

- **Goal:** Stand up a clean, lint-enforced Python package skeleton with a working CLI.
- **What I built:**
  - `src/` layout package (`cv_dataset_toolkit`) with `pyproject.toml` (PEP 621)
  - Minimal argparse-based CLI with `--version` and a placeholder `scan` subcommand
  - Ruff configured for linting (`E`, `F`, `I`, `UP`, `B`, `SIM` rule sets)
  - Pre-commit hooks (ruff lint + format)
  - Makefile with `venv`, `install`, `lint`, `fmt`, `run`, `test` targets
  - `.gitignore` excluding venvs, caches, build artifacts, and datasets
- **Key concepts:**
  - `src/` layout prevents accidentally importing the package from the repo root instead of the installed version.
  - `pyproject.toml` (PEP 621) is the modern single-source-of-truth for packaging metadata.
  - Console-script entry points (`project.scripts`) wire a CLI command to a Python function.
  - Pre-commit hooks catch lint issues before they reach a commit.
- **How to run / verify:**
  ```bash
  pip install -e ".[dev]"
  ruff check .
  python -m cv_dataset_toolkit.cli --version
  ```
- **Milestone tag:** `day-01`

### Day 2 — Iterators & Generators

- **Goal:** Turn the toolkit into a lazy, streaming pipeline that never loads the full dataset into memory.
- **What I built:**
  - Recursive lazy walker (`iter_image_paths`, `os.scandir` + `yield from`) and `iter_many_roots` (`itertools.chain`)
  - Re-iterable `ImageFolder` (fresh generator per `__iter__`, cached `__len__`) plus an explicit `ImageFolderIterator` (`__iter__`/`__next__`)
  - `iter_metadata`: streams one record per image via header-only `PIL.Image.open` reads
  - `iterutils`: `batched`, `take`, `count_by_label` (all `itertools`-backed, no intermediate lists)
  - `write_manifest_csv`: streams rows to CSV via `csv.DictWriter` while consuming the generator
  - `running_stats()`: a `send()`-based generator coroutine tracking count/mean/min/max in one pass
  - `scan` CLI command (`--limit`, `--batch-size`, `--out`) and a `tracemalloc` memory demo script
- **Key concepts:**
  - Iterable vs. iterator vs. generator, and why exhausting an iterator matters (see `ImageFolder` docstring)
  - `yield from` for transparent recursive delegation to sub-generators
  - Lazy evaluation with `itertools` (`chain`, `islice`, `filterfalse`) keeps memory flat regardless of dataset size
  - Generator coroutines: priming with `next()`, feeding values with `.send()`, cleanup on `.close()`
- **How to run / verify:**
  ```bash
  pip install -e ".[dev]"
  ruff check .
  python scripts/make_sample_dataset.py
  cv-dataset-toolkit scan sample_data --batch-size 4 --out manifest.csv
  cv-dataset-toolkit scan sample_data --limit 3
  python scripts/day02_memory_demo.py
  python -c "from cv_dataset_toolkit.utils.iterutils import batched; assert list(batched(range(5),2))==[(0,1),(2,3),(4,)]"
  ```
- **Milestone tag:** `day-02`

### Day 3 — OOP / Pipeline

- **Goal:** Replace loose dicts and function chains with a composable, object-oriented pipeline, without losing Day 2's laziness.
- **What I built:**
  - `ImageRecord`: a frozen, slotted dataclass with `aspect_ratio`/`megapixels` properties, `from_path()`, `to_dict()`; `iter_metadata` now yields these instead of dicts
  - `Transform(ABC)` with `Filter`/`Mapper` template-method subclasses, plus 5 concrete transforms (`FilterByFormat`, `FilterMinSize`, `NormalizeLabel`, `AddAspectBucket`, the stateful `DropDuplicates`)
  - `Pipeline`: lazy `run()`, composable via `|` and immutable `.then()`, with `PipelineStats` (per-step seen/passed/dropped table)
  - `Exporter(ABC)` with `CSVExporter` (wraps Day 2's writer) and `JSONLinesExporter`, both streaming
  - `scan` CLI extended with `--formats`, `--min-size`, `--dedupe`, `--format csv|jsonl` — all Day 2 flags unchanged
- **Key concepts:**
  - Abstract base classes + template method: `Filter`/`Mapper` implement the shared wiring once, concrete transforms only supply the decision
  - Frozen dataclasses & immutability: `dataclasses.replace()` builds a changed copy instead of mutating in place
  - Operator overloading for composition: `Transform.__or__`/`Pipeline.__or__` let pipelines read as `step1 | step2 | step3`
  - Polymorphism via `Exporter`: the CLI picks a concrete exporter by string flag, calls the same `export()` interface either way
- **Pipeline shape:**
  ```
  walker (paths) -> iter_metadata (ImageRecord) -> Pipeline (Filter/Mapper steps) -> Exporter (CSV | JSONL)
  ```
- **How to run / verify:**
  ```bash
  pip install -e ".[dev]"
  ruff check .
  python scripts/make_sample_dataset.py
  cv-dataset-toolkit scan sample_data --out manifest.csv
  cv-dataset-toolkit scan sample_data --formats PNG --min-size 16 16 --dedupe --format jsonl --out manifest.jsonl
  cv-dataset-toolkit scan sample_data --limit 3
  python scripts/day03_pipeline_demo.py
  ```
- **Milestone tag:** `day-03`

### Day 4 — Type Hints / Pydantic

- **Goal:** Make the codebase pass `mypy --strict` with zero errors, and validate everything that enters from outside with Pydantic v2.
- **What I built:**
  - Full strict typing: `collections.abc` generics, `TypeVar`s, `Generator[YieldT, SendT, ReturnT]` for `running_stats`, `Literal`/`TypeAlias`/`Final`, `Self` on `Pipeline.then()`, `@overload` on `Transform`/`Pipeline.__or__`, and a `RecordSource` `Protocol`
  - `PipelineConfig`/`OutputConfig` (Pydantic v2, frozen, `extra="forbid"`) with a `field_validator` normalizing/validating `formats` and a `model_validator` auto-correcting the output suffix to match `output.format`
  - `load_config()`: explicit precedence — model defaults < YAML file < `CVTK_*` env vars (via `pydantic-settings`) < CLI flags
  - `build_pipeline(config) -> Pipeline` factory; the CLI no longer wires transforms by hand
  - `ManifestRow` (Pydantic) + `validate_manifest_csv()`: streams a manifest CSV row-by-row, collecting `(row_number, error)` pairs without loading the file; new `validate-manifest` CLI command
  - `mypy --strict` wired into `make typecheck` and a local pre-commit hook; `py.typed` marker added
- **Key concepts:**
  - Strict typing & generics: `TypeVar`-based `batched`/`take`, a `TypedDict` (`StatsSnapshot`) instead of `dict[str, Any]` for the coroutine's yield type
  - Protocol vs ABC: `Transform` is nominal (must inherit); `RecordSource` is structural (any object with a matching `__iter__` qualifies) — see its docstring
  - Pydantic validators at the boundaries: dataclasses (`ImageRecord`) stay fast and trusted inside the pipeline; Pydantic models validate config and on-disk manifests, the only places untrusted data enters
  - Config precedence: each layer (YAML/env/CLI) only contributes the fields it actually set, so a lower layer's value survives untouched when a higher layer is silent
- **How to run / verify:**
  ```bash
  pip install -e ".[dev]"
  mypy --strict src/
  ruff check .
  cv-dataset-toolkit scan sample_data --out manifest.csv
  cv-dataset-toolkit scan --config configs/default.yaml
  CVTK_BATCH_SIZE=2 cv-dataset-toolkit scan --config configs/default.yaml
  # PowerShell equivalent: $env:CVTK_BATCH_SIZE=2; cv-dataset-toolkit scan --config configs/default.yaml
  cv-dataset-toolkit scan --config configs/default.yaml --batch-size 3
  cv-dataset-toolkit scan sample_data --batch-size 0   # exit code 2, validation error
  cv-dataset-toolkit validate-manifest manifest.csv
  cv-dataset-toolkit scan sample_data --limit 3
  python scripts/day04_types_demo.py
  make schema
  ```
- **Milestone tag:** `day-04`

### Day 5 — Decorators / Context Managers

- **Goal:** Implement reusable, strictly typed decorators and context managers for performance telemetry, transient error retry, LRU caching, deprecation, atomic file writes, and environment isolation.
- **What I built:**
  - `@timed` & `TimingRegistry`: tracks call count, total, mean, and max wall time via `time.perf_counter()`; handles generator functions by timing lazy iteration rather than initial instantiation; wired into pipeline stages with the new `--timings` CLI flag
  - `@retry(attempts, delay, backoff, exceptions)`: decorator factory with exponential backoff, re-raising the last exception on exhaustion; applied to `ImageRecord.from_path()` to recover from transient filesystem/network sharing locks
  - `@memoize(maxsize)`: LRU cache using `collections.OrderedDict` with `.cache_info()` and `.cache_clear()`; explicitly handles unhashable arguments with a descriptive `TypeError`
  - `@deprecated(reason)`: emits `DeprecationWarning` with `stacklevel=2` attributing the warning to the caller line; applied to the superseded `write_manifest_csv` helper
  - `timer(label)`: `@contextlib.contextmanager` ensuring elapsed time is printed in a `try/finally` block even if the body raises
  - `Stopwatch`: class-based context manager exposing `.elapsed` both during live execution and after exit; wired into the `scan` CLI summary line
  - `atomic_write(path, mode="w", encoding="utf-8")`: writes to a staging file in the target directory and replaces atomically via `os.replace` on success, cleaning up on error; used in `CSVExporter`, `JSONLinesExporter`, and `write_manifest_csv`
  - `temporary_env(**vars)`: context manager setting or unsetting environment variables and restoring original values on exit
  - `multi_atomic_write` & `MultiExporter`: uses `contextlib.ExitStack` to manage multiple atomic file writers simultaneously
  - `scripts/day05_decorators_demo.py`: comprehensive runnable demo verifying all decorators, context managers, and failure paths
- **Key concepts:**
  - Plain decorator (`Callable[P, R] -> Callable[P, R]`) vs. decorator factory (`*args -> Callable[[Callable[P, R]], Callable[P, R]]`) vs. class-based decorator (`__call__` + descriptor protocol `__get__`)
  - `functools.wraps` preserves `__name__`, `__doc__`, `__annotations__`, and `__wrapped__`, enabling introspection and generator detection
  - Generator timing pitfall: naive decorators measure only generator object creation; wrapping `yield from` measures actual lazy consumption time
  - Context managers: generator-based (`@contextlib.contextmanager`) vs class-based (`__enter__`/`__exit__`); resource cleanup via `try/finally`
  - Atomic file writes: staging in `.tmp` files in the same directory before `os.replace()` avoids corrupted or partial files on crash or cancellation
  - `contextlib.ExitStack`: coordinates dynamic sets of context managers cleanly unwinding them in LIFO order
- **How to run / verify:**
  ```bash
  pip install -e ".[dev]"
  ruff check .
  ruff format --check .
  mypy --strict src/
  python scripts/make_sample_dataset.py
  cv-dataset-toolkit scan sample_data --out manifest.csv --timings
  cv-dataset-toolkit scan sample_data --format jsonl --out manifest.jsonl
  cv-dataset-toolkit validate-manifest manifest.csv
  python scripts/day05_decorators_demo.py
  python scripts/day04_types_demo.py
  ```
- **Milestone tag:** `day-05`

