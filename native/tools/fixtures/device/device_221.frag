#version 460
#define FRAGMENT_SHADER
#extension GL_ARB_conservative_depth : enable
#define FLW_EMBEDDED
#define _FLW_LIGHT_SMOOTHNESS 2

#line 0 1 // flywheel:internal/uniforms/frame.glsl
struct FrustumPlanes {
    vec4 xyX; // <nx.x, px.x, ny.x, py.x>
    vec4 xyY; // <nx.y, px.y, ny.y, py.y>
    vec4 xyZ; // <nx.z, px.z, ny.z, py.z>
    vec4 xyW; // <nx.w, px.w, ny.w, py.w>
    vec2 zX; // <nz.x, pz.x>
    vec2 zY; // <nz.y, pz.y>
    vec2 zZ; // <nz.z, pz.z>
    vec2 zW; // <nz.w, pz.w>
};

struct _FlwCullData {
    float znear;
    float zfar;
    float P00;
    float P11;
    float pyramidWidth;
    float pyramidHeight;
    int pyramidLevels;
    uint useMin;
};

layout(std140) uniform _FlwFrameUniforms {
    FrustumPlanes flw_frustumPlanes;

    _FlwCullData _flw_cullData;

    mat4 flw_view;
    mat4 flw_viewInverse;
    mat4 flw_viewPrev;
    mat4 flw_projection;
    mat4 flw_projectionInverse;
    mat4 flw_projectionPrev;
    mat4 flw_viewProjection;
    mat4 flw_viewProjectionInverse;
    mat4 flw_viewProjectionPrev;

    ivec4 _flw_renderOrigin;

    vec4 _flw_cameraPos;
    vec4 _flw_cameraPosPrev;
    vec4 _flw_cameraLook;
    vec4 _flw_cameraLookPrev;
    vec2 flw_cameraRot;
    vec2 flw_cameraRotPrev;

    vec2 flw_viewportSize;
    float flw_aspectRatio;
    float flw_defaultLineWidth;
    float flw_viewDistance;

    uint flw_ticks;
    float flw_partialTick;
    float flw_renderTicks;
    float flw_renderSeconds;
    float flw_systemSeconds;
    uint flw_systemMillis;

    /** 0 means no fluid. Use FLW_CAMERA_IN_FLUID_* defines to detect fluid type. */
    uint flw_cameraInFluid;
    /** 0 means no block. Use FLW_CAMERA_IN_BLOCK_* defines to detect block type. */
    uint flw_cameraInBlock;

    uint _flw_debugMode;

    float _flw_oitNoise;
};

#define flw_renderOrigin (_flw_renderOrigin.xyz)
#define flw_cameraPos (_flw_cameraPos.xyz)
#define flw_cameraLook (_flw_cameraLook.xyz)
#define flw_cameraPosPrev (_flw_cameraPosPrev.xyz)
#define flw_cameraLookPrev (_flw_cameraLookPrev.xyz)

#define FLW_CAMERA_IN_FLUID_WATER 1
#define FLW_CAMERA_IN_FLUID_LAVA 2
#define FLW_CAMERA_IN_FLUID_UNKNOWN 0xFFFFFFFFu

#define FLW_CAMERA_IN_BLOCK_POWDER_SNOW 1
#define FLW_CAMERA_IN_BLOCK_UNKNOWN 0xFFFFFFFFu

#line 0 2 // flywheel:internal/uniforms/fog.glsl
layout(std140) uniform _FlwFogUniforms {
    vec4 flw_fogColor;
    vec2 flw_fogRange;
    int flw_fogShape;
};

#line 0 3 // flywheel:internal/uniforms/options.glsl
// options.glsl - Houses uniforms for many of the game's settings, focusing on video and accessibility settings.

layout(std140) uniform _FlwOptionsUniforms {
    float flw_brightnessOption;
    uint flw_fovOption;
    float flw_distortionOption;
    float flw_glintSpeedOption;
    float flw_glintStrengthOption;
    uint flw_biomeBlendOption;
    uint flw_smoothLightingOption;
    uint flw_viewBobbingOption;

    uint flw_highContrastOption;
    float flw_textBackgroundOpacityOption;
    uint flw_textBackgroundForChatOnlyOption;
    float flw_darknessPulsingOption;
    float flw_damageTiltOption;
    uint flw_hideLightningFlashesOption;
};

#line 0 4 // flywheel:internal/uniforms/player.glsl
// player.glsl - Holds uniforms for player state.

layout (std140) uniform _FlwPlayerUniforms {
    vec4 _flw_eyePos;

    /** Alpha is 1 if any team color is present, 0 otherwise. */
    vec4 flw_teamColor;

    /** The brightness at the player's eye position. */
    vec2 flw_eyeBrightness;

    /** Brightness of the brightest light that the player is holding, 0-1. */
    float flw_heldLight;
    /** 0 means no fluid. Use FLW_PLAYER_EYE_IN_FLUID_* defines to detect fluid type. */
    uint flw_playerEyeInFluid;
    /** 0 means no block. Use FLW_PLAYER_EYE_IN_BLOCK_* defines to detect block type. */
    uint flw_playerEyeInBlock;

    uint flw_playerCrouching;
    uint flw_playerSleeping;
    uint flw_playerSwimming;
    uint flw_playerFallFlying;

    uint flw_shiftKeyDown;

    /** 0 = survival, 1 = creative, 2 = adventure, 3 = spectator. */
    uint flw_gameMode;
};

#define flw_eyePos _flw_eyePos.xyz

#define FLW_PLAYER_EYE_IN_FLUID_WATER 1
#define FLW_PLAYER_EYE_IN_FLUID_LAVA 2
#define FLW_PLAYER_EYE_IN_FLUID_UNKNOWN 0xFFFFFFFFu

#define FLW_PLAYER_EYE_IN_BLOCK_POWDER_SNOW 1
#define FLW_PLAYER_EYE_IN_BLOCK_UNKNOWN 0xFFFFFFFFu

#line 0 5 // flywheel:internal/uniforms/level.glsl
layout(std140) uniform _FlwLevelUniforms {
    vec4 flw_skyColor;
    vec4 flw_cloudColor;

    vec4 _flw_light0Direction;
    vec4 _flw_light1Direction;

    /** The current day number of the level. */
    uint flw_levelDay;
    /** The current fraction of the current day that has elapsed. */
    float flw_timeOfDay;

    uint flw_levelHasSkyLight;

    float flw_sunAngle;

    float flw_moonBrightness;
    /** There are normally only 8 moon phases. */
    uint flw_moonPhase;

    uint flw_isRaining;
    float flw_rainLevel;
    uint flw_isThundering;
    float flw_thunderLevel;

    float flw_skyDarken;

    uint flw_constantAmbientLight;

    /** Use FLW_DIMENSION_* ids to determine the dimension. May eventually be implemented for custom dimensions. */
    uint flw_dimension;
};

#define flw_light0Direction (_flw_light0Direction.xyz)
#define flw_light1Direction (_flw_light1Direction.xyz)

#define FLW_DIMENSION_OVERWORLD 0
#define FLW_DIMENSION_NETHER 1
#define FLW_DIMENSION_END 2
#define FLW_DIMENSION_UNKNOWN 0xFFFFFFFFu

#line 0 6 // flywheel:internal/material.glsl
const uint FLW_MAT_DEPTH_TEST_OFF = 0u;
const uint FLW_MAT_DEPTH_TEST_NEVER = 1u;
const uint FLW_MAT_DEPTH_TEST_LESS = 2u;
const uint FLW_MAT_DEPTH_TEST_EQUAL = 3u;
const uint FLW_MAT_DEPTH_TEST_LEQUAL = 4u;
const uint FLW_MAT_DEPTH_TEST_GREATER = 5u;
const uint FLW_MAT_DEPTH_TEST_NOTEQUAL = 6u;
const uint FLW_MAT_DEPTH_TEST_GEQUAL = 7u;
const uint FLW_MAT_DEPTH_TEST_ALWAYS = 8u;

const uint FLW_MAT_TRANSPARENCY_OPAQUE = 0u;
const uint FLW_MAT_TRANSPARENCY_ADDITIVE = 1u;
const uint FLW_MAT_TRANSPARENCY_LIGHTNING = 2u;
const uint FLW_MAT_TRANSPARENCY_GLINT = 3u;
const uint FLW_MAT_TRANSPARENCY_CRUMBLING = 4u;
const uint FLW_MAT_TRANSPARENCY_TRANSLUCENT = 5u;

const uint FLW_MAT_WRITE_MASK_COLOR_DEPTH = 0u;
const uint FLW_MAT_WRITE_MASK_COLOR = 1u;
const uint FLW_MAT_WRITE_MASK_DEPTH = 2u;

const uint FLW_MAT_CARDINAL_LIGHTING_MODE_OFF = 0u;
const uint FLW_MAT_CARDINAL_LIGHTING_MODE_CHUNK = 1u;
const uint FLW_MAT_CARDINAL_LIGHTING_MODE_ENTITY = 2u;

struct FlwMaterial {
    bool blur;
    bool mipmap;
    bool backfaceCulling;
    bool polygonOffset;
    uint depthTest;
    uint transparency;
    uint writeMask;
    bool useOverlay;
    bool useLight;
    uint cardinalLightingMode;
    bool ambientOcclusion;
};

#line 0 7 // flywheel:internal/api_impl.glsl
struct FlwLightAo {
    vec2 light;
    float ao;
};

/// Get the light at the given world position relative to flw_renderOrigin from the given normal.
/// This may be interpolated for smooth lighting.
bool flw_light(vec3 worldPos, vec3 normal, out FlwLightAo light);

/// Fetches the light value at the given block position.
/// Returns false if the light for the given block is not available.
bool flw_lightFetch(ivec3 blockPos, out vec2 light);

#line 0 8 // flywheel:internal/uniforms/uniforms.glsl
// uniforms.glsl - Includes common uniforms.






#line 0 9 // flywheel:internal/api_impl.frag




in vec4 flw_vertexPos;
in vec4 flw_vertexColor;
in vec2 flw_vertexTexCoord;
flat in ivec2 flw_vertexOverlay;
in vec2 flw_vertexLight;
in vec3 flw_vertexNormal;

in float flw_distance;

vec4 flw_sampleColor;

FlwMaterial flw_material;

bool flw_fragDiffuse;
vec4 flw_fragColor;
ivec2 flw_fragOverlay;
vec2 flw_fragLight;

uniform sampler2D flw_diffuseTex;
uniform sampler2D flw_overlayTex;
uniform sampler2D flw_lightTex;

#line 0 10 // flywheel:material/default.frag
void flw_materialFragment() {
}

#line 0 11 // flywheel:internal/components_header.frag
uint _flw_uberFogIndex;
uint _flw_uberCutoutIndex;

#line 0 0 // (generated) flywheel:string_substitution / flywheel:fog/linear.glsl
vec4 linearFog(vec4 color, float distance, float fogStart, float fogEnd, vec4 fogColor) {
    if (distance <= fogStart) {
        return color;
    }

    float fogValue = distance < fogEnd ? smoothstep(fogStart, fogEnd, distance) : 1.0;
    return vec4(mix(color.rgb, fogColor.rgb, fogValue * fogColor.a), color.a);
}

vec4 _flw_fogFilter_0(vec4 color) {
    return linearFog(color, flw_distance, flw_fogRange.x, flw_fogRange.y, flw_fogColor);
}

#line 13 0 // (generated) flywheel:uber_shader / flywheel:fog
vec4 flw_fogFilter(vec4 color) {
    switch (_flw_uberFogIndex) {
    case 0u:
        return _flw_fogFilter_0(color);
    default:
        return color;
    }
}

#line 0 12 // flywheel:light/smooth_when_embedded.glsl
void flw_shaderLight() {
    #ifdef FLW_EMBEDDED
    FlwLightAo light;
    if (flw_light(flw_vertexPos.xyz, flw_vertexNormal, light)) {
        flw_fragLight = max(flw_fragLight, light.light);

        if (flw_material.ambientOcclusion) {
            flw_fragColor.rgb *= light.ao;
        }
    }
    #endif
}

#line 0 13 // flywheel:cutout/off.glsl
bool flw_discardPredicate(vec4 color) {
    return false;
}

#line 0 14 // flywheel:internal/packed_material.glsl
// The number of bits each property takes up
const uint _FLW_BLUR_LENGTH = 1u;
const uint _FLW_MIPMAP_LENGTH = 1u;
const uint _FLW_BACKFACE_CULLING_LENGTH = 1u;
const uint _FLW_POLYGON_OFFSET_LENGTH = 1u;
const uint _FLW_DEPTH_TEST_LENGTH = 4u;
const uint _FLW_TRANSPARENCY_LENGTH = 3u;
const uint _FLW_WRITE_MASK_LENGTH = 2u;
const uint _FLW_USE_OVERLAY_LENGTH = 1u;
const uint _FLW_USE_LIGHT_LENGTH = 1u;
const uint _FLW_CARDINAL_LIGHTING_MODE_LENGTH = 2u;
const uint _FLW_AMBIENT_OCCLUSION_LENGTH = 1u;

// The bit offset of each property
const uint _FLW_BLUR_OFFSET = 0u;
const uint _FLW_MIPMAP_OFFSET = _FLW_BLUR_OFFSET + _FLW_BLUR_LENGTH;
const uint _FLW_BACKFACE_CULLING_OFFSET = _FLW_MIPMAP_OFFSET + _FLW_MIPMAP_LENGTH;
const uint _FLW_POLYGON_OFFSET_OFFSET = _FLW_BACKFACE_CULLING_OFFSET + _FLW_BACKFACE_CULLING_LENGTH;
const uint _FLW_DEPTH_TEST_OFFSET = _FLW_POLYGON_OFFSET_OFFSET + _FLW_POLYGON_OFFSET_LENGTH;
const uint _FLW_TRANSPARENCY_OFFSET = _FLW_DEPTH_TEST_OFFSET + _FLW_DEPTH_TEST_LENGTH;
const uint _FLW_WRITE_MASK_OFFSET = _FLW_TRANSPARENCY_OFFSET + _FLW_TRANSPARENCY_LENGTH;
const uint _FLW_USE_OVERLAY_OFFSET = _FLW_WRITE_MASK_OFFSET + _FLW_WRITE_MASK_LENGTH;
const uint _FLW_USE_LIGHT_OFFSET = _FLW_USE_OVERLAY_OFFSET + _FLW_USE_OVERLAY_LENGTH;
const uint _FLW_CARDINAL_LIGHTING_MODE_OFFSET = _FLW_USE_LIGHT_OFFSET + _FLW_USE_LIGHT_LENGTH;
const uint _FLW_AMBIENT_OCCLUSION_OFFSET = _FLW_CARDINAL_LIGHTING_MODE_OFFSET + _FLW_CARDINAL_LIGHTING_MODE_LENGTH;

// The bit mask for each property
const uint _FLW_BLUR_MASK = ((1u << _FLW_BLUR_LENGTH) - 1u) << _FLW_BLUR_OFFSET;
const uint _FLW_MIPMAP_MASK = ((1u << _FLW_MIPMAP_LENGTH) - 1u) << _FLW_MIPMAP_OFFSET;
const uint _FLW_BACKFACE_CULLING_MASK = ((1u << _FLW_BACKFACE_CULLING_LENGTH) - 1u) << _FLW_BACKFACE_CULLING_OFFSET;
const uint _FLW_POLYGON_OFFSET_MASK = ((1u << _FLW_POLYGON_OFFSET_LENGTH) - 1u) << _FLW_POLYGON_OFFSET_OFFSET;
const uint _FLW_DEPTH_TEST_MASK = ((1u << _FLW_DEPTH_TEST_LENGTH) - 1u) << _FLW_DEPTH_TEST_OFFSET;
const uint _FLW_TRANSPARENCY_MASK = ((1u << _FLW_TRANSPARENCY_LENGTH) - 1u) << _FLW_TRANSPARENCY_OFFSET;
const uint _FLW_WRITE_MASK_MASK = ((1u << _FLW_WRITE_MASK_LENGTH) - 1u) << _FLW_WRITE_MASK_OFFSET;
const uint _FLW_USE_OVERLAY_MASK = ((1u << _FLW_USE_OVERLAY_LENGTH) - 1u) << _FLW_USE_OVERLAY_OFFSET;
const uint _FLW_USE_LIGHT_MASK = ((1u << _FLW_USE_LIGHT_LENGTH) - 1u) << _FLW_USE_LIGHT_OFFSET;
const uint _FLW_CARDINAL_LIGHTING_MODE_MASK = ((1u << _FLW_CARDINAL_LIGHTING_MODE_LENGTH) - 1u) << _FLW_CARDINAL_LIGHTING_MODE_OFFSET;
const uint _FLW_AMBIENT_OCCLUSION_MASK = ((1u << _FLW_AMBIENT_OCCLUSION_LENGTH) - 1u) << _FLW_AMBIENT_OCCLUSION_OFFSET;

// Packed format:
// ambientOcclusion[1] | cardinalLightingMode[2] | useLight[1] | useOverlay[1] | writeMask[2] | transparency[3] | depthTest[4] | polygonOffset[1] | backfaceCulling[1] | mipmap[1] | blur[1]
void _flw_unpackMaterialProperties(uint p, out FlwMaterial m) {
    m.blur = (p & _FLW_BLUR_MASK) != 0u;
    m.mipmap = (p & _FLW_MIPMAP_MASK) != 0u;
    m.backfaceCulling = (p & _FLW_BACKFACE_CULLING_MASK) != 0u;
    m.polygonOffset = (p & _FLW_POLYGON_OFFSET_MASK) != 0u;
    m.depthTest = (p & _FLW_DEPTH_TEST_MASK) >> _FLW_DEPTH_TEST_OFFSET;
    m.transparency = (p & _FLW_TRANSPARENCY_MASK) >> _FLW_TRANSPARENCY_OFFSET;
    m.writeMask = (p & _FLW_WRITE_MASK_MASK) >> _FLW_WRITE_MASK_OFFSET;
    m.useOverlay = (p & _FLW_USE_OVERLAY_MASK) != 0u;
    m.useLight = (p & _FLW_USE_LIGHT_MASK) != 0u;
    m.cardinalLightingMode = (p & _FLW_CARDINAL_LIGHTING_MODE_MASK) >> _FLW_CARDINAL_LIGHTING_MODE_OFFSET;
    m.ambientOcclusion = (p & _FLW_AMBIENT_OCCLUSION_MASK) != 0;
}

void _flw_unpackUint2x16(uint s, out uint hi, out uint lo) {
    hi = (s >> 16) & 0xFFFFu;
    lo = s & 0xFFFFu;
}

#line 0 15 // flywheel:internal/diffuse.glsl
float diffuse(vec3 normal) {
    vec3 n2 = normal * normal * vec3(.6, .25, .8);
    return min(n2.x + n2.y * (3. + normal.y) + n2.z, 1.);
}

float diffuseNether(vec3 normal) {
    vec3 n2 = normal * normal * vec3(.6, .9, .8);
    return min(n2.x + n2.y + n2.z, 1.);
}

float diffuseFromLightDirections(vec3 normal) {
    // We assume the directions are normalized before upload.
    float light0 = max(0.0, dot(flw_light0Direction, normal));
    float light1 = max(0.0, dot(flw_light1Direction, normal));
    return min(1.0, (light0 + light1) * 0.6 + 0.4);
}


#line 0 16 // flywheel:internal/colorizer.glsl
// https://stackoverflow.com/a/17479300
uint _flw_hash(in uint x) {
    x += (x << 10u);
    x ^= (x >> 6u);
    x += (x << 3u);
    x ^= (x >> 11u);
    x += (x << 15u);
    return x;
}

vec4 _flw_id2Color(in uint id) {
    uint x = _flw_hash(id);

    return vec4(
    float(x & 0xFFu) / 255.0,
    float((x >> 8u) & 0xFFu) / 255.0,
    float((x >> 16u) & 0xFFu) / 255.0,
    1.
    );
}

#line 0 17 // flywheel:internal/wavelet.glsl
#define TRANSPARENCY_WAVELET_RANK 3
#define TRANSPARENCY_WAVELET_COEFFICIENT_COUNT 16

// -------------------------------------------------------------------------
// WRITING
// -------------------------------------------------------------------------

void add_to_index(inout vec4[4] coefficients, int index, float addend) {
    coefficients[index >> 2][index & 3] = addend;
}

void add_absorbance(inout vec4[4] coefficients, float signal, float depth) {
    depth *= float(TRANSPARENCY_WAVELET_COEFFICIENT_COUNT-1) / TRANSPARENCY_WAVELET_COEFFICIENT_COUNT;

    int index = clamp(int(floor(depth * TRANSPARENCY_WAVELET_COEFFICIENT_COUNT)), 0, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
    index += TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1;

    for (int i = 0; i < (TRANSPARENCY_WAVELET_RANK+1); ++i) {
        int power = TRANSPARENCY_WAVELET_RANK - i;
        int new_index = (index - 1) >> 1;
        float k = float((new_index + 1) & ((1 << power) - 1));

        int wavelet_sign = ((index & 1) << 1) - 1;
        float wavelet_phase = ((index + 1) & 1) * exp2(-power);
        float addend = fma(fma(-exp2(-power), k, depth), wavelet_sign, wavelet_phase) * exp2(power * 0.5) * signal;
        add_to_index(coefficients, new_index, addend);

        index = new_index;
    }

    float addend = fma(signal, -depth, signal);
    add_to_index(coefficients, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1, addend);
}

void add_transmittance(inout vec4[4] coefficients, float transmittance, float depth) {
    float absorbance = -log(max(transmittance, 0.00001));// transforming the signal from multiplicative transmittance to additive absorbance
    add_absorbance(coefficients, absorbance, depth);
}

// -------------------------------------------------------------------------
// READING
// -------------------------------------------------------------------------

// TODO: maybe we could reduce the number of texel fetches below?
float get_coefficients(in sampler2DArray coefficients, int index) {
    return texelFetch(coefficients, ivec3(gl_FragCoord.xy, index >> 2), 0)[index & 3];
}

/// Compute the total absorbance, as if at infinite depth.
float total_absorbance(in sampler2DArray coefficients) {
    float scale_coefficient = get_coefficients(coefficients, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
    if (scale_coefficient == 0) {
        return 0;
    }

    int index_b = TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1;

    index_b += TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1;

    float b = scale_coefficient;

    for (int i = 0; i < (TRANSPARENCY_WAVELET_RANK+1); ++i) {
        int power = TRANSPARENCY_WAVELET_RANK - i;

        int new_index_b = (index_b - 1) >> 1;
        int wavelet_sign_b = ((index_b & 1) << 1) - 1;
        float coeff_b = get_coefficients(coefficients, new_index_b);
        b -= exp2(float(power) * 0.5) * coeff_b * wavelet_sign_b;
        index_b = new_index_b;
    }

    return b;
}

/// Compute the absorbance at a given normalized depth.
float absorbance(in sampler2DArray coefficients, float depth) {
    float scale_coefficient = get_coefficients(coefficients, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
    if (scale_coefficient == 0) {
        return 0;
    }

    depth *= float(TRANSPARENCY_WAVELET_COEFFICIENT_COUNT-1) / TRANSPARENCY_WAVELET_COEFFICIENT_COUNT;

    float coefficient_depth = depth * TRANSPARENCY_WAVELET_COEFFICIENT_COUNT;
    int index_b = clamp(int(floor(coefficient_depth)), 0, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
    bool sample_a = index_b >= 1;
    int index_a = sample_a ? (index_b - 1) : index_b;

    index_b += TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1;
    index_a += TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1;

    float b = scale_coefficient;
    float a = sample_a ? scale_coefficient : 0;

    for (int i = 0; i < (TRANSPARENCY_WAVELET_RANK+1); ++i) {
        int power = TRANSPARENCY_WAVELET_RANK - i;

        int new_index_b = (index_b - 1) >> 1;
        int wavelet_sign_b = ((index_b & 1) << 1) - 1;
        float coeff_b = get_coefficients(coefficients, new_index_b);
        b -= exp2(float(power) * 0.5) * coeff_b * wavelet_sign_b;
        index_b = new_index_b;

        if (sample_a) {
            int new_index_a = (index_a - 1) >> 1;
            int wavelet_sign_a = ((index_a & 1) << 1) - 1;
            float coeff_a = (new_index_a == new_index_b) ? coeff_b : get_coefficients(coefficients, new_index_a);
            a -= exp2(float(power) * 0.5) * coeff_a * wavelet_sign_a;
            index_a = new_index_a;
        }
    }

    float t = coefficient_depth >= TRANSPARENCY_WAVELET_COEFFICIENT_COUNT ? 1.0 : fract(coefficient_depth);

    return mix(a, b, t);
}

/// Compute the absorbance at a given normalized depth,
/// correcting for self-occlusion by undoing the previously recorded absorbance event.
float signal_corrected_absorbance(in sampler2DArray coefficients, float depth, float signal) {
    float scale_coefficient = get_coefficients(coefficients, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
    if (scale_coefficient == 0) {
        return 0;
    }

    depth *= float(TRANSPARENCY_WAVELET_COEFFICIENT_COUNT-1) / TRANSPARENCY_WAVELET_COEFFICIENT_COUNT;

    float scale_coefficient_addend = fma(signal, -depth, signal);
    scale_coefficient -= scale_coefficient_addend;

    float coefficient_depth = depth * TRANSPARENCY_WAVELET_COEFFICIENT_COUNT;
    int index_b = clamp(int(floor(coefficient_depth)), 0, TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1);
    bool sample_a = index_b >= 1;
    int index_a = sample_a ? (index_b - 1) : index_b;

    index_b += TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1;
    index_a += TRANSPARENCY_WAVELET_COEFFICIENT_COUNT - 1;

    float b = scale_coefficient;
    float a = sample_a ? scale_coefficient : 0;

    for (int i = 0; i < (TRANSPARENCY_WAVELET_RANK+1); ++i) {
        int power = TRANSPARENCY_WAVELET_RANK - i;

        int new_index_b = (index_b - 1) >> 1;
        int wavelet_sign_b = ((index_b & 1) << 1) - 1;
        float coeff_b = get_coefficients(coefficients, new_index_b);

        float wavelet_phase_b = ((index_b + 1) & 1) * exp2(-power);
        float k = float((new_index_b + 1) & ((1 << power) - 1));
        float addend = fma(fma(-exp2(-power), k, depth), wavelet_sign_b, wavelet_phase_b) * exp2(power * 0.5) * signal;
        coeff_b -= addend;

        b -= exp2(float(power) * 0.5) * coeff_b * wavelet_sign_b;
        index_b = new_index_b;

        if (sample_a) {
            int new_index_a = (index_a - 1) >> 1;
            int wavelet_sign_a = ((index_a & 1) << 1) - 1;
            float coeff_a = (new_index_a == new_index_b) ? coeff_b : get_coefficients(coefficients, new_index_a);// No addend here on purpose, the original signal didn't contribute to this coefficient
            a -= exp2(float(power) * 0.5) * coeff_a * wavelet_sign_a;
            index_a = new_index_a;
        }
    }

    float t = coefficient_depth >= TRANSPARENCY_WAVELET_COEFFICIENT_COUNT ? 1.0 : fract(coefficient_depth);

    return mix(a, b, t);
}

// Helpers below to deal directly in transmittance.

#define ABSORBANCE_TO_TRANSMITTANCE(a) clamp(exp(-(a)), 0., 1.)

float total_transmittance(in sampler2DArray coefficients) {
    return ABSORBANCE_TO_TRANSMITTANCE(total_absorbance(coefficients));
}

float transmittance(in sampler2DArray coefficients, float depth) {
    return ABSORBANCE_TO_TRANSMITTANCE(absorbance(coefficients, depth));
}

float signal_corrected_transmittance(in sampler2DArray coefficients, float depth, float signal) {
    return ABSORBANCE_TO_TRANSMITTANCE(signal_corrected_absorbance(coefficients, depth, signal));
}

#line 0 18 // flywheel:internal/depth.glsl
float linearize_depth(float d, float zNear, float zFar) {
    float z_n = 2.0 * d - 1.0;
    return 2.0 * zNear * zFar / (zFar + zNear - z_n * (zFar - zNear));
}

float delinearize_depth(float linearDepth, float zNear, float zFar) {
    float z_n = (2.0 * zNear * zFar / linearDepth) - (zFar + zNear);
    return 0.5 * (z_n / (zNear - zFar) + 1.0);
}

#line 0 19 // flywheel:internal/light_lut.glsl
const uint _FLW_BLOCKS_PER_SECTION = 18u * 18u * 18u;
const uint _FLW_LIGHT_SIZE_BYTES = _FLW_BLOCKS_PER_SECTION;
const uint _FLW_SOLID_SIZE_BYTES = ((_FLW_BLOCKS_PER_SECTION + 31u) / 32u) * 4u;
const uint _FLW_LIGHT_START_BYTES = _FLW_SOLID_SIZE_BYTES;
const uint _FLW_LIGHT_SECTION_SIZE_BYTES = _FLW_SOLID_SIZE_BYTES + _FLW_LIGHT_SIZE_BYTES;

const uint _FLW_SOLID_START_INTS = 0u;
const uint _FLW_LIGHT_START_INTS = _FLW_SOLID_SIZE_BYTES / 4u;
const uint _FLW_LIGHT_SECTION_SIZE_INTS = _FLW_LIGHT_SECTION_SIZE_BYTES / 4u;

const uint _FLW_COMPLETELY_SOLID = 0x7FFFFFFu;
const float _FLW_EPSILON = 1e-5;

const uint _FLW_LOWER_10_BITS = 0x3FFu;
const uint _FLW_UPPER_10_BITS = 0xFFF00000u;

const float _FLW_LIGHT_NORMALIZER = 1. / 16.;

uint _flw_indexLut(uint index);

uint _flw_indexLight(uint index);

/// Find the index for the next step in the LUT.
/// @param base The base index in the LUT, should point to the start of a coordinate span.
/// @param coord The coordinate to look for.
/// @param next Output. The index of the next step in the LUT.
/// @return true if the coordinate is not in the span.
bool _flw_nextLut(uint base, int coord, out uint next) {
    // The base coordinate.
    int start = int(_flw_indexLut(base));
    // The width of the coordinate span.
    uint size = _flw_indexLut(base + 1u);

    // Index of the coordinate in the span.
    int i = coord - start;

    if (i < 0 || i >= int(size)) {
        // We missed.
        return true;
    }

    next = _flw_indexLut(base + 2u + uint(i));

    return false;
}

bool _flw_chunkCoordToSectionIndex(ivec3 sectionPos, out uint index) {
    uint first;
    if (_flw_nextLut(0u, sectionPos.y, first) || first == 0u) {
        return true;
    }

    uint second;
    if (_flw_nextLut(first, sectionPos.x, second) || second == 0u) {
        return true;
    }

    uint sectionIndex;
    if (_flw_nextLut(second, sectionPos.z, sectionIndex) || sectionIndex == 0u) {
        return true;
    }

    // The index is written as 1-based so we can properly detect missing sections.
    index = sectionIndex - 1u;

    return false;
}

uvec2 _flw_lightAt(uint sectionOffset, uvec3 blockInSectionPos) {
    uint byteOffset = blockInSectionPos.x + blockInSectionPos.z * 18u + blockInSectionPos.y * 18u * 18u;

    uint uintOffset = byteOffset >> 2u;
    uint bitOffset = (byteOffset & 3u) << 3;

    uint raw = _flw_indexLight(sectionOffset + _FLW_LIGHT_START_INTS + uintOffset);
    uint block = (raw >> bitOffset) & 0xFu;
    uint sky = (raw >> (bitOffset + 4u)) & 0xFu;

    return uvec2(block, sky);
}

bool _flw_isSolid(uint sectionOffset, uvec3 blockInSectionPos) {
    uint bitOffset = blockInSectionPos.x + blockInSectionPos.z * 18u + blockInSectionPos.y * 18u * 18u;

    uint uintOffset = bitOffset >> 5u;
    uint bitInWordOffset = bitOffset & 31u;

    uint word = _flw_indexLight(sectionOffset + _FLW_SOLID_START_INTS + uintOffset);

    return (word & (1u << bitInWordOffset)) != 0u;
}

bool flw_lightFetch(ivec3 blockPos, out vec2 lightCoord) {
    uint lightSectionIndex;
    if (_flw_chunkCoordToSectionIndex(blockPos >> 4, lightSectionIndex)) {
        return false;
    }
    // The offset of the section in the light buffer.
    uint sectionOffset = lightSectionIndex * _FLW_LIGHT_SECTION_SIZE_INTS;

    uvec3 blockInSectionPos = uvec3((blockPos & 0xF) + 1);

    lightCoord = vec2(_flw_lightAt(sectionOffset, blockInSectionPos)) * _FLW_LIGHT_NORMALIZER;
    return true;
}


uint _flw_fetchSolid3x3x3(uint sectionOffset, ivec3 blockInSectionPos) {
    uint ret = 0u;

    // The formatter does NOT like these macros
    // @formatter:off

    #define _FLW_FETCH_SOLID(x, y, z, i) { \
        bool flag = _flw_isSolid(sectionOffset, uvec3(blockInSectionPos + ivec3(x, y, z))); \
        ret |= uint(flag) << i; \
    }

    /// fori y, z, x: unrolled
    _FLW_FETCH_SOLID(-1, -1, -1, 0)
    _FLW_FETCH_SOLID(0, -1, -1, 1)
    _FLW_FETCH_SOLID(1, -1, -1, 2)

    _FLW_FETCH_SOLID(-1, -1, 0, 3)
    _FLW_FETCH_SOLID(0, -1, 0, 4)
    _FLW_FETCH_SOLID(1, -1, 0, 5)

    _FLW_FETCH_SOLID(-1, -1, 1, 6)
    _FLW_FETCH_SOLID(0, -1, 1, 7)
    _FLW_FETCH_SOLID(1, -1, 1, 8)

    _FLW_FETCH_SOLID(-1, 0, -1, 9)
    _FLW_FETCH_SOLID(0, 0, -1, 10)
    _FLW_FETCH_SOLID(1, 0, -1, 11)

    _FLW_FETCH_SOLID(-1, 0, 0, 12)
    _FLW_FETCH_SOLID(0, 0, 0, 13)
    _FLW_FETCH_SOLID(1, 0, 0, 14)

    _FLW_FETCH_SOLID(-1, 0, 1, 15)
    _FLW_FETCH_SOLID(0, 0, 1, 16)
    _FLW_FETCH_SOLID(1, 0, 1, 17)

    _FLW_FETCH_SOLID(-1, 1, -1, 18)
    _FLW_FETCH_SOLID(0, 1, -1, 19)
    _FLW_FETCH_SOLID(1, 1, -1, 20)

    _FLW_FETCH_SOLID(-1, 1, 0, 21)
    _FLW_FETCH_SOLID(0, 1, 0, 22)
    _FLW_FETCH_SOLID(1, 1, 0, 23)

    _FLW_FETCH_SOLID(-1, 1, 1, 24)
    _FLW_FETCH_SOLID(0, 1, 1, 25)
    _FLW_FETCH_SOLID(1, 1, 1, 26)

    // @formatter:on

    return ret;
}

/// Premtively collect all light in a 3x3x3 area centered on our block.
/// Depending on the normal, we won't use all the data, but fetching on demand will have many duplicated fetches.
/// Only fetching what we'll actually use using a bitmask turned out significantly slower, but perhaps a less
/// granular approach could see wins.
///
/// The output is a 3-component vector <blockLight, skyLight, valid ? 1 : 0> packed into a single uint to save
/// memory and ALU ops later on. 10 bits are used for each component. This allows 4 such packed ints to be added
/// together with room to spare before overflowing into the next component.
uint[27] _flw_fetchLight3x3x3(uint sectionOffset, ivec3 blockInSectionPos, uint solidMask) {
    uint[27] lights;

    // @formatter:off
    #define _FLW_FETCH_LIGHT(_x, _y, _z, i) { \
        uvec2 light = _flw_lightAt(sectionOffset, uvec3(blockInSectionPos + ivec3(_x, _y, _z))); \
        lights[i] = (light.x) | ((light.y) << 10) | (uint((solidMask & (1u << i)) == 0u) << 20); \
    }

    /// fori y, z, x: unrolled
    _FLW_FETCH_LIGHT(-1, -1, -1, 0)
    _FLW_FETCH_LIGHT(0, -1, -1, 1)
    _FLW_FETCH_LIGHT(1, -1, -1, 2)

    _FLW_FETCH_LIGHT(-1, -1, 0, 3)
    _FLW_FETCH_LIGHT(0, -1, 0, 4)
    _FLW_FETCH_LIGHT(1, -1, 0, 5)

    _FLW_FETCH_LIGHT(-1, -1, 1, 6)
    _FLW_FETCH_LIGHT(0, -1, 1, 7)
    _FLW_FETCH_LIGHT(1, -1, 1, 8)

    _FLW_FETCH_LIGHT(-1, 0, -1, 9)
    _FLW_FETCH_LIGHT(0, 0, -1, 10)
    _FLW_FETCH_LIGHT(1, 0, -1, 11)

    _FLW_FETCH_LIGHT(-1, 0, 0, 12)
    _FLW_FETCH_LIGHT(0, 0, 0, 13)
    _FLW_FETCH_LIGHT(1, 0, 0, 14)

    _FLW_FETCH_LIGHT(-1, 0, 1, 15)
    _FLW_FETCH_LIGHT(0, 0, 1, 16)
    _FLW_FETCH_LIGHT(1, 0, 1, 17)

    _FLW_FETCH_LIGHT(-1, 1, -1, 18)
    _FLW_FETCH_LIGHT(0, 1, -1, 19)
    _FLW_FETCH_LIGHT(1, 1, -1, 20)

    _FLW_FETCH_LIGHT(-1, 1, 0, 21)
    _FLW_FETCH_LIGHT(0, 1, 0, 22)
    _FLW_FETCH_LIGHT(1, 1, 0, 23)

    _FLW_FETCH_LIGHT(-1, 1, 1, 24)
    _FLW_FETCH_LIGHT(0, 1, 1, 25)
    _FLW_FETCH_LIGHT(1, 1, 1, 26)

    // @formatter:on

    return lights;
}

#define _flw_index3x3x3(x, y, z) ((x) + (z) * 3u + (y) * 9u)
#define _flw_validCountToAo(validCount) (1. - (4. - (validCount)) * 0.2)

/// Calculate the light for a direction by averaging the light at the corners of the block.
///
/// To make this reusable across directions, c00..c11 choose what values relative to each corner to use.
/// e.g. (0, 0, 0) (0, 0, 1) (0, 1, 0) (0, 1, 1) would give you the light coming from -x at each corner.
/// In general, to get the light for a particular direction, you fix the x, y, or z coordinate of the c values, and permutate 0 and 1 for the other two.
/// Fixing the x coordinate to 0 gives you the light from -x, 1 gives you the light from +x.
///
/// @param lights The light data for the 3x3x3 area.
/// @param interpolant The position within the center block.
/// @param c00..c11 4 offsets to determine which "direction" we are averaging.
/// @param oppositeMask A bitmask telling this function which bit to flip to get the opposite index for a given corner
vec3 _flw_lightForDirection(uint[27] lights, vec3 interpolant, uint c00, uint c01, uint c10, uint c11, uint oppositeMask) {
    // Sum up the light and number of valid blocks in each corner for this direction
    uint[8] summed;

    // @formatter:off

    #define _FLW_SUM_CORNER(_x, _y, _z, i) { \
        const uint corner = _flw_index3x3x3(_x, _y, _z); \
        summed[i] = lights[c00 + corner] + lights[c01 + corner] + lights[c10 + corner] + lights[c11 + corner]; \
    }

    _FLW_SUM_CORNER(0u, 0u, 0u, 0)
    _FLW_SUM_CORNER(1u, 0u, 0u, 1)
    _FLW_SUM_CORNER(0u, 0u, 1u, 2)
    _FLW_SUM_CORNER(1u, 0u, 1u, 3)
    _FLW_SUM_CORNER(0u, 1u, 0u, 4)
    _FLW_SUM_CORNER(1u, 1u, 0u, 5)
    _FLW_SUM_CORNER(0u, 1u, 1u, 6)
    _FLW_SUM_CORNER(1u, 1u, 1u, 7)

    // @formatter:on

    // The final light and number of valid blocks for each corner.
    vec3[8] adjusted;

    #ifdef _FLW_INNER_FACE_CORRECTION
    // If the current corner has no valid blocks, use the opposite
    // corner's light based on which direction we're evaluating.
    // Because of how our corners are indexed, moving along one axis is the same as flipping a bit.
    #define _FLW_CORNER_INDEX(i) ((summed[i] & _FLW_UPPER_10_BITS) == 0u ? i ^ oppositeMask : i)
    #else
    #define _FLW_CORNER_INDEX(i) i
    #endif

    // Division and branching (to avoid dividing by zero) are both kinda expensive, so use this table for the valid block normalization
    const float[5] normalizers = float[](0., 1., 1. / 2., 1. / 3., 1. / 4.);

    // @formatter:off

    #define _FLW_ADJUST_CORNER(i) { \
        uint corner = summed[_FLW_CORNER_INDEX(i)]; \
        uint validCount = corner >> 20u; \
        adjusted[i].xy = vec2(corner & _FLW_LOWER_10_BITS, (corner >> 10u) & _FLW_LOWER_10_BITS) * normalizers[validCount]; \
        adjusted[i].z = float(validCount); \
    }

    _FLW_ADJUST_CORNER(0)
    _FLW_ADJUST_CORNER(1)
    _FLW_ADJUST_CORNER(2)
    _FLW_ADJUST_CORNER(3)
    _FLW_ADJUST_CORNER(4)
    _FLW_ADJUST_CORNER(5)
    _FLW_ADJUST_CORNER(6)
    _FLW_ADJUST_CORNER(7)

    // @formatter:on

    // Trilinear interpolation, including valid count
    vec3 light00 = mix(adjusted[0], adjusted[1], interpolant.x);
    vec3 light01 = mix(adjusted[2], adjusted[3], interpolant.x);
    vec3 light10 = mix(adjusted[4], adjusted[5], interpolant.x);
    vec3 light11 = mix(adjusted[6], adjusted[7], interpolant.x);

    vec3 light0 = mix(light00, light01, interpolant.z);
    vec3 light1 = mix(light10, light11, interpolant.z);

    vec3 light = mix(light0, light1, interpolant.y);

    // Normalize the light coords
    light.xy *= _FLW_LIGHT_NORMALIZER;
    // Calculate the AO multiplier from the number of valid blocks
    light.z = _flw_validCountToAo(light.z);

    return light;
}

bool flw_light(vec3 worldPos, vec3 normal, out FlwLightAo light) {
    // Always use the section of the block we are contained in to ensure accuracy.
    // We don't want to interpolate between sections, but also we might not be able
    // to rely on the existence neighboring sections, so don't do any extra rounding here.
    ivec3 blockPos = ivec3(floor(worldPos)) + flw_renderOrigin;

    uint lightSectionIndex;
    if (_flw_chunkCoordToSectionIndex(blockPos >> 4, lightSectionIndex)) {
        return false;
    }
    // The offset of the section in the light buffer.
    uint sectionOffset = lightSectionIndex * _FLW_LIGHT_SECTION_SIZE_INTS;

    // The block's position in the section adjusted into 18x18x18 space
    ivec3 blockInSectionPos = (blockPos & 0xF) + 1;

    // Directly trilerp as if sampling a texture
    #if _FLW_LIGHT_SMOOTHNESS == 1

    // The lowest corner of the 2x2x2 area we'll be trilinear interpolating.
    // The ugly bit on the end evaluates to -1 or 0 depending on which side of 0.5 we are.
    uvec3 lowestCorner = blockInSectionPos + ivec3(floor(fract(worldPos) - 0.5));

    // The distance our fragment is from the center of the lowest corner.
    vec3 interpolant = fract(worldPos - 0.5);

    // Fetch everything for trilinear interpolation
    // Hypothetically we could re-order these and do some calculations in-between fetches
    // to help with latency hiding, but the compiler should be able to do that for us.
    vec2 light000 = vec2(_flw_lightAt(sectionOffset, lowestCorner));
    vec2 light100 = vec2(_flw_lightAt(sectionOffset, lowestCorner + uvec3(1, 0, 0)));
    vec2 light001 = vec2(_flw_lightAt(sectionOffset, lowestCorner + uvec3(0, 0, 1)));
    vec2 light101 = vec2(_flw_lightAt(sectionOffset, lowestCorner + uvec3(1, 0, 1)));
    vec2 light010 = vec2(_flw_lightAt(sectionOffset, lowestCorner + uvec3(0, 1, 0)));
    vec2 light110 = vec2(_flw_lightAt(sectionOffset, lowestCorner + uvec3(1, 1, 0)));
    vec2 light011 = vec2(_flw_lightAt(sectionOffset, lowestCorner + uvec3(0, 1, 1)));
    vec2 light111 = vec2(_flw_lightAt(sectionOffset, lowestCorner + uvec3(1, 1, 1)));

    vec2 light00 = mix(light000, light001, interpolant.z);
    vec2 light01 = mix(light010, light011, interpolant.z);
    vec2 light10 = mix(light100, light101, interpolant.z);
    vec2 light11 = mix(light110, light111, interpolant.z);

    vec2 light0 = mix(light00, light01, interpolant.y);
    vec2 light1 = mix(light10, light11, interpolant.y);

    light.light = mix(light0, light1, interpolant.x) * _FLW_LIGHT_NORMALIZER;
    light.ao = 1.;

    // Lighting and AO accurate to chunk baking
    #elif _FLW_LIGHT_SMOOTHNESS == 2

    uint solid = _flw_fetchSolid3x3x3(sectionOffset, blockInSectionPos);

    if (solid == _FLW_COMPLETELY_SOLID) {
        // No point in doing any work if the entire 3x3x3 volume around us is filled.
        // Kinda rare but this may happen if our fragment is in the middle of a lot of tinted glass
        light.light = vec2(0.);
        light.ao = _flw_validCountToAo(0.);
        return true;
    }

    // Fetch everything in a 3x3x3 area centered around the block.
    uint[27] lights = _flw_fetchLight3x3x3(sectionOffset, blockInSectionPos, solid);

    vec3 interpolant = fract(worldPos);

    // Average the light in relevant directions at each corner, skipping directions that would have no influence

    vec3 lightX;
    if (normal.x > _FLW_EPSILON) {
        lightX = _flw_lightForDirection(lights, interpolant, _flw_index3x3x3(1u, 0u, 0u), _flw_index3x3x3(1u, 0u, 1u), _flw_index3x3x3(1u, 1u, 0u), _flw_index3x3x3(1u, 1u, 1u), 1u);
    } else if (normal.x < -_FLW_EPSILON) {
        lightX = _flw_lightForDirection(lights, interpolant, _flw_index3x3x3(0u, 0u, 0u), _flw_index3x3x3(0u, 0u, 1u), _flw_index3x3x3(0u, 1u, 0u), _flw_index3x3x3(0u, 1u, 1u), 1u);
    } else {
        lightX = vec3(0.);
    }

    vec3 lightZ;
    if (normal.z > _FLW_EPSILON) {
        lightZ = _flw_lightForDirection(lights, interpolant, _flw_index3x3x3(0u, 0u, 1u), _flw_index3x3x3(0u, 1u, 1u), _flw_index3x3x3(1u, 0u, 1u), _flw_index3x3x3(1u, 1u, 1u), 2u);
    } else if (normal.z < -_FLW_EPSILON) {
        lightZ = _flw_lightForDirection(lights, interpolant, _flw_index3x3x3(0u, 0u, 0u), _flw_index3x3x3(0u, 1u, 0u), _flw_index3x3x3(1u, 0u, 0u), _flw_index3x3x3(1u, 1u, 0u), 2u);
    } else {
        lightZ = vec3(0.);
    }

    vec3 lightY;
    if (normal.y > _FLW_EPSILON) {
        lightY = _flw_lightForDirection(lights, interpolant, _flw_index3x3x3(0u, 1u, 0u), _flw_index3x3x3(0u, 1u, 1u), _flw_index3x3x3(1u, 1u, 0u), _flw_index3x3x3(1u, 1u, 1u), 4u);
    } else if (normal.y < -_FLW_EPSILON) {
        lightY = _flw_lightForDirection(lights, interpolant, _flw_index3x3x3(0u, 0u, 0u), _flw_index3x3x3(0u, 0u, 1u), _flw_index3x3x3(1u, 0u, 0u), _flw_index3x3x3(1u, 0u, 1u), 4u);
    } else {
        lightY = vec3(0.);
    }

    vec3 n2 = normal * normal;
    vec3 lightAo = lightX * n2.x + lightY * n2.y + lightZ * n2.z;

    light.light = lightAo.xy;
    light.ao = lightAo.z;

    // Entirely flat lighting, the lowest setting and a fallback in case an invalid option is set
    #else

    light.light = vec2(_flw_lightAt(sectionOffset, blockInSectionPos)) * _FLW_LIGHT_NORMALIZER;
    light.ao = 1.;

    #endif

    return true;
}


#line 0 20 // flywheel:internal/common.frag






// optimize discard usage
#if defined(GL_ARB_conservative_depth) && defined(_FLW_USE_DISCARD)
layout (depth_greater) out float gl_FragDepth;
#endif

#ifdef _FLW_CRUMBLING
uniform sampler2D _flw_crumblingTex;

in vec2 _flw_crumblingTexCoord;
#endif

#ifdef _FLW_DEBUG
flat in uvec2 _flw_ids;
#endif

#ifdef _FLW_OIT

uniform sampler2D _flw_depthRange;

uniform sampler2DArray _flw_coefficients;

uniform sampler2D _flw_blueNoise;

float tented_blue_noise(float normalizedDepth) {

    float tentIn = abs(normalizedDepth * 2. - 1);
    float tentIn2 = tentIn * tentIn;
    float tentIn4 = tentIn2 * tentIn2;
    float tent = 1 - (tentIn2 * tentIn4);

    float b = texture(_flw_blueNoise, gl_FragCoord.xy / vec2(64)).r;

    return b * tent;
}

float linear_depth() {
    return linearize_depth(gl_FragCoord.z, _flw_cullData.znear, _flw_cullData.zfar);
}

#ifdef _FLW_DEPTH_RANGE

out vec2 _flw_depthRange_out;

#endif

#ifdef _FLW_COLLECT_COEFFS

out vec4 _flw_coeffs0;
out vec4 _flw_coeffs1;
out vec4 _flw_coeffs2;
out vec4 _flw_coeffs3;

#endif

#ifdef _FLW_EVALUATE

out vec4 _flw_accumulate;

#endif

#else

out vec4 _flw_outputColor;

#endif

float _flw_diffuseFactor() {
    if (flw_material.cardinalLightingMode == 2u) {
        return diffuseFromLightDirections(flw_vertexNormal);
    } else if (flw_material.cardinalLightingMode == 1u) {
        if (flw_constantAmbientLight == 1u) {
            return diffuseNether(flw_vertexNormal);
        } else {
            return diffuse(flw_vertexNormal);
        }
    } else {
        return 1.;
    }
}

void _flw_main() {
    flw_sampleColor = texture(flw_diffuseTex, flw_vertexTexCoord);
    flw_fragColor = flw_vertexColor * flw_sampleColor;
    flw_fragOverlay = flw_vertexOverlay;
    flw_fragLight = flw_vertexLight;

    flw_materialFragment();

    #ifdef _FLW_CRUMBLING
    vec4 crumblingSampleColor = texture(_flw_crumblingTex, _flw_crumblingTexCoord);

    // Make the crumbling overlay transparent when the fragment color after the material shader is transparent.
    flw_fragColor.rgb = crumblingSampleColor.rgb;
    flw_fragColor.a *= crumblingSampleColor.a;
    #endif

    flw_shaderLight();

    vec4 color = flw_fragColor;

    #ifdef _FLW_USE_DISCARD
    if (flw_discardPredicate(color)) {
        discard;
    }
    #endif

    float diffuseFactor = _flw_diffuseFactor();
    color.rgb *= diffuseFactor;

    if (flw_material.useOverlay) {
        vec4 overlayColor = texelFetch(flw_overlayTex, flw_fragOverlay, 0);
        color.rgb = mix(overlayColor.rgb, color.rgb, overlayColor.a);
    }

    vec4 lightColor = vec4(1.);
    if (flw_material.useLight) {
        lightColor = texture(flw_lightTex, clamp(flw_fragLight, 0.5 / 16.0, 15.5 / 16.0));
        color *= lightColor;
    }

    #ifdef _FLW_DEBUG
    switch (_flw_debugMode) {
        case 1u:
        color = vec4(flw_vertexNormal * .5 + .5, 1.);
        break;
        case 2u:
        color = _flw_id2Color(_flw_ids.x);
        break;
        case 3u:
        color = vec4(vec2((flw_fragLight * 15.0 + 0.5) / 16.), 0., 1.);
        break;
        case 4u:
        color = lightColor;
        break;
        case 5u:
        color = vec4(flw_fragOverlay / 16., 0., 1.);
        break;
        case 6u:
        color = vec4(vec3(diffuseFactor), 1.);
        break;
        case 7u:
        color = _flw_id2Color(_flw_ids.y);
        break;
    }
    #endif

    color = flw_fogFilter(color);

    #ifdef _FLW_OIT

    float linearDepth = linear_depth();
    #ifdef _FLW_DEPTH_RANGE

    // Pad the depth by some unbalanced epsilons because minecraft has a lot of single-quad tranparency.
    // The unbalance means our fragment will be considered closer to the screen in the normalization,
    // which helps prevent unnecessary noise as it'll be closer to the edge of our tent function.
    _flw_depthRange_out = vec2(-linearDepth + 1e-5, linearDepth + 1e-2);
    #else
    // This section is common to both other passes.

    vec2 depthRange = texelFetch(_flw_depthRange, ivec2(gl_FragCoord.xy), 0).rg;
    float delta = depthRange.x + depthRange.y;
    float our_depth = (linearDepth + depthRange.x) / delta;

    float depth_adjustment = tented_blue_noise(our_depth) * _flw_oitNoise;

    float our_transmittance = 1. - color.a;
    // Don't do the depth adjustment if this fragment is opaque.
    if (our_transmittance > 1e-5) {
        our_depth -= depth_adjustment;
    }
    #endif

    #ifdef _FLW_COLLECT_COEFFS

    vec4[4] result;
    result[0] = vec4(0.);
    result[1] = vec4(0.);
    result[2] = vec4(0.);
    result[3] = vec4(0.);

    add_transmittance(result, our_transmittance, our_depth);

    _flw_coeffs0 = result[0];
    _flw_coeffs1 = result[1];
    _flw_coeffs2 = result[2];
    _flw_coeffs3 = result[3];

    #endif

    #ifdef _FLW_EVALUATE

    float transmittance = signal_corrected_transmittance(_flw_coefficients, our_depth, our_transmittance);

    _flw_accumulate = vec4(color.rgb * color.a, color.a) * transmittance;

    #endif

    #else

    _flw_outputColor = color;

    #endif
}

#line 0 21 // flywheel:internal/instancing/light.glsl


uniform usamplerBuffer _flw_lightLut;
uniform usamplerBuffer _flw_lightSections;

uint _flw_indexLut(uint index) {
    return texelFetch(_flw_lightLut, int(index)).r;
}

uint _flw_indexLight(uint index) {
    return texelFetch(_flw_lightSections, int(index)).r;
}

#line 0 22 // flywheel:internal/instancing/main.frag



uniform uvec2 _flw_packedMaterial;

void main() {
    _flw_unpackUint2x16(_flw_packedMaterial.x, _flw_uberFogIndex, _flw_uberCutoutIndex);
    _flw_unpackMaterialProperties(_flw_packedMaterial.y, flw_material);

    _flw_main();
}
