#version 460

// Faithful reduction of Engine-Room/Flywheel: flywheel/internal/wavelet.glsl
//
// The macro body is a plain integer literal (16), and the macro is used in
// BOTH integer and float contexts:
//     float context: depth *= float(COUNT-1) / COUNT;
//     int context:   int index = clamp(int(floor(depth * COUNT)), 0, COUNT - 1);
// Desktop GLSL bridges the two with implicit conversion; GLSL ES does not.
// So the correct handling is to expand the macro to its literal and let the
// per-position rules decide -- NOT to declare the macro itself as int or float
// (either choice breaks the other half).
//
// Regression guard: 用例 21 in native/tools/test_shader_convert.c
//   - `float(16-1) / 16.0`            the `-1` must stay int, `/ 16` becomes float
//   - `clamp(int(...), 0, 16 - 1)`    both must stay int (int overload)
#define TRANSPARENCY_WAVELET_COEFFICIENT_COUNT 16

in float depthIn;
out vec4 fragColor;

float add_absorbance_like(float depth) {
    depth *= float(TRANSPARENCY_WAVELET_COEFFICIENT_COUNT-1) / TRANSPARENCY_WAVELET_COEFFICIENT_COUNT;
    return depth;
}

int index_of(float depth) {
    return clamp(int(floor(depth * TRANSPARENCY_WAVELET_COEFFICIENT_COUNT)), 0,
                 TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
}

void main() {
    float d = add_absorbance_like(depthIn);
    fragColor = vec4(d, float(index_of(d)), 0.0, 1.0);
}
