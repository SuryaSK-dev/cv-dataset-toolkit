.PHONY: venv install lint fmt run test typecheck schema

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

venv:
	python -m venv $(VENV)

install: venv
	$(PIP) install -e ".[dev]"

lint:
	ruff check .

fmt:
	ruff format .

typecheck:
	mypy --strict src/

run:
	python -m cv_dataset_toolkit.cli

test:
	pytest --cov=cv_dataset_toolkit --cov-report=term-missing

schema:
	python scripts/export_schema.py
