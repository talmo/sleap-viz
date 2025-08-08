# sleap-viz

Fast, smooth visualization for SLEAP `.slp` pose data over video using `pygfx`/`wgpu`.

Quick start (with uv):

```bash
uv sync
uvx sleap-viz path/to/labels.slp --fps 25
```

Development:

```bash
uv run ruff check --fix
uv run ruff format
uv run pytest -q
```