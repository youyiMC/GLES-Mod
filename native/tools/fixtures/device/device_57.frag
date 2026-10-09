#version 330 core
vec4 linear_fog(vec4 inColor, float vertexDistance, float fogStart, float fogEnd, vec4 fogColor) {
	if(vertexDistance <= fogStart) {
		return inColor;
	}
	float fogValue = vertexDistance < fogEnd ? smoothstep(fogStart, fogEnd, vertexDistance) : 1.0;
	return vec4(mix(inColor.rgb, fogColor.rgb, (fogValue * fogColor.a)), inColor.a);
}
float linear_fog_fade(float vertexDistance, float fogStart, float fogEnd) {
	if(vertexDistance <= fogStart) {
		return 1.0;
	} else {
		if(vertexDistance >= fogEnd) {
			return 0.0;
		}
	}
	return smoothstep(fogEnd, fogStart, vertexDistance);
}
float fog_distance(mat4 modelViewMat, vec3 pos, int shape) {
	if(shape == 0) {
		return length((modelViewMat * vec4(pos, 1.0)).xyz);
	} else {
		float distXZ = length((modelViewMat * vec4(pos.x, 0.0, pos.z, 1.0)).xyz);
		float distY = length((modelViewMat * vec4(0.0, pos.y, 0.0, 1.0)).xyz);
		return max(distXZ, distY);
	}
}
float fog_distance(vec3 pos, int shape) {
	if(shape == 0) {
		return length(pos);
	} else {
		return max(length(vec3(pos.x, 0.0, pos.z)), pos.y);
	}
}
vec4 toGamma(vec4 linear) {
	return vec4(pow(linear.rgb, vec3((1.0 / 2.2))), linear.a);
}
vec3 toGamma(vec3 linear) {
	return pow(linear, vec3((1.0 / 2.2)));
}
float toGamma(float linear) {
	return pow(linear, (1.0 / 2.2));
}
vec4 toLinear(vec4 gamma) {
	return vec4(pow(gamma.rgb, vec3(2.2)), gamma.a);
}
vec3 toLinear(vec3 gamma) {
	return pow(gamma, vec3(2.2));
}
float toLinear(float gamma) {
	return pow(gamma, 2.2);
}
vec3 linearToLogC(vec3 color) {
	return (0.386036 + ((0.244161 * log(((5.555556 * color) + 0.047996))) / log(10.0)));
}
vec4 linearToLogC(vec4 color) {
	return vec4(linearToLogC(color.rgb), color.a);
}
vec3 logCToLinear(vec3 color) {
	return ((pow(vec3(10.0), ((color - 0.386036) / 0.244161)) - 0.047996) / 5.555556);
}
vec4 logCToLinear(vec4 color) {
	return vec4(logCToLinear(color.rgb), color.a);
}
vec3 rgbToHsv(vec3 c) {
	const vec4 K = vec4(0.0, (-1.0 / 3.0), (2.0 / 3.0), -1.0);
	vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = (q.x - min(q.w, q.y));
	float e = 1.0E-10;
	return vec3(abs((q.z + ((q.w - q.y) / ((6.0 * d) + e)))), (d / (q.x + e)), q.x);
}
vec3 hsvToRgb(vec3 c) {
	const vec4 K = vec4(1.0, (2.0 / 3.0), (1.0 / 3.0), 3.0);
	vec3 p = abs(((fract((c.xxx + K.xyz)) * 6.0) - K.www));
	return (c.z * mix(K.xxx, clamp((p - K.xxx), 0.0, 1.0), c.y));
}
float luminance(vec3 c) {
	return dot(c, vec3(0.2, 0.7, 0.1));
}
vec3 acesToneMapping(vec3 color) {
	color = ((color * ((2.51 * color) + 0.03)) / ((color * ((2.43 * color) + 0.59)) + 0.14));
	return clamp(color, 0.0, 1.0);
}
vec3 reverseAces(vec3 color) {
	color = clamp(color, 0.01, 0.99);
	return (((-(sqrt((((-0.0428 * color) * color) + (0.0555 * color)))) - (0.1214 * color)) + 0.006) / (color - 1.0));
}
in float vertexDistance;
in float litFrac;
in vec2 texCoord0;
in vec4 vertexColor;
in vec4 vertexLight;
out vec4 fragColor;
uniform vec4 ColorModulator;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;
uniform sampler2D TextureSheet;
void main() {
	vec4 colA = (texture(TextureSheet, texCoord0) * vertexLight);
	vec4 colB = texture(TextureSheet, (texCoord0 + (vec2(16.0, 0) / textureSize(TextureSheet, 0))));
	vec4 col = ((mix(colB, colA, litFrac) * vertexColor) * ColorModulator);
	fragColor = linear_fog(col, vertexDistance, FogStart, FogEnd, FogColor);
}
