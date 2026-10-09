#version 330 core

// Verbatim from Engine-Room/Flywheel: assets/flywheel/flywheel/internal/diffuse.glsl
float diffuse(vec3 normal) {
    vec3 n2 = normal * normal * vec3(.6, .25, .8);
    return min(n2.x + n2.y * (3. + normal.y) + n2.z, 1.);
}

float diffuseNether(vec3 normal) {
    vec3 n2 = normal * normal * vec3(.6, .9, .8);
    return min(n2.x + n2.y + n2.z, 1.);
}

in vec3 v_Normal;

out vec4 fragColor;

void main() {
    fragColor = vec4(vec3(diffuse(v_Normal) + diffuseNether(v_Normal)), 1.0);
}
