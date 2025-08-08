"""High-level playback/scrubbing controller tying sources to the renderer."""

from __future__ import annotations

import asyncio

from .annotation_source import AnnotationSource
from .video_source import VideoSource


class Controller:
    """Manage playhead, requests, and drawing.

    This is a minimal stub that implements `goto()` so the CLI can render once.
    """

    def __init__(
        self,
        video_source: VideoSource,
        anno_source: AnnotationSource,
        visualizer,
        video,
        play_fps: float = 25.0,
    ) -> None:
        """Initialize the controller.

        Args:
            video_source: Video frame provider.
            anno_source: Annotation provider.
            visualizer: Renderer instance.
            video: The `sio.Video` for context.
            play_fps: Target playback FPS for timing.
        """
        self.vs = video_source
        self.anno = anno_source
        self.vis = visualizer
        self.video = video
        self.play_fps = play_fps

    async def goto(self, index: int) -> None:
        """Seek to a specific frame index and draw once."""
        await self.vs.request(index)
        # Give the worker a moment; then try exact, else nearest.
        await asyncio.sleep(0.01)
        frame = await self.vs.get(index)
        if frame is None:
            near = self.vs.nearest_available(index)
            if near is not None:
                frame = await self.vs.get(near)
        if frame is not None:
            self.vis.set_frame_image(frame)
        # Annotations (missing allowed)
        try:
            data = self.anno.get_frame_data(self.video, index, missing_policy="blank")
            self.vis.set_overlay(
                data["points_xy"],
                data["visible"],
                data["edges"],
                data.get("inst_kind"),
                data.get("track_id"),
                data.get("node_ids"),
                None,
                data.get("labels"),
            )
        except Exception:
            pass
        self.vis.draw()
