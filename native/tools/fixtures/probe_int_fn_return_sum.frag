#version 330 core
out vec4 fragColor;
// Minimal: does an int-returning function's `return a + b;` get corrupted
// independently of anything else?
//
// If `a` is wrapped as `float(a)` here, the culprit is NOT rule R -- rule R
// only acts on a bare int literal that is an argument of a user function, and
// there is no such literal in `return a + b;`.
//
// Kept deliberately tiny so the output is unambiguous.

int add(int a, int b) {
    return a + b;
}

float scale(int n) {
    return float(n) / 16.0;
}

void main() {
    fragColor = vec4(scale(add(1, 2)), 0.0, 0.0, 1.0);
}
