"""Config loading with explicit precedence.

Precedence, lowest to highest:
    Pydantic field defaults  <  YAML file  <  environment variables (CVTK_*)  <  CLI flags

`pydantic-settings` handles the environment-variable layer: it gives typed
coercion (`"2"` -> `2`, `"true"` -> `True`), a `CVTK_` prefix, and validation
errors, for free, for the *scalar* fields (`root`, `batch_size`, `limit`,
`dedupe`). It only covers scalars deliberately — `formats` (a set) and
`min_size`/`output` (nested/tuple shapes) stay YAML/CLI-only, where their
structure is unambiguous, rather than inventing an env-var encoding
(comma lists, JSON strings, ...) for a handful of fields nothing in this
project's verification actually exercises.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from cv_dataset_toolkit.config.models import PipelineConfig


class _CVTKEnvSettings(BaseSettings):
    """Scalar `PipelineConfig` fields, sourced from `CVTK_`-prefixed env vars."""

    model_config = SettingsConfigDict(env_prefix="CVTK_", extra="ignore")

    root: Path | None = None
    batch_size: int | None = None
    limit: int | None = None
    dedupe: bool | None = None


def _load_yaml(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as f:
        data: object = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"config file {path} must contain a YAML mapping at the top level")
    return data


def _deep_update(base: MutableMapping[str, object], updates: Mapping[str, object]) -> None:
    """Recursively merge `updates` into `base` in place.

    Nested dicts merge key by key; any other value type simply replaces
    what was there.
    """
    for key, value in updates.items():
        existing = base.get(key)
        if isinstance(value, Mapping) and isinstance(existing, MutableMapping):
            _deep_update(existing, value)
        else:
            base[key] = value


def load_config(path: Path | None, overrides: Mapping[str, object]) -> PipelineConfig:
    """Build a `PipelineConfig` by merging, in increasing priority:

    Pydantic field defaults < YAML file at `path` (skipped if `path` is
    `None`) < `CVTK_*` environment variables < `overrides` (typically CLI
    flags the caller has explicitly set).
    """
    merged: dict[str, object] = _load_yaml(path) if path is not None else {}

    env_settings = _CVTKEnvSettings()
    env_data = {
        field: value for field, value in env_settings.model_dump().items() if value is not None
    }
    _deep_update(merged, env_data)
    _deep_update(merged, overrides)

    return PipelineConfig.model_validate(merged)
