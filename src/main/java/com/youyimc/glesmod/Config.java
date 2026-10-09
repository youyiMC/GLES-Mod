package com.youyimc.glesmod;

import net.neoforged.neoforge.common.ModConfigSpec;

/**
 * 模组配置。
 *
 * <p>字段语义与 native 侧的环境变量对应（见 docs/capability-interface.md §5）。
 * 优先级约定：<b>FCL 插件环境变量 &gt; 本配置文件 &gt; 能力自动探测 &gt; 内置默认值</b>。
 * 环境变量优先是因为它由用户在 FCL 界面显式选择，意图更明确。
 *
 * <p>功能开关语义：{@code false} = 强制禁用，{@code true} = 允许使用
 * （仍需通过原生能力探测）。这样「配置为 true 但设备不支持」不会导致崩溃。
 *
 * @since 0.1.0
 */
public final class Config {

    private static final ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();

    /** 总开关。关闭后不进行任何后端状态检查与兼容层联动。 */
    public static final ModConfigSpec.BooleanValue ENABLED = BUILDER
            .comment("是否启用 GLES Mod。",
                     "关闭后模组不做任何事，渲染完全由启动器的兼容层处理。",
                     "对应环境变量 GLESMOD_ENABLE。")
            .define("enabled", true);

    /** 降级档位。 */
    public static final ModConfigSpec.IntValue DEGRADE_LEVEL = BUILDER
            .comment("降级档位：0=保守（能降则降，最稳），1=默认，2=激进（能用则用，最快）。",
                     "对应环境变量 GLESMOD_DEGRADE_LEVEL。",
                     "注意：native 侧通过环境变量读取此值，修改配置后需重启游戏。")
            .defineInRange("degradeLevel", 1, 0, 2);

    /** 是否在启动时输出详细的能力与降级报告。 */
    public static final ModConfigSpec.BooleanValue VERBOSE_LOG = BUILDER
            .comment("是否在启动时输出详细诊断报告（能力快照、降级事件、缺失符号）。",
                     "排查渲染问题时建议开启。")
            .define("verboseLog", true);

    /** 是否在后端未激活时给出显式警告。 */
    public static final ModConfigSpec.BooleanValue WARN_IF_INACTIVE = BUILDER
            .comment("后端未激活时是否在日志中输出警告。",
                     "若你刻意不使用本模组的渲染器，可关闭此项以避免噪音。")
            .define("warnIfInactive", true);

    /** 是否启用状态文件轮询（用于获取运行期新增的降级事件）。 */
    public static final ModConfigSpec.BooleanValue POLL_STATUS = BUILDER
            .comment("是否定期重新读取 native 状态文件。",
                     "启用后可捕获运行期新增的降级事件（如进入存档后才出现的功能降级）。",
                     "关闭则只在启动时读取一次。")
            .define("pollStatusFile", true);

    static final ModConfigSpec SPEC = BUILDER.build();

    private Config() {
    }
}
