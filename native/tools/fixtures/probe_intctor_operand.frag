#version 330 core
// Isolate: is wrapping of an INTEGER CONSTRUCTOR (`ivec2(1)` -> `vec2(ivec2(1))`)
// a defect of its own, or only a knock-on effect of the name-shadowing bug?
//
// Here every int identifier is a UNIQUELY NAMED parameter, so the int-identity
// table cannot be confused. If `coord + ivec2(1)` still becomes
// `coord + vec2(ivec2(1))`, the ctor rule is broken independently.

out vec4 fragColor;

// (a) known-int lhs + int ctor rhs
vec2 a(ivec2 coord) {
    return vec2(coord + ivec2(1));
}

// (b) int ctor as a standalone argument to a float-returning call
vec2 b(ivec2 coord) {
    return vec2(coord) / vec2(ivec2(16));
}

// (c) scalar int ctor in float context (must become float(...))
float c(int n) {
    return float(n) / 16.0 + float(int(2));
}

void main() {
    fragColor = vec4(a(ivec2(0)) + b(ivec2(0)), c(1), 1.0);
}
