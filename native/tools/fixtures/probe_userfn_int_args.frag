#version 330 core
out vec4 fragColor;

// Rule R probe: a bare int literal passed to a USER-DEFINED function must keep
// its integer type, and a float parameter must get its `.0`.
//
// Desktop GLSL implicitly converts int -> float, so the old converter float-ized
// these arguments "because they sit inside a float constructor", producing
//     'add' : no matching overloaded function found
// on GLSL ES.
//
// Scope discipline -- read before editing this file:
//   * Tests ONLY rule R.
//   * Every parameter name is UNIQUE across the file. A name that is `int` in
//     one function and `float` in another triggers a DIFFERENT, pre-existing
//     defect (cross-scope name aliasing, see probe_scope_alias_arith.frag).
//     Mixing the two here would make failures unattributable.
//   * No GLSL reserved words (`half` is reserved; use `halve`).
//   * No `float(param)` cast, for the same reason.

int   add(int a, int b) { return a + b; }           // int params
uint  bump(uint n) { return n + 1u; }               // uint param
float ratio(float x) { return x / 2.0; }            // float param
float blend(int k, float w) { return w * 2.0; }     // mixed positions

void main() {
    float s = ratio(4)
            + blend(5, 0.5)
            + float(add(1, 2))
            + float(bump(3u));
    fragColor = vec4(s, 0.0, 0.0, 1.0);
}
