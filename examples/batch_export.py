"""Example for batch exporting frames with pose overlays.

This example demonstrates how to:
- Process multiple frames or videos
- Export rendered frames to image files
- Use offscreen rendering for headless operation
"""

import asyncio
from pathlib import Path
import numpy as np
from PIL import Image
import sleap_io as sio
from sleap_viz.video_source import VideoSource
from sleap_viz.annotation_source import AnnotationSource
from sleap_viz.renderer import Visualizer
from sleap_viz.controller import Controller


async def export_frame(
    controller: Controller,
    frame_idx: int,
    output_path: Path
) -> None:
    """Export a single frame with pose overlay.
    
    Args:
        controller: The controller instance.
        frame_idx: Frame index to export.
        output_path: Path to save the image.
    """
    # Navigate to frame
    await controller.goto(frame_idx)
    
    # Render and get pixels
    controller.visualizer.draw()
    pixels = controller.visualizer.read_pixels()
    
    # Save as image (pixels are RGBA)
    image = Image.fromarray(pixels)
    image.save(output_path)
    print(f"  Exported frame {frame_idx} to {output_path}")


async def export_frames_at_intervals(
    labels_path: Path,
    output_dir: Path,
    interval: int = 100,
    max_frames: int = 10
) -> None:
    """Export frames at regular intervals.
    
    Args:
        labels_path: Path to SLEAP labels file.
        output_dir: Directory to save exported frames.
        interval: Frame interval for exports.
        max_frames: Maximum number of frames to export.
    """
    print(f"Loading {labels_path}...")
    labels = sio.load_slp(str(labels_path), open_videos=True)
    video = labels.videos[0]
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up offscreen renderer
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(
        width=width,
        height=height,
        mode="offscreen",  # No window needed
        timeline_height=0   # No timeline for exports
    )
    
    # Apply nice visualization settings
    visualizer.set_color_policy(color_by="instance", colormap="tab20")
    visualizer.set_image_adjust(gain=1.2, bias=0.0, gamma=1.0)
    
    controller = Controller(
        video_source,
        annotation_source,
        visualizer,
        video,
        play_fps=25
    )
    
    # Export frames
    total_frames = len(video)
    frames_to_export = []
    
    for i in range(0, total_frames, interval):
        frames_to_export.append(i)
        if len(frames_to_export) >= max_frames:
            break
    
    print(f"\nExporting {len(frames_to_export)} frames...")
    for frame_idx in frames_to_export:
        output_path = output_dir / f"frame_{frame_idx:06d}.png"
        await export_frame(controller, frame_idx, output_path)
    
    print(f"\nExport complete! Frames saved to {output_dir}")


async def export_key_frames(
    labels_path: Path,
    output_dir: Path
) -> None:
    """Export only frames that have annotations.
    
    Args:
        labels_path: Path to SLEAP labels file.
        output_dir: Directory to save exported frames.
    """
    print(f"Loading {labels_path}...")
    labels = sio.load_slp(str(labels_path), open_videos=True)
    video = labels.videos[0]
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up offscreen renderer
    video_source = VideoSource(video)
    annotation_source = AnnotationSource(labels)
    
    width = video.backend.shape[2]
    height = video.backend.shape[1]
    visualizer = Visualizer(
        width=width,
        height=height,
        mode="offscreen"
    )
    
    controller = Controller(
        video_source,
        annotation_source,
        visualizer,
        video,
        play_fps=25
    )
    
    # Find frames with annotations
    annotated_frames = []
    for frame_idx in range(len(video)):
        frame_data = annotation_source.get_frame_data(video.filename, frame_idx)
        if frame_data and (frame_data.get("user") or frame_data.get("predicted")):
            annotated_frames.append(frame_idx)
    
    print(f"\nFound {len(annotated_frames)} frames with annotations")
    print(f"Exporting first 20 annotated frames...")
    
    # Export up to 20 annotated frames
    for i, frame_idx in enumerate(annotated_frames[:20]):
        output_path = output_dir / f"annotated_frame_{frame_idx:06d}.png"
        await export_frame(controller, frame_idx, output_path)
    
    print(f"\nExport complete! Annotated frames saved to {output_dir}")


async def main():
    """Run batch export examples."""
    # Example 1: Export frames at regular intervals
    labels_path = Path("path/to/your/labels.slp")
    
    if labels_path.exists():
        print("Example 1: Exporting frames at intervals")
        output_dir = Path("exports/interval_frames")
        await export_frames_at_intervals(
            labels_path, 
            output_dir,
            interval=100,  # Every 100 frames
            max_frames=10  # Export 10 frames total
        )
        
        print("\n" + "="*50 + "\n")
        
        print("Example 2: Exporting annotated frames only")
        output_dir = Path("exports/annotated_frames")
        await export_key_frames(labels_path, output_dir)
    else:
        print("Please update the labels_path in this script to point to your .slp file")


if __name__ == "__main__":
    asyncio.run(main())