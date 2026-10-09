#version 330 core
// BSL 018_terrain_solid.vsh 的真实形态（真机地形顶点着色器）
//   int blockID = int(mc_Entity.x / 100);
// mc_Entity.x 是 float、100 是 int -> `float / int`。
// `int(...)` 在 INT_CTORS 里，且句子含整数变量 blockID（规则 C 会归零），
// 因此旧版转换器整段跳过。
// 注意：本文件是顶点着色器，扩展名必须为 .vert，否则 roundtrip 会误用 frag。
in vec2 mc_Entity;
in vec3 Position;
uniform mat4 gbufferModelView;

void main() {
    int blockID = int(mc_Entity.x / 100);
    float mat = 0.0f;
    if (blockID >= 100 && blockID < 150) mat = 1.0f;
    if (blockID == 105 || blockID == 106) mat = 2.0f;
    gl_Position = gbufferModelView * vec4(Position * mat, 1.0f);
}
