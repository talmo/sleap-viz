"""High-level playback/scrubbing controller tying sources to the renderer."""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Optional, Callable, TYPE_CHECKING

from .annotation_source import AnnotationSource
from .video_source import VideoSource
from .performance import PerformanceMonitor
from .frame_skipper import AdaptiveFrameSkipper

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
        
        # Share performance monitor with visualizer
        self.perf_monitor = PerformanceMonitor()
        self.vis.perf_monitor = self.perf_monitor
        
        # Frame skipping for smooth playback
        self.frame_skipper = AdaptiveFrameSkipper(
            target_fps=play_fps,
            min_quality=0.25,  # Show at least 25% of frames
            adaptation_rate=0.15
        )
        self.enable_frame_skipping = True  # Can be toggled
        self.force_render_every_n = 5  # Force render at least every N frames during skip
        self._frames_since_render = 0
        
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
        
        # Scrubbing optimization
        self._last_rendered_frame: Optional[np.ndarray] = None
        self._frame_load_task: Optional[asyncio.Task] = None
        self._pending_frame_index: Optional[int] = None
        self._is_scrubbing = False

    async def goto(self, index: int) -> None:
        """Seek to a specific frame index and draw once."""
        # Start frame timing
        self.perf_monitor.start_frame(index)
        
        # Clamp to valid range
        index = max(0, min(index, self.total_frames - 1))
        self.current_frame = index
        
        # Request frame and wait briefly for it to load
        self.perf_monitor.start_timer("video_load")
        await self.vs.request(index)
        await asyncio.sleep(0.01)
        
        # Try to get exact frame, fall back to nearest if not ready
        frame = await self.vs.get(index)
        if frame is None:
            near = self.vs.nearest_available(index)
            if near is not None:
                frame = await self.vs.get(near)
        self.perf_monitor.end_timer("video_load")
        
        if frame is not None:
            self.perf_monitor.start_timer("set_frame")
            # Handle both Frame objects and raw arrays
            if hasattr(frame, 'rgb'):
                image_data = frame.rgb
            else:
                image_data = frame
            self.vis.set_frame_image(image_data)
            self._last_rendered_frame = image_data
            self.perf_monitor.end_timer("set_frame")
        
        # Load and set annotations
        try:
            self.perf_monitor.start_timer("annotation_load")
            data = self.anno.get_frame_data(self.video, index, missing_policy=self.missing_frame_policy)
            self.perf_monitor.end_timer("annotation_load")
            
            self.perf_monitor.start_timer("set_overlay")
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
            self.perf_monitor.end_timer("set_overlay")
        except Exception:
            pass
        
        self.perf_monitor.start_timer("draw")
        self.vis.draw()
        self.perf_monitor.end_timer("draw")
        
        # Update timeline playhead
        if self.timeline_controller:
            self.perf_monitor.start_timer("timeline_update")
            self.timeline_controller.set_current_frame(self.current_frame)
            self.perf_monitor.end_timer("timeline_update")
        
        # End frame timing
        self.perf_monitor.end_frame()
        
        # Update performance display if enabled
        if self.vis.show_perf_stats:
            stats_text = self.perf_monitor.get_stats_text()
            self.vis.update_perf_display(stats_text)
        
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
        # Update frame skipper target
        if self.enable_frame_skipping:
            self.frame_skipper.set_target_fps(self.play_fps * self.playback_speed)
    
    def set_loop(self, loop: bool) -> None:
        """Enable or disable looping at end of video."""
        self.loop = loop
    
    async def _playback_loop(self) -> None:
        """Internal playback loop for continuous frame advancement."""
        try:
            # Reset frame skipper at start of playback
            if self.enable_frame_skipping:
                self.frame_skipper.reset()
                self.frame_skipper.set_target_fps(self.play_fps * self.playback_speed)
            
            while self.state == PlaybackState.PLAYING:
                # Calculate target frame time with speed adjustment
                target_interval = self._frame_interval / self.playback_speed
                current_time = time.monotonic()
                
                # Check if it's time for next frame
                if current_time - self._last_frame_time >= target_interval:
                    frame_start = current_time
                    self._last_frame_time = current_time
                    
                    # Advance frame
                    next_frame = self.current_frame + 1
                    
                    # Handle end of video
                    if next_frame >= self.total_frames:
                        if self.loop:
                            next_frame = 0
                            if self.enable_frame_skipping:
                                self.frame_skipper.reset()  # Reset skipper on loop
                        else:
                            await self.stop()
                            break
                    
                    # Check if we should render this frame
                    should_render = True
                    if self.enable_frame_skipping and self.state == PlaybackState.PLAYING:
                        should_render = self.frame_skipper.should_render_frame(next_frame, current_time)
                        
                        # Force render if we've skipped too many frames
                        if not should_render:
                            self._frames_since_render += 1
                            if self._frames_since_render >= self.force_render_every_n:
                                should_render = True
                                self._frames_since_render = 0
                        else:
                            self._frames_since_render = 0
                    
                    if should_render:
                        # Navigate to and render frame
                        await self.goto(next_frame)
                        
                        # Record frame time for adaptation
                        if self.enable_frame_skipping:
                            frame_time = time.monotonic() - frame_start
                            self.frame_skipper.record_frame_time(frame_time)
                            
                            # Update skip indicator
                            stats = self.frame_skipper.get_stats()
                            self.vis.update_skip_indicator(
                                stats.current_quality,
                                stats.frames_skipped
                            )
                    else:
                        # Just update frame counter without rendering
                        self.current_frame = next_frame
                        if self.on_frame_changed:
                            self.on_frame_changed(self.current_frame)
                
                # Small sleep to prevent busy waiting
                await asyncio.sleep(0.001)
        
        except asyncio.CancelledError:
            pass
    
    def get_playback_info(self) -> dict:
        """Get current playback status information."""
        info = {
            "state": self.state.value,
            "current_frame": self.current_frame,
            "total_frames": self.total_frames,
            "fps": self.play_fps,
            "speed": self.playback_speed,
            "loop": self.loop,
            "frame_skipping": self.enable_frame_skipping,
        }
        
        # Add frame skip stats if enabled
        if self.enable_frame_skipping:
            stats = self.frame_skipper.get_stats()
            info["skip_stats"] = {
                "frames_rendered": stats.frames_rendered,
                "frames_skipped": stats.frames_skipped,
                "skip_rate": f"{stats.skip_rate * 100:.1f}%",
                "quality": f"{stats.current_quality * 100:.0f}%",
                "target_achieved": stats.target_achieved,
            }
        
        return info
    
    def toggle_frame_skipping(self) -> None:
        """Toggle adaptive frame skipping on/off."""
        self.enable_frame_skipping = not self.enable_frame_skipping
        if self.enable_frame_skipping:
            self.frame_skipper.reset()
    
    def set_frame_skip_quality(self, min_quality: float) -> None:
        """Set minimum quality for frame skipping (0.0-1.0).
        
        Args:
            min_quality: Minimum fraction of frames to show (1.0 = all frames).
        """
        self.frame_skipper.min_quality = max(0.1, min(1.0, min_quality))
    
    def set_target_fps(self, fps: float) -> None:
        """Set target FPS for adaptive frame skipping.
        
        Args:
            fps: Target frames per second.
        """
        self.play_fps = fps
        self._frame_interval = 1.0 / fps
        self.frame_skipper.set_target_fps(fps * self.playback_speed)
    
    async def scrub_to(self, index: int) -> None:
        """Optimized seek for scrubbing - renders annotations immediately, loads image async.
        
        This method provides responsive scrubbing by:
        1. Immediately updating annotations and timeline
        2. Keeping the last frame image if new one isn't ready
        3. Cancelling pending frame loads if a newer frame is requested
        4. Loading the image asynchronously without blocking
        
        Args:
            index: Frame index to scrub to.
        """
        # Mark that we're scrubbing
        self._is_scrubbing = True
        
        # Start frame timing
        self.perf_monitor.start_frame(index)
        
        # Clamp to valid range
        index = max(0, min(index, self.total_frames - 1))
        self.current_frame = index
        
        # Cancel any pending frame load if we have a newer request
        if self._frame_load_task and not self._frame_load_task.done():
            self._frame_load_task.cancel()
            self._frame_load_task = None
        
        # Update annotations immediately (very fast)
        try:
            self.perf_monitor.start_timer("annotation_load")
            data = self.anno.get_frame_data(self.video, index, missing_policy=self.missing_frame_policy)
            self.perf_monitor.end_timer("annotation_load")
            
            self.perf_monitor.start_timer("set_overlay")
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
            self.perf_monitor.end_timer("set_overlay")
        except Exception:
            pass
        
        # Update timeline immediately
        if self.timeline_controller:
            self.perf_monitor.start_timer("timeline_update")
            self.timeline_controller.set_current_frame(self.current_frame)
            self.perf_monitor.end_timer("timeline_update")
        
        # Draw with current frame image (reuse last if available)
        if self._last_rendered_frame is not None:
            # Keep the existing frame image
            self.perf_monitor.start_timer("draw")
            self.vis.draw()
            self.perf_monitor.end_timer("draw")
        else:
            # No previous frame, try to get something quickly
            frame = await self.vs.get(index, timeout=0.001)  # Very short timeout
            if frame is None:
                # Try nearest available
                near = self.vs.nearest_available(index)
                if near is not None:
                    frame = await self.vs.get(near, timeout=0.001)
            
            if frame is not None:
                # Handle both Frame objects and raw arrays
                if hasattr(frame, 'rgb'):
                    image_data = frame.rgb
                else:
                    image_data = frame
                self.vis.set_frame_image(image_data)
                self._last_rendered_frame = image_data
                
            self.perf_monitor.start_timer("draw")
            self.vis.draw()
            self.perf_monitor.end_timer("draw")
        
        # End frame timing for immediate render
        self.perf_monitor.end_frame()
        
        # Update performance display if enabled
        if self.vis.show_perf_stats:
            stats_text = self.perf_monitor.get_stats_text()
            self.vis.update_perf_display(stats_text)
        
        # Store the pending frame index
        self._pending_frame_index = index
        
        # Start async task to load the actual frame
        self._frame_load_task = asyncio.create_task(self._load_frame_async(index))
        
        # Notify callback
        if self.on_frame_changed:
            self.on_frame_changed(self.current_frame)
    
    async def _load_frame_async(self, index: int) -> None:
        """Load a frame asynchronously and update display when ready.
        
        Args:
            index: Frame index to load.
        """
        try:
            # Request the frame
            await self.vs.request(index)
            
            # Wait a bit for it to load
            await asyncio.sleep(0.02)  # 20ms wait
            
            # Check if we still want this frame (not cancelled or superseded)
            if self._pending_frame_index != index:
                return  # A newer frame was requested
            
            # Try to get the frame
            frame = await self.vs.get(index, timeout=0.01)
            
            if frame is not None and self._pending_frame_index == index:
                # We got the frame and it's still the one we want
                # Handle both Frame objects and raw arrays
                if hasattr(frame, 'rgb'):
                    image_data = frame.rgb
                else:
                    image_data = frame
                self.vis.set_frame_image(image_data)
                self._last_rendered_frame = image_data
                self.vis.draw()
                
                # Clear pending since we loaded it
                self._pending_frame_index = None
                
        except asyncio.CancelledError:
            # Task was cancelled, that's fine
            pass
        except Exception:
            # Ignore other errors during async load
            pass
