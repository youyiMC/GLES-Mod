package com.youyimc.glesmod.compat;

/**
 * 检测到的优化模组及其兼容状态。
 *
 * @param modId   模组 ID（{@code "sodium"} / {@code "embeddium"}）
 * @param version 实际检测到的版本
 * @param level   兼容级别
 * @param reason  判定理由，用于日志
 *
 * @since 0.1.0
 */
public record CompatTarget(String modId, String version, SupportLevel level, String reason) {

    /** 兼容级别。 */
    public enum SupportLevel {
        /** 已知版本，应用专用兼容策略。 */
        FULLY_SUPPORTED,
        /** 版本未知或未测试，应用保守策略。 */
        CONSERVATIVE,
        /** 版本过低或已确认不兼容，不联动。 */
        UNSUPPORTED
    }
}
