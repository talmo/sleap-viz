"""pygfx-based renderer for video + overlays (onscreen/offscreen)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TYPE_CHECKING, Optional

import numpy as np
import pygfx as gfx
from wgpu.gui.auto import WgpuCanvas
from wgpu.gui.offscreen import WgpuCanvas as OffscreenCanvas

if TYPE_CHECKING:
    from .video_source import Frame
    from .timeline import TimelineView

from .styles import ColorPolicy
from . import lut as lut_module


class Visualizer:
    """Owns a pygfx scene; renders a video quad + instanced points/lines.

    Modes: desktop (window), notebook (rfb), offscreen.
    """

    def __init__(self, width: int, height: int, mode: str = "auto", timeline_height: int = 50) -> None:
        """Create canvas, device, and persistent GPU resources.
        
        Args:
            width: Video width in pixels.
            height: Video height in pixels.
            mode: Rendering mode (desktop, offscreen, etc.).
            timeline_height: Height of timeline in pixels.
        """
        self.width = width
        self.height = height
        self.timeline_height = timeline_height
        self.total_height = height + timeline_height
        self.mode = mode
        
        # Determine render mode
        if mode == "offscreen":
            self.canvas = OffscreenCanvas(size=(width, self.total_height), pixel_ratio=1)
        else:
            self.canvas = WgpuCanvas(size=(width, self.total_height), title="SLEAP Visualizer")
        
        # Create renderer
        self.renderer = gfx.WgpuRenderer(self.canvas)
        
        # Create single scene for both video and timeline
        self.scene = gfx.Scene()
        
        # Timeline meshes will be added to main scene
        self.timeline_meshes = []
        
        # Use OrthographicCamera for entire canvas (video + timeline)
        self.camera = gfx.OrthographicCamera(width, self.total_height, maintain_aspect=False)
        # Set view rectangle to cover video + timeline
        self.camera.show_rect(0, width, 0, self.total_height, depth=10)
        
        # Video background mesh
        self.video_texture = None
        self.video_mesh = None
        
        # Points overlay
        self.points_geometry = None
        self.points_material = gfx.PointsMaterial(
            size=10.0,  # Increased size for visibility
            color=(1, 0, 0, 1),  # Red
            size_space="screen",
            aa=True
        )
        self.points_mesh = None
        
        # Lines overlay
        self.lines_geometry = None
        self.lines_material = gfx.LineSegmentMaterial(
            thickness=4.0,  # Increased thickness for visibility
            color=(0, 1, 0, 1)  # Green
        )
        self.lines_mesh = None
        
        # Image adjustment parameters
        self.gain = 1.0
        self.bias = 0.0
        self.gamma = 1.0
        self.tone_map = "linear"
        self.lut = None
        self.lut_mode = "none"  # none, histogram, clahe, gamma, sigmoid
        self.lut_params = {}  # Parameters for LUT generation
        
        # Color policy
        self.color_policy = ColorPolicy(
            color_by="instance",
            colormap="tab20",
            invisible_mode="dim"
        )
        
        # Selection state for highlighting
        self.selected_instance = -1
        self.selected_node = -1
        self.hovered_instance = -1
        self.hovered_node = -1

    def set_frame_image(self, frame: Frame) -> None:
        """Upload/replace the background texture with the given frame."""
        if frame is None or frame.rgb is None:
            return
        
        # Remove old video mesh if exists
        if self.video_mesh is not None:
            self.scene.remove(self.video_mesh)
            self.video_mesh = None
        
        # Ensure frame data is float32 and normalized
        frame_data = frame.rgb.astype(np.float32) / 255.0
        
        # Convert grayscale to RGB if needed
        if frame_data.ndim == 3 and frame_data.shape[2] == 1:
            frame_data = np.repeat(frame_data, 3, axis=2)
        elif frame_data.ndim == 2:
            frame_data = np.stack([frame_data] * 3, axis=2)
        
        # Apply image adjustments
        frame_data = self._apply_image_adjustments(frame_data)
        
        # Create or update texture
        if self.video_texture is None:
            self.video_texture = gfx.Texture(frame_data, dim=2)
        else:
            try:
                # Update existing texture data
                self.video_texture.data[:] = frame_data
                h, w = frame_data.shape[:2]
                self.video_texture.update_range((0, 0, 0), (w, h, 1))
            except Exception:
                # If update fails, recreate texture
                self.video_texture = gfx.Texture(frame_data, dim=2)
        
        # Create a plane mesh that fills the canvas
        # Use plane_geometry to create a quad
        plane_geo = gfx.plane_geometry(self.width, self.height)
        
        # Create material with the texture
        material = gfx.MeshBasicMaterial(map=self.video_texture)
        
        # Create the mesh
        self.video_mesh = gfx.Mesh(plane_geo, material)
        
        # Position video at top portion of canvas (timeline is at bottom)
        # Shift up by timeline_height/2 to make room for timeline
        self.video_mesh.local.position = (
            self.width / 2, 
            self.timeline_height + self.height / 2,  # Shifted up
            -1
        )
        
        # Add to scene as background
        self.scene.add(self.video_mesh)

    def set_overlay(
        self,
        points_xy: np.ndarray,
        visible: np.ndarray,
        edges: np.ndarray,
        inst_kind: np.ndarray | None = None,
        track_id: np.ndarray | None = None,
        node_ids: np.ndarray | None = None,
        colors_rgba: np.ndarray | None = None,
        labels: list[str] | None = None,
    ) -> None:
        """Update GPU buffers for points/lines and prepare labels/tooltips."""
        # Remove old overlays
        if self.points_mesh is not None:
            self.scene.remove(self.points_mesh)
            self.points_mesh = None
        if self.lines_mesh is not None:
            self.scene.remove(self.lines_mesh)
            self.lines_mesh = None
        
        if points_xy.size == 0:
            return
        
        # Get colors from color policy if not provided
        if colors_rgba is None:
            colors_rgba = self.color_policy.get_colors(
                points_xy, visible, inst_kind, track_id, node_ids
            )
        
        # Flatten points for rendering
        n_inst, n_nodes, _ = points_xy.shape
        points_flat = points_xy.reshape(-1, 2)
        visible_flat = visible.reshape(-1)
        colors_flat = colors_rgba.reshape(-1, 4)
        
        # Filter points based on visibility mode
        if self.color_policy.invisible_mode == "hide":
            # Only include visible points
            visible_indices = np.where(visible_flat)[0]
        else:
            # Include all points (invisible ones will be dimmed)
            visible_indices = np.arange(len(points_flat))
        
        if len(visible_indices) == 0:
            return
        
        # Convert pixel coordinates to OpenGL coordinates (flip Y and shift for timeline)
        positions_3d = np.zeros((len(visible_indices), 3), dtype=np.float32)
        positions_3d[:, 0] = points_flat[visible_indices, 0]  # X stays the same
        # Flip Y and shift up by timeline height
        positions_3d[:, 1] = self.timeline_height + (self.height - points_flat[visible_indices, 1])
        positions_3d[:, 2] = 0  # Z = 0 for overlay (in front of background at z=-1)
        
        # Create points geometry and mesh
        self.points_geometry = gfx.Geometry(positions=positions_3d)
        
        # Apply colors with highlighting
        visible_colors = colors_flat[visible_indices].astype(np.float32)
        
        # Apply highlight for selected/hovered points
        for i, idx in enumerate(visible_indices):
            inst_idx = idx // n_nodes
            node_idx = idx % n_nodes
            
            # Check if this point is selected
            if inst_idx == self.selected_instance and node_idx == self.selected_node:
                # Highlight selected point (make brighter/add outline)
                visible_colors[i] = np.array([1.0, 1.0, 0.0, 1.0])  # Yellow for selection
            elif inst_idx == self.hovered_instance and node_idx == self.hovered_node:
                # Highlight hovered point
                visible_colors[i] = visible_colors[i] * 1.5  # Brighten
                visible_colors[i] = np.clip(visible_colors[i], 0, 1)
        
        # Create a Buffer for colors
        colors_buffer = gfx.Buffer(visible_colors)
        self.points_geometry.colors = colors_buffer
        self.points_material.color_mode = "vertex"
        
        self.points_mesh = gfx.Points(self.points_geometry, self.points_material)
        self.scene.add(self.points_mesh)
        
        # Create lines for edges with color support
        if edges is not None and edges.size > 0:
            line_positions = []
            line_colors = []
            line_count = 0
            
            for inst_idx in range(n_inst):
                inst_points = points_xy[inst_idx]
                inst_visible = visible[inst_idx]
                inst_colors = colors_rgba[inst_idx]
                
                for edge in edges:
                    node1, node2 = int(edge[0]), int(edge[1])
                    # Check bounds and visibility
                    if (node1 < len(inst_visible) and node2 < len(inst_visible)):
                        # Check visibility based on policy
                        should_draw = False
                        if self.color_policy.invisible_mode == "hide":
                            # Only draw if both nodes are visible
                            should_draw = inst_visible[node1] and inst_visible[node2]
                        else:
                            # Draw if at least one node exists (dimmed lines will show)
                            should_draw = True
                        
                        if should_draw:
                            p1 = inst_points[node1]
                            p2 = inst_points[node2]
                            
                            # Add line segment (flip Y coordinate and shift for timeline)
                            line_positions.extend([
                                [float(p1[0]), float(self.timeline_height + self.height - p1[1]), 0],
                                [float(p2[0]), float(self.timeline_height + self.height - p2[1]), 0]
                            ])
                            
                            # Use average color of the two nodes for the edge
                            edge_color = (inst_colors[node1] + inst_colors[node2]) / 2.0
                            line_colors.extend([edge_color, edge_color])
                            line_count += 1
            
            if line_count > 0:
                line_positions = np.array(line_positions, dtype=np.float32)
                line_colors = np.array(line_colors, dtype=np.float32)
                
                self.lines_geometry = gfx.Geometry(positions=line_positions)
                # Add colors to lines
                colors_buffer = gfx.Buffer(line_colors)
                self.lines_geometry.colors = colors_buffer
                
                # Update line material to use vertex colors
                self.lines_material.color_mode = "vertex"
                
                self.lines_mesh = gfx.Line(
                    self.lines_geometry,
                    self.lines_material
                )
                self.scene.add(self.lines_mesh)

    def set_color_policy(
        self,
        *,
        color_by: str | Callable[..., np.ndarray] = "instance",
        colormap: str | Callable[..., np.ndarray] = "tab20",
        invisible_mode: Literal["dim", "hide"] = "dim",
        dim_factor: float = 0.3,
    ) -> None:
        """Configure color mapping and invisible-point styling."""
        self.color_policy = ColorPolicy(
            color_by=color_by,
            colormap=colormap,
            invisible_mode=invisible_mode,
            dim_factor=dim_factor
        )

    def set_image_adjust(
        self,
        *,
        gain: float = 1.0,
        bias: float = 0.0,
        gamma: float = 1.0,
        tone_map: Literal["linear", "lut"] = "linear",
        lut: np.ndarray | None = None,
        lut_mode: Literal["none", "histogram", "clahe", "gamma", "sigmoid"] = "none",
        lut_params: dict | None = None,
    ) -> None:
        """Configure brightness/contrast/gamma and optional LUT tone mapping.
        
        Args:
            gain: Contrast multiplier (default 1.0).
            bias: Brightness offset (default 0.0).
            gamma: Gamma correction value (default 1.0).
            tone_map: Tone mapping mode ("linear" or "lut").
            lut: Pre-computed 256x3 uint8 LUT array.
            lut_mode: LUT generation mode if lut is None.
            lut_params: Parameters for LUT generation (depends on mode).
        """
        self.gain = gain
        self.bias = bias
        self.gamma = gamma
        self.tone_map = tone_map
        self.lut = lut
        self.lut_mode = lut_mode
        self.lut_params = lut_params or {}
    
    def _apply_image_adjustments(self, frame: np.ndarray) -> np.ndarray:
        """Apply gain, bias, gamma, and optional LUT to frame data.
        
        Args:
            frame: Normalized float32 frame data in range [0, 1] with shape (H, W, 3).
            
        Returns:
            Adjusted frame data, still in range [0, 1].
        """
        # Apply gain and bias (contrast and brightness)
        adjusted = frame * self.gain + self.bias
        
        # Apply gamma correction
        if self.gamma != 1.0:
            # Clamp to avoid negative values before gamma
            adjusted = np.clip(adjusted, 0, 1)
            adjusted = np.power(adjusted, 1.0 / self.gamma)
        
        # Apply tone mapping
        if self.tone_map == "lut":
            # Generate LUT if needed
            if self.lut is None and self.lut_mode != "none":
                self._generate_lut(frame)
            
            if self.lut is not None:
                # Convert to uint8 indices for LUT lookup
                indices = np.clip(adjusted * 255, 0, 255).astype(np.uint8)
                # Apply LUT (assumed to be 256x3 uint8)
                # Index each channel separately
                result = np.zeros_like(frame)
                for c in range(3):
                    result[:, :, c] = self.lut[indices[:, :, c], c].astype(np.float32) / 255.0
                adjusted = result
        
        # Final clamp to valid range
        return np.clip(adjusted, 0, 1)
    
    def _generate_lut(self, frame: np.ndarray) -> None:
        """Generate LUT based on current mode and parameters.
        
        Args:
            frame: Current frame data for histogram-based methods.
        """
        # Convert frame to uint8 for LUT generation
        frame_uint8 = np.clip(frame * 255, 0, 255).astype(np.uint8)
        
        if self.lut_mode == "histogram":
            channel_mode = self.lut_params.get("channel_mode", "luminance")
            self.lut = lut_module.generate_histogram_equalization_lut(
                frame_uint8, channel_mode=channel_mode
            )
        elif self.lut_mode == "clahe":
            clip_limit = self.lut_params.get("clip_limit", 2.0)
            grid_size = self.lut_params.get("grid_size", (8, 8))
            channel_mode = self.lut_params.get("channel_mode", "luminance")
            self.lut = lut_module.generate_clahe_lut(
                frame_uint8, clip_limit=clip_limit, 
                grid_size=grid_size, channel_mode=channel_mode
            )
        elif self.lut_mode == "gamma":
            gamma = self.lut_params.get("gamma", 2.2)
            self.lut = lut_module.generate_gamma_lut(gamma)
        elif self.lut_mode == "sigmoid":
            midpoint = self.lut_params.get("midpoint", 0.5)
            slope = self.lut_params.get("slope", 10.0)
            self.lut = lut_module.generate_sigmoid_lut(midpoint, slope)
        else:
            self.lut = lut_module.generate_identity_lut()
    
    def update_lut(self, frame: np.ndarray | None = None) -> None:
        """Update the LUT based on current mode and optionally a reference frame.
        
        Args:
            frame: Optional frame to use for histogram-based LUT generation.
                   If None, the LUT will be cleared.
        """
        if frame is not None and self.lut_mode != "none":
            self._generate_lut(frame)
        else:
            self.lut = None
    def set_timeline(self, timeline_view: TimelineView) -> None:
        """Set the timeline view for rendering.
        
        Args:
            timeline_view: The timeline view to render.
        """
        # Clear old timeline meshes
        for mesh in self.timeline_meshes:
            self.scene.remove(mesh)
        self.timeline_meshes.clear()
        
        # Add timeline meshes to main scene
        # Position them at the bottom of the canvas
        for mesh in timeline_view.scene.children:
            # Clone the mesh and adjust position
            if hasattr(mesh, "local"):
                # Timeline meshes are already positioned correctly in their own coord system
                # We just need to ensure they're at the bottom of our canvas
                self.scene.add(mesh)
                self.timeline_meshes.append(mesh)

    def draw(self) -> None:
        """Render one frame to the current canvas or offscreen target."""
        # Render everything in one pass
        self.renderer.render(self.scene, self.camera)
        
        if self.mode != "offscreen":
            self.canvas.request_draw()

    def read_pixels(self) -> np.ndarray:
        """Return the last rendered image as uint8 H x W x 3.
        
        Note: The returned array shape is (height, width, 3) which is standard
        for image arrays, even though the canvas was created with (width, height).
        """
        # For offscreen mode or notebook mode, use canvas.draw()
        if self.mode in ("offscreen", "notebook"):
            image = np.asarray(self.canvas.draw())
        else:
            # For desktop mode, try to use snapshot
            try:
                image = self.renderer.snapshot()
            except AttributeError:
                # Fallback to canvas.draw() if snapshot not available
                image = np.asarray(self.canvas.draw())
        
        # The image is RGBA, convert to RGB
        if image.shape[-1] == 4:
            image = image[:, :, :3]
        
        # Ensure it's uint8
        if image.dtype != np.uint8:
            image = image.astype(np.uint8)
        
        return image