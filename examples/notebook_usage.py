"""Example of using sleap-viz in Jupyter notebooks.

This script demonstrates how to use the NotebookViewer widget to visualize
SLEAP data interactively in Jupyter notebooks.

To run this example in a Jupyter notebook:

1. Start Jupyter Lab:
   ```bash
   jupyter lab
   ```

2. In a notebook cell, run:
   ```python
   import asyncio
   from sleap_viz.notebook import NotebookViewer
   
   # Create viewer
   viewer = NotebookViewer(
       "tests/fixtures/centered_pair_predictions.slp",  # Or your own .slp file
       width=800,
       height=600,
       fps=25.0
   )
   
   # Initialize (must be awaited)
   await viewer.initialize()
   
   # Display the widget
   viewer.show()
   ```

3. Use keyboard shortcuts while the viewer is focused:
   - Space: Play/pause
   - Left/Right arrows: Previous/next frame
   - J/K: Frame step backward/forward
   - B/C/G: Adjust brightness/contrast/gamma
   - T: Toggle tone mapping
   - Z: Zoom timeline
   - See InteractiveControls for full list

4. Control programmatically:
   ```python
   # Jump to frame 100
   await viewer.goto(100)
   
   # Start playback
   await viewer.play()
   
   # Change playback speed
   viewer.set_playback_speed(2.0)
   
   # Adjust image
   viewer.set_image_adjust(gain=1.5, bias=0.1)
   
   # Change color policy
   viewer.set_color_policy(color_by="track", colormap="viridis")
   
   # Get current frame as numpy array
   frame = viewer.get_current_frame()
   ```
"""

import argparse
import asyncio
from pathlib import Path


async def main():
    """Demonstrate notebook viewer usage."""
    parser = argparse.ArgumentParser(description="Notebook viewer example")
    parser.add_argument(
        "labels_path",
        nargs="?",
        default="tests/fixtures/centered_pair_predictions.slp",
        help="Path to SLEAP labels file (.slp)",
    )
    args = parser.parse_args()
    
    from sleap_viz.notebook import NotebookViewer
    
    # Create viewer with custom settings
    viewer = NotebookViewer(
        str(args.labels_path),
        width=800,
        height=600,
        fps=25.0,
        color_by="instance",
        colormap="tab20",
        gain=1.0,
        bias=0.0,
        gamma=1.0,
        tone_map="linear",
        lut_mode="none"
    )
    
    # Initialize the viewer
    print("Initializing viewer...")
    await viewer.initialize()
    print(f"Loaded {viewer.total_frames} frames")
    
    # This would display the widget in a notebook
    # widget = viewer.show()
    
    # Demonstrate programmatic control
    print("\nDemonstrating programmatic control:")
    
    # Jump to middle frame
    mid_frame = viewer.total_frames // 2
    print(f"Jumping to frame {mid_frame}...")
    await viewer.goto(mid_frame)
    
    # Adjust image settings
    print("Adjusting image (higher contrast)...")
    viewer.set_image_adjust(gain=1.5)
    
    # Change color policy
    print("Changing colors to track-based...")
    viewer.set_color_policy(color_by="track")
    
    # Start playback
    print("Starting playback at 2x speed...")
    viewer.set_playback_speed(2.0)
    await viewer.play()
    
    # Play for 2 seconds
    await asyncio.sleep(2)
    
    # Pause
    print("Pausing...")
    await viewer.pause()
    
    print(f"Current frame: {viewer.current_frame_index}")
    
    # Get current frame (not yet supported in notebook mode)
    frame = viewer.get_current_frame()
    if frame is not None:
        print(f"Got frame with shape: {frame.shape}")
    else:
        print("Frame extraction not yet supported in notebook mode")
    
    print("\nIn a Jupyter notebook, use viewer.show() to display the widget")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())