"""Test script to verify examples work with test fixtures."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import sleap_io as sio
from sleap_viz.video_source import VideoSource
from sleap_viz.annotation_source import AnnotationSource
from sleap_viz.renderer import Visualizer
from sleap_viz.controller import Controller


async def test_basic_example():
    """Test the basic usage pattern with test fixtures."""
    print("Testing basic example with test fixtures...")
    
    # Use test fixture
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    labels = sio.load_slp(str(labels_path), open_videos=True)
    
    # Get the first video
    video = labels.videos[0]
    print(f"  Loaded video: {video.filename}")
    print(f"  Dimensions: {video.backend.shape}")
    print(f"  Total frames: {len(video)}")
    
    # Create data sources
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    # Create visualizer in offscreen mode for testing
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(width=width, height=height, mode="offscreen")
    
    # Create controller
    controller = Controller(
        video_source, 
        annotation_source, 
        visualizer, 
        video,
        play_fps=25
    )
    
    # Test navigation
    print("\n  Testing frame navigation:")
    await controller.goto(0)
    print(f"    Frame 0: current={controller.current_frame}")
    
    await controller.goto(50)
    print(f"    Frame 50: current={controller.current_frame}")
    
    # Test rendering
    visualizer.draw()
    pixels = visualizer.read_pixels()
    print(f"\n  Rendered frame shape: {pixels.shape}")
    
    # Test finding annotations
    annotated_count = 0
    for frame_idx in range(min(100, len(video))):
        frame_data = annotation_source.get_frame_data(video, frame_idx)
        if frame_data:
            # Check for actual instances in the data
            n_instances = frame_data["points_xy"].shape[0] if "points_xy" in frame_data else 0
            if n_instances > 0:
                annotated_count += 1
    
    print(f"  Found {annotated_count} annotated frames in first 100 frames")
    
    print("\n✅ Basic example test passed!")
    return True


async def test_customization_example():
    """Test visualization customization with test fixtures."""
    print("\nTesting customization example...")
    
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    labels = sio.load_slp(str(labels_path), open_videos=True)
    video = labels.videos[0]
    
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(
        width=width, 
        height=height, 
        mode="offscreen",
        timeline_height=50
    )
    
    # Test different color policies
    print("  Testing color policies:")
    visualizer.set_color_policy(color_by="instance", colormap="tab20")
    print("    - Instance coloring set")
    
    visualizer.set_color_policy(color_by="node", colormap="hsv")
    print("    - Node coloring set")
    
    visualizer.set_color_policy(color_by="track", colormap="tab10")
    print("    - Track coloring set")
    
    # Test image adjustments
    print("\n  Testing image adjustments:")
    visualizer.set_image_adjust(gain=1.5, bias=0.2, gamma=0.8)
    print(f"    - Applied: gain={visualizer.gain}, bias={visualizer.bias}, gamma={visualizer.gamma}")
    
    visualizer.set_image_adjust(gain=1.0, bias=0.0, gamma=1.0)
    print("    - Reset to defaults")
    
    controller = Controller(video_source, annotation_source, visualizer, video)
    await controller.goto(10)
    
    visualizer.draw()
    pixels = visualizer.read_pixels()
    print(f"\n  Rendered customized frame: {pixels.shape}")
    
    print("✅ Customization example test passed!")
    return True


async def test_batch_export():
    """Test batch export functionality."""
    print("\nTesting batch export example...")
    
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    labels = sio.load_slp(str(labels_path), open_videos=True)
    video = labels.videos[0]
    
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(
        width=width,
        height=height,
        mode="offscreen"
    )
    
    controller = Controller(video_source, annotation_source, visualizer, video)
    
    # Test export of a few frames
    print("  Testing frame export:")
    test_frames = [0, 10, 25, 50]
    for frame_idx in test_frames:
        await controller.goto(frame_idx)
        visualizer.draw()
        pixels = visualizer.read_pixels()
        print(f"    Frame {frame_idx}: exported {pixels.shape[0]}x{pixels.shape[1]} image")
    
    print("\n✅ Batch export test passed!")
    return True


async def main():
    """Run all example tests."""
    print("="*60)
    print("Testing SLEAP-viz Examples")
    print("="*60)
    
    results = []
    
    # Test each example pattern
    results.append(await test_basic_example())
    results.append(await test_customization_example())
    results.append(await test_batch_export())
    
    print("\n" + "="*60)
    if all(results):
        print("✅ All example tests passed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())