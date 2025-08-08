# Test Plan (Smoke)

1. **Tiny synthetic dataset**: 100 frames, 2 instances × 5 kps; verify two draw calls and >200 FPS on laptop dGPU

2. **Large video**: 120k–300k frames; seek latency <1 frame for preview; refine <150 ms typical

3. **Mixed visibility**: validate dim/hide correct

4. **Skeleton swap**: switch across segments; verify single rebuild per change

5. **Notebook**: VS Code + JupyterLab + (later) Colab: interactive canvas appears; controls responsive

6. **Headless**: render 1k frames to arrays; encode via `sleap-io`; validate output