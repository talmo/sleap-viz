# Color Palettes & Styling

## Built-in Palettes
- `tab10`, `tab20`
- ColorBrewer qualitative/sequential/diverging
- HSV

## Implementation
- No heavy deps: embed palette tables or use a lightweight palette lib
- Expose both **palette** and **mapping policy** as callables for:
  - by-node
  - by-instance
  - by-track
  - by-meta