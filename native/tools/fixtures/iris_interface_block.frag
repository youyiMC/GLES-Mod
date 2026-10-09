#version 120

// Iris injects std140 interface blocks at GLOBAL SCOPE for shaderpacks that use
// the legacy uniform style (VanillaTransformer / VanillaCoreTransformer):
//
//     layout(std140) uniform iris_Fog {
//         vec4 FogColor;
//         float FogEnvironmentalStart;
//         ...
//     } iris_fogP;
//
// Two hazards for our non-constant-global-initializer rewriter:
//   1. A block ends with `};`. The statement splitter resets at every brace, so
//      the `;` after `}` is a statement of its own containing no '='. It must be
//      written through untouched.
//   2. Shaderpacks then initialize globals FROM the block instance:
//          vec3 fogColor = iris_fogP.FogColor.rgb;
//      `iris_fogP` is a plain global (not a uniform name and not a builtin), so
//      detection must consult the global-name table, not just the uniform table.
//
// Also covers `layout (location = N)` on an `in` declaration, the shape Iris's
// LayoutTransformer produces for fragment inputs on the core profile.

uniform sampler2D colortex0;

layout(std140) uniform iris_Fog {
    vec4 FogColor;
    float FogEnvironmentalStart;
    float FogEnvironmentalEnd;
} iris_fogP;

varying vec2 texCoord;

vec3 fogColor = iris_fogP.FogColor.rgb;
float fogStart = iris_fogP.FogEnvironmentalStart;

void main() {
    gl_FragColor = vec4(fogColor * fogStart, texture2D(colortex0, texCoord).r);
}
