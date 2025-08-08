# SLEAP Pose Visualization - Goals & Overview

## Project Goals
- Fast, smooth, interactive visualization of SLEAP `.slp` data overlaid on video frames
- Cross-mode: desktop (onscreen), headless (batch), notebooks (interactive via `jupyter_rfb`), with future-friendly web reach
- Scales: single videos with **100k–300k+ frames**; **0–100 instances** × **1–50 keypoints** per frame
- Quality: crisp antialiased points/lines/text, sRGB-correct color, optional tone mapping (brightness, contrast, LUT, clipping)
- Flexibility: modular color policies (by node/instance/track/meta), visibility styling, user/pred precedence, skeleton changes

## Stack Motivation
- **`pygfx` + `wgpu`**: modern GPU (Vulkan/Metal/DX12), robust primitives, instancing, MSAA, sRGB. Cleaner than OpenCV; more portable than legacy GL
- **`jupyter_rfb`**: real interactive GPU canvases in notebooks (VS Code/JupyterLab/Colab)
- **`sleap-io`**: unified I/O for videos (FFmpeg/OpenCV/imageio/TIFF/HDF5) and labels (`Labels`, `LabeledFrame`, `Instance`, skeletons)
- **Async-first**: render loop never blocks; heavy I/O/CPU work happens in background tasks

## Tooling & Packaging
- **Layout:** `src/sleap_viz/` (packaged app, `uv init --package sleap-viz`)
- **Package name:** `sleap-viz`
- **CLI:** `sleap-viz labels.slp` (view is default; other modes via flags)
- **CLI framework:** `click`
- **Packaging & deps:** `uv`
- **Lint/format:** `ruff` (with `black` + `pydocstyle` rules)
- **Code style:** Google-style docstrings, double quotes