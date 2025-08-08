# Feature Roadmap

## MVP (Milestone 1)
- Render video frames as textured quads using `pygfx` + `wgpu`
- Overlays:
  - **Points:** single instanced draw (instances × keypoints)
  - **Edges:** single line-segments draw using a static edge index buffer per skeleton
- Draw **user** and **predicted** instances together; **optionally hide** predicted referenced by a user instance's `from_predicted`
- Visibility semantics:
  - Support points with `visible=False` that still have coordinates
  - `render_invisible`: `dim` (default) or `hide`
- Interactivity:
  - Scrub + play/pause with instant seek feedback (nearest-available preview → refine swap)
  - Labels/tooltips (initially CPU nearest-neighbor; GPU picking later)
- Image adjustments (real-time):
  - **Gain**/**Bias**/**Gamma** + **Clipping** uniforms in fragment shader
  - Optional **LUT** (256×3 uint8) tone mapping (CLAHE/HE computed off-thread)
- Missing frames / partial data policy:
  - If video frame missing: keep last rendered frame onscreen with a visual indicator (TBD); **still render** keypoints
  - If **no** video frames available: render poses on black background sized from metadata

## v1 (Milestone 2)
- Notebook widget via `jupyter_rfb` (VS Code/JupyterLab/Colab)
- Headless renderer exporting frames (NumPy) to `sleap-io` encoders
- Configurable missing-frame policy for annotations (`error|blank`)
- Pluggable palettes and color policies; config persistence

## Post-v1 (Future)
- GPU picking via ID buffer
- Motion traces / temporal effects for tracked videos
- Line joins/caps: miter/round joins and caps (custom line material if needed)
- Web reach: JS viewer export with Three.js or Pyodide/WebGPU spike

## Explicit Exclusions (for now)
- Per-frame histogram equalization done fully in-shader (we use LUT upload instead)
- Heavy UI chrome; focus on rendering core + thin control layer