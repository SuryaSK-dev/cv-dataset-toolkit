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
| 3   | OOP / Pipeline                | ⬜     |         |
| 4   | Type Hints / Pydantic         | ⬜     |         |
| 5   | Decorators / Context Managers | ⬜     |         |
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
│       ├── cli.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── metadata.py      # iter_metadata: streaming metadata extraction
│       │   └── stats.py         # running_stats: send()-based coroutine
│       ├── io/
│       │   ├── __init__.py
│       │   ├── walker.py        # iter_image_paths, iter_many_roots
│       │   ├── dataset.py       # ImageFolder, ImageFolderIterator
│       │   └── export.py        # write_manifest_csv
│       └── utils/
│           ├── __init__.py
│           └── iterutils.py     # batched, take, count_by_label
├── scripts/
│   ├── make_sample_dataset.py
│   └── day02_memory_demo.py
├── pyproject.toml
├── Makefile
├── .pre-commit-config.yaml
├── .gitignore
└── README.md
```

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
