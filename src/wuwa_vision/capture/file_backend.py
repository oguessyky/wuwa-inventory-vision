# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Fixture-replay capture backend.

Makes the pipeline runnable with the game closed, which is what lets Milestone 1
be built and regression-tested before any live capture exists (PLAN.md D18).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
from PIL import Image

from .base import Frame

# Raw captures were once saved without an extension. Sniffing magic bytes costs
# one line and removes that class of bug entirely (PLAN.md D8-amended).
_MAGIC: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"RIFF": "webp",
    b"\xff\xd8\xff": "jpeg",
}


def looks_like_image(path: Path) -> bool:
    try:
        head = path.open("rb").read(12)
    except OSError:
        return False
    return any(head.startswith(m) for m in _MAGIC)


class FileCapture:
    """Replays image files from a directory, sorted by name."""

    def __init__(self, source: Path | str) -> None:
        self.source = Path(source)
        if self.source.is_dir():
            self.paths = sorted(p for p in self.source.iterdir() if looks_like_image(p))
        elif looks_like_image(self.source):
            self.paths = [self.source]
        else:
            raise ValueError(f"not an image or directory of images: {self.source}")
        if not self.paths:
            raise ValueError(f"no readable images in {self.source}")

    def __len__(self) -> int:
        return len(self.paths)

    def frames(self) -> Iterator[Frame]:
        for i, path in enumerate(self.paths):
            with Image.open(path) as im:
                rgb = np.asarray(im.convert("RGB"))
            yield Frame(rgb=rgb, source=path.stem, seq=i)
