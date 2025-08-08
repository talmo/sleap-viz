"""pygfx-based renderer for video + overlays (onscreen/offscreen)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TYPE_CHECKING

import numpy as np
import pygfx as gfx
from wgpu.gui.auto import WgpuCanvas
from wgpu.gui.offscreen import WgpuCanvas as OffscreenCanvas

if TYPE_CHECKING:
    from .video_source import Frame


class Visualizer:
    """Owns a pygfx scene; renders a video quad + instanced points/lines.

    Modes: desktop (window), notebook (rfb), offscreen.
    """

    def __init__(self, width: int, height: int, mode: str = "auto") -> None:
        """Create canvas, device, and persistent GPU resources."""
        self.width = width
        self.height = height
        self.mode = mode
        
        # Determine render mode
        if mode == "offscreen":
            self.canvas = OffscreenCanvas(size=(width, height), pixel_ratio=1)
        else:
            self.canvas = WgpuCanvas(size=(width, height), title="SLEAP Visualizer")
        
        # Create renderer
        self.renderer = gfx.WgpuRenderer(self.canvas)
        
        # Create scene
        self.scene = gfx.Scene()
        
        # Use OrthographicCamera for better control
        self.camera = gfx.OrthographicCamera(width, height, maintain_aspect=False)
        # Set view rectangle: left, right, top, bottom
        # Flip Y-axis to match image coordinates (Y increases downward)
        self.camera.show_rect(0, width, height, 0)  # bottom=height, top=0 flips Y
        
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
        self.lines_material = gfx.LineMaterial(
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
        
        # Color policy
        self.color_by = "instance"
        self.colormap = "tab20"
        self.invisible_mode = "dim"

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
        
        # Position at center of canvas (plane_geometry is centered at origin)
        self.video_mesh.local.position = (self.width / 2, self.height / 2, -1)
        
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
        
        # Flatten points for rendering
        n_inst, n_nodes, _ = points_xy.shape
        points_flat = points_xy.reshape(-1, 2)
        visible_flat = visible.reshape(-1)
        
        # Filter visible points
        visible_indices = np.where(visible_flat)[0]
        if len(visible_indices) == 0:
            return
        
        # Use pixel coordinates directly
        positions_3d = np.zeros((len(visible_indices), 3), dtype=np.float32)
        positions_3d[:, :2] = points_flat[visible_indices]
        positions_3d[:, 2] = 0  # Z = 0 for overlay (in front of background at z=-1)
        
        # Create points geometry and mesh
        self.points_geometry = gfx.Geometry(positions=positions_3d)
        
        # Apply colors if provided
        if colors_rgba is not None and colors_rgba.size > 0:
            colors_flat = colors_rgba.reshape(-1, 4)
            visible_colors = colors_flat[visible_indices].astype(np.float32)
            self.points_geometry.colors = visible_colors
            self.points_material.color_mode = "vertex"
        else:
            self.points_material.color_mode = "uniform"
            self.points_material.color = (1, 0, 0, 1)  # Red
        
        self.points_mesh = gfx.Points(self.points_geometry, self.points_material)
        self.scene.add(self.points_mesh)
        
        # Create lines for edges
        if edges is not None and edges.size > 0:
            print(f"Processing {edges.shape[0]} edges for {n_inst} instances")
            line_positions = []
            line_count = 0
            
            for inst_idx in range(n_inst):
                inst_points = points_xy[inst_idx]
                inst_visible = visible[inst_idx]
                
                for edge in edges:
                    node1, node2 = int(edge[0]), int(edge[1])
                    # Check bounds and visibility
                    if (node1 < len(inst_visible) and node2 < len(inst_visible)):
                        if inst_visible[node1] and inst_visible[node2]:
                            p1 = inst_points[node1]
                            p2 = inst_points[node2]
                            
                            # Add line segment
                            line_positions.extend([
                                [float(p1[0]), float(p1[1]), 0],
                                [float(p2[0]), float(p2[1]), 0]
                            ])
                            line_count += 1
            
            print(f"Created {line_count} line segments")
            
            if line_count > 0:  # Check line_count instead of line_positions
                try:
                    line_positions = np.array(line_positions, dtype=np.float32)
                    print(f"Line positions shape: {line_positions.shape}")
                    self.lines_geometry = gfx.Geometry(positions=line_positions)
                    self.lines_mesh = gfx.Line(
                        self.lines_geometry,
                        self.lines_material,
                        mode="segments"
                    )
                    self.scene.add(self.lines_mesh)
                    print(f"Added lines mesh to scene")
                except Exception as e:
                    print(f"Error adding lines: {e}")

    def set_color_policy(
        self,
        *,
        color_by: str | Callable[..., np.ndarray] = "instance",
        colormap: str | Callable[..., np.ndarray] = "tab20",
        invisible_mode: Literal["dim", "hide"] = "dim",
    ) -> None:
        """Configure color mapping and invisible-point styling."""
        self.color_by = color_by
        self.colormap = colormap
        self.invisible_mode = invisible_mode

    def set_image_adjust(
        self,
        *,
        gain: float = 1.0,
        bias: float = 0.0,
        gamma: float = 1.0,
        tone_map: Literal["linear", "lut"] = "linear",
        lut: np.ndarray | None = None,
    ) -> None:
        """Configure brightness/contrast/gamma and optional LUT tone mapping."""
        self.gain = gain
        self.bias = bias
        self.gamma = gamma
        self.tone_map = tone_map
        self.lut = lut

    def draw(self) -> None:
        """Render one frame to the current canvas or offscreen target."""
        self.renderer.render(self.scene, self.camera)
        
        if self.mode != "offscreen":
            self.canvas.request_draw()

    def read_pixels(self) -> np.ndarray:
        """Return the last rendered image as uint8 H x W x 3.
        
        Note: The returned array shape is (height, width, 3) which is standard
        for image arrays, even though the canvas was created with (width, height).
        """
        # For offscreen mode, use canvas.draw() which returns the rendered image
        if self.mode == "offscreen":
            image = np.asarray(self.canvas.draw())
        else:
            # For onscreen, use snapshot
            image = self.renderer.snapshot()
        
        # The image is RGBA, convert to RGB
        if image.shape[-1] == 4:
            image = image[:, :, :3]
        
        # Ensure it's uint8
        if image.dtype != np.uint8:
            image = image.astype(np.uint8)
        
        return image