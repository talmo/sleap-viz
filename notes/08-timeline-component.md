# Timeline Component Design

## Goals
- Smooth, frame-accurate scrubbing on datasets with **up to 300k+ frames**
- Visualize **per-frame markers** (e.g., has labels) and later **arbitrary timeseries** in sync
- **Zoomable & pannable** across many orders of magnitude (<10 frames to 300k+), with crisp demarcations when zoomed in
- **Asynchronous** updates for expensive per-frame computations; UI must stay responsive

## Decisions for MVP (Locked-in)
- **Tile defaults:** power-of-two pyramid with **4096-bin tiles** per level
- **Zoomed-out categorical rendering:** **winner-takes-all** color per pixel column (no stacked categories in MVP)
- **Timeseries:** **defer**; design supports user-provided arrays/callbacks later, but not in MVP scope
- **Frame-range selection:** **include**—click-drag to select ranges for interactive clip rendering/export; `[`/`]` to nudge edges; `Shift`×10; `Ctrl/Cmd`×100
- **Per-frame markers (MVP):** render every frame in a **default neutral gray**; later add colors for user/pred frames and other attributes

## Architecture (MVC-ish)
All three components consolidated in `timeline.py`:
- **TimelineModel** — duration `N_frames`, registered channels, async tile aggregates + cache
- **TimelineView** — dedicated `pygfx` canvas; tracks (rows), playhead (subpixel 1px line), selection regions; virtualization & LoD
- **TimelineController** — input → model range; playhead sync; tile prefetch; debounced redraws

## Rendering Strategy
- Frames → pixels via affine transform of `[x_min_frame, x_max_frame]`
- **Zoomed out (>1 frame/px):** per-pixel bins rendered from a 1D texture (winner-takes-all color via palette lookup)
- **Zoomed in (≤1 frame/px):** instanced per-frame quads with nearest sampling and 1px separators
- Playhead: overlay pass 1px vertical line (device pixel aligned). Selections: translucent quads

## Level-of-Detail & Tiling
- Multi-resolution pyramid per channel; power-of-two bin widths
- Tiles: fixed width (4096 bins) cached SoA; choose coarsest level with ≤1 bin/px

## Async & Cache
- Job queue for tile computation; cancel stale jobs; prefetch visible + neighbors; LRU cap per level

## API Surface (Draft)
- **Model**: `register_channel(...)`, `set_range(xmin,xmax)`, `get_tile(level,i)`
- **View**: `set_tracks(...)`, `set_palette(...)`, `render(...)`
- **Controller**: `on_wheel/pinch/drag/key`, `seek_to_frame(i)`, `set_selection(range)`

## Timeseries (Deferred)
- Support user-provided arrays/callbacks; reuse numeric track path later