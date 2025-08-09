"""Jupyter notebook widget for interactive SLEAP visualization."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import numpy as np
import pygfx as gfx
from wgpu.gui.jupyter import JupyterWgpuCanvas

from .annotation_source import AnnotationSource
from .controller import Controller
from .interactive import InteractiveControls
from .renderer import Visualizer
from .timeline import TimelineController, TimelineModel, TimelineView
from .video_source import VideoSource

if TYPE_CHECKING:
    from sleap_io import Labels


class NotebookViewer:
    """Interactive SLEAP viewer widget for Jupyter notebooks.
    
    This provides a fully interactive viewer that can be embedded in Jupyter
    notebooks. It supports all the features of the desktop viewer including:
    - Video playback with pose overlays
    - Timeline scrubbing and zoom
    - Keyboard and mouse controls
    - Image adjustments (brightness, contrast, gamma)
    - Color policies for nodes/instances/tracks
    - LUT tone mapping
    
    Example:
        ```python
        from sleap_viz.notebook import NotebookViewer
        
        viewer = NotebookViewer("path/to/labels.slp", width=800, height=600)
        await viewer.initialize()
        viewer.show()  # Returns widget to display in notebook
        ```
    """
    
    def __init__(
        self,
        labels_path: str,
        width: int = 800,
        height: int = 600,
        fps: float = 25.0,
        color_by: str = "instance",
        colormap: str = "tab20",
        gain: float = 1.0,
        bias: float = 0.0,
        gamma: float = 1.0,
        tone_map: str = "linear",
        lut_mode: str = "none",
    ):
        """Initialize the notebook viewer.
        
        Args:
            labels_path: Path to SLEAP labels file (.slp).
            width: Width of viewer in pixels.
            height: Height of viewer in pixels (excluding timeline).
            fps: Playback frames per second.
            color_by: Color policy ('instance', 'node', 'track').
            colormap: Color palette to use.
            gain: Image contrast adjustment (1.0 = normal).
            bias: Image brightness adjustment (0.0 = normal).
            gamma: Image gamma correction (1.0 = normal).
            tone_map: Tone mapping mode ('linear' or 'lut').
            lut_mode: LUT mode ('none', 'histogram', 'clahe', 'gamma', 'sigmoid').
        """
        self.labels_path = labels_path
        self.width = width
        self.height = height
        self.fps = fps
        
        # Image adjustment settings
        self.gain = gain
        self.bias = bias
        self.gamma = gamma
        self.tone_map = tone_map
        self.lut_mode = lut_mode
        
        # Color settings
        self.color_by = color_by
        self.colormap = colormap
        
        # Components (initialized in initialize())
        self.labels: Labels | None = None
        self.video_source: VideoSource | None = None
        self.annotation_source: AnnotationSource | None = None
        self.visualizer: Visualizer | None = None
        self.controller: Controller | None = None
        self.timeline_controller: TimelineController | None = None
        self.interactive: InteractiveControls | None = None
        
        # Jupyter-specific components
        self.canvas: JupyterWgpuCanvas | None = None
        
    async def initialize(self) -> None:
        """Initialize all components asynchronously.
        
        This must be called before using the viewer.
        """
        # Load labels
        from sleap_io import load_file
        self.labels = load_file(self.labels_path)
        
        # Get video
        video = self.labels.video
        if not video:
            raise ValueError("No video found in labels file")
        
        # Create data sources
        self.video_source = VideoSource(video)
        self.annotation_source = AnnotationSource(self.labels)
        
        # Get video dimensions
        video_width = video.backend.shape[2] if len(video.backend.shape) > 2 else 640
        video_height = video.backend.shape[1] if len(video.backend.shape) > 1 else 480
        
        # Create Jupyter canvas with jupyter_rfb
        self.canvas = JupyterWgpuCanvas(size=(self.width, self.height + 50))
        
        # Create visualizer with notebook mode
        self.visualizer = Visualizer(
            video_width, 
            video_height, 
            mode="notebook",
            timeline_height=20
        )
        
        # Override canvas with our Jupyter canvas
        self.visualizer.canvas = self.canvas
        
        # Re-initialize renderer with new canvas
        self.visualizer.renderer = gfx.WgpuRenderer(self.canvas)
        
        # Apply initial settings
        self.visualizer.set_image_adjust(
            gain=self.gain,
            bias=self.bias,
            gamma=self.gamma,
            tone_map=self.tone_map,
            lut_mode=self.lut_mode
        )
        
        self.visualizer.set_color_policy(
            color_by=self.color_by,
            colormap=self.colormap
        )
        
        # Create timeline components
        total_frames = self.labels.video.shape[0] if self.labels.video else 0
        self.timeline_model = TimelineModel(total_frames)
        self.timeline_view = TimelineView(self.width, 20)
        self.timeline_controller = TimelineController(
            self.timeline_model,
            self.timeline_view
        )
        
        # Set annotation source for timeline
        self.timeline_controller.set_annotation_source(self.annotation_source)
        
        # Create controller
        self.controller = Controller(
            self.video_source,
            self.annotation_source,
            self.visualizer,
            video,  # Pass the video object
            play_fps=self.fps
        )
        
        # Store timeline reference in controller for keyboard shortcuts
        self.controller.timeline_controller = self.timeline_controller
        
        # Create interactive controls
        self.interactive = InteractiveControls(self.controller, self.canvas)
        self.interactive.attach_handlers()
        
        # Initial render
        await self.controller.goto(0)
        
    def show(self) -> Any:
        """Return the widget to display in Jupyter notebook.
        
        Returns:
            The JupyterWgpuCanvas widget that can be displayed in a notebook cell.
        """
        if self.canvas is None:
            raise RuntimeError("Viewer not initialized. Call await viewer.initialize() first.")
        
        # Return the canvas widget directly
        return self.canvas
    
    async def play(self) -> None:
        """Start playback."""
        if self.controller:
            await self.controller.play()
    
    async def pause(self) -> None:
        """Pause playback."""
        if self.controller:
            await self.controller.pause()
    
    async def goto(self, frame: int) -> None:
        """Go to a specific frame.
        
        Args:
            frame: Frame index to jump to.
        """
        if self.controller:
            await self.controller.goto(frame)
    
    def set_playback_speed(self, speed: float) -> None:
        """Set playback speed.
        
        Args:
            speed: Playback speed multiplier (1.0 = normal).
        """
        if self.controller:
            self.controller.set_playback_speed(speed)
    
    def set_color_policy(
        self,
        color_by: str | None = None,
        colormap: str | None = None,
        invisible_mode: str | None = None
    ) -> None:
        """Update color policy settings.
        
        Args:
            color_by: How to color ('instance', 'node', 'track').
            colormap: Color palette to use.
            invisible_mode: How to handle invisible points ('dim', 'hide').
        """
        if self.visualizer:
            self.visualizer.set_color_policy(
                color_by=color_by or self.color_by,
                colormap=colormap or self.colormap,
                invisible_mode=invisible_mode or "dim"
            )
            # Trigger redraw
            if self.controller:
                asyncio.create_task(
                    self.controller.goto(self.controller.current_frame)
                )
    
    def set_image_adjust(
        self,
        gain: float | None = None,
        bias: float | None = None,
        gamma: float | None = None,
        tone_map: str | None = None,
        lut_mode: str | None = None
    ) -> None:
        """Update image adjustment settings.
        
        Args:
            gain: Contrast adjustment (1.0 = normal).
            bias: Brightness adjustment (0.0 = normal).
            gamma: Gamma correction (1.0 = normal).
            tone_map: Tone mapping mode ('linear' or 'lut').
            lut_mode: LUT mode ('none', 'histogram', 'clahe', 'gamma', 'sigmoid').
        """
        if self.visualizer:
            self.visualizer.set_image_adjust(
                gain=gain if gain is not None else self.gain,
                bias=bias if bias is not None else self.bias,
                gamma=gamma if gamma is not None else self.gamma,
                tone_map=tone_map if tone_map is not None else self.tone_map,
                lut_mode=lut_mode if lut_mode is not None else self.lut_mode
            )
            # Trigger redraw
            if self.controller:
                asyncio.create_task(
                    self.controller.goto(self.controller.current_frame)
                )
    
    def get_current_frame(self) -> np.ndarray | None:
        """Get the current rendered frame as a numpy array.
        
        Note: Frame extraction is not currently supported in notebook mode.
        
        Returns:
            RGB image array of shape (height, width, 3) or None if not available.
        """
        # TODO: Implement frame extraction for JupyterWgpuCanvas
        # This requires either using offscreen rendering or finding
        # the right method to extract pixels from JupyterWgpuCanvas
        return None
    
    @property
    def current_frame_index(self) -> int:
        """Get the current frame index."""
        if self.controller:
            return self.controller.current_frame
        return 0
    
    @property
    def total_frames(self) -> int:
        """Get total number of frames."""
        if self.controller:
            return self.controller.total_frames
        return 0