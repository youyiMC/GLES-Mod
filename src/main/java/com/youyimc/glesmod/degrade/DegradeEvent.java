package com.youyimc.glesmod.degrade;

/**
 * 一次功能降级的记录。
 *
 * <p>同一原因码的降级会聚合为一条记录，{@code count} 累加。这样即使降级发生在
 * 每帧的渲染循环里，日志也不会被淹没。
 *
 * @param reason  降级原因
 * @param count   发生次数
 * @param detail  native 侧提供的补充说明，可能为空字符串
 *
 * @since 0.1.0
 */
public record DegradeEvent(DegradeReason reason, long count, String detail) {

    public DegradeEvent {
        if (reason == null) {
            throw new IllegalArgumentException("reason 不可为 null");
        }
        if (detail == null) {
            detail = "";
        }
    }

    /** 面向玩家的单行描述。 */
    public String describe() {
        return reason.feature() + "：" + reason.fallback()
                + (detail.isEmpty() ? "" : "（" + detail + "）")
                + (count > 1 ? " [发生 " + count + " 次]" : "");
    }
}
