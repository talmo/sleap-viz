"""Adaptive frame skipping for smooth playback."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FrameSkipStats:
    """Statistics for frame skipping behavior."""
    
    total_frames_processed: int = 0
    frames_skipped: int = 0
    frames_rendered: int = 0
    skip_rate: float = 0.0
    current_quality: float = 1.0  # 1.0 = full quality, 0.0 = maximum skipping
    avg_frame_time: float = 0.0
    target_achieved: bool = True


class AdaptiveFrameSkipper:
    """Manages adaptive frame skipping to maintain target FPS.
    
    This class implements an adaptive algorithm that skips frames when
    the system can't maintain the target frame rate, ensuring smooth
    perceived playback at the cost of temporal resolution.
    """
    
    def __init__(
        self,
        target_fps: float = 30.0,
        min_quality: float = 0.25,  # Minimum 25% of frames shown
        adaptation_rate: float = 0.1,  # How quickly to adapt
        history_size: int = 30,  # Frames to consider for adaptation
    ):
        """Initialize the frame skipper.
        
        Args:
            target_fps: Target frames per second to maintain.
            min_quality: Minimum quality (0.0-1.0), where 1.0 shows all frames.
            adaptation_rate: How quickly to adapt quality (0.0-1.0).
            history_size: Number of recent frames to consider for adaptation.
        """
        self.target_fps = target_fps
        self.target_frame_time = 1.0 / target_fps
        self.min_quality = max(0.1, min(1.0, min_quality))
        self.adaptation_rate = max(0.01, min(1.0, adaptation_rate))
        self.history_size = history_size
        
        # Current state
        self.quality = 1.0  # Start at full quality
        self.frame_times: list[float] = []
        self.last_rendered_frame: Optional[int] = None
        self.stats = FrameSkipStats()
        
        # Timing
        self.last_frame_start: Optional[float] = None
        self.cumulative_lag: float = 0.0
    
    def should_render_frame(self, frame_index: int, current_time: Optional[float] = None) -> bool:
        """Determine if a frame should be rendered or skipped.
        
        Args:
            frame_index: Index of the current frame.
            current_time: Current time in seconds (uses time.monotonic() if None).
            
        Returns:
            True if the frame should be rendered, False if it should be skipped.
        """
        if current_time is None:
            current_time = time.monotonic()
        
        self.stats.total_frames_processed += 1
        
        # Always render first frame
        if self.last_rendered_frame is None:
            self.last_rendered_frame = frame_index
            self.last_frame_start = current_time
            self.stats.frames_rendered += 1
            return True
        
        # Calculate frames since last render
        frames_since_render = frame_index - self.last_rendered_frame
        
        # Determine if we should skip based on quality setting
        skip_interval = max(1, int(1.0 / self.quality))
        
        # Check if we should render this frame
        should_render = frames_since_render >= skip_interval
        
        # Additional check: force render if we're falling too far behind
        if not should_render and self.cumulative_lag > self.target_frame_time * 2:
            should_render = False  # Skip more aggressively when lagging
        
        if should_render:
            self.last_rendered_frame = frame_index
            self.stats.frames_rendered += 1
        else:
            self.stats.frames_skipped += 1
        
        # Update skip rate
        if self.stats.total_frames_processed > 0:
            self.stats.skip_rate = self.stats.frames_skipped / self.stats.total_frames_processed
        
        self.stats.current_quality = self.quality
        
        return should_render
    
    def record_frame_time(self, frame_time: float) -> None:
        """Record the time taken to render a frame and adapt quality.
        
        Args:
            frame_time: Time taken to render the frame in seconds.
        """
        # Add to history
        self.frame_times.append(frame_time)
        if len(self.frame_times) > self.history_size:
            self.frame_times.pop(0)
        
        # Calculate average frame time
        if self.frame_times:
            self.stats.avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        
        # Update cumulative lag
        lag = frame_time - self.target_frame_time
        self.cumulative_lag = max(0, self.cumulative_lag + lag)
        
        # Adapt quality based on performance
        self._adapt_quality()
    
    def _adapt_quality(self) -> None:
        """Adapt rendering quality based on recent performance."""
        if not self.frame_times:
            return
        
        avg_time = self.stats.avg_frame_time
        
        # Check if we're meeting target
        if avg_time > self.target_frame_time * 1.1:  # 10% tolerance
            # We're too slow, decrease quality
            quality_adjustment = -self.adaptation_rate
            self.stats.target_achieved = False
        elif avg_time < self.target_frame_time * 0.9:
            # We're fast enough, try to increase quality
            quality_adjustment = self.adaptation_rate
            self.stats.target_achieved = True
        else:
            # We're within tolerance, small adjustment toward ideal
            quality_adjustment = 0
            self.stats.target_achieved = True
        
        # Apply adjustment with smoothing
        if quality_adjustment != 0:
            # Smooth the adjustment based on how far we are from target
            distance_factor = abs(avg_time - self.target_frame_time) / self.target_frame_time
            quality_adjustment *= min(2.0, 1.0 + distance_factor)
            
            self.quality += quality_adjustment
            self.quality = max(self.min_quality, min(1.0, self.quality))
    
    def reset(self) -> None:
        """Reset the frame skipper state."""
        self.quality = 1.0
        self.frame_times.clear()
        self.last_rendered_frame = None
        self.last_frame_start = None
        self.cumulative_lag = 0.0
        self.stats = FrameSkipStats()
    
    def get_stats(self) -> FrameSkipStats:
        """Get current frame skipping statistics."""
        return self.stats
    
    def set_target_fps(self, fps: float) -> None:
        """Update the target FPS.
        
        Args:
            fps: New target frames per second.
        """
        self.target_fps = max(1.0, min(120.0, fps))
        self.target_frame_time = 1.0 / self.target_fps
    
    def get_skip_pattern(self, num_frames: int = 10) -> list[bool]:
        """Get a preview of the skip pattern for the next frames.
        
        Args:
            num_frames: Number of frames to preview.
            
        Returns:
            List of booleans indicating render (True) or skip (False).
        """
        skip_interval = max(1, int(1.0 / self.quality))
        pattern = []
        
        for i in range(num_frames):
            should_render = (i % skip_interval) == 0
            pattern.append(should_render)
        
        return pattern