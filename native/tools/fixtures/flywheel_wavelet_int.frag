#version 460

// Faithful reduction of Engine-Room/Flywheel: flywheel/internal/wavelet.glsl
// The macro body is a plain integer literal (16). It is used ONLY in integer
// contexts, but our converter floats the adjacent literals anyway.
//
// Expected output: the macro and the literals around it must keep their
// integer type, i.e. `TRANSPARENCY_WAVELET_COEFFICIENT_COUNT-1` stays as-is
// and `clamp(..., 0, COUNT - 1)` keeps int 0 and int COUNT-1.
#define TRANSPARENCY_WAVELET_COEFFICIENT_COUNT 16

in float depthIn;
out vec4 fragColor;

float f1(float depth) {
    depth *= float(TRANSPARENCY_WAVELET_COEFFICIENT_COUNT-1) / TRANSPARENCY_WAVELET_COEFFICIENT_COUNT;
    return depth;
}

float f2(float coefficient_depth) {
    int index_b = clamp(int(floor(coefficient_depth)), 0, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
    return float(index_b);
}

float f3(float signal) {
    return f1(signal) + f2(signal);
}

void main() {
    fragColor = vec4(f3(depthIn));
}
