"""Performance monitoring and timing utilities."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class FrameStats:
    """Statistics for a single frame render."""
    frame_idx: int
    total_time: float
    video_load_time: float = 0.0
    annotation_load_time: float = 0.0
    set_frame_time: float = 0.0
    set_overlay_time: float = 0.0
    draw_time: float = 0.0
    timeline_update_time: float = 0.0
    
    # Detailed breakdowns
    set_frame_details: Dict[str, float] = field(default_factory=dict)
    set_overlay_details: Dict[str, float] = field(default_factory=dict)
    draw_details: Dict[str, float] = field(default_factory=dict)
    
    @property
    def fps(self) -> float:
        """Calculate FPS from total time."""
        return 1.0 / self.total_time if self.total_time > 0 else 0.0


class PerformanceMonitor:
    """Monitor and track performance metrics for the viewer."""
    
    def __init__(self, history_size: int = 60) -> None:
        """Initialize performance monitor.
        
        Args:
            history_size: Number of frames to keep in history for averaging.
        """
        self.history_size = history_size
        self.frame_history: deque[FrameStats] = deque(maxlen=history_size)
        self.current_frame: Optional[FrameStats] = None
        self.timers: Dict[str, float] = {}
        
        # Overall statistics
        self.total_frames_rendered = 0
        self.start_time = time.perf_counter()
    
    def start_frame(self, frame_idx: int) -> None:
        """Start timing a new frame."""
        self.current_frame = FrameStats(
            frame_idx=frame_idx,
            total_time=0.0
        )
        self.timers.clear()
        self.timers["frame_start"] = time.perf_counter()
    
    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        self.timers[name] = time.perf_counter()
    
    def end_timer(self, name: str, parent: str = None) -> float:
        """End a named timer and record the elapsed time.
        
        Args:
            name: Timer name.
            parent: Parent operation name for nested timing.
        
        Returns:
            Elapsed time in seconds.
        """
        if name not in self.timers or self.current_frame is None:
            return 0.0
        
        elapsed = time.perf_counter() - self.timers[name]
        
        # Handle nested timing
        if parent:
            if parent == "set_frame":
                self.current_frame.set_frame_details[name] = elapsed
            elif parent == "set_overlay":
                self.current_frame.set_overlay_details[name] = elapsed
            elif parent == "draw":
                self.current_frame.draw_details[name] = elapsed
        else:
            # Map timer names to frame stats attributes
            if name == "video_load":
                self.current_frame.video_load_time = elapsed
            elif name == "annotation_load":
                self.current_frame.annotation_load_time = elapsed
            elif name == "set_frame":
                self.current_frame.set_frame_time = elapsed
            elif name == "set_overlay":
                self.current_frame.set_overlay_time = elapsed
            elif name == "draw":
                self.current_frame.draw_time = elapsed
            elif name == "timeline_update":
                self.current_frame.timeline_update_time = elapsed
        
        return elapsed
    
    def end_frame(self) -> None:
        """End timing for the current frame."""
        if self.current_frame is None or "frame_start" not in self.timers:
            return
        
        self.current_frame.total_time = time.perf_counter() - self.timers["frame_start"]
        self.frame_history.append(self.current_frame)
        self.total_frames_rendered += 1
        self.current_frame = None
    
    def get_average_fps(self) -> float:
        """Get average FPS over recent history."""
        if not self.frame_history:
            return 0.0
        
        total_time = sum(f.total_time for f in self.frame_history)
        if total_time <= 0:
            return 0.0
        
        return len(self.frame_history) / total_time
    
    def get_current_fps(self) -> float:
        """Get FPS of the most recent frame."""
        if not self.frame_history:
            return 0.0
        return self.frame_history[-1].fps
    
    def get_timing_breakdown(self) -> Dict[str, float]:
        """Get average timing breakdown for recent frames.
        
        Returns:
            Dictionary mapping operation names to average times in milliseconds.
        """
        if not self.frame_history:
            return {}
        
        n = len(self.frame_history)
        breakdown = {
            "video_load": sum(f.video_load_time for f in self.frame_history) / n * 1000,
            "annotation_load": sum(f.annotation_load_time for f in self.frame_history) / n * 1000,
            "set_frame": sum(f.set_frame_time for f in self.frame_history) / n * 1000,
            "set_overlay": sum(f.set_overlay_time for f in self.frame_history) / n * 1000,
            "draw": sum(f.draw_time for f in self.frame_history) / n * 1000,
            "timeline": sum(f.timeline_update_time for f in self.frame_history) / n * 1000,
            "total": sum(f.total_time for f in self.frame_history) / n * 1000,
        }
        
        return breakdown
    
    def get_detailed_breakdown(self) -> Dict[str, any]:
        """Get detailed timing breakdown including sub-operations.
        
        Returns:
            Nested dictionary with detailed timing information.
        """
        if not self.frame_history:
            return {}
        
        n = len(self.frame_history)
        
        # Aggregate detailed timings
        set_frame_details = {}
        set_overlay_details = {}
        draw_details = {}
        
        for frame in self.frame_history:
            for key, val in frame.set_frame_details.items():
                if key not in set_frame_details:
                    set_frame_details[key] = 0
                set_frame_details[key] += val
            
            for key, val in frame.set_overlay_details.items():
                if key not in set_overlay_details:
                    set_overlay_details[key] = 0
                set_overlay_details[key] += val
                
            for key, val in frame.draw_details.items():
                if key not in draw_details:
                    draw_details[key] = 0
                draw_details[key] += val
        
        # Convert to averages in milliseconds
        for d in [set_frame_details, set_overlay_details, draw_details]:
            for key in d:
                d[key] = (d[key] / n) * 1000
        
        return {
            "video_load": sum(f.video_load_time for f in self.frame_history) / n * 1000,
            "annotation_load": sum(f.annotation_load_time for f in self.frame_history) / n * 1000,
            "set_frame": {
                "total": sum(f.set_frame_time for f in self.frame_history) / n * 1000,
                "details": set_frame_details
            },
            "set_overlay": {
                "total": sum(f.set_overlay_time for f in self.frame_history) / n * 1000,
                "details": set_overlay_details
            },
            "draw": {
                "total": sum(f.draw_time for f in self.frame_history) / n * 1000,
                "details": draw_details
            },
            "timeline": sum(f.timeline_update_time for f in self.frame_history) / n * 1000,
            "total": sum(f.total_time for f in self.frame_history) / n * 1000,
        }
    
    def get_stats_text(self) -> str:
        """Get formatted performance statistics as text.
        
        Returns:
            Multi-line string with performance metrics.
        """
        avg_fps = self.get_average_fps()
        current_fps = self.get_current_fps()
        breakdown = self.get_timing_breakdown()
        
        lines = [
            f"FPS: {current_fps:.1f} (avg: {avg_fps:.1f})",
            f"Frame: {breakdown.get('total', 0):.1f}ms",
        ]
        
        # Add breakdown if we have detailed timings
        if breakdown:
            details = []
            if breakdown.get("video_load", 0) > 0.1:
                details.append(f"video:{breakdown['video_load']:.1f}ms")
            if breakdown.get("annotation_load", 0) > 0.1:
                details.append(f"anno:{breakdown['annotation_load']:.1f}ms")
            if breakdown.get("set_overlay", 0) > 0.1:
                details.append(f"overlay:{breakdown['set_overlay']:.1f}ms")
            if breakdown.get("draw", 0) > 0.1:
                details.append(f"draw:{breakdown['draw']:.1f}ms")
            
            if details:
                lines.append(" ".join(details))
        
        return "\n".join(lines)
    
    def reset(self) -> None:
        """Reset all performance statistics."""
        self.frame_history.clear()
        self.current_frame = None
        self.timers.clear()
        self.total_frames_rendered = 0
        self.start_time = time.perf_counter()