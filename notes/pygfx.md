# pygfx Rendering Notes

## Latest Findings (2025-01-08)

### Working Implementation Patterns

Based on hands-on testing, here are the confirmed working patterns for our use case:

#### 1. Offscreen Canvas Creation
```python
from wgpu.gui.offscreen import WgpuCanvas
canvas = WgpuCanvas(size=(width, height))
renderer = gfx.renderers.WgpuRenderer(canvas)
```

#### 2. Video Frame Rendering
```python
# Create texture from numpy array (H, W, 3) uint8
texture = gfx.Texture(frame_rgb, dim=2, colorspace="srgb")

# Create plane mesh with texture
plane_geo = gfx.plane_geometry(width, height)
material = gfx.MeshBasicMaterial(map=texture)
video_mesh = gfx.Mesh(plane_geo, material)

# Position at center, set z=-1 for background
video_mesh.local.position = (width/2, height/2, -1)
scene.add(video_mesh)
```

#### 3. Camera Setup
```python
# OrthographicCamera is best for 2D overlays
camera = gfx.OrthographicCamera(width, height, maintain_aspect=False)
camera.show_rect(0, width, 0, height)
```

#### 4. Points Rendering (Keypoints)
```python
# positions: (N, 3) float32 array with x, y, z=0
points_geo = gfx.Geometry(positions=positions)
points_mat = gfx.PointsMaterial(color="#ff0000", size=8)
points = gfx.Points(points_geo, points_mat)
scene.add(points)
```

#### 5. Lines Rendering (Skeleton)
```python
# Create line segments (each pair of points defines a segment)
line_positions = []  # List of [x, y, z] points
for edge in edges:
    line_positions.append(point1)
    line_positions.append(point2)

line_geo = gfx.Geometry(positions=np.array(line_positions, dtype=np.float32))
line_mat = gfx.LineMaterial(color="#00ff00", thickness=2)
lines = gfx.Line(line_geo, line_mat)
scene.add(lines)
```

#### 6. Rendering and Reading Pixels
```python
renderer.render(scene, camera)
pixels = np.asarray(canvas.draw())  # Returns (H, W, 4) uint8 RGBA
```

### Important API Notes

- **Texture format**: Accepts uint8 (0-255) or float32 (0-1) normalized
- **Grayscale handling**: Must convert to RGB by repeating channels
- **Z-ordering**: Use z-position for layering (background at z=-1, overlays at z=0)
- **Line segments**: Each pair of consecutive points in the geometry forms a segment
- **Canvas output**: Always returns (height, width, 4) RGBA array

### SLEAP Integration Specifics

```python
# Get labeled frame
lf = labels.find(video, frame_idx)
lf = lf[0] if lf else None

# Extract instance points
points_xy = instance.numpy()  # (n_nodes, 2) array
valid_mask = ~np.isnan(points_xy[:, 0])

# Convert to 3D positions for pygfx
positions = np.zeros((n_valid, 3), dtype=np.float32)
positions[:, :2] = points_xy[valid_mask]
positions[:, 2] = 0
```

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