# Decision Points & Open Questions

## Resolved Incrementally

- **pygfx materials**: start with built-ins; add minimal custom modules for per-point/per-edge styling and joins/caps if needed

- **Point primitive**: circle SDF quads (preferred) for crisp scaling

- **Line joins/caps**: plan custom line material (post-MVP) for miter/round joins/caps if built-ins insufficient

- **Text renderer**: start with pygfx text; add MSDF only if zoomed sharpness is insufficient

- **Palettes**: ship tab10/tab20, ColorBrewer, HSV; consider tiny palette lib to mirror seaborn sets without heavy deps

- **Controller UX**: bindings as in Input & UX doc; step sizes confirmed

- **Missing frames**: indicator TBD; draw annotations regardless; black background fallback

- **Colab**: integration details deferred; add a setup helper later

- **Color/LUT**: MVP has gain/bias/gamma/clip; optional LUT per channel

- **Batch output**: RGB `(H, W, 3)` uint8 arrays to `sleap-io` encoders by default