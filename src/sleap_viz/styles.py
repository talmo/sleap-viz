"""Palettes and color mapping policies (minimal stubs)."""

from __future__ import annotations

import numpy as np

# Minimal embedded palettes to avoid heavy deps.
TAB10 = np.array(
    [
        [31, 119, 180],
        [255, 127, 14],
        [44, 160, 44],
        [214, 39, 40],
        [148, 103, 189],
        [140, 86, 75],
        [227, 119, 194],
        [127, 127, 127],
        [188, 189, 34],
        [23, 190, 207],
    ],
    dtype=np.uint8,
)

TAB20 = np.array(
    [
        [31, 119, 180],
        [174, 199, 232],
        [255, 127, 14],
        [255, 187, 120],
        [44, 160, 44],
        [152, 223, 138],
        [214, 39, 40],
        [255, 152, 150],
        [148, 103, 189],
        [197, 176, 213],
        [140, 86, 75],
        [196, 156, 148],
        [227, 119, 194],
        [247, 182, 210],
        [127, 127, 127],
        [199, 199, 199],
        [188, 189, 34],
        [219, 219, 141],
        [23, 190, 207],
        [158, 218, 229],
    ],
    dtype=np.uint8,
)

HSV = (
    np.stack(
        [
            (np.linspace(0, 1, 20, endpoint=False)),
            np.ones(20),
            np.ones(20),
        ],
        axis=1,
    )
    * 255
).astype(np.uint8)  # naive HSV wheel placeholder

PALETTES = {"tab10": TAB10, "tab20": TAB20, "hsv": HSV}


def palette_lookup(name: str, n: int) -> np.ndarray:
    """Return an (n,3) uint8 palette by cycling the named palette."""
    base = PALETTES.get(name, TAB20)
    reps = int(np.ceil(n / len(base)))
    return np.tile(base, (reps, 1))[:n]
