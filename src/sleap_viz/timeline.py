"""Timeline component for virtualized, tiled, multi-resolution timeline display.

This module consolidates the model, view, and controller for the timeline component.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np


# ============================================================================
# Model
# ============================================================================


@dataclass
class Tile:
    """A tile of aggregated timeline data at a given level."""

    level: int
    index: int
    bins: np.ndarray  # shape (W,) of uint8 category indices for MVP


class TimelineModel:
    """Maintains LoD pyramid and async computation of tiles."""

    def __init__(self, n_frames: int, tile_bins: int = 4096) -> None:
        """Initialize the model.

        Args:
            n_frames: Total number of frames in the video.
            tile_bins: Number of bins per tile per level.
        """
        self.n_frames = n_frames
        self.tile_bins = tile_bins
        self._cache: dict[tuple[int, int], Tile] = {}
        self._jobs: set[asyncio.Task] = set()

    def level_for_pixels(self, frames_per_px: float) -> int:
        """Choose LoD level so that ≤1 bin maps to one device pixel."""
        level = 0
        while (1 << level) < frames_per_px:
            level += 1
        return level

    async def get_tile(self, level: int, tile_index: int) -> Tile:
        """Return (and compute if needed) a tile for (level, tile_index)."""
        key = (level, tile_index)
        if key in self._cache:
            return self._cache[key]
        # MVP: default state (neutral gray index 0) everywhere
        bins = np.zeros((self.tile_bins,), dtype=np.uint8)
        tile = Tile(level=level, index=tile_index, bins=bins)
        self._cache[key] = tile
        return tile


# ============================================================================
# View
# ============================================================================


class TimelineView:
    """Render the timeline into its own canvas (stub for MVP)."""

    def __init__(self) -> None:
        """Create canvas and materials for the timeline."""
        ...


# ============================================================================
# Controller
# ============================================================================


class TimelineController:
    """Map input to timeline model/view (stub)."""

    def __init__(self) -> None: ...