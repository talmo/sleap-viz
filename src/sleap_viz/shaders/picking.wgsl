// GPU picking shader for ID buffer rendering
// Each point is rendered with a unique color encoding its instance and node IDs

struct VertexInput {
    @builtin(vertex_index) vertex_index: u32,
    @location(0) position: vec3<f32>,
    @location(1) point_id: vec2<u32>,  // (instance_id, node_id)
    @location(2) size: f32,
}

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) encoded_id: vec4<f32>,
    @location(1) point_coord: vec2<f32>,
}

struct Uniforms {
    mvp_matrix: mat4x4<f32>,
    viewport_size: vec2<f32>,
}

@group(0) @binding(0)
var<uniform> uniforms: Uniforms;

// Vertex shader
@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var output: VertexOutput;
    
    // Transform position to clip space
    output.position = uniforms.mvp_matrix * vec4<f32>(input.position, 1.0);
    
    // Encode IDs as color
    // Instance ID in RG channels (16 bits)
    let r = f32((input.point_id.x >> 8u) & 0xFFu) / 255.0;
    let g = f32(input.point_id.x & 0xFFu) / 255.0;
    // Node ID in B channel (8 bits)
    let b = f32(input.point_id.y) / 255.0;
    // Alpha = 1.0 for valid points
    output.encoded_id = vec4<f32>(r, g, b, 1.0);
    
    // Calculate point coordinates for circle rendering
    // Map vertex index to quad corners
    let quad_pos = vec2<f32>(
        f32((input.vertex_index & 1u) * 2u) - 1.0,
        f32(((input.vertex_index >> 1u) & 1u) * 2u) - 1.0
    );
    output.point_coord = quad_pos;
    
    // Apply point size in screen space
    let screen_pos = output.position.xy / output.position.w;
    let size_ndc = input.size / uniforms.viewport_size * 2.0;
    output.position.x += quad_pos.x * size_ndc.x * output.position.w;
    output.position.y += quad_pos.y * size_ndc.y * output.position.w;
    
    return output;
}

// Fragment shader
@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    // Check if fragment is within circle
    let dist = length(input.point_coord);
    if (dist > 1.0) {
        discard;
    }
    
    // Return encoded ID as color
    return input.encoded_id;
}

// Alternative fragment shader for edge picking
@fragment
fn fs_edge_main(input: VertexOutput) -> @location(0) vec4<f32> {
    // For edges, just return the encoded ID without circle test
    return input.encoded_id;
}