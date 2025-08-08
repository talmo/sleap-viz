# Algorithmic Performance Design

## Rendering (two-draw overlay)
- **Points**: instanced draw with per-point attributes: xy (f32), visible (bit), style flags, RGBA (u8) if precomputed
- **Edges**: line segments with static `edges[E,2]` index buffer; per-edge width/color inherited or via compact buffer
- **Persistent GPU resources**: create once; update via `wgpu.queue.write_buffer` each frame. Recreate the video texture only on resolution change
- **Color space & AA**: sRGB-correct sampling and MSAA for crisp visuals

## I/O + Scrubbing
- **VideoSource**: thin async wrapper over `sio.Video` with a prefetch ring (e.g., ±32), cancellable requests, nearest-available fallback for instant feedback
- **AnnotationSource**: zero-copy reads of `.points["xy"]` / `["visible"]`; merge user + predicted with precedence via `from_predicted`
- **Seek policy**: on big jumps, show closest cached frame immediately; swap to exact target when ready (never stall render loop)

## Labels/Tooltips
- Use pygfx screen-space text anchored to world positions (atlas-backed). Limit to hovered/selected or top‑K while scrubbing; expand on pause
- **Picking v0**: CPU nearest-neighbor on a capped candidate set; **v1+**: GPU ID buffer

## Tone Mapping
- **Gain/Bias/Gamma/Clip** uniforms (cheap, per-pixel)
- **LUT tone mapping**: optional 256×3 uint8 table uploaded as a small texture; LUT computed off-thread (CLAHE/HE). If LUT not ready, fall back to linear