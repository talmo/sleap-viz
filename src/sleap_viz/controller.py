"""High-level playback/scrubbing controller tying sources to the renderer."""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Optional, Callable, TYPE_CHECKING

from .annotation_source import AnnotationSource
from .video_source import VideoSource

if TYPE_CHECKING:
    from .timeline import TimelineController


class PlaybackState(Enum):
    """Playback state enumeration."""
    
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class Controller:
    """Manage playhead, requests, and drawing.

    Handles frame navigation, playback control, and synchronization between
    video source, annotations, and renderer.
    """

    def __init__(
        self,
        video_source: VideoSource,
        anno_source: AnnotationSource,
        visualizer,
        video,
        play_fps: float = 25.0,
        missing_frame_policy: str = "blank",
    ) -> None:
        """Initialize the controller.

        Args:
            video_source: Video frame provider.
            anno_source: Annotation provider.
            visualizer: Renderer instance.
            video: The `sio.Video` for context.
            play_fps: Target playback FPS for timing.
            missing_frame_policy: Policy for missing annotation frames ("error" or "blank").
        """
        self.vs = video_source
        self.anno = anno_source
        self.vis = visualizer
        self.video = video
        self.play_fps = play_fps
        self.missing_frame_policy = missing_frame_policy
        
        # Playback state
        self.state = PlaybackState.STOPPED
        self.current_frame = 0
        self.total_frames = len(video)
        self.playback_speed = 1.0
        self.loop = False
        
        # Timing for smooth playback
        self._frame_interval = 1.0 / play_fps
        self._last_frame_time = 0.0
        self._playback_task: Optional[asyncio.Task] = None
        
        # Callbacks for UI updates
        self.on_frame_changed: Optional[Callable[[int], None]] = None
        self.on_state_changed: Optional[Callable[[PlaybackState], None]] = None
        
        # Timeline controller (set by CLI)
        self.timeline_controller: Optional[TimelineController] = None

    async def goto(self, index: int) -> None:
        """Seek to a specific frame index and draw once."""
        # Clamp to valid range
        index = max(0, min(index, self.total_frames - 1))
        self.current_frame = index
        
        # Request frame and wait briefly for it to load
        await self.vs.request(index)
        await asyncio.sleep(0.01)
        
        # Try to get exact frame, fall back to nearest if not ready
        frame = await self.vs.get(index)
        if frame is None:
            near = self.vs.nearest_available(index)
            if near is not None:
                frame = await self.vs.get(near)
        
        if frame is not None:
            self.vis.set_frame_image(frame)
        
        # Load and set annotations
        try:
            data = self.anno.get_frame_data(self.video, index, missing_policy=self.missing_frame_policy)
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
        
        # Update timeline playhead
        if self.timeline_controller:
            self.timeline_controller.set_current_frame(self.current_frame)
        
        # Notify callback
        if self.on_frame_changed:
            self.on_frame_changed(self.current_frame)
    
    async def next_frame(self) -> None:
        """Navigate to the next frame."""
        await self.goto(self.current_frame + 1)
    
    async def prev_frame(self) -> None:
        """Navigate to the previous frame."""
        await self.goto(self.current_frame - 1)
    
    async def skip_frames(self, n: int) -> None:
        """Skip forward or backward by n frames."""
        await self.goto(self.current_frame + n)
    
    async def goto_start(self) -> None:
        """Jump to the first frame."""
        await self.goto(0)
    
    async def goto_end(self) -> None:
        """Jump to the last frame."""
        await self.goto(self.total_frames - 1)
    
    async def play(self) -> None:
        """Start or resume playback."""
        if self.state == PlaybackState.PLAYING:
            return
        
        self.state = PlaybackState.PLAYING
        if self.on_state_changed:
            self.on_state_changed(self.state)
        
        # Cancel any existing playback task
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
        
        # Start new playback task
        self._playback_task = asyncio.create_task(self._playback_loop())
    
    async def pause(self) -> None:
        """Pause playback."""
        if self.state != PlaybackState.PLAYING:
            return
        
        self.state = PlaybackState.PAUSED
        if self.on_state_changed:
            self.on_state_changed(self.state)
        
        # Cancel playback task
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
    
    async def stop(self) -> None:
        """Stop playback and reset to start."""
        self.state = PlaybackState.STOPPED
        if self.on_state_changed:
            self.on_state_changed(self.state)
        
        # Cancel playback task
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
        
        # Reset to first frame
        await self.goto_start()
    
    async def toggle_play_pause(self) -> None:
        """Toggle between play and pause states."""
        if self.state == PlaybackState.PLAYING:
            await self.pause()
        else:
            await self.play()
    
    def set_playback_speed(self, speed: float) -> None:
        """Set playback speed multiplier (1.0 = normal, 2.0 = 2x, etc)."""
        self.playback_speed = max(0.1, min(speed, 10.0))
    
    def set_loop(self, loop: bool) -> None:
        """Enable or disable looping at end of video."""
        self.loop = loop
    
    async def _playback_loop(self) -> None:
        """Internal playback loop for continuous frame advancement."""
        try:
            while self.state == PlaybackState.PLAYING:
                # Calculate target frame time with speed adjustment
                target_interval = self._frame_interval / self.playback_speed
                current_time = time.monotonic()
                
                # Check if it's time for next frame
                if current_time - self._last_frame_time >= target_interval:
                    self._last_frame_time = current_time
                    
                    # Advance frame
                    next_frame = self.current_frame + 1
                    
                    # Handle end of video
                    if next_frame >= self.total_frames:
                        if self.loop:
                            next_frame = 0
                        else:
                            await self.stop()
                            break
                    
                    # Navigate to next frame
                    await self.goto(next_frame)
                
                # Small sleep to prevent busy waiting
                await asyncio.sleep(0.001)
        
        except asyncio.CancelledError:
            pass
    
    def get_playback_info(self) -> dict:
        """Get current playback status information."""
        return {
            "state": self.state.value,
            "current_frame": self.current_frame,
            "total_frames": self.total_frames,
            "fps": self.play_fps,
            "speed": self.playback_speed,
            "loop": self.loop,
        }
