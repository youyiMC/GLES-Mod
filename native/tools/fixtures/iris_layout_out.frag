#version 120

// Clean, minimal reproduction of the deferred1.fsh failure reported by the
// device under Iris 1.8.14-beta.1 + BSL_v10.1.8 on Adreno 750:
//
//   Shader compilation log for deferred1.fsh:
//     ERROR: 0:20: 'location' : not a legal layout qualifier id
//     ERROR: 0:20: ';' : Syntax error:  syntax error
//
// BSL v10 declares its fragment outputs in the legacy form; Iris's
// CompatibilityTransformer / LayoutTransformer rewrites them into explicit
// form, allocating sequential locations. The line our converter must survive
// is therefore:
//
//     layout (location = 0) out vec4 outColor0;
//
// The '=' inside a layout qualifier is NOT an initializer. The globals
// rewriter searched for the first '=' in the statement, mistook it for an
// initializer and rewrote the declaration as `layout (location;`, which is
// exactly 'location' : not a legal layout qualifier id.
//
// Deliberately comment-light so the reproduction is unambiguous.

uniform vec3 sunPosition;
uniform int worldTime;
uniform sampler2D colortex0;

varying vec2 texCoord;

vec3 sunVec = normalize(sunPosition);
float timeAngle = worldTime / 24000.0;

layout (location = 0) out vec4 outColor0;
layout (location = 1) out vec4 outColor1;

void main() {
    outColor0 = vec4(timeAngle, sunVec.x, texCoord.x, 1.0);
    outColor1 = vec4(texture2D(colortex0, texCoord).r);
}
