"""Pydantic configuration models and loaders — the untrusted-input boundary.

Design principle: dataclasses inside (fast, trusted — `ImageRecord`), Pydantic
at the boundaries (untrusted input — config files, env vars, CLI flags, and
manifests read back from disk).
"""
