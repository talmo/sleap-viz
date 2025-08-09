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

    def __init__(self, width: int, height: int, mode: str = "auto", timeline_height: int = 20) -> None:
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
            size=5.0,  # Node size (half of original)
            color=(1, 0, 0, 1),  # Red
            size_space="screen",
            aa=True,
            color_mode="vertex"  # Always use vertex colors
        )
        self.points_mesh = None
        self.points_color_buffer = None
        self._last_points_count = 0
        
        # Lines overlay
        self.lines_geometry = None
        self.lines_material = gfx.LineSegmentMaterial(
            thickness=1.5,  # Edge line width
            color=(0, 1, 0, 1),  # Green
            color_mode="vertex"  # Always use vertex colors
        )
        self.lines_mesh = None
        self.lines_color_buffer = None
        self._last_lines_count = 0
        
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
        
        # Performance display
        self.show_perf_stats = False
        self.perf_text_mesh = None
        self._init_perf_display()
        
        # Frame skip indicator
        self.show_skip_indicator = True
        self.skip_indicator_mesh = None
        self._frame_skip_quality = 1.0  # 1.0 = no skipping
        
        # Zoom and pan state
        self.zoom_level = 1.0  # 1.0 = fit to window, >1.0 = zoomed in
        self.pan_x = 0.0  # Pan offset in pixels
        self.pan_y = 0.0
        self._base_width = width
        self._base_height = height
        
        # Performance monitor (optional)
        self.perf_monitor = None

    def set_frame_image(self, frame) -> None:
        """Upload/replace the background texture with the given frame.
        
        Args:
            frame: Either a Frame object with .rgb attribute or a raw numpy array.
        """
        if frame is None:
            return
        
        # Handle both Frame objects and raw arrays
        if hasattr(frame, 'rgb'):
            image_data = frame.rgb
        else:
            image_data = frame
        
        if image_data is None:
            return
        
        perf = self.perf_monitor
        
        # Ensure frame data is float32 and normalized
        if perf: perf.start_timer("prepare_frame_data")
        frame_data = image_data.astype(np.float32) / 255.0
        
        # Convert grayscale to RGB if needed
        if frame_data.ndim == 3 and frame_data.shape[2] == 1:
            frame_data = np.repeat(frame_data, 3, axis=2)
        elif frame_data.ndim == 2:
            frame_data = np.stack([frame_data] * 3, axis=2)
        if perf: perf.end_timer("prepare_frame_data", "set_frame")
        
        # Apply image adjustments
        if perf: perf.start_timer("apply_adjustments")
        frame_data = self._apply_image_adjustments(frame_data)
        if perf: perf.end_timer("apply_adjustments", "set_frame")
        
        # Create or update texture
        if perf: perf.start_timer("texture_update")
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
        if perf: perf.end_timer("texture_update", "set_frame")
        
        # Create mesh only if it doesn't exist
        if self.video_mesh is None:
            if perf: perf.start_timer("create_mesh")
            
            # Create a plane mesh that fills the canvas
            plane_geo = gfx.plane_geometry(self.width, self.height)
            
            # Create material with the texture
            material = gfx.MeshBasicMaterial(map=self.video_texture)
            
            # Create the mesh
            self.video_mesh = gfx.Mesh(plane_geo, material)
            
            # Position video at top portion of canvas (timeline is at bottom)
            self.video_mesh.local.position = (
                self.width / 2, 
                self.timeline_height + self.height / 2,  # Shifted up
                -1
            )
            
            # Add to scene as background
            self.scene.add(self.video_mesh)
            
            if perf: perf.end_timer("create_mesh", "set_frame")
        else:
            # Just update the texture reference in the material
            if perf: perf.start_timer("update_mesh_texture")
            self.video_mesh.material.map = self.video_texture
            if perf: perf.end_timer("update_mesh_texture", "set_frame")
        
        # Apply current zoom/pan
        if perf: perf.start_timer("update_camera")
        self._update_camera()
        if perf: perf.end_timer("update_camera", "set_frame")

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
        """Update GPU buffers for points/lines with mesh reuse optimization."""
        perf = self.perf_monitor
        
        if points_xy.size == 0:
            # Clear overlays if no data
            if perf: perf.start_timer("clear_overlays")
            if self.points_mesh is not None:
                self.scene.remove(self.points_mesh)
                self.points_mesh = None
                self._last_points_count = 0
            if self.lines_mesh is not None:
                self.scene.remove(self.lines_mesh)
                self.lines_mesh = None
                self._last_lines_count = 0
            if perf: perf.end_timer("clear_overlays", "set_overlay")
            return
        
        # Get colors from color policy if not provided
        if perf: perf.start_timer("compute_colors")
        if colors_rgba is None:
            colors_rgba = self.color_policy.get_colors(
                points_xy, visible, inst_kind, track_id, node_ids
            )
        if perf: perf.end_timer("compute_colors", "set_overlay")
        
        # Flatten points for rendering
        if perf: perf.start_timer("prepare_data")
        n_inst, n_nodes, _ = points_xy.shape
        points_flat = points_xy.reshape(-1, 2)
        visible_flat = visible.reshape(-1)
        colors_flat = colors_rgba.reshape(-1, 4)
        if perf: perf.end_timer("prepare_data", "set_overlay")
        
        # Filter points based on visibility mode
        if perf: perf.start_timer("filter_points")
        if self.color_policy.invisible_mode == "hide":
            # Only include visible points
            visible_indices = np.where(visible_flat)[0]
        else:
            # Include all points (invisible ones will be dimmed)
            visible_indices = np.arange(len(points_flat))
        
        if len(visible_indices) == 0:
            return
        if perf: perf.end_timer("filter_points", "set_overlay")
        
        # Convert pixel coordinates to OpenGL coordinates (flip Y and shift for timeline)
        if perf: perf.start_timer("convert_coordinates")
        positions_3d = np.zeros((len(visible_indices), 3), dtype=np.float32)
        positions_3d[:, 0] = points_flat[visible_indices, 0]  # X stays the same
        # Flip Y and shift up by timeline height
        positions_3d[:, 1] = self.timeline_height + (self.height - points_flat[visible_indices, 1])
        positions_3d[:, 2] = 0  # Z = 0 for overlay (in front of background at z=-1)
        if perf: perf.end_timer("convert_coordinates", "set_overlay")
        
        # Update or create points mesh with buffer reuse
        if perf: perf.start_timer("update_points_mesh")
        
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
        
        points_count = len(positions_3d)
        
        # Check if we need to recreate the mesh (size changed)
        if self.points_mesh is None or points_count != self._last_points_count:
            # Remove old mesh if it exists
            if self.points_mesh is not None:
                self.scene.remove(self.points_mesh)
            
            # Create new geometry and mesh
            self.points_geometry = gfx.Geometry(positions=positions_3d)
            self.points_color_buffer = gfx.Buffer(visible_colors)
            self.points_geometry.colors = self.points_color_buffer
            
            self.points_mesh = gfx.Points(self.points_geometry, self.points_material)
            self.scene.add(self.points_mesh)
            
            self._last_points_count = points_count
        else:
            # Just update the buffers (much faster!)
            self.points_geometry.positions.data[:] = positions_3d
            self.points_geometry.positions.update_range()
            
            self.points_color_buffer.data[:] = visible_colors
            self.points_color_buffer.update_range()
        
        if perf: perf.end_timer("update_points_mesh", "set_overlay")
        
        # Apply zoom/pan transform
        if self.zoom_level != 1.0 or self.pan_x != 0 or self.pan_y != 0:
            self._update_camera()  # Use the centralized update method
        
        # Update or create lines for edges with buffer reuse
        if edges is not None and edges.size > 0:
            if perf: perf.start_timer("update_lines_mesh")
            line_positions = []
            line_colors = []
            
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
            
            if line_positions:
                line_positions = np.array(line_positions, dtype=np.float32)
                line_colors = np.array(line_colors, dtype=np.float32)
                lines_count = len(line_positions)
                
                # Check if we need to recreate the lines mesh (size changed)
                if self.lines_mesh is None or lines_count != self._last_lines_count:
                    # Remove old mesh if it exists
                    if self.lines_mesh is not None:
                        self.scene.remove(self.lines_mesh)
                    
                    # Create new geometry and mesh
                    self.lines_geometry = gfx.Geometry(positions=line_positions)
                    self.lines_color_buffer = gfx.Buffer(line_colors)
                    self.lines_geometry.colors = self.lines_color_buffer
                    
                    self.lines_mesh = gfx.Line(self.lines_geometry, self.lines_material)
                    self.scene.add(self.lines_mesh)
                    
                    self._last_lines_count = lines_count
                else:
                    # Just update the buffers (much faster!)
                    self.lines_geometry.positions.data[:] = line_positions
                    self.lines_geometry.positions.update_range()
                    
                    self.lines_color_buffer.data[:] = line_colors
                    self.lines_color_buffer.update_range()
                
                # Apply zoom/pan transform
                if self.zoom_level != 1.0 or self.pan_x != 0 or self.pan_y != 0:
                    self._update_camera()  # Use the centralized update method
            
            if perf: perf.end_timer("update_lines_mesh", "set_overlay")

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
        # Store reference to timeline view
        self.timeline_view = timeline_view
        self.timeline_meshes = []
        self._timeline_mesh_ids = set()
        self._sync_timeline_meshes()
    
    def _sync_timeline_meshes(self) -> None:
        """Sync timeline meshes from timeline view to main scene."""
        if not hasattr(self, 'timeline_view'):
            return
            
        # Check if timeline meshes have changed by comparing object IDs
        current_mesh_ids = {id(mesh) for mesh in self.timeline_view.all_meshes if mesh is not None}
        
        # If mesh IDs are the same, no sync needed
        if current_mesh_ids == self._timeline_mesh_ids:
            return
        
        # Clear old timeline meshes from main scene
        for mesh in self.timeline_meshes:
            try:
                self.scene.remove(mesh)
            except:
                pass  # Mesh wasn't in scene
        self.timeline_meshes.clear()
        
        # Add current timeline meshes to main scene
        for mesh in self.timeline_view.all_meshes:
            if mesh is not None and hasattr(mesh, "local"):
                self.scene.add(mesh)
                self.timeline_meshes.append(mesh)
        
        self._timeline_mesh_ids = current_mesh_ids

    def draw(self) -> None:
        """Render one frame to the current canvas or offscreen target."""
        perf = self.perf_monitor
        
        # Sync timeline meshes if needed
        if perf: perf.start_timer("sync_timeline")
        if hasattr(self, 'timeline_view'):
            self._sync_timeline_meshes()
        if perf: perf.end_timer("sync_timeline", "draw")
        
        # Render everything in one pass
        if perf: perf.start_timer("wgpu_render")
        self.renderer.render(self.scene, self.camera)
        if perf: perf.end_timer("wgpu_render", "draw")
        
        if self.mode != "offscreen":
            if perf: perf.start_timer("request_draw")
            self.canvas.request_draw()
            if perf: perf.end_timer("request_draw", "draw")
    
    def _init_perf_display(self) -> None:
        """Initialize performance stats text display."""
        # For now, we'll use console output for performance stats
        # TODO: Add proper text overlay once pygfx text rendering is figured out
        self.perf_text_mesh = None  # Placeholder for future implementation
    
    def update_perf_display(self, stats_text: str) -> None:
        """Update performance stats display.
        
        Args:
            stats_text: Multi-line performance statistics text.
        """
        # For now, print to console when stats are enabled
        if self.show_perf_stats:
            # Clear previous lines and print stats
            print("\033[2J\033[H")  # Clear screen
            print("[PERFORMANCE STATS]")
            print(stats_text)
            print("-" * 40)
    
    def toggle_perf_display(self) -> None:
        """Toggle visibility of performance statistics."""
        self.show_perf_stats = not self.show_perf_stats
        if self.show_perf_stats:
            print("[Performance stats enabled - will print to console]")
        else:
            print("[Performance stats disabled]")
            print("\033[2J\033[H")  # Clear screen when disabling
    
    def update_skip_indicator(self, quality: float, frames_skipped: int = 0) -> None:
        """Update frame skip quality indicator.
        
        Args:
            quality: Current rendering quality (0.0-1.0).
            frames_skipped: Number of frames skipped recently.
        """
        self._frame_skip_quality = quality
        
        # Create visual indicator (small colored box in corner)
        if self.show_skip_indicator and self.skip_indicator_mesh is None:
            # Create a small colored rectangle as indicator
            import pygfx as gfx
            
            # Create indicator geometry (small box in top-right corner)
            indicator_size = 20
            indicator_geo = gfx.plane_geometry(indicator_size, indicator_size)
            
            # Color based on quality (green = good, yellow = medium, red = poor)
            if quality > 0.8:
                color = (0, 1, 0, 0.7)  # Green
            elif quality > 0.5:
                color = (1, 1, 0, 0.7)  # Yellow
            else:
                color = (1, 0, 0, 0.7)  # Red
            
            indicator_mat = gfx.MeshBasicMaterial(color=color)
            self.skip_indicator_mesh = gfx.Mesh(indicator_geo, indicator_mat)
            
            # Position in top-right corner
            self.skip_indicator_mesh.local.position = (
                self.width - indicator_size / 2 - 10,
                self.total_height - indicator_size / 2 - 10,
                1  # In front of everything
            )
            
            self.scene.add(self.skip_indicator_mesh)
        
        # Update color based on current quality
        if self.skip_indicator_mesh and self.show_skip_indicator:
            if quality > 0.8:
                color = (0, 1, 0, 0.7)  # Green
            elif quality > 0.5:
                color = (1, 1, 0, 0.7)  # Yellow  
            else:
                color = (1, 0, 0, 0.7)  # Red
            
            self.skip_indicator_mesh.material.color = color
        
        # Hide indicator if quality is 100%
        if self.skip_indicator_mesh:
            self.skip_indicator_mesh.visible = quality < 0.99 and self.show_skip_indicator

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
    
    def set_zoom(self, zoom_level: float, center_x: float = None, center_y: float = None) -> None:
        """Set the zoom level and optionally zoom around a specific point.
        
        Args:
            zoom_level: Zoom factor (1.0 = fit to window, >1.0 = zoomed in)
            center_x: X coordinate to zoom around (in canvas pixels)
            center_y: Y coordinate to zoom around (in canvas pixels)
        """
        # Clamp zoom level to reasonable bounds
        zoom_level = max(0.5, min(10.0, zoom_level))
        
        if center_x is not None and center_y is not None:
            # Calculate the point in world space before zoom
            old_world_x = (center_x - self._base_width / 2) / self.zoom_level + self.pan_x
            old_world_y = (center_y - self._base_height / 2) / self.zoom_level + self.pan_y
            
            # Update zoom
            self.zoom_level = zoom_level
            
            # Calculate new pan to keep the same point under cursor
            new_world_x = (center_x - self._base_width / 2) / self.zoom_level + self.pan_x
            new_world_y = (center_y - self._base_height / 2) / self.zoom_level + self.pan_y
            
            # Adjust pan to compensate
            self.pan_x += old_world_x - new_world_x
            self.pan_y += old_world_y - new_world_y
        else:
            # Zoom around center
            self.zoom_level = zoom_level
        
        self._update_camera()
    
    def zoom_in(self, factor: float = 1.2, center_x: float = None, center_y: float = None) -> None:
        """Zoom in by a factor."""
        self.set_zoom(self.zoom_level * factor, center_x, center_y)
    
    def zoom_out(self, factor: float = 1.2, center_x: float = None, center_y: float = None) -> None:
        """Zoom out by a factor."""
        self.set_zoom(self.zoom_level / factor, center_x, center_y)
    
    def reset_zoom(self) -> None:
        """Reset zoom to fit the window."""
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._update_camera()
    
    def pan(self, dx: float, dy: float) -> None:
        """Pan the view by the given offset in screen pixels.
        
        Args:
            dx: Horizontal pan in pixels (positive = right)
            dy: Vertical pan in pixels (positive = down)
        """
        # Convert screen pixels to world units based on zoom
        self.pan_x += dx / self.zoom_level
        self.pan_y += dy / self.zoom_level
        self._update_camera()
    
    def set_pan(self, x: float, y: float) -> None:
        """Set absolute pan position."""
        self.pan_x = x
        self.pan_y = y
        self._update_camera()
    
    def _update_camera(self) -> None:
        """Update camera based on current zoom and pan."""
        # Apply zoom/pan by transforming the video mesh instead of the camera
        # This keeps the timeline fixed
        if self.video_mesh:
            # Scale the video mesh
            self.video_mesh.local.scale = (self.zoom_level, self.zoom_level, 1)
            
            # Position the video mesh with pan offset
            self.video_mesh.local.position = (
                self.width / 2 + self.pan_x,
                self.timeline_height + self.height / 2 + self.pan_y,
                -1
            )
        
        # Scale and position overlay meshes to match video
        # The overlays need to be scaled and positioned the same way
        if self.points_mesh:
            # Points are positioned in screen space, so we need to apply zoom around center
            # then translate by pan amount
            self.points_mesh.local.scale = (self.zoom_level, self.zoom_level, 1)
            # Center the scaling, then apply pan
            center_x = self.width / 2
            center_y = self.timeline_height + self.height / 2
            self.points_mesh.local.position = (
                center_x * (1 - self.zoom_level) + self.pan_x,
                center_y * (1 - self.zoom_level) + self.pan_y,
                0
            )
            
        if self.lines_mesh:
            # Same transformation for lines
            self.lines_mesh.local.scale = (self.zoom_level, self.zoom_level, 1)
            center_x = self.width / 2
            center_y = self.timeline_height + self.height / 2
            self.lines_mesh.local.position = (
                center_x * (1 - self.zoom_level) + self.pan_x,
                center_y * (1 - self.zoom_level) + self.pan_y,
                0
            )