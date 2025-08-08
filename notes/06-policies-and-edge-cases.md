# Policies & Edge Cases

## Labels Indexing
- Always `labels[(video, frame_idx)]`
- `missing_policy="blank"` returns a blank `LabeledFrame` (not inserted) via `Labels.find(..., return_new=True)`

## User vs Predicted Precedence
- If a user instance has `from_predicted`, hide that predicted instance when `precedence="user_over_from_predicted"` (default)
- Other modes supported

## Missing Video Frames
- Do **not** log or error
- Keep last frame with an indicator (TBD) and still draw keypoints
- Black background if none

## Skeleton Changes
- Detect per frame
- Rebuild static edges buffer only on change (cache by `id(skeleton)`)

## Frame Format
- Expect `(H, W, 3)` uint8 RGB from `sio.Video`