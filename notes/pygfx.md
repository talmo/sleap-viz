# pygfx Rendering Notes

## Key Findings from Research

### 1. Image Rendering Issues

The main issue with our current implementation is that `gfx.Image` with `ScreenCoordsCamera` doesn't properly fill the canvas. The solution is to use a textured mesh instead:

```python
# Instead of gfx.Image:
geometry = gfx.plane_geometry(canvas_width, canvas_height)
mesh = gfx.Mesh(geometry, gfx.MeshBasicMaterial(map=texture))
```

### 2. Camera Selection

- **ScreenCoordsCamera**: Good for UI/2D graphics but has limitations with image filling
- **OrthographicCamera**: Better control, use with `maintain_aspect=False` for stretching
- **NDCCamera**: Uses normalized coordinates (-1 to 1), good for full-screen effects

For our use case, **OrthographicCamera** is the best choice:
```python
camera = gfx.OrthographicCamera(width, height, maintain_aspect=False)
camera.show_rect(0, width, 0, height)  # left, right, top, bottom
```

### 3. Coordinate System Issues

pygfx uses different coordinate conventions:
- Image data: Origin at top-left, Y increases downward
- OpenGL/WebGPU: Origin at bottom-left, Y increases upward
- Solution: Flip Y-axis in camera or positioning

### 4. Texture Data Requirements

- Must be float32 normalized (0-1) or uint8 (0-255)
- Grayscale must be converted to RGB
- Use `colorspace="srgb"` for display images

### 5. Offscreen Canvas Quirks

The `canvas.draw()` method returns an array with shape that might not match the canvas size specification. This is a known pygfx/wgpu behavior where the returned array shape is (height, width, 4) regardless of how the canvas was created.

### 6. Rendering Pipeline

Correct order:
1. Create/update texture
2. Create mesh with texture
3. Position mesh correctly
4. Add to scene
5. Call `renderer.render(scene, camera)`
6. Call `canvas.draw()` for offscreen

## Solutions for Our Issues

### Problem 1: Video Not Rendering
**Cause**: `gfx.Image` doesn't properly stretch to fill canvas with `ScreenCoordsCamera`
**Solution**: Use `gfx.Mesh` with `gfx.plane_geometry`

### Problem 2: Wrong Output Dimensions
**Cause**: `canvas.draw()` returns array in (height, width, channels) format
**Solution**: Accept this as expected behavior, document it

### Problem 3: Skeleton Lines Not Visible
**Cause**: Lines might be too thin or wrong color
**Solution**: Increase thickness, use brighter color, ensure Z-ordering is correct

## Recommended Implementation

```python
# Camera setup
camera = gfx.OrthographicCamera(width, height, maintain_aspect=False)
camera.show_rect(0, width, 0, height)

# Video background using mesh
plane_geo = gfx.plane_geometry(width, height)
video_mesh = gfx.Mesh(plane_geo, gfx.MeshBasicMaterial(map=texture))
video_mesh.local.position = (width/2, height/2, -1)

# Overlays at z=0
points.local.position[2] = 0
lines.local.position[2] = 0
```

## Testing Strategy

1. Test with a simple colored texture first
2. Verify coordinate mapping with test points at corners
3. Check Z-ordering by varying Z positions
4. Test line rendering with thicker lines and bright colors