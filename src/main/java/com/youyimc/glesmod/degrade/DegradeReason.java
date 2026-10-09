package com.youyimc.glesmod.degrade;

import java.util.HashMap;
import java.util.Map;

import com.youyimc.glesmod.GLESMod;

/**
 * 降级原因码。
 *
 * <p><b>码值与 native 侧 {@code glesmod_degrade_code} 一一对应，一经发布不可更改</b>，
 * 只能废弃后新增。第三方模组可能依赖它们做判断。
 *
 * <p>新增原因时必须同步更新：
 * <ul>
 *   <li>native/include/gles_backend.h 的 {@code glesmod_degrade_code}</li>
 *   <li>本文档的映射表</li>
 *   <li>docs/capability-interface.md</li>
 * </ul>
 *
 * @since 0.1.0
 */
public enum DegradeReason {

    MULTI_DRAW_UNSUPPORTED(0x0001, "Multi-Draw 不可用", "已降级为循环绘制", true),
    COMPUTE_SHADER_UNSUPPORTED(0x0002, "计算着色器不可用", "相关功能已禁用", true),
    PERSISTENT_MAP_UNSUPPORTED(0x0003, "持久映射不可用", "已回退为 glBufferSubData", false),
    INDIRECT_DRAW_UNSUPPORTED(0x0004, "间接绘制不可用", "已降级为逐次绘制", false),
    PERSISTENT_MAP_UNSTABLE(0x0005, "持久映射不稳定", "已回退为 glBufferSubData", false),
    SHADER_CONVERSION_FAILED(0x0006, "着色器转换", "着色器已转换为 GLSL ES", false),
    SHADER_UNSUPPORTED_FEATURE(0x0007, "着色器使用了 ES 不支持的特性", "该特性已失效", true),
    TEXTURE_UNIT_LIMIT(0x0008, "纹理单元不足", "已减少同时绑定的纹理", false),
    DRIVER_BLACKLISTED(0x0009, "该设备驱动已被列入黑名单", "已回退到兼容层", true),
    BACKEND_INIT_FAILED(0x0010, "GLES 后端初始化失败", "已回退到兼容层", true),
    FALLBACK_TO_COMPAT_LAYER(0x0011, "已回退到兼容层", "渲染由 GL4ES 处理", true),
    UNSUPPORTED_FUNCTION(0x0020, "调用了 ES 不支持的 GL 函数", "该调用已被忽略", false),
    ENUM_MAPPED(0x0021, "枚举值已映射", "已转换为 ES 等价枚举", false),
    TEXTURE_FORMAT_MAPPED(0x0022, "纹理格式已映射", "已转换为 ES 等价格式", false);

    private static final Map<Integer, DegradeReason> BY_CODE = new HashMap<>();

    static {
        for (DegradeReason r : values()) {
            BY_CODE.put(r.code, r);
        }
    }

    private final int code;
    private final String feature;
    private final String fallback;
    private final boolean userVisible;

    DegradeReason(int code, String feature, String fallback, boolean userVisible) {
        this.code = code;
        this.feature = feature;
        this.fallback = fallback;
        this.userVisible = userVisible;
    }

    /** 与 native 层一致的数值码。 */
    public int code() {
        return code;
    }

    /** 被降级的功能名，面向玩家可读。 */
    public String feature() {
        return feature;
    }

    /** 实际使用的替代方案。 */
    public String fallback() {
        return fallback;
    }

    /** 是否应展示给普通玩家（技术性过强的降级只记入日志文件）。 */
    public boolean userVisible() {
        return userVisible;
    }

    /**
     * 按码值反查。
     *
     * @param code native 上报的码值
     * @return 对应枚举；未识别时返回 {@link #UNSUPPORTED_FUNCTION} 并记录一次警告
     */
    public static DegradeReason fromCode(int code) {
        DegradeReason r = BY_CODE.get(code);
        if (r != null) {
            return r;
        }
        GLESMod.LOGGER.warn("未知的降级原因码 0x{}，按 UNSUPPORTED_FUNCTION 处理",
                Integer.toHexString(code));
        return UNSUPPORTED_FUNCTION;
    }
}
