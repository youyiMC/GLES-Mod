#version 330 core
// BSL 020_terrain_translucent.fsh 的真实形态（真机 548 行）。
// 关键点：uniform 是【逗号分隔的多声明符】形式，
// 而依赖它的全局初始化器**没有被剥离**，驱动报
//   'isCold' : Only consts can be used in a global initializer
//   'weatherWeight' : Only consts can be used in a global initializer
uniform float isDesert, isMesa, isCold, isSwamp, isMushroom, isSavanna, isJungle;
uniform vec4 gcolor;

float weatherWeight = clamp(isCold + isDesert + isMesa + isSwamp + isMushroom + isSavanna + isJungle, 0.0f, 1.0f);

float fogDensity = 1.0f * mix(1.0f, (1.0f * isCold + 1.0f * (isDesert + isMesa + isSavanna) + 1.0f * (isSwamp + isMushroom + isJungle)) / max(weatherWeight, 1.0E-4f), weatherWeight);

out vec4 fragColor;

void main() {
    fragColor = vec4(fogDensity, weatherWeight, gcolor.r, 1.0f);
}
