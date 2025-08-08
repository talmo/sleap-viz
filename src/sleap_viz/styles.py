"""Palettes and color mapping policies for visualization."""

from __future__ import annotations

from typing import Literal, Callable
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

# Generate HSV palette with proper HSV to RGB conversion
def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """Convert HSV to RGB (h in [0,1], s,v in [0,1])."""
    c = v * s
    x = c * (1 - abs((h * 6) % 2 - 1))
    m = v - c
    
    if h < 1/6:
        r, g, b = c, x, 0
    elif h < 2/6:
        r, g, b = x, c, 0
    elif h < 3/6:
        r, g, b = 0, c, x
    elif h < 4/6:
        r, g, b = 0, x, c
    elif h < 5/6:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    
    return (
        int((r + m) * 255),
        int((g + m) * 255),
        int((b + m) * 255)
    )

HSV = np.array([
    hsv_to_rgb(h, 0.8, 0.9) for h in np.linspace(0, 1, 20, endpoint=False)
], dtype=np.uint8)

PALETTES = {"tab10": TAB10, "tab20": TAB20, "hsv": HSV}


def palette_lookup(name: str, n: int) -> np.ndarray:
    """Return an (n,3) uint8 palette by cycling the named palette."""
    base = PALETTES.get(name, TAB20)
    reps = int(np.ceil(n / len(base)))
    return np.tile(base, (reps, 1))[:n]


class ColorPolicy:
    """Manages color assignment for nodes, instances, and tracks."""
    
    def __init__(
        self,
        color_by: Literal["instance", "node", "track"] | Callable = "instance",
        colormap: str | np.ndarray | Callable = "tab20",
        invisible_mode: Literal["dim", "hide"] = "dim",
        dim_factor: float = 0.3,
    ):
        """Initialize color policy.
        
        Args:
            color_by: What to color by - "instance", "node", "track", or callable.
            colormap: Palette name, array of colors, or callable.
            invisible_mode: How to handle invisible points - "dim" or "hide".
            dim_factor: Factor to dim invisible points (0-1).
        """
        self.color_by = color_by
        self.colormap = colormap
        self.invisible_mode = invisible_mode
        self.dim_factor = dim_factor
        
        # Cache for color assignments
        self._color_cache: dict[int, np.ndarray] = {}
        
    def get_colors(
        self,
        points_xy: np.ndarray,
        visible: np.ndarray,
        inst_kind: np.ndarray | None = None,
        track_id: np.ndarray | None = None,
        node_ids: np.ndarray | None = None,
    ) -> np.ndarray:
        """Get RGBA colors for all points.
        
        Args:
            points_xy: Point coordinates [N_inst, N_nodes, 2].
            visible: Visibility flags [N_inst, N_nodes].
            inst_kind: Instance types [N_inst] (0=user, 1=predicted).
            track_id: Track IDs [N_inst].
            node_ids: Node IDs [N_nodes].
            
        Returns:
            RGBA colors [N_inst, N_nodes, 4] as float32 in [0, 1].
        """
        n_inst, n_nodes, _ = points_xy.shape
        
        # Initialize with default colors
        colors = np.ones((n_inst, n_nodes, 4), dtype=np.float32)
        
        # Get base colors based on color_by mode
        if callable(self.color_by):
            # Custom color function
            base_colors = self.color_by(
                points_xy, visible, inst_kind, track_id, node_ids
            )
        elif self.color_by == "instance":
            base_colors = self._color_by_instance(n_inst, n_nodes, inst_kind)
        elif self.color_by == "node":
            base_colors = self._color_by_node(n_inst, n_nodes, node_ids)
        elif self.color_by == "track":
            base_colors = self._color_by_track(n_inst, n_nodes, track_id)
        else:
            # Default to instance coloring
            base_colors = self._color_by_instance(n_inst, n_nodes, inst_kind)
        
        # Apply base colors
        colors[:, :, :3] = base_colors[:, :, :3]
        
        # Handle invisible points
        if self.invisible_mode == "dim":
            # Dim invisible points
            for i in range(n_inst):
                for j in range(n_nodes):
                    if not visible[i, j]:
                        colors[i, j, :3] *= self.dim_factor
                        colors[i, j, 3] *= 0.5  # Also reduce alpha
        elif self.invisible_mode == "hide":
            # Make invisible points fully transparent
            for i in range(n_inst):
                for j in range(n_nodes):
                    if not visible[i, j]:
                        colors[i, j, 3] = 0.0
        
        return colors
    
    def _color_by_instance(
        self, n_inst: int, n_nodes: int, inst_kind: np.ndarray | None
    ) -> np.ndarray:
        """Color by instance index."""
        colors = np.ones((n_inst, n_nodes, 4), dtype=np.float32)
        
        # Get palette
        if isinstance(self.colormap, str):
            palette = palette_lookup(self.colormap, n_inst)
        elif isinstance(self.colormap, np.ndarray):
            palette = self.colormap
        elif callable(self.colormap):
            palette = self.colormap(n_inst)
        else:
            palette = palette_lookup("tab20", n_inst)
        
        # Convert to float32 and normalize
        palette = palette.astype(np.float32) / 255.0
        
        # Assign colors by instance
        for i in range(n_inst):
            color_idx = i % len(palette)
            colors[i, :, :3] = palette[color_idx]
            
            # Optionally modify color based on instance kind
            if inst_kind is not None and i < len(inst_kind):
                if inst_kind[i] == 1:  # Predicted instance
                    # Slightly desaturate predicted instances
                    colors[i, :, :3] = colors[i, :, :3] * 0.8 + 0.2
        
        return colors
    
    def _color_by_node(
        self, n_inst: int, n_nodes: int, node_ids: np.ndarray | None
    ) -> np.ndarray:
        """Color by node/keypoint type."""
        colors = np.ones((n_inst, n_nodes, 4), dtype=np.float32)
        
        # Get palette
        if isinstance(self.colormap, str):
            palette = palette_lookup(self.colormap, n_nodes)
        elif isinstance(self.colormap, np.ndarray):
            palette = self.colormap
        elif callable(self.colormap):
            palette = self.colormap(n_nodes)
        else:
            palette = palette_lookup("tab20", n_nodes)
        
        # Convert to float32 and normalize
        palette = palette.astype(np.float32) / 255.0
        
        # Assign colors by node
        for j in range(n_nodes):
            color_idx = j % len(palette)
            colors[:, j, :3] = palette[color_idx]
        
        return colors
    
    def _color_by_track(
        self, n_inst: int, n_nodes: int, track_id: np.ndarray | None
    ) -> np.ndarray:
        """Color by track ID."""
        colors = np.ones((n_inst, n_nodes, 4), dtype=np.float32)
        
        if track_id is None:
            # No track info, fall back to instance coloring
            return self._color_by_instance(n_inst, n_nodes, None)
        
        # Get unique track IDs
        unique_tracks = np.unique(track_id[track_id >= 0])
        n_tracks = len(unique_tracks)
        
        if n_tracks == 0:
            # No valid tracks
            return colors
        
        # Get palette
        if isinstance(self.colormap, str):
            palette = palette_lookup(self.colormap, n_tracks)
        elif isinstance(self.colormap, np.ndarray):
            palette = self.colormap
        elif callable(self.colormap):
            palette = self.colormap(n_tracks)
        else:
            palette = palette_lookup("tab20", n_tracks)
        
        # Convert to float32 and normalize
        palette = palette.astype(np.float32) / 255.0
        
        # Create track ID to color index mapping
        track_to_color = {tid: i for i, tid in enumerate(unique_tracks)}
        
        # Assign colors by track
        for i in range(n_inst):
            if i < len(track_id) and track_id[i] >= 0:
                if track_id[i] in track_to_color:
                    color_idx = track_to_color[track_id[i]] % len(palette)
                    colors[i, :, :3] = palette[color_idx]
            else:
                # No track, use gray
                colors[i, :, :3] = 0.5
        
        return colors
