# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`sleap-viz` is a high-performance visualization tool for SLEAP pose data (.slp files) overlaid on video frames. It targets smooth, interactive visualization of datasets with 100k-300k+ frames, supporting 0-100 instances × 1-50 keypoints per frame.

## Core Commands

### Development
```bash
# Install dependencies
uv sync

# Run the application 
uvx sleap-viz path/to/labels.slp --fps 25

# Linting and formatting
uv run ruff check --fix
uv run ruff format  

# Run tests
uv run pytest -q

# Run specific test file
uv run pytest tests/test_smoke.py -v
```

## Architecture

### Rendering Pipeline
- **Modern GPU rendering** via `pygfx` + `wgpu` (Vulkan/Metal/DX12)
- **Two-draw overlay strategy**: video texture + instanced point/edge overlays
- **Async-first design**: render loop never blocks; I/O happens in background tasks
- **Frame prefetching**: VideoSource maintains ±32 frame cache with cancellable requests

### Core Components

1. **VideoSource** (`video_source.py`): Async wrapper over `sleap-io.Video` with prefetch ring buffer. Shows nearest cached frame immediately on seek, swaps to exact frame when ready.

2. **AnnotationSource** (`annotation_source.py`): Zero-copy adapter over `sleap-io.Labels`. Merges user/predicted instances with configurable precedence policies.

3. **Visualizer** (`renderer.py`): pygfx-based renderer supporting onscreen/offscreen/notebook modes. Handles instanced drawing for points/edges with MSAA and sRGB-correct color.

4. **Controller** (`controller.py`): Main playback/scrub loop. Real-time playback at configurable FPS (default 25) with frame-skip when needed.

5. **Timeline** (`timeline.py`): Consolidated MVC component for multi-resolution timeline. Uses 4096-bin tiles in power-of-2 pyramid for smooth scrubbing on 300k+ frame datasets.

### Key Design Decisions

- **Instanced drawing**: Points/edges drawn via GPU instancing for performance
- **Tile-based timeline**: 4096-bin tiles with LoD pyramid for scalable timeline rendering
- **Frame format**: `(H, W, 3)` uint8 RGB throughout the pipeline
- **Color policies**: Configurable by node/instance/track with dim/hide visibility modes
- **Tone mapping**: Gain/Bias/Gamma/Clip uniforms + optional LUT support

### Async Pattern
All I/O operations are async to prevent blocking the render loop:
```python
frame = await video_source.get(index, timeout=0.01)
if frame is None:
    # Use nearest available frame for instant feedback
    fallback_idx = video_source.nearest_available(index)
```

## Testing Infrastructure

- Test fixtures in `tests/fixtures/` include sample .slp and .mp4 files
- `conftest.py` provides pytest fixtures for common test setup
- Offscreen rendering tests verify GPU pipeline without display

## Code Style

- **Docstrings**: Google-style format
- **Quotes**: Double quotes for strings
- **Line length**: 88 characters (configured in ruff)
- **Type hints**: Use modern Python 3.10+ syntax (`list[str]`, `tuple[int, int]`)
- **Imports**: Organized by ruff with `from __future__ import annotations`

## Current Status

Most modules exist as stubs with basic structure defined. Priority implementation order:
1. Basic video frame loading in VideoSource
2. pygfx rendering pipeline in Visualizer  
3. Frame display without overlays
4. Annotation data loading
5. Point overlay rendering

See `notes/progress.md` for detailed implementation status and `notes/` directory for design documentation.

## Remember
- Use context7 MCP to look up pygfx docs.
- Feel free to write temp scripts, images, plots or whatever else needed to troubleshoot, but do so in the `scratch/` directory. For individual scratch investigations or tasks, create a subfolder called `scratch/YYYY-MM-DD-informative-name` with a `README.md` in it describing what the experiment is for. Later, update it with your findings and include images generated (embedded references to the image file so it renders in markdown). When running the scripts, run from the project root with `uv run scratch/.../test_script.py`
- This is a very visual app. Use your vision capabilities whenever possible to check for graphical/rendering correctness.