#version 460

// Engine-Room/Flywheel `flywheel/internal/wavelet.glsl` 的忠实还原
// （faithful reduction）—— 内容源自该文件，非逐字副本。
//
//   上游: https://github.com/Engine-Room/Flywheel
//   许可: MIT License
//   版权: Copyright (c) 2021-2024 Jozufozu
//   依 MIT 要求保留版权与许可声明；完整许可全文见同目录
//   flywheel_int_macro.frag 的文件头。
//
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
