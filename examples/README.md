# SLEAP-viz Examples

This directory contains example scripts demonstrating various features and use cases of the SLEAP visualization tool.

## Getting Started

Before running the examples, make sure you have:

1. Installed sleap-viz: `pip install sleap-viz` or `uv add sleap-viz`
2. A SLEAP labels file (`.slp`) with associated video

Update the `labels_path` in each example to point to your own `.slp` file.

## Examples

### 1. Basic Usage (`basic_usage.py`)
The simplest example showing how to load and visualize SLEAP pose data.

**Features demonstrated:**
- Loading SLEAP labels and video
- Creating visualization components
- Basic playback control
- Async/await pattern

**Usage:**
```python
python examples/basic_usage.py
```

### 2. Custom Visualization (`custom_visualization.py`)
Shows how to customize the appearance of your visualizations.

**Features demonstrated:**
- Color policies (instance/node/track coloring)
- Color palettes (tab10/tab20/HSV)
- Image adjustments (brightness/contrast/gamma)
- Dynamic visualization updates
- Timeline integration

**Usage:**
```python
python examples/custom_visualization.py
```

### 3. Batch Export (`batch_export.py`)
Demonstrates exporting frames with pose overlays for documentation or analysis.

**Features demonstrated:**
- Offscreen rendering (headless operation)
- Batch frame export to PNG files
- Export at regular intervals
- Export only annotated frames
- Frame pixel capture

**Usage:**
```python
python examples/batch_export.py
```

This is useful for:
- Creating figures for publications
- Generating training data visualizations
- Quality control snapshots
- Time-lapse compilations

### 4. Programmatic Control (`programmatic_control.py`)
Advanced example showing custom playback patterns and frame navigation.

**Features demonstrated:**
- Custom playback controllers
- Frame change callbacks
- Jump to annotated frames
- Slow motion playback
- Ping-pong (forward-backward) playback
- Custom frame sequences

**Usage:**
```python
python examples/programmatic_control.py
```

This is useful for:
- Detailed behavior analysis
- Creating custom review workflows
- Automated quality checks
- Integration with analysis pipelines

## Interactive Viewer

For interactive visualization with keyboard controls, use the CLI:

```bash
# Basic usage
uvx sleap-viz path/to/labels.slp

# With custom settings
uvx sleap-viz path/to/labels.slp --fps 30 --color-by track --gain 1.5

# See all options
uvx sleap-viz --help
```

### Keyboard Controls

When using the interactive viewer:

**Playback:**
- `Space` - Play/pause
- `←/→` - Previous/next frame
- `Shift+←/→` - Skip 10 frames
- `Home/End` - Jump to start/end
- `J/K` - Frame step (vim-style)
- `L` - Toggle loop mode

**Speed:**
- `0-9` - Set playback speed (0=10x, 1=1x, 2=2x, etc.)
- `-/+` - Decrease/increase speed

**Image Adjustments:**
- `B/Shift+B` - Brightness up/down
- `C/Shift+C` - Contrast up/down
- `G/Shift+G` - Gamma down/up
- `R` - Reset adjustments

**Other:**
- `Q/Esc` - Quit

### Mouse Controls

- Click on timeline to jump to frame
- Drag on timeline to scrub through video

## Common Patterns

### Loading with Specific Video

If your `.slp` file contains multiple videos:

```python
labels = sio.load_slp("labels.slp", open_videos=True)
video = labels.videos[2]  # Use third video (0-indexed)
```

### Finding Frames with Specific Conditions

```python
# Find frames with multiple instances
multi_instance_frames = []
for frame_idx in range(len(video)):
    frame_data = annotation_source.get_frame_data(video.filename, frame_idx)
    if frame_data:
        n_instances = len(frame_data.get("user", [])) + len(frame_data.get("predicted", []))
        if n_instances > 1:
            multi_instance_frames.append(frame_idx)
```

### Applying Processing to Each Frame

```python
async def process_frame(controller, frame_idx):
    await controller.goto(frame_idx)
    controller.visualizer.draw()
    pixels = controller.visualizer.read_pixels()
    # Process pixels array (RGBA format)
    return analyze_pose(pixels)

# Process all frames
results = []
for frame_idx in range(controller.total_frames):
    result = await process_frame(controller, frame_idx)
    results.append(result)
```

## Performance Tips

1. **Use offscreen mode** for batch processing to avoid window overhead
2. **Prefetch frames** - VideoSource automatically caches nearby frames
3. **Adjust timeline height** - Set to 0 if not needed to save rendering
4. **Use appropriate FPS** - Match your analysis needs, not necessarily video FPS

## Troubleshooting

### ImportError
Make sure sleap-viz and its dependencies are installed:
```bash
uv add sleap-viz sleap-io
```

### Video not loading
- Check that video path in `.slp` file is correct
- Try opening with `open_videos=True` in `load_slp()`
- Verify video codec is supported

### Slow performance
- Reduce window size for real-time display
- Use offscreen mode for batch processing
- Check GPU drivers are up to date
- Reduce playback FPS if needed

## Additional Resources

- [SLEAP Documentation](https://sleap.ai)
- [sleap-io Documentation](https://github.com/talmolab/sleap-io)
- [pygfx Documentation](https://docs.pygfx.org)