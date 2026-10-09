package com.youyimc.glesmod.compat;

import java.util.ArrayList;
import java.util.List;

import com.youyimc.glesmod.GLESMod;
import com.youyimc.glesmod.capability.GlesCapabilities;

import net.neoforged.fml.ModList;

/**
 * 优化模组软依赖检测。
 *
 * <p>本模组<b>不修改</b> Sodium / Embeddium 的代码，也不反射调用其内部类。
 * 只读取模组列表中的公开版本信息，据此调整自身策略并输出日志。
 *
 * <p>为什么不做 Mixin 注入：Sodium 的内部实现随时可能随版本变动，
 * 注入会导致难以诊断的冲突，且升级即失效。软依赖 + 保守策略更可持续。
 *
 * <p>许可证提醒：Sodium 自 0.6 起采用 Polyform Shield 许可证，
 * <b>不得复制其代码</b>。本项目只做运行时检测。
 *
 * @since 0.1.0
 */
public final class CompatDetector {

    /** Sodium 的模组 ID。 */
    public static final String MOD_SODIUM = "sodium";

    /** Embeddium 的模组 ID（NeoForge 侧的 Sodium 分支）。 */
    public static final String MOD_EMBEDDIUM = "embeddium";

    /** 已验证可用的 Sodium 版本（NeoForge 1.21.1）。 */
    public static final String KNOWN_SODIUM_VERSION = "0.8.13";

    private CompatDetector() {
    }

    /**
     * 检测并输出兼容性报告。
     *
     * @param caps 当前能力快照
     * @return 检测到的兼容目标列表
     */
    public static List<CompatTarget> detectAndReport(GlesCapabilities caps) {
        List<CompatTarget> found = new ArrayList<>();

        ModList modList = ModList.get();
        if (modList == null) {
            // 服务端或极早期阶段调用，无模组列表
            return found;
        }

        checkOne(modList, MOD_SODIUM, caps).ifPresent(found::add);
        checkOne(modList, MOD_EMBEDDIUM, caps).ifPresent(found::add);

        if (found.isEmpty()) {
            GLESMod.LOGGER.info("未检测到优化模组（Sodium / Embeddium），使用原版渲染路径。");
        } else {
            for (CompatTarget t : found) {
                GLESMod.LOGGER.info("优化模组: {} {} -> {}（{}）",
                        t.modId(), t.version(), t.level(), t.reason());
            }
        }

        // 输出对 Sodium 有实际影响的能力结论
        if (!found.isEmpty()) {
            reportImpactOnOptimizers(caps);
        }

        return found;
    }

    private static java.util.Optional<CompatTarget> checkOne(ModList modList,
                                                             String modId,
                                                             GlesCapabilities caps) {
        return modList.getModContainerById(modId).map(container -> {
            String version = container.getModInfo().getVersion().toString();

            if (MOD_SODIUM.equals(modId)) {
                if (version.startsWith(KNOWN_SODIUM_VERSION)) {
                    return new CompatTarget(modId, version,
                            CompatTarget.SupportLevel.FULLY_SUPPORTED,
                            "已验证版本，使用专用策略");
                }
                return new CompatTarget(modId, version,
                        CompatTarget.SupportLevel.CONSERVATIVE,
                        "未经测试的版本，使用保守策略");
            }

            // Embeddium：目前没有针对 1.21.1 的验证结论
            return new CompatTarget(modId, version,
                    CompatTarget.SupportLevel.CONSERVATIVE,
                    "尚未验证，使用保守策略");
        });
    }

    /**
     * 输出 ES 能力对优化模组功能的影响。
     *
     * <p>这些结论直接来自 docs/o-02-symbol-inventory.md 的分析：
     * 原版 MC 不使用 Multi-Draw / 计算着色器 / 间接绘制，
     * 但 Sodium 会使用，因此它们是「只影响优化模组」的功能项。
     */
    private static void reportImpactOnOptimizers(GlesCapabilities caps) {
        List<String> disabled = new ArrayList<>();

        if (!caps.supportsMultiDraw()) {
            disabled.add("Multi-Draw（Sodium 区块渲染会降级为逐次绘制，性能略降）");
        }
        if (!caps.supportsComputeShaders()) {
            disabled.add("计算着色器（依赖它的优化特性将禁用）");
        }
        if (!caps.supportsIndirectDraw()) {
            disabled.add("间接绘制（部分批次合并优化失效）");
        }
        if (!caps.supportsPersistentMapping()) {
            disabled.add("持久映射缓冲（改为 glBufferSubData，CPU 开销略增）");
        }

        if (disabled.isEmpty()) {
            GLESMod.LOGGER.info("ES 能力满足优化模组的全部功能需求，无降级。");
        } else {
            GLESMod.LOGGER.info("以下功能在 ES 环境下不可用，优化模组已相应降级：");
            for (String s : disabled) {
                GLESMod.LOGGER.info("  - {}", s);
            }
        }
    }
}
