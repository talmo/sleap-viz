"""Example demonstrating customization of visualization appearance.

This example shows how to:
- Apply different color policies
- Adjust image brightness/contrast/gamma
- Configure visibility modes for predictions
"""

import asyncio
from pathlib import Path
import sleap_io as sio
from sleap_viz.video_source import VideoSource
from sleap_viz.annotation_source import AnnotationSource
from sleap_viz.renderer import Visualizer
from sleap_viz.controller import Controller
from sleap_viz.interactive import InteractiveControls


async def main():
    """Demonstrate visualization customization options."""
    # Load SLEAP data
    labels_path = Path("path/to/your/labels.slp")
    labels = sio.load_slp(str(labels_path), open_videos=True)
    video = labels.videos[0]
    
    # Create data sources
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    # Create visualizer
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(
        width=width, 
        height=height, 
        mode="desktop",
        timeline_height=50  # Add timeline at bottom
    )
    
    # Customize appearance
    print("Applying customizations...")
    
    # 1. Color by track (instead of instance)
    visualizer.set_color_policy(
        color_by="track",  # Options: "instance", "node", "track"
        colormap="hsv",     # Options: "tab10", "tab20", "hsv"
        invisible_mode="dim"  # Options: "dim", "hide"
    )
    
    # 2. Adjust image for better visibility
    visualizer.set_image_adjust(
        gain=1.5,    # Contrast (1.0 = normal, >1 = higher contrast)
        bias=0.1,    # Brightness (-1 to +1, 0 = normal)
        gamma=0.8    # Gamma correction (1.0 = normal, <1 = brighter)
    )
    
    # Create controller
    controller = Controller(
        video_source,
        annotation_source,
        visualizer,
        video,
        play_fps=30
    )
    
    # Navigate to a frame with annotations
    await controller.goto(100)
    
    print("\nVisualization customizations applied:")
    print("- Colors based on track identity")
    print("- HSV color palette for better distinction")
    print("- Increased contrast (gain=1.5)")
    print("- Slightly brightened (bias=0.1)")
    print("- Gamma adjusted for mid-tones (gamma=0.8)")
    
    # Demonstrate dynamic adjustment
    await asyncio.sleep(3)
    
    print("\nSwitching to node-based coloring...")
    visualizer.set_color_policy(color_by="node", colormap="tab20")
    await controller.goto(controller.current_frame)  # Refresh display
    
    await asyncio.sleep(3)
    
    print("\nSwitching to instance-based coloring...")
    visualizer.set_color_policy(color_by="instance", colormap="tab10")
    await controller.goto(controller.current_frame)  # Refresh display
    
    await asyncio.sleep(3)
    
    print("\nAdjusting image to high contrast...")
    visualizer.set_image_adjust(gain=2.0, bias=-0.2, gamma=1.0)
    await controller.goto(controller.current_frame)  # Refresh display
    
    await asyncio.sleep(3)
    
    print("\nResetting to defaults...")
    visualizer.set_image_adjust(gain=1.0, bias=0.0, gamma=1.0)
    visualizer.set_color_policy(color_by="instance", colormap="tab20")
    await controller.goto(controller.current_frame)  # Refresh display
    
    # Play for a bit
    await controller.play()
    await asyncio.sleep(5)
    await controller.stop()
    
    print("\nCustomization demo complete!")


if __name__ == "__main__":
    asyncio.run(main())