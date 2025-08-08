"""Advanced batch export examples using the offscreen renderer.

This demonstrates advanced batch processing capabilities:
- High-performance batch rendering
- Video generation with ffmpeg
- Frame montages
- Progress tracking
- Custom frame selection
"""

import asyncio
from pathlib import Path
import time

from sleap_viz.offscreen import OffscreenRenderer


async def example_basic_export():
    """Basic frame export example."""
    print("=" * 60)
    print("EXAMPLE 1: Basic Frame Export")
    print("=" * 60)
    
    # Use test fixture
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    
    # Create renderer
    renderer = OffscreenRenderer(
        str(labels_path),
        color_by="instance",
        colormap="tab20",
        gain=1.2,  # Slightly increase contrast
        bias=0.05,  # Slightly brighten
    )
    
    print("Initializing renderer...")
    await renderer.initialize()
    print(f"Loaded video with {renderer.total_frames} frames")
    
    # Export specific frames
    output_dir = Path("exports/basic")
    frame_indices = [0, 100, 200, 300, 400]
    
    print(f"\nExporting {len(frame_indices)} frames to {output_dir}...")
    start_time = time.time()
    
    exported_files = await renderer.export_frames(
        frame_indices=frame_indices,
        output_dir=output_dir,
        name_pattern="frame_{:04d}.png"
    )
    
    elapsed = time.time() - start_time
    print(f"Exported {len(exported_files)} frames in {elapsed:.2f} seconds")
    print(f"Average: {elapsed/len(exported_files):.3f} seconds per frame")


async def example_annotated_frames():
    """Export only frames with annotations."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Export Annotated Frames Only")
    print("=" * 60)
    
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    
    renderer = OffscreenRenderer(
        str(labels_path),
        color_by="track",  # Color by track ID
        colormap="viridis",
        include_timeline=True  # Include timeline in exports
    )
    
    await renderer.initialize()
    
    # Find annotated frames
    annotated_frames = renderer.get_annotated_frames()
    print(f"Found {len(annotated_frames)} frames with annotations")
    
    # Export first 10 annotated frames
    frames_to_export = annotated_frames[:10]
    output_dir = Path("exports/annotated")
    
    def progress_callback(current, total):
        percent = (current / total) * 100
        print(f"  Progress: {current}/{total} ({percent:.1f}%)", end="\r")
    
    print(f"\nExporting {len(frames_to_export)} annotated frames...")
    await renderer.export_frames(
        frame_indices=frames_to_export,
        output_dir=output_dir,
        progress_callback=progress_callback
    )
    print("\nDone!")


async def example_frame_montage():
    """Create a montage of frames."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Frame Montage")
    print("=" * 60)
    
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    
    renderer = OffscreenRenderer(
        str(labels_path),
        color_by="node",  # Color by body part
        colormap="rainbow",
        tone_map="lut",
        lut_mode="histogram"  # Auto-enhance contrast
    )
    
    await renderer.initialize()
    
    # Select frames for montage (every 100th frame)
    total_frames = renderer.total_frames
    frame_indices = list(range(0, min(total_frames, 1000), 100))
    
    print(f"Creating montage with {len(frame_indices)} frames...")
    output_path = Path("exports/montage.jpg")
    
    await renderer.export_montage(
        frame_indices=frame_indices,
        output_path=output_path,
        grid_size=(3, 4),  # 3 rows, 4 columns
        tile_size=(320, 240),
        spacing=5,
        background_color=(32, 32, 32)  # Dark gray background
    )
    
    print(f"Montage saved to {output_path}")


async def example_video_export():
    """Export as video file (requires ffmpeg-python)."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Video Export")
    print("=" * 60)
    
    try:
        import ffmpeg
    except ImportError:
        print("ffmpeg-python not installed. Install with: pip install ffmpeg-python")
        print("Skipping video export example.")
        return
    
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    
    renderer = OffscreenRenderer(
        str(labels_path),
        color_by="instance",
        colormap="tab20",
        gain=1.1,
        include_timeline=True
    )
    
    await renderer.initialize()
    
    # Export first 100 frames as video
    output_path = Path("exports/output_video.mp4")
    
    def progress_callback(current, total):
        percent = (current / total) * 100
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"  [{bar}] {current}/{total} frames ({percent:.1f}%)", end="\r")
    
    print(f"Exporting video to {output_path}...")
    start_time = time.time()
    
    await renderer.export_video(
        output_path=output_path,
        start_frame=0,
        end_frame=100,
        fps=25.0,
        codec="libx264",
        quality=23,
        progress_callback=progress_callback
    )
    
    elapsed = time.time() - start_time
    print(f"\nVideo exported in {elapsed:.2f} seconds")


async def example_dynamic_settings():
    """Demonstrate dynamic setting updates during batch processing."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Dynamic Settings")
    print("=" * 60)
    
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    
    renderer = OffscreenRenderer(str(labels_path))
    await renderer.initialize()
    
    output_dir = Path("exports/dynamic")
    
    # Export same frame with different settings
    test_frame = 100
    
    settings_variations = [
        {"name": "default", "settings": {}},
        {"name": "high_contrast", "settings": {"gain": 2.0, "bias": -0.1}},
        {"name": "track_colors", "settings": {"color_by": "track", "colormap": "plasma"}},
        {"name": "histogram_eq", "settings": {"tone_map": "lut", "lut_mode": "histogram"}},
        {"name": "clahe", "settings": {"tone_map": "lut", "lut_mode": "clahe"}},
    ]
    
    print(f"Exporting frame {test_frame} with {len(settings_variations)} variations...")
    
    for variation in settings_variations:
        name = variation["name"]
        settings = variation["settings"]
        
        # Update renderer settings
        renderer.update_settings(**settings)
        
        # Export frame
        output_path = output_dir / f"frame_{test_frame}_{name}.png"
        await renderer.export_frame(test_frame, output_path)
        print(f"  Exported: {name}")
    
    print("Done! Check exports/dynamic/ to compare results")


async def example_performance_benchmark():
    """Benchmark rendering performance."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Performance Benchmark")
    print("=" * 60)
    
    labels_path = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    
    # Test with and without timeline
    for include_timeline in [False, True]:
        mode = "with timeline" if include_timeline else "without timeline"
        print(f"\nBenchmarking {mode}...")
        
        renderer = OffscreenRenderer(
            str(labels_path),
            include_timeline=include_timeline
        )
        await renderer.initialize()
        
        # Warm up cache
        await renderer.render_frame(0)
        
        # Benchmark sequential rendering
        n_frames = 50
        start_time = time.time()
        
        for i in range(n_frames):
            await renderer.render_frame(i, use_cache=False)
        
        elapsed = time.time() - start_time
        fps = n_frames / elapsed
        
        print(f"  Rendered {n_frames} frames in {elapsed:.2f} seconds")
        print(f"  Performance: {fps:.1f} FPS ({1000/fps:.1f} ms/frame)")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("SLEAP-VIZ ADVANCED BATCH EXPORT EXAMPLES")
    print("=" * 60)
    
    # Check if test file exists
    test_file = Path(__file__).parent.parent / "tests/fixtures/centered_pair_predictions.slp"
    if not test_file.exists():
        print(f"\nError: Test file not found at {test_file}")
        print("Please ensure you're running from the sleap-viz directory")
        return
    
    # Run examples
    await example_basic_export()
    await example_annotated_frames()
    await example_frame_montage()
    await example_video_export()
    await example_dynamic_settings()
    await example_performance_benchmark()
    
    print("\n" + "=" * 60)
    print("ALL EXAMPLES COMPLETE!")
    print("Check the 'exports' directory for output files")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())