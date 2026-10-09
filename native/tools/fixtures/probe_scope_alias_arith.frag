#version 330 core
out vec4 fragColor;

// DEFECT 3 probe -- cross-scope name aliasing inside ARITHMETIC rules.
//
// `b` is `int` in `add()` and `float` in `blend()`. GLSL scopes parameters to
// their own function, so this is legal. But the converter's float-variable
// tables are keyed by NAME ONLY, so `b` is recorded as float and 情形 A
// ("int operand * / with a float operand -> wrap") fires inside `add()`,
// producing
//     int add(int a, int b) { return float(a) + b; }   // float + int, invalid ES
//
// Same family as the defect fixed for rule R / scope-aware parameter lookup,
// but on a different code path: here the wrap is applied to a VARIABLE in an
// arithmetic expression, not to a literal argument.
//
// Verified independent of rule R: an A/B build with rule R compiled out
// (-DGLESMOD_NO_RULE_R) produces byte-identical output for this file.
//
// This fixture is registered in roundtrip_validate.py's KNOWN_UNFIXED so the
// gate stays green while the defect is real, and HARD-FAILS the moment it is
// fixed -- forcing the entry to be cleaned up.

int   add(int a, int b) { return a + b; }           // b is int here
float blend(int a, float b) { return b * 2.0; }     // b is float here

void main() {
    fragColor = vec4(float(add(1, 2)) + blend(3, 0.5), 0.0, 0.0, 1.0);
}
