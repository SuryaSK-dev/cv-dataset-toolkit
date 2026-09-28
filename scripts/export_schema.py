"""Exports PipelineConfig's JSON Schema to docs/config.schema.json. Run via `make schema`."""

from __future__ import annotations

import json
from pathlib import Path

from cv_dataset_toolkit.config.models import PipelineConfig

OUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "config.schema.json"


def main() -> None:
    schema = PipelineConfig.model_json_schema()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"schema written to: {OUT_PATH}")


if __name__ == "__main__":
    main()
