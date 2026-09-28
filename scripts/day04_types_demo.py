"""Demonstrates Day 4's Pydantic boundary: valid/invalid configs, env overrides,
JSON export, and streaming manifest validation.
"""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from cv_dataset_toolkit.config.loader import load_config
from cv_dataset_toolkit.config.models import PipelineConfig
from cv_dataset_toolkit.io.manifest import validate_manifest_csv

SAMPLE_ROOT = Path(__file__).resolve().parent.parent / "sample_data"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


def demo_valid_config() -> None:
    print("=== 1. Loading a valid config ===")
    config = load_config(CONFIG_PATH, overrides={})
    print(repr(config))


def demo_invalid_config() -> None:
    print("\n=== 2. A deliberately invalid config ===")
    try:
        PipelineConfig.model_validate(
            {
                "root": str(SAMPLE_ROOT),
                "batch_size": 0,  # PositiveInt violation
                "formats": ["NOT_A_REAL_FORMAT"],  # unknown format
            }
        )
    except ValidationError as exc:
        print(f"ValidationError with {exc.error_count()} error(s):")
        for error in exc.errors():
            loc = ".".join(str(part) for part in error["loc"])
            print(f"  {loc}: {error['msg']}")
    else:
        raise AssertionError("expected a ValidationError")


def demo_env_override() -> None:
    print("\n=== 3. Environment variable override ===")
    before = load_config(CONFIG_PATH, overrides={})
    print(f"batch_size before CVTK_BATCH_SIZE: {before.batch_size}")

    os.environ["CVTK_BATCH_SIZE"] = "4"
    try:
        after = load_config(CONFIG_PATH, overrides={})
    finally:
        del os.environ["CVTK_BATCH_SIZE"]
    print(f"batch_size with CVTK_BATCH_SIZE=4:  {after.batch_size}")
    assert after.batch_size == 4


def demo_json_dump() -> None:
    print("\n=== 4. model_dump_json(indent=2) ===")
    config = load_config(CONFIG_PATH, overrides={})
    print(config.model_dump_json(indent=2))


def demo_validate_manifest() -> None:
    print("\n=== 5. Streaming validation of a manifest with one corrupted row ===")
    rows = [
        {
            "path": "a.jpg",
            "label": "cat",
            "format": "JPEG",
            "size_bytes": "100",
            "width": "32",
            "height": "32",
        },
        {
            "path": "b.png",
            "label": "dog",
            "format": "PNG",
            "size_bytes": "200",
            "width": "16",
            "height": "16",
        },
        {
            # corrupted: negative size_bytes
            "path": "c.jpg",
            "label": "car",
            "format": "JPEG",
            "size_bytes": "-1",
            "width": "8",
            "height": "8",
        },
    ]
    with tempfile.NamedTemporaryFile(
        "w", suffix=".csv", newline="", encoding="utf-8", delete=False
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        tmp_path = Path(tmp.name)

    try:
        summary = validate_manifest_csv(tmp_path)
        print(f"valid rows: {summary.valid_count}")
        print(f"invalid rows: {len(summary.errors)}")
        for error in summary.errors:
            print(f"  row {error.row_number}: {error.message}")
        assert summary.valid_count == 2
        assert len(summary.errors) == 1
    finally:
        tmp_path.unlink()


def main() -> None:
    demo_valid_config()
    demo_invalid_config()
    demo_env_override()
    demo_json_dump()
    demo_validate_manifest()


if __name__ == "__main__":
    main()
