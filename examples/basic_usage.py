"""Basic usage example for sleap-viz.

This example demonstrates the simplest way to visualize SLEAP pose data
with a video overlay.
"""

import asyncio
from pathlib import Path
import sleap_io as sio
from sleap_viz.video_source import VideoSource
from sleap_viz.annotation_source import AnnotationSource
from sleap_viz.renderer import Visualizer
from sleap_viz.controller import Controller


async def main():
    """Load and visualize SLEAP pose data."""
    # Load SLEAP labels file
    labels_path = Path("path/to/your/labels.slp")
    labels = sio.load_slp(str(labels_path), open_videos=True)
    
    # Get the first video
    video = labels.videos[0]
    
    # Create data sources
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    # Create visualizer with video dimensions
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(width=width, height=height, mode="desktop")
    
    # Create controller for playback
    controller = Controller(
        video_source, 
        annotation_source, 
        visualizer, 
        video,
        play_fps=25  # Playback at 25 FPS
    )
    
    # Navigate to first frame
    await controller.goto(0)
    
    # Start playback
    await controller.play()
    
    # Keep running for 10 seconds
    await asyncio.sleep(10)
    
    # Stop playback
    await controller.stop()
    
    print("Visualization complete!")


if __name__ == "__main__":
    asyncio.run(main())