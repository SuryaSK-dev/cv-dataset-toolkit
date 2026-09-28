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
| 2   | Iterators & Generators        | ⬜     |         |
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
│       └── cli.py
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
