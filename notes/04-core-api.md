# Core API Types

> Code style: Google docstrings, double quotes, `black`-friendly

## `Frame`
- `index: int` — frame index
- `rgb: np.ndarray` — `(H, W, 3)` uint8
- `size: tuple[int, int]` — `(width, height)`

## `VideoSource` — async wrapper over `sio.Video`
- `__init__(video: sio.Video, cache_size=64)`
- `await request(index: int)` — enqueue decode
- `await get(index: int, timeout=0.01) -> Frame | None` — return if ready else `None`
- `nearest_available(index: int) -> int | None`
- `close()`

## `AnnotationSource` — adapter over `sio.Labels`
- `__init__(labels: sio.Labels)`
- `get_edges(skel: sio.Skeleton) -> np.ndarray[int32,(E,2)]` (cached)
- `get_frame_data(video: sio.Video, index: int, *, missing_policy="error"|"blank", include_user=True, include_predicted=True, precedence="user_over_from_predicted"|"show_both"|"user_only"|"predicted_only", render_invisible="dim"|"hide"|callable) -> dict`
  - Returns: `points_xy [N_inst,N_nodes,2]`, `visible [N_inst,N_nodes]`, `inst_kind [N_inst] (0=user,1=pred)`, `track_id [N_inst]`, `node_ids [N_nodes]`, `edges [E,2]`, `labels list[str]`, `skeleton_id`

## `Visualizer` — pygfx renderer (onscreen/offscreen)
- `__init__(width, height, mode="auto"|"desktop"|"notebook"|"offscreen")`
- `set_frame_image(frame)`
- `set_overlay(points_xy, visible, edges, inst_kind=None, track_id=None, node_ids=None, colors_rgba=None, labels=None)`
- `set_color_policy(color_by="instance"|callable, colormap="tab20"|callable, invisible_mode="dim"|"hide")`
- `set_image_adjust(gain=1.0, bias=0.0, gamma=1.0, tone_map="linear"|"lut" = "linear", lut=None)`
- `draw()`
- `read_pixels() -> np.ndarray[uint8,(H,W,3)]`

## `Controller` — play/scrub loop
- `__init__(video_source, anno_source, visualizer, video: sio.Video, play_fps=25.0)`
- `await goto(index: int)` — seek; preview nearest; refine swap
- `await play()` — real-time playback with frame-skip when needed
- `pause()`

## Controller Defaults
- **Playback FPS:** default **25 FPS**; configurable at runtime and via CLI (`--fps`)
- **Frame format:** `(H, W, 3)` uint8 RGB