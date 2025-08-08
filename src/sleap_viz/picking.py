"""GPU-based picking for efficient point selection and hover detection.

This module implements GPU picking using an ID buffer approach where each
point is rendered with a unique color that encodes its instance and node IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

import numpy as np
import pygfx as gfx
from wgpu.gui.offscreen import WgpuCanvas as OffscreenCanvas

if TYPE_CHECKING:
    from .renderer import Visualizer


@dataclass
class PickingResult:
    """Result of a picking operation."""
    
    instance_id: int
    node_id: int
    screen_pos: Tuple[int, int]
    world_pos: Optional[np.ndarray] = None
    node_name: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        """Check if this is a valid pick (not background)."""
        return self.instance_id >= 0 and self.node_id >= 0


class GPUPicker:
    """GPU-based picker for point selection using ID buffer rendering.
    
    This class renders points to an offscreen buffer where each point's color
    encodes its instance and node IDs. Picking is then performed by reading
    the pixel value at the mouse position.
    """
    
    def __init__(self, visualizer: Visualizer):
        """Initialize the GPU picker.
        
        Args:
            visualizer: The main visualizer to pick from.
        """
        self.visualizer = visualizer
        self.renderer = visualizer.renderer
        self.canvas = visualizer.canvas
        
        # Create offscreen render target for ID buffer
        self._picking_renderer = None
        self._picking_scene = None
        self._picking_camera = None
        self._picking_points = None
        
        self._setup_picking_pipeline()
    
    def _setup_picking_pipeline(self):
        """Set up the offscreen rendering pipeline for picking."""
        # Create a separate scene for picking
        self._picking_scene = gfx.Scene()
        
        # Create camera matching the main camera
        self._picking_camera = gfx.OrthographicCamera()
        
        # Create picking-specific renderer using offscreen canvas
        self._picking_canvas = OffscreenCanvas(size=(100, 100))
        self._picking_renderer = gfx.WgpuRenderer(self._picking_canvas)
    
    def _encode_id(self, instance_id: int, node_id: int) -> Tuple[float, float, float, float]:
        """Encode instance and node IDs as RGBA color.
        
        Args:
            instance_id: Instance index (0-65535).
            node_id: Node/keypoint index (0-255).
            
        Returns:
            RGBA color values in [0, 1] range.
        """
        # Encode instance ID in RG channels (16 bits)
        r = (instance_id >> 8) / 255.0
        g = (instance_id & 0xFF) / 255.0
        
        # Encode node ID in B channel (8 bits)
        b = node_id / 255.0
        
        # Alpha always 1.0 for valid picks
        a = 1.0
        
        return (r, g, b, a)
    
    def _decode_id(self, color: np.ndarray) -> Tuple[int, int]:
        """Decode instance and node IDs from RGBA color.
        
        Args:
            color: RGBA color values as uint8 array.
            
        Returns:
            Tuple of (instance_id, node_id).
        """
        if color[3] == 0:  # Alpha = 0 means background
            return (-1, -1)
        
        # Decode instance ID from RG channels
        instance_id = (int(color[0]) << 8) | int(color[1])
        
        # Decode node ID from B channel
        node_id = int(color[2])
        
        return (instance_id, node_id)
    
    def _create_picking_geometry(self) -> Optional[gfx.Points]:
        """Create point geometry with ID-encoded colors for picking.
        
        Returns:
            Points object for picking or None if no data.
        """
        # Get current frame data
        frame_idx = self.visualizer.controller.current_frame
        frame_data = self.visualizer.annotation_source.get_frame_data(frame_idx)
        
        if frame_data is None:
            return None
        
        points = []
        colors = []
        sizes = []
        
        # Process each instance
        for inst_idx, instance in enumerate(frame_data.instances):
            for node_idx, point in enumerate(instance.points):
                if point.x is None or point.y is None:
                    continue
                
                # Add point position
                points.append([point.x, point.y, 0])
                
                # Encode IDs as color
                color = self._encode_id(inst_idx, node_idx)
                colors.append(color)
                
                # Use slightly larger size for easier picking
                sizes.append(self.visualizer.point_size * 1.5)
        
        if not points:
            return None
        
        # Create points geometry
        points_array = np.array(points, dtype=np.float32)
        colors_array = np.array(colors, dtype=np.float32)
        sizes_array = np.array(sizes, dtype=np.float32)
        
        geometry = gfx.Geometry(
            positions=points_array,
            colors=colors_array,
            sizes=sizes_array,
        )
        
        # Use unlit material to preserve exact colors
        material = gfx.PointsMaterial(
            color_mode="vertex",
            size_mode="vertex",
        )
        
        return gfx.Points(geometry, material)
    
    def pick(self, x: int, y: int) -> PickingResult:
        """Perform picking at the given screen coordinates.
        
        Args:
            x: Screen X coordinate.
            y: Screen Y coordinate.
            
        Returns:
            PickingResult with the picked instance/node or invalid result.
        """
        # Get canvas size
        width, height = self.canvas.get_logical_size()
        
        # Resize picking canvas if needed
        if self._picking_canvas.get_logical_size() != (width, height):
            self._picking_canvas.set_logical_size(width, height)
        
        # Clear picking scene
        for child in list(self._picking_scene.children):
            self._picking_scene.remove(child)
        
        # Create picking geometry
        picking_points = self._create_picking_geometry()
        if picking_points is None:
            return PickingResult(-1, -1, (x, y))
        
        # Add to picking scene
        self._picking_scene.add(picking_points)
        
        # Set camera to match canvas size
        self._picking_camera.width = width
        self._picking_camera.height = height
        self._picking_camera.show_rect(0, width, 0, height, depth=10)
        
        # Render to offscreen buffer
        self._picking_renderer.render(
            self._picking_scene,
            self._picking_camera,
            clear_color=(0, 0, 0, 0),  # Clear to transparent
        )
        
        # Force the render to complete
        self._picking_canvas.draw()
        
        # Read pixel at mouse position
        # Note: Y coordinate is flipped in GPU coordinates
        gpu_y = height - y - 1
        
        # Read a 1x1 pixel region at the mouse position
        pixel_data = self._picking_renderer.render(
            self._picking_scene,
            self._picking_camera,
        )
        image = np.asarray(self._picking_canvas.draw())
        
        # Bounds check
        if gpu_y < 0 or gpu_y >= height or x < 0 or x >= width:
            return PickingResult(-1, -1, (x, y))
        
        # Get pixel color
        color = image[int(gpu_y), int(x)]
        instance_id, node_id = self._decode_id(color)
        
        # Get world position and node name if valid pick
        world_pos = None
        node_name = None
        if instance_id >= 0 and node_id >= 0:
            frame_idx = self.visualizer.controller.current_frame
            frame_data = self.visualizer.annotation_source.get_frame_data(frame_idx)
            if frame_data and instance_id < len(frame_data.instances):
                instance = frame_data.instances[instance_id]
                if node_id < len(instance.points):
                    point = instance.points[node_id]
                    if point.x is not None and point.y is not None:
                        world_pos = np.array([point.x, point.y], dtype=np.float32)
                    # Get node name from skeleton
                    skeleton = self.visualizer.annotation_source.skeleton
                    if skeleton and node_id < len(skeleton.nodes):
                        node_name = skeleton.nodes[node_id].name
        
        return PickingResult(instance_id, node_id, (x, y), world_pos, node_name)
    
    def pick_radius(self, x: int, y: int, radius: int = 5) -> list[PickingResult]:
        """Pick all points within a radius of the given position.
        
        Args:
            x: Screen X coordinate.
            y: Screen Y coordinate.
            radius: Search radius in pixels.
            
        Returns:
            List of PickingResults for all points within radius.
        """
        results = []
        
        # Sample in a grid pattern within radius
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                # Check if within circular radius
                if dx * dx + dy * dy > radius * radius:
                    continue
                
                # Pick at this position
                result = self.pick(x + dx, y + dy)
                if result.is_valid and result not in results:
                    results.append(result)
        
        return results