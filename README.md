# sleap-viz

Fast, smooth visualization for SLEAP `.slp` pose data over video using `pygfx`/`wgpu`.

## Quick Start

### Run directly from GitHub (no installation needed!)

With [uv](https://github.com/astral-sh/uv) installed, you can run `sleap-viz` directly from the GitHub repository:

```bash
# Run the latest version directly from GitHub
uvx --from git+https://github.com/talmo/sleap-viz sleap-viz path/to/labels.slp --fps 25

# Or use the shorter syntax
uvx sleap-viz@git+https://github.com/talmo/sleap-viz path/to/labels.slp --fps 25
```

### Install locally for development

```bash
# Clone the repository
git clone https://github.com/talmo/sleap-viz.git
cd sleap-viz

# Install dependencies
uv sync

# Run the tool
uvx sleap-viz path/to/labels.slp --fps 25
```

## Usage

```bash
# Basic usage
sleap-viz path/to/labels.slp

# With custom FPS (default: 25)
sleap-viz path/to/labels.slp --fps 30

# With color policies
sleap-viz path/to/labels.slp --color-by instance --colormap tab20

# With image adjustments
sleap-viz path/to/labels.slp --gain 1.5 --bias 0.2 --gamma 0.8

# With tone mapping
sleap-viz path/to/labels.slp --tone-map lut --lut-mode clahe
```

## Interactive Controls

### Playback
- **Space**: Play/pause
- **Left/Right arrows**: Previous/next frame
- **Shift+Left/Right**: Skip 10 frames
- **J/K**: Frame step backward/forward
- **L**: Toggle loop mode
- **0-9**: Set playback speed (1=1x, 2=2x, 0=10x)

### Image Adjustments
- **B/Shift+B**: Increase/decrease brightness
- **C/Shift+C**: Increase/decrease contrast
- **G/Shift+G**: Adjust gamma
- **R**: Reset adjustments
- **T**: Toggle tone mapping
- **E**: Toggle CLAHE enhancement

### Timeline
- **Click**: Jump to frame
- **Drag**: Scrub through frames
- **Wheel**: Zoom timeline
- **Z/Shift+Z**: Zoom in/out
- **X**: Reset zoom
- **A/D**: Pan timeline left/right

### Other
- **Q/Escape**: Quit
- **H**: Show help

## Development

```bash
# Run tests
uv run pytest -q

# Lint and format
uv run ruff check --fix
uv run ruff format
```