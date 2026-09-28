"""Lazy, recursive filesystem walking.

Everything here is a generator: no directory listing is ever materialized
into a list. `os.scandir` gives an iterator of `DirEntry` objects, and we
recurse into subdirectories with `yield from` so the caller sees one flat
stream of matching file paths regardless of how deep the tree is.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from itertools import chain, filterfalse
from pathlib import Path

DEFAULT_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"})


def iter_image_paths(
    root: str | os.PathLike[str],
    extensions: frozenset[str] = DEFAULT_IMAGE_EXTENSIONS,
) -> Iterator[Path]:
    """Yield image file paths under `root`, recursively, in scandir order.

    Uses `os.scandir` (not `os.walk`, not `Path.rglob`) because it exposes
    `DirEntry.is_dir()`/`is_file()` without an extra `stat` syscall per entry
    on most platforms. Recursion into subdirectories is done with
    `yield from iter_image_paths(...)` so this stays a pure generator: no
    intermediate list of paths is ever built, even for a dataset with
    millions of files.
    """
    with os.scandir(root) as entries:
        # filterfalse drops dotfiles/dot-directories (e.g. .git, .DS_Store)
        # lazily, before any is_dir/is_file check touches them.
        visible = filterfalse(lambda e: e.name.startswith("."), entries)
        for entry in visible:
            if entry.is_dir(follow_symlinks=False):
                yield from iter_image_paths(entry.path, extensions)
                continue
            suffix = Path(entry.name).suffix.lower()
            if entry.is_file(follow_symlinks=False) and suffix in extensions:
                yield Path(entry.path)


def iter_many_roots(
    *roots: str | os.PathLike[str],
    extensions: frozenset[str] = DEFAULT_IMAGE_EXTENSIONS,
) -> Iterator[Path]:
    """Chain `iter_image_paths` over several dataset roots as one lazy stream.

    `itertools.chain.from_iterable` pulls from each root's generator only as
    the consumer advances, so roots are never eagerly walked ahead of time.
    """
    per_root: Iterable[Iterator[Path]] = (iter_image_paths(root, extensions) for root in roots)
    return chain.from_iterable(per_root)
