"""`ImageFolder`: a re-iterable dataset over a folder of images.

Iterable vs iterator vs generator
----------------------------------
- An **iterator** is any object with `__next__` (and `__iter__` returning
  `self`). It is single-use and stateful: once exhausted (raises
  `StopIteration`), it is permanently empty. `ImageFolderIterator` below is
  one, explicitly.
- A **generator** (a function using `yield`) is a convenient way to *write*
  an iterator without a class — calling it returns a fresh iterator object
  each time.
- An **iterable** is any object with `__iter__` that returns an iterator.
  It does not have to be an iterator itself. `ImageFolder.__iter__` returns
  a *new* generator on every call, so the same `ImageFolder` instance can be
  looped over multiple times (`for x in folder` twice gives two full
  passes) — unlike handing someone an exhausted generator, which would
  silently yield nothing the second time.

This distinction matters here because `scan` may need to pass over the
dataset more than once (e.g. counting then exporting); an `ImageFolder`
supports that, while a bare generator would not.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from cv_dataset_toolkit.io.walker import DEFAULT_IMAGE_EXTENSIONS, iter_image_paths


class ImageFolder:
    """Re-iterable view over the image files under `root`.

    `__len__` walks the folder once to count files, then caches the result
    (invalidated only if you construct a new instance) — so calling
    `len(folder)` repeatedly doesn't re-walk the filesystem every time, but
    `iter(folder)` always re-walks lazily to reflect the current directory
    state.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        extensions: frozenset[str] = DEFAULT_IMAGE_EXTENSIONS,
    ) -> None:
        self.root = Path(root)
        self.extensions = extensions
        self._length: int | None = None

    def __iter__(self) -> Iterator[Path]:
        return iter_image_paths(self.root, self.extensions)

    def __len__(self) -> int:
        if self._length is None:
            self._length = sum(1 for _ in self)
        return self._length

    def __repr__(self) -> str:
        return f"ImageFolder(root={str(self.root)!r}, extensions={sorted(self.extensions)})"


class ImageFolderIterator:
    """Explicit, single-use iterator over an `ImageFolder`.

    Demonstrates the iterator protocol by hand: `__iter__` returns `self`,
    and `__next__` pulls one path at a time from an internal generator,
    re-raising `StopIteration` once exhausted. Unlike `ImageFolder`, an
    instance of this class can only be consumed once — a second `for`
    loop over the *same instance* yields nothing.
    """

    def __init__(self, folder: ImageFolder) -> None:
        self._generator = iter(folder)

    def __iter__(self) -> ImageFolderIterator:
        return self

    def __next__(self) -> Path:
        return next(self._generator)
