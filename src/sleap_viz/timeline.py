"""Timeline component for virtualized, tiled, multi-resolution timeline display.

This module consolidates the model, view, and controller for the timeline component.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

import numpy as np
import pygfx as gfx

if TYPE_CHECKING:
    from .annotation_source import AnnotationSource


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
        self._annotation_source: Optional[AnnotationSource] = None
        
        # Frame range currently visible (for zooming)
        self.frame_min = 0
        self.frame_max = n_frames
        
        # Zoom level (1.0 = show all frames, higher = more zoomed in)
        self.zoom_level = 1.0
        self.zoom_center = n_frames // 2  # Center frame for zoom
        
        # Selection range
        self.selection_start: Optional[int] = None
        self.selection_end: Optional[int] = None

    def set_annotation_source(self, source: AnnotationSource) -> None:
        """Set the annotation source for frame markers."""
        self._annotation_source = source
        self._cache.clear()  # Clear cache when source changes

    def level_for_pixels(self, frames_per_px: float) -> int:
        """Choose LoD level so that ≤1 bin maps to one device pixel."""
        if frames_per_px <= 1:
            return 0
        level = 0
        while (1 << level) < frames_per_px:
            level += 1
        return level

    def set_visible_range(self, frame_min: int, frame_max: int) -> None:
        """Set the visible frame range for tile computation."""
        self.frame_min = max(0, frame_min)
        self.frame_max = min(self.n_frames, frame_max)
        
    def zoom(self, factor: float, center_frame: Optional[int] = None) -> None:
        """Apply zoom to the timeline.
        
        Args:
            factor: Zoom factor (>1 to zoom in, <1 to zoom out).
            center_frame: Frame to center zoom on (None = current center).
        """
        # Update zoom level
        new_zoom = self.zoom_level * factor
        new_zoom = max(1.0, min(new_zoom, 100.0))  # Clamp between 1x and 100x
        
        # Update center if provided
        if center_frame is not None:
            self.zoom_center = center_frame
            
        # Calculate visible frame range based on zoom
        visible_frames = self.n_frames / new_zoom
        half_visible = visible_frames / 2
        
        new_min = int(self.zoom_center - half_visible)
        new_max = int(self.zoom_center + half_visible)
        
        # Clamp to valid range
        if new_min < 0:
            new_max -= new_min
            new_min = 0
        if new_max > self.n_frames:
            new_min -= (new_max - self.n_frames)
            new_max = self.n_frames
            
        new_min = max(0, new_min)
        new_max = min(self.n_frames, new_max)
        
        self.zoom_level = new_zoom
        self.frame_min = new_min
        self.frame_max = new_max
        
    def pan(self, delta_frames: int) -> None:
        """Pan the timeline by a number of frames.
        
        Args:
            delta_frames: Number of frames to pan (positive = right, negative = left).
        """
        visible_frames = self.frame_max - self.frame_min
        new_min = self.frame_min + delta_frames
        new_max = self.frame_max + delta_frames
        
        # Clamp to valid range
        if new_min < 0:
            new_min = 0
            new_max = min(visible_frames, self.n_frames)
        elif new_max > self.n_frames:
            new_max = self.n_frames
            new_min = max(0, self.n_frames - visible_frames)
            
        self.frame_min = new_min
        self.frame_max = new_max
        self.zoom_center = (new_min + new_max) // 2

    async def get_tile(self, level: int, tile_index: int) -> Tile:
        """Return (and compute if needed) a tile for (level, tile_index)."""
        key = (level, tile_index)
        if key in self._cache:
            return self._cache[key]
        
        # Compute tile data
        bins = await self._compute_tile(level, tile_index)
        tile = Tile(level=level, index=tile_index, bins=bins)
        self._cache[key] = tile
        return tile
    
    async def _compute_tile(self, level: int, tile_index: int) -> np.ndarray:
        """Compute tile data for a given level and index."""
        bins = np.zeros((self.tile_bins,), dtype=np.uint8)
        
        if self._annotation_source is None:
            return bins
        
        # Calculate frame range for this tile
        frames_per_bin = 1 << level
        start_frame = tile_index * self.tile_bins * frames_per_bin
        end_frame = min(start_frame + self.tile_bins * frames_per_bin, self.n_frames)
        
        # For each bin, check if any frames have annotations
        for bin_idx in range(self.tile_bins):
            bin_start = start_frame + bin_idx * frames_per_bin
            bin_end = min(bin_start + frames_per_bin, end_frame)
            
            if bin_start >= self.n_frames:
                break
            
            # Check for annotations in this bin's frame range
            has_user = False
            has_pred = False
            
            for frame_idx in range(bin_start, bin_end):
                # Get frame data using the proper API
                # AnnotationSource.get_frame_data needs the video object
                frame_data = self._annotation_source.get_frame_data_simple(frame_idx)
                if frame_data:
                    if any(not inst.from_predicted for inst in frame_data.instances):
                        has_user = True
                    if any(inst.from_predicted for inst in frame_data.instances):
                        has_pred = True
                    
                    if has_user and has_pred:
                        break
            
            # Set bin color index: 0=empty, 1=user, 2=predicted, 3=both
            if has_user and has_pred:
                bins[bin_idx] = 3
            elif has_user:
                bins[bin_idx] = 1
            elif has_pred:
                bins[bin_idx] = 2
            else:
                bins[bin_idx] = 0
        
        return bins


# ============================================================================
# View
# ============================================================================


class TimelineView:
    """Render the timeline using pygfx."""

    def __init__(self, width: int = 800, height: int = 50) -> None:
        """Create canvas and materials for the timeline.
        
        Args:
            width: Timeline width in pixels.
            height: Timeline height in pixels.
        """
        self.width = width
        self.height = height
        
        # Create scene and camera
        self.scene = gfx.Scene()
        self.camera = gfx.OrthographicCamera(width, height, maintain_aspect=False)
        self.camera.show_rect(0, width, 0, height, depth=10)
        
        # Timeline background
        self.background_mesh = None
        self._create_background()
        
        # Data visualization mesh
        self.data_mesh = None
        self.data_texture = None
        
        # Playhead line
        self.playhead_mesh = None
        self.playhead_position = 0.0
        
        # Selection overlay
        self.selection_mesh = None
        
        # Color palette for timeline states
        self.palette = np.array([
            [50, 50, 50, 255],      # 0: empty (dark gray)
            [0, 200, 0, 255],       # 1: user labels (green)
            [200, 200, 0, 255],     # 2: predicted (yellow)
            [0, 200, 200, 255],     # 3: both (cyan)
        ], dtype=np.uint8)
        
    def _create_background(self) -> None:
        """Create the background mesh for the timeline."""
        # Create a dark background rectangle
        plane_geo = gfx.plane_geometry(self.width, self.height)
        material = gfx.MeshBasicMaterial(color=(0.15, 0.15, 0.15, 1))
        self.background_mesh = gfx.Mesh(plane_geo, material)
        self.background_mesh.local.position = (self.width / 2, self.height / 2, -2)
        self.scene.add(self.background_mesh)
        
    def update_data(self, bins: np.ndarray, frame_min: int, frame_max: int, total_frames: int) -> None:
        """Update the timeline data visualization.
        
        Args:
            bins: Array of bin values (uint8 category indices).
            frame_min: First frame in visible range.
            frame_max: Last frame in visible range.
            total_frames: Total number of frames.
        """
        self.current_frame_min = frame_min
        self.current_frame_max = frame_max
        self.total_frames = total_frames
        if self.data_mesh is not None:
            self.scene.remove(self.data_mesh)
            self.data_mesh = None
            
        if bins.size == 0:
            return
            
        # Create texture from bins with color mapping
        # Expand bins to match timeline width if needed
        if len(bins) < self.width:
            # Repeat bins to fill width
            expanded_bins = np.zeros(self.width, dtype=np.uint8)
            bin_width = self.width / len(bins)
            for i, bin_val in enumerate(bins):
                start_px = int(i * bin_width)
                end_px = int((i + 1) * bin_width)
                expanded_bins[start_px:end_px] = bin_val
            bins = expanded_bins
        elif len(bins) > self.width:
            # Downsample bins
            indices = np.linspace(0, len(bins) - 1, self.width, dtype=int)
            bins = bins[indices]
            
        # Map bins to colors
        colors = self.palette[bins]
        
        # Create a 1D texture that we'll stretch across the timeline
        # Make it 2D (height x width x 4) for pygfx texture
        texture_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        for y in range(self.height):
            texture_data[y, :] = colors
            
        # Convert to float32 normalized
        texture_data = texture_data.astype(np.float32) / 255.0
        
        # Create texture and mesh
        self.data_texture = gfx.Texture(texture_data, dim=2)
        plane_geo = gfx.plane_geometry(self.width, self.height)
        material = gfx.MeshBasicMaterial(map=self.data_texture)
        self.data_mesh = gfx.Mesh(plane_geo, material)
        self.data_mesh.local.position = (self.width / 2, self.height / 2, -1)
        self.scene.add(self.data_mesh)
        
    def update_playhead(self, frame: int, total_frames: int, frame_min: int = 0, frame_max: Optional[int] = None) -> None:
        """Update the playhead position.
        
        Args:
            frame: Current frame number.
            total_frames: Total number of frames.
            frame_min: First visible frame (for zoomed view).
            frame_max: Last visible frame (for zoomed view).
        """
        if self.playhead_mesh is not None:
            self.scene.remove(self.playhead_mesh)
            self.playhead_mesh = None
            
        if total_frames == 0:
            return
            
        # Use zoomed range if provided
        if frame_max is None:
            frame_max = total_frames
            
        visible_frames = frame_max - frame_min
        if visible_frames == 0:
            return
            
        # Calculate playhead position within visible range
        if frame < frame_min or frame > frame_max:
            # Playhead is outside visible range
            return
            
        x_pos = ((frame - frame_min) / visible_frames) * self.width
        
        # Create a vertical line for the playhead
        positions = np.array([
            [x_pos, 0, 1],
            [x_pos, self.height, 1]
        ], dtype=np.float32)
        
        geometry = gfx.Geometry(positions=positions)
        material = gfx.LineMaterial(thickness=2.0, color=(1, 0, 0, 1))  # Red playhead
        self.playhead_mesh = gfx.Line(geometry, material)
        self.scene.add(self.playhead_mesh)
        
        self.playhead_position = x_pos
        
    def update_selection(self, start_frame: Optional[int], end_frame: Optional[int], 
                        frame_min: int = 0, frame_max: Optional[int] = None) -> None:
        """Update the selection overlay.
        
        Args:
            start_frame: Start frame of selection (None if no selection).
            end_frame: End frame of selection.
            frame_min: First visible frame (for zoomed view).
            frame_max: Last visible frame (for zoomed view, None = total_frames).
        """
        if self.selection_mesh is not None:
            self.scene.remove(self.selection_mesh)
            self.selection_mesh = None
            
        if start_frame is None or end_frame is None:
            return
            
        # Use frame_max if provided, otherwise use total_frames
        if frame_max is None:
            frame_max = self.total_frames if hasattr(self, 'total_frames') else 0
            
        visible_frames = frame_max - frame_min
        if visible_frames == 0:
            return
            
        # Check if selection is visible in current zoom
        if end_frame < frame_min or start_frame > frame_max:
            return
            
        # Clamp selection to visible range
        visible_start = max(start_frame, frame_min)
        visible_end = min(end_frame, frame_max)
        
        # Calculate selection rectangle in visible range
        x_start = ((visible_start - frame_min) / visible_frames) * self.width
        x_end = ((visible_end - frame_min) / visible_frames) * self.width
        width = x_end - x_start
        
        if width <= 0:
            return
            
        # Create selection overlay
        plane_geo = gfx.plane_geometry(width, self.height)
        material = gfx.MeshBasicMaterial(color=(0.5, 0.5, 1.0, 0.3))  # Semi-transparent blue
        self.selection_mesh = gfx.Mesh(plane_geo, material)
        self.selection_mesh.local.position = (x_start + width / 2, self.height / 2, 0)
        self.scene.add(self.selection_mesh)
        
    def frame_from_x(self, x: float, total_frames: int, frame_min: int = 0, frame_max: Optional[int] = None) -> int:
        """Convert x coordinate to frame number.
        
        Args:
            x: X coordinate in timeline.
            total_frames: Total number of frames.
            frame_min: First visible frame (for zoomed view).
            frame_max: Last visible frame (for zoomed view).
            
        Returns:
            Frame number.
        """
        if self.width == 0:
            return 0
            
        # Use zoomed range if provided
        if frame_max is None:
            frame_max = total_frames
            
        visible_frames = frame_max - frame_min
        if visible_frames == 0:
            return frame_min
            
        # Map x to frame within visible range
        frame = frame_min + int((x / self.width) * visible_frames)
        return max(0, min(frame, total_frames - 1))


# ============================================================================
# Controller
# ============================================================================


class TimelineController:
    """Handle timeline interaction and updates."""

    def __init__(self, model: TimelineModel, view: TimelineView) -> None:
        """Initialize the timeline controller.
        
        Args:
            model: Timeline data model.
            view: Timeline view for rendering.
        """
        self.model = model
        self.view = view
        self.current_frame = 0
        self._update_task: Optional[asyncio.Task] = None
        
        # Mouse state for panning
        self._pan_start_x: Optional[float] = None
        self._pan_start_frame_min: Optional[int] = None
        self._pan_start_frame_max: Optional[int] = None
        
    def set_annotation_source(self, source: AnnotationSource) -> None:
        """Set the annotation source for the timeline."""
        self.model.set_annotation_source(source)
        self.request_update()
        
    def set_current_frame(self, frame: int) -> None:
        """Update the current frame position."""
        self.current_frame = frame
        self.view.update_playhead(
            frame, 
            self.model.n_frames,
            self.model.frame_min,
            self.model.frame_max
        )
        
    def set_selection(self, start: Optional[int], end: Optional[int]) -> None:
        """Set the selection range."""
        self.model.selection_start = start
        self.model.selection_end = end
        self.view.update_selection(
            start, end, 
            self.model.frame_min,
            self.model.frame_max
        )
        
    def request_update(self) -> None:
        """Request an async update of the timeline."""
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
        
        loop = asyncio.get_event_loop()
        self._update_task = loop.create_task(self._update_timeline())
        
    async def _update_timeline(self) -> None:
        """Update the timeline visualization."""
        # Calculate frames per pixel for zoomed range
        visible_frames = self.model.frame_max - self.model.frame_min
        frames_per_px = visible_frames / self.view.width
        
        # Get appropriate level
        level = self.model.level_for_pixels(frames_per_px)
        
        # Calculate which tiles we need
        frames_per_tile = self.model.tile_bins * (1 << level)
        start_tile = self.model.frame_min // frames_per_tile
        end_tile = (self.model.frame_max + frames_per_tile - 1) // frames_per_tile
        
        # Collect all bins from visible tiles
        all_bins = []
        for tile_idx in range(start_tile, end_tile):
            tile = await self.model.get_tile(level, tile_idx)
            all_bins.append(tile.bins)
            
        if all_bins:
            combined_bins = np.concatenate(all_bins)
            self.view.update_data(
                combined_bins, 
                self.model.frame_min, 
                self.model.frame_max,
                self.model.n_frames
            )
        
        # Update playhead position for zoomed view
        self.view.update_playhead(
            self.current_frame,
            self.model.n_frames,
            self.model.frame_min,
            self.model.frame_max
        )
        
        # Update selection if present
        if self.model.selection_start is not None and self.model.selection_end is not None:
            self.view.update_selection(
                self.model.selection_start,
                self.model.selection_end,
                self.model.frame_min,
                self.model.frame_max
            )
            
    def handle_click(self, x: float, y: float) -> int:
        """Handle mouse click on timeline.
        
        Args:
            x: X coordinate of click.
            y: Y coordinate of click.
            
        Returns:
            Frame number to seek to.
        """
        return self.view.frame_from_x(
            x, 
            self.model.n_frames,
            self.model.frame_min,
            self.model.frame_max
        )
        
    def handle_drag(self, x_start: float, x_end: float) -> Tuple[int, int]:
        """Handle mouse drag for selection.
        
        Args:
            x_start: Start X coordinate.
            x_end: End X coordinate.
            
        Returns:
            Tuple of (start_frame, end_frame).
        """
        start_frame = self.view.frame_from_x(
            x_start, 
            self.model.n_frames,
            self.model.frame_min,
            self.model.frame_max
        )
        end_frame = self.view.frame_from_x(
            x_end, 
            self.model.n_frames,
            self.model.frame_min,
            self.model.frame_max
        )
        
        if start_frame > end_frame:
            start_frame, end_frame = end_frame, start_frame
            
        return start_frame, end_frame
    
    def handle_wheel(self, delta: float, x: float) -> None:
        """Handle mouse wheel for zooming.
        
        Args:
            delta: Wheel delta (positive = zoom in, negative = zoom out).
            x: X coordinate of mouse (zoom center).
        """
        # Calculate zoom factor
        factor = 1.1 if delta > 0 else 0.9
        
        # Get frame at mouse position
        center_frame = self.view.frame_from_x(
            x,
            self.model.n_frames,
            self.model.frame_min,
            self.model.frame_max
        )
        
        # Apply zoom
        self.model.zoom(factor, center_frame)
        self.request_update()
    
    def start_pan(self, x: float) -> None:
        """Start panning with mouse drag.
        
        Args:
            x: Starting X coordinate.
        """
        self._pan_start_x = x
        self._pan_start_frame_min = self.model.frame_min
        self._pan_start_frame_max = self.model.frame_max
    
    def update_pan(self, x: float) -> None:
        """Update pan based on mouse drag.
        
        Args:
            x: Current X coordinate.
        """
        if self._pan_start_x is None:
            return
            
        # Calculate pixel delta
        delta_px = x - self._pan_start_x
        
        # Convert to frame delta
        visible_frames = self._pan_start_frame_max - self._pan_start_frame_min
        delta_frames = -int((delta_px / self.view.width) * visible_frames)
        
        # Apply pan
        self.model.pan(delta_frames)
        self.request_update()
    
    def end_pan(self) -> None:
        """End panning."""
        self._pan_start_x = None
        self._pan_start_frame_min = None
        self._pan_start_frame_max = None
    
    def zoom_in(self) -> None:
        """Zoom in by a fixed factor."""
        self.model.zoom(1.5, self.current_frame)
        self.request_update()
    
    def zoom_out(self) -> None:
        """Zoom out by a fixed factor."""
        self.model.zoom(0.67, self.current_frame)
        self.request_update()
    
    def reset_zoom(self) -> None:
        """Reset zoom to show all frames."""
        self.model.zoom_level = 1.0
        self.model.frame_min = 0
        self.model.frame_max = self.model.n_frames
        self.model.zoom_center = self.model.n_frames // 2
        self.request_update()