"""Offscreen/headless rendering for batch processing and export."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

import numpy as np
from PIL import Image

from .annotation_source import AnnotationSource
from .controller import Controller
from .renderer import Visualizer
from .timeline import TimelineController, TimelineModel, TimelineView
from .video_source import VideoSource

if TYPE_CHECKING:
    from sleap_io import Labels


class OffscreenRenderer:
    """Headless renderer for batch processing SLEAP visualizations.
    
    This provides efficient batch rendering without requiring a display.
    Ideal for:
    - Server-side rendering
    - Batch video generation
    - Automated frame exports
    - CI/CD pipelines
    - High-throughput processing
    
    Example:
        ```python
        renderer = OffscreenRenderer("labels.slp")
        await renderer.initialize()
        
        # Export single frame
        frame = await renderer.render_frame(100)
        
        # Batch export
        await renderer.export_frames(
            frame_indices=[0, 50, 100],
            output_dir="exports"
        )
        
        # Generate video
        await renderer.export_video(
            output_path="output.mp4",
            start_frame=0,
            end_frame=1000,
            fps=30
        )
        ```
    """
    
    def __init__(
        self,
        labels_path: str,
        width: int | None = None,
        height: int | None = None,
        color_by: str = "instance",
        colormap: str = "tab20",
        gain: float = 1.0,
        bias: float = 0.0,
        gamma: float = 1.0,
        tone_map: str = "linear",
        lut_mode: str = "none",
        include_timeline: bool = False,
        timeline_height: int = 50,
    ):
        """Initialize the offscreen renderer.
        
        Args:
            labels_path: Path to SLEAP labels file (.slp).
            width: Override video width (None to use original).
            height: Override video height (None to use original).
            color_by: Color policy ('instance', 'node', 'track').
            colormap: Color palette to use.
            gain: Image contrast adjustment (1.0 = normal).
            bias: Image brightness adjustment (0.0 = normal).
            gamma: Image gamma correction (1.0 = normal).
            tone_map: Tone mapping mode ('linear' or 'lut').
            lut_mode: LUT mode ('none', 'histogram', 'clahe', 'gamma', 'sigmoid').
            include_timeline: Whether to include timeline in renders.
            timeline_height: Height of timeline if included.
        """
        self.labels_path = labels_path
        self.override_width = width
        self.override_height = height
        
        # Rendering settings
        self.color_by = color_by
        self.colormap = colormap
        self.gain = gain
        self.bias = bias
        self.gamma = gamma
        self.tone_map = tone_map
        self.lut_mode = lut_mode
        
        # Timeline settings
        self.include_timeline = include_timeline
        self.timeline_height = timeline_height if include_timeline else 0
        
        # Components (initialized in initialize())
        self.labels: Labels | None = None
        self.video_source: VideoSource | None = None
        self.annotation_source: AnnotationSource | None = None
        self.visualizer: Visualizer | None = None
        self.controller: Controller | None = None
        self.timeline_controller: TimelineController | None = None
        
        # Render cache
        self._last_frame_idx: int = -1
        self._render_cache: np.ndarray | None = None
        
    async def initialize(self) -> None:
        """Initialize all components for rendering.
        
        This must be called before any rendering operations.
        """
        from sleap_io import load_file
        
        # Load labels
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
        
        # Override dimensions if specified
        if self.override_width:
            video_width = self.override_width
        if self.override_height:
            video_height = self.override_height
        
        # Create offscreen visualizer
        self.visualizer = Visualizer(
            video_width,
            video_height,
            mode="offscreen",
            timeline_height=self.timeline_height
        )
        
        # Apply rendering settings
        self.visualizer.set_color_policy(
            color_by=self.color_by,
            colormap=self.colormap
        )
        
        self.visualizer.set_image_adjust(
            gain=self.gain,
            bias=self.bias,
            gamma=self.gamma,
            tone_map=self.tone_map,
            lut_mode=self.lut_mode
        )
        
        # Create timeline if requested
        if self.include_timeline:
            total_frames = len(video)
            self.timeline_model = TimelineModel(total_frames)
            self.timeline_view = TimelineView(video_width, self.timeline_height)
            self.timeline_controller = TimelineController(
                self.timeline_model,
                self.timeline_view
            )
            self.timeline_controller.set_annotation_source(self.annotation_source)
            
            # Connect timeline to visualizer
            self.visualizer.set_timeline(self.timeline_view)
        
        # Create controller
        self.controller = Controller(
            self.video_source,
            self.annotation_source,
            self.visualizer,
            video,
            play_fps=25
        )
        
        if self.timeline_controller:
            self.controller.timeline_controller = self.timeline_controller
    
    async def render_frame(
        self,
        frame_idx: int,
        use_cache: bool = True
    ) -> np.ndarray:
        """Render a single frame and return as numpy array.
        
        Args:
            frame_idx: Frame index to render.
            use_cache: Whether to use cached result if available.
        
        Returns:
            RGB image array of shape (height, width, 3).
        """
        if not self.controller:
            raise RuntimeError("Renderer not initialized. Call await initialize() first.")
        
        # Check cache
        if use_cache and frame_idx == self._last_frame_idx and self._render_cache is not None:
            return self._render_cache.copy()
        
        # Navigate to frame
        await self.controller.goto(frame_idx)
        
        # Update timeline if present
        if self.timeline_controller:
            self.timeline_controller.set_current_frame(frame_idx)
            self.timeline_controller.request_update()
        
        # Render
        self.visualizer.draw()
        
        # Get pixels
        pixels = self.visualizer.read_pixels()
        
        # Cache result
        self._last_frame_idx = frame_idx
        self._render_cache = pixels.copy()
        
        return pixels
    
    async def render_frames(
        self,
        frame_indices: list[int],
        progress_callback: Callable[[int, int], None] | None = None
    ) -> list[np.ndarray]:
        """Render multiple frames.
        
        Args:
            frame_indices: List of frame indices to render.
            progress_callback: Optional callback(current, total) for progress.
        
        Returns:
            List of RGB image arrays.
        """
        frames = []
        total = len(frame_indices)
        
        for i, frame_idx in enumerate(frame_indices):
            if progress_callback:
                progress_callback(i, total)
            
            frame = await self.render_frame(frame_idx)
            frames.append(frame)
        
        if progress_callback:
            progress_callback(total, total)
        
        return frames
    
    async def export_frame(
        self,
        frame_idx: int,
        output_path: str | Path,
        format: str = "PNG"
    ) -> None:
        """Export a single frame to an image file.
        
        Args:
            frame_idx: Frame index to export.
            output_path: Path to save the image.
            format: Image format (PNG, JPEG, etc.).
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Render frame
        pixels = await self.render_frame(frame_idx)
        
        # Save as image
        image = Image.fromarray(pixels)
        image.save(output_path, format=format)
    
    async def export_frames(
        self,
        frame_indices: list[int] | None = None,
        output_dir: str | Path = "exports",
        name_pattern: str = "frame_{:06d}.png",
        format: str = "PNG",
        progress_callback: Callable[[int, int], None] | None = None
    ) -> list[Path]:
        """Export multiple frames to image files.
        
        Args:
            frame_indices: List of frame indices (None for all frames).
            output_dir: Directory to save images.
            name_pattern: Filename pattern with format placeholder.
            format: Image format.
            progress_callback: Optional callback(current, total) for progress.
        
        Returns:
            List of paths to exported files.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Default to all frames
        if frame_indices is None:
            if not self.labels or not self.labels.video:
                raise RuntimeError("No video loaded")
            frame_indices = list(range(len(self.labels.video)))
        
        exported_paths = []
        total = len(frame_indices)
        
        for i, frame_idx in enumerate(frame_indices):
            if progress_callback:
                progress_callback(i, total)
            
            # Generate filename
            filename = name_pattern.format(frame_idx)
            output_path = output_dir / filename
            
            # Export frame
            await self.export_frame(frame_idx, output_path, format=format)
            exported_paths.append(output_path)
        
        if progress_callback:
            progress_callback(total, total)
        
        return exported_paths
    
    async def export_video(
        self,
        output_path: str | Path,
        start_frame: int = 0,
        end_frame: int | None = None,
        fps: float = 30.0,
        codec: str = "libx264",
        quality: int = 23,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> None:
        """Export frames as a video file.
        
        Requires ffmpeg-python to be installed.
        
        Args:
            output_path: Path for output video.
            start_frame: First frame to include.
            end_frame: Last frame to include (None for last frame).
            fps: Output video framerate.
            codec: Video codec to use.
            quality: Quality setting (lower is better, 0-51 for h264).
            progress_callback: Optional callback(current, total) for progress.
        """
        try:
            import ffmpeg
        except ImportError:
            raise ImportError(
                "ffmpeg-python is required for video export. "
                "Install with: pip install ffmpeg-python"
            )
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine frame range
        if not self.labels or not self.labels.video:
            raise RuntimeError("No video loaded")
        
        total_frames = len(self.labels.video)
        if end_frame is None:
            end_frame = total_frames - 1
        
        end_frame = min(end_frame, total_frames - 1)
        frame_count = end_frame - start_frame + 1
        
        # Get first frame to determine dimensions
        first_frame = await self.render_frame(start_frame)
        height, width = first_frame.shape[:2]
        
        # Set up ffmpeg process
        process = (
            ffmpeg
            .input('pipe:', format='rawvideo', pix_fmt='rgb24', s=f'{width}x{height}', r=fps)
            .output(str(output_path), vcodec=codec, crf=quality, pix_fmt='yuv420p')
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )
        
        try:
            # Write first frame
            process.stdin.write(first_frame.tobytes())
            
            # Process remaining frames
            for i, frame_idx in enumerate(range(start_frame + 1, end_frame + 1)):
                if progress_callback:
                    progress_callback(i + 1, frame_count)
                
                frame = await self.render_frame(frame_idx)
                process.stdin.write(frame.tobytes())
            
            # Finalize
            process.stdin.close()
            process.wait()
            
            if progress_callback:
                progress_callback(frame_count, frame_count)
                
        except Exception as e:
            process.kill()
            raise e
    
    def get_annotated_frames(self) -> list[int]:
        """Get list of frame indices that have annotations.
        
        Returns:
            List of frame indices with user or predicted annotations.
        """
        if not self.annotation_source or not self.labels or not self.labels.video:
            return []
        
        annotated = []
        video = self.labels.video
        
        for frame_idx in range(len(video)):
            try:
                frame_data = self.annotation_source.get_frame_data(
                    video, frame_idx, missing_policy="error"
                )
                if frame_data and (frame_data.get("points_xy") is not None):
                    # Check if we have any instances
                    if len(frame_data.get("points_xy", [])) > 0:
                        annotated.append(frame_idx)
            except (IndexError, KeyError):
                # No annotation for this frame
                continue
        
        return annotated
    
    def get_frames_with_instances(self, min_instances: int = 1) -> list[int]:
        """Get frames with a minimum number of instances.
        
        Args:
            min_instances: Minimum number of instances required.
        
        Returns:
            List of frame indices meeting the criteria.
        """
        if not self.annotation_source or not self.labels or not self.labels.video:
            return []
        
        frames_with_instances = []
        video = self.labels.video
        
        for frame_idx in range(len(video)):
            try:
                frame_data = self.annotation_source.get_frame_data(
                    video, frame_idx, missing_policy="error"
                )
                if frame_data and frame_data.get("points_xy") is not None:
                    # Count instances (first dimension of points_xy)
                    points = frame_data.get("points_xy", [])
                    if len(points) >= min_instances:
                        frames_with_instances.append(frame_idx)
            except (IndexError, KeyError):
                # No annotation for this frame
                continue
        
        return frames_with_instances
    
    async def export_montage(
        self,
        frame_indices: list[int],
        output_path: str | Path,
        grid_size: tuple[int, int] | None = None,
        tile_size: tuple[int, int] = (320, 240),
        spacing: int = 2,
        background_color: tuple[int, int, int] = (0, 0, 0)
    ) -> None:
        """Export a montage/grid of frames.
        
        Args:
            frame_indices: List of frame indices to include.
            output_path: Path to save the montage image.
            grid_size: (rows, cols) for the grid (None for auto).
            tile_size: (width, height) for each tile.
            spacing: Pixels between tiles.
            background_color: RGB color for background.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        n_frames = len(frame_indices)
        
        # Auto-calculate grid size if not provided
        if grid_size is None:
            cols = int(np.ceil(np.sqrt(n_frames)))
            rows = int(np.ceil(n_frames / cols))
            grid_size = (rows, cols)
        
        rows, cols = grid_size
        tile_w, tile_h = tile_size
        
        # Calculate montage dimensions
        montage_w = cols * tile_w + (cols - 1) * spacing
        montage_h = rows * tile_h + (rows - 1) * spacing
        
        # Create montage image
        montage = Image.new('RGB', (montage_w, montage_h), background_color)
        
        # Render and place each frame
        for i, frame_idx in enumerate(frame_indices):
            if i >= rows * cols:
                break
            
            # Get grid position
            row = i // cols
            col = i % cols
            x = col * (tile_w + spacing)
            y = row * (tile_h + spacing)
            
            # Render frame
            frame = await self.render_frame(frame_idx)
            frame_img = Image.fromarray(frame)
            
            # Resize to tile size
            frame_img = frame_img.resize(tile_size, Image.Resampling.LANCZOS)
            
            # Paste into montage
            montage.paste(frame_img, (x, y))
        
        # Save montage
        montage.save(output_path)
    
    def update_settings(
        self,
        color_by: str | None = None,
        colormap: str | None = None,
        gain: float | None = None,
        bias: float | None = None,
        gamma: float | None = None,
        tone_map: str | None = None,
        lut_mode: str | None = None
    ) -> None:
        """Update rendering settings dynamically.
        
        Args:
            color_by: Color policy ('instance', 'node', 'track').
            colormap: Color palette.
            gain: Contrast adjustment.
            bias: Brightness adjustment.
            gamma: Gamma correction.
            tone_map: Tone mapping mode.
            lut_mode: LUT mode.
        """
        if not self.visualizer:
            return
        
        # Update color policy if changed
        if color_by is not None or colormap is not None:
            self.visualizer.set_color_policy(
                color_by=color_by or self.color_by,
                colormap=colormap or self.colormap
            )
            if color_by:
                self.color_by = color_by
            if colormap:
                self.colormap = colormap
        
        # Update image adjustments if changed
        if any(x is not None for x in [gain, bias, gamma, tone_map, lut_mode]):
            self.visualizer.set_image_adjust(
                gain=gain if gain is not None else self.gain,
                bias=bias if bias is not None else self.bias,
                gamma=gamma if gamma is not None else self.gamma,
                tone_map=tone_map if tone_map is not None else self.tone_map,
                lut_mode=lut_mode if lut_mode is not None else self.lut_mode
            )
            
            # Update stored values
            if gain is not None:
                self.gain = gain
            if bias is not None:
                self.bias = bias
            if gamma is not None:
                self.gamma = gamma
            if tone_map is not None:
                self.tone_map = tone_map
            if lut_mode is not None:
                self.lut_mode = lut_mode
        
        # Clear cache to force re-render
        self._render_cache = None
    
    @property
    def total_frames(self) -> int:
        """Get total number of frames in the video."""
        if self.labels and self.labels.video:
            return len(self.labels.video)
        return 0
    
    @property
    def video_shape(self) -> tuple[int, int]:
        """Get video dimensions as (width, height)."""
        if self.visualizer:
            return (self.visualizer.width, self.visualizer.height)
        return (0, 0)