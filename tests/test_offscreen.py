"""Test offscreen rendering with actual SLEAP data."""

import asyncio
import numpy as np
import sleap_io as sio
from PIL import Image

from sleap_viz.video_source import VideoSource
from sleap_viz.annotation_source import AnnotationSource
from sleap_viz.renderer import Visualizer
from sleap_viz.controller import Controller


async def test_offscreen_rendering():
    """Test the visualization pipeline with offscreen rendering."""
    print("Loading SLEAP data...")
    
    # Load the SLEAP labels from fixtures
    labels = sio.load_slp("tests/fixtures/centered_pair_predictions.slp")
    print(f"Loaded {len(labels)} labeled frames")
    
    # Get the first video
    if not labels.videos:
        print("No videos found in labels")
        return
    
    video = labels.videos[0]
    print(f"Video: {video.shape} frames")
    
    # Create components
    print("Initializing components...")
    video_source = VideoSource(video, cache_size=32)
    anno_source = AnnotationSource(labels)
    
    # Create offscreen visualizer matching video dimensions
    # Get first frame to determine actual dimensions
    test_frame = video[0]
    height, width = test_frame.shape[:2]
    
    print(f"Video frame shape: {test_frame.shape}")
    print(f"Canvas size: {width}x{height}")
    
    visualizer = Visualizer(width, height, mode="offscreen")
    
    # Create controller
    controller = Controller(
        video_source,
        anno_source,
        visualizer,
        video,
        play_fps=25.0
    )
    
    # Test rendering a few frames from the first 100 frames
    test_frames = [0, 10, 25, 50, 75, 99]
    test_frames = [f for f in test_frames if f < min(100, len(video))]
    
    for frame_idx in test_frames:
        print(f"\nRendering frame {frame_idx}...")
        
        # Seek to frame and render
        await controller.goto(frame_idx)
        
        # Get the actual frame to check dimensions
        frame = await video_source.get(frame_idx)
        if frame and frame_idx == 0:
            print(f"  Actual frame shape: {frame.rgb.shape}")
            print(f"  Frame size property: {frame.size}")
        
        # Read back the rendered image
        image = visualizer.read_pixels()
        
        # Save the image to scratch directory
        output_path = f"scratch/test_frame_{frame_idx:04d}.png"
        Image.fromarray(image).save(output_path)
        print(f"Saved rendered frame to {output_path}")
        
        # Print some stats
        print(f"  Image shape: {image.shape}")
        print(f"  Min/max values: {image.min()}/{image.max()}")
        
        # Check if we have annotations for this frame
        try:
            frame_data = anno_source.get_frame_data(
                video, frame_idx, missing_policy="blank"
            )
            n_instances = frame_data["points_xy"].shape[0] if frame_data["points_xy"].size > 0 else 0
            n_edges = frame_data["edges"].shape[0] if frame_data["edges"].size > 0 else 0
            print(f"  Instances in frame: {n_instances}")
            print(f"  Edges in skeleton: {n_edges}")
            if n_instances > 0:
                print(f"  Points shape: {frame_data['points_xy'].shape}")
                print(f"  Sample point: {frame_data['points_xy'][0, 0] if frame_data['points_xy'].size > 0 else 'none'}")
        except Exception as e:
            print(f"  No annotations: {e}")
    
    # Clean up
    video_source.close()
    print("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(test_offscreen_rendering())