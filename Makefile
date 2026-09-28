.PHONY: venv install lint fmt run test

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

run:
	python -m cv_dataset_toolkit.cli

test:
	pytest --cov=cv_dataset_toolkit --cov-report=term-missing
