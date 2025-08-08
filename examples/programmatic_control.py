"""Example demonstrating programmatic control of the viewer.

This example shows how to:
- Control playback programmatically
- Navigate frames with code
- Respond to frame changes
- Implement custom playback patterns
"""

import asyncio
from pathlib import Path
from typing import Optional
import numpy as np
import sleap_io as sio
from sleap_viz.video_source import VideoSource
from sleap_viz.annotation_source import AnnotationSource
from sleap_viz.renderer import Visualizer
from sleap_viz.controller import Controller


class CustomPlaybackController:
    """Custom controller demonstrating programmatic control patterns."""
    
    def __init__(self, controller: Controller):
        """Initialize with a controller instance.
        
        Args:
            controller: The sleap-viz Controller instance.
        """
        self.controller = controller
        self.annotation_source = controller.annotation_source
        self.video = controller.video
        
        # Register callbacks
        controller.on_frame_change = self.on_frame_change
        controller.on_state_change = self.on_state_change
        
        # Track state
        self.frames_with_annotations = []
        self.current_annotation_idx = 0
        
    def on_frame_change(self, frame: int) -> None:
        """Called when frame changes.
        
        Args:
            frame: New frame index.
        """
        print(f"  Frame changed to: {frame}")
        
        # Check if frame has annotations
        frame_data = self.annotation_source.get_frame_data(
            self.video, frame
        )
        if frame_data and "points_xy" in frame_data:
            n_instances = frame_data["points_xy"].shape[0]
            if n_instances > 0:
                # Check instance kinds to distinguish user vs predicted
                inst_kinds = frame_data.get("inst_kind", [])
                n_user = np.sum(inst_kinds == 0) if len(inst_kinds) > 0 else 0
                n_predicted = np.sum(inst_kinds == 1) if len(inst_kinds) > 0 else 0
                print(f"    -> Found {n_user} user + {n_predicted} predicted instances")
    
    def on_state_change(self, playing: bool) -> None:
        """Called when playback state changes.
        
        Args:
            playing: True if playing, False if paused/stopped.
        """
        state = "Playing" if playing else "Paused"
        print(f"  Playback state: {state}")
    
    def find_annotated_frames(self) -> None:
        """Find all frames with annotations."""
        self.frames_with_annotations = []
        total_frames = self.controller.total_frames
        
        for frame_idx in range(total_frames):
            frame_data = self.annotation_source.get_frame_data(
                self.video, frame_idx
            )
            if frame_data and "points_xy" in frame_data and frame_data["points_xy"].shape[0] > 0:
                self.frames_with_annotations.append(frame_idx)
        
        print(f"Found {len(self.frames_with_annotations)} frames with annotations")
    
    async def jump_to_next_annotation(self) -> None:
        """Jump to next frame with annotations."""
        if not self.frames_with_annotations:
            self.find_annotated_frames()
        
        if self.frames_with_annotations:
            self.current_annotation_idx = (self.current_annotation_idx + 1) % len(self.frames_with_annotations)
            target_frame = self.frames_with_annotations[self.current_annotation_idx]
            print(f"\nJumping to annotated frame {self.current_annotation_idx + 1}/{len(self.frames_with_annotations)}")
            await self.controller.goto(target_frame)
    
    async def play_annotated_frames_only(self, fps: float = 5.0) -> None:
        """Play only frames with annotations.
        
        Args:
            fps: Playback rate for annotated frames.
        """
        if not self.frames_with_annotations:
            self.find_annotated_frames()
        
        print(f"\nPlaying {len(self.frames_with_annotations)} annotated frames at {fps} FPS")
        
        for i, frame_idx in enumerate(self.frames_with_annotations):
            print(f"  Showing annotated frame {i+1}/{len(self.frames_with_annotations)}: frame {frame_idx}")
            await self.controller.goto(frame_idx)
            await asyncio.sleep(1.0 / fps)
    
    async def slow_motion_playback(
        self, 
        start_frame: int, 
        end_frame: int, 
        slowdown_factor: float = 0.25
    ) -> None:
        """Play a segment in slow motion.
        
        Args:
            start_frame: Starting frame.
            end_frame: Ending frame.
            slowdown_factor: Speed multiplier (0.25 = 1/4 speed).
        """
        print(f"\nSlow motion playback: frames {start_frame}-{end_frame} at {slowdown_factor}x speed")
        
        # Set slow playback speed
        original_speed = self.controller.playback_speed
        self.controller.set_playback_speed(slowdown_factor)
        
        # Jump to start and play
        await self.controller.goto(start_frame)
        await self.controller.play()
        
        # Wait for segment to complete
        while self.controller.current_frame < end_frame and self.controller.is_playing:
            await asyncio.sleep(0.1)
        
        # Stop and restore speed
        await self.controller.stop()
        self.controller.set_playback_speed(original_speed)
        print("  Slow motion complete")
    
    async def ping_pong_playback(
        self,
        center_frame: int,
        radius: int = 10,
        cycles: int = 3
    ) -> None:
        """Play back and forth around a frame.
        
        Args:
            center_frame: Center frame to ping-pong around.
            radius: Number of frames before/after center.
            cycles: Number of forward-backward cycles.
        """
        start = max(0, center_frame - radius)
        end = min(self.controller.total_frames - 1, center_frame + radius)
        
        print(f"\nPing-pong playback: frames {start}-{end} ({cycles} cycles)")
        
        for cycle in range(cycles):
            print(f"  Cycle {cycle + 1}/{cycles}")
            
            # Forward
            for frame in range(start, end + 1):
                await self.controller.goto(frame)
                await asyncio.sleep(0.04)  # ~25 FPS
            
            # Backward
            for frame in range(end, start - 1, -1):
                await self.controller.goto(frame)
                await asyncio.sleep(0.04)


async def main():
    """Demonstrate programmatic control of the viewer."""
    # Load SLEAP data
    labels_path = Path("path/to/your/labels.slp")
    
    if not labels_path.exists():
        # Use test fixture if no path specified
        labels_path = Path("tests/fixtures/centered_pair_predictions.slp")
    
    print(f"Loading {labels_path}...")
    labels = sio.load_slp(str(labels_path), open_videos=True)
    video = labels.videos[0]
    
    # Create components
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(width=width, height=height, mode="desktop")
    
    controller = Controller(
        video_source,
        annotation_source,
        visualizer,
        video,
        play_fps=25
    )
    
    # Create custom controller
    custom = CustomPlaybackController(controller)
    
    print(f"\nVideo info: {len(video)} frames")
    print("="*50)
    
    # Example 1: Jump between annotated frames
    print("\n1. Jumping between annotated frames:")
    custom.find_annotated_frames()
    for _ in range(5):
        await custom.jump_to_next_annotation()
        await asyncio.sleep(1)
    
    # Example 2: Play only annotated frames
    print("\n2. Playing annotated frames only:")
    await custom.play_annotated_frames_only(fps=3.0)
    
    # Example 3: Slow motion on interesting segment
    if len(custom.frames_with_annotations) > 2:
        start = custom.frames_with_annotations[0]
        end = min(start + 20, custom.frames_with_annotations[-1])
        print("\n3. Slow motion playback:")
        await custom.slow_motion_playback(start, end, slowdown_factor=0.5)
    
    # Example 4: Ping-pong around a frame
    if custom.frames_with_annotations:
        center = custom.frames_with_annotations[len(custom.frames_with_annotations)//2]
        print("\n4. Ping-pong playback:")
        await custom.ping_pong_playback(center, radius=5, cycles=2)
    
    # Example 5: Custom frame sequence
    print("\n5. Custom frame sequence:")
    sequence = [0, 10, 20, 30, 20, 10, 0]  # Custom order
    for i, frame in enumerate(sequence):
        if frame < controller.total_frames:
            print(f"  Step {i+1}/{len(sequence)}: frame {frame}")
            await controller.goto(frame)
            await asyncio.sleep(0.5)
    
    print("\n" + "="*50)
    print("Programmatic control demo complete!")


if __name__ == "__main__":
    asyncio.run(main())