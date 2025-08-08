# Project Structure

## Repository Layout
```
src/
  sleap_viz/
    __init__.py
    cli.py           # click CLI entrypoint
    video_source.py  # async sio.Video wrapper
    annotation_source.py
    renderer.py      # pygfx renderer
    controller.py    # main play/scrub loop
    timeline.py      # timeline component (model, view, controller)
    styles.py        # palettes + color policies
    shaders/
      __init__.py
      tone_mapping.wgsl
examples/
  desktop_mvp.py
  notebook_demo.ipynb
  batch_render.py
pyproject.toml       # uv/ruff/black/pydocstyle config, click entrypoint
```

## CLI Configuration
- Console script: `sleap-viz = "sleap_viz.cli:main"` in `pyproject.toml`
- CLI usage: `uvx sleap-viz path/to/labels.slp --fps 25`