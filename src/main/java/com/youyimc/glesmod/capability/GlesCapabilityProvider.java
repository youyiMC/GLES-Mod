package com.youyimc.glesmod.capability;

/**
 * 能力查询入口。实现保证线程安全、无阻塞、不抛异常。
 *
 * <p>该接口是 {@code glesmod} 对外的稳定契约。第三方模组应通过
 * {@link GlesCapabilities#get()} 获取快照，而非自行读取状态文件。
 *
 * <p>设计约束：所有方法在 {@link GlesCapabilities#INACTIVE} 状态下返回保守值，
 * 不抛异常。渲染路径上的异常会导致崩溃，这与「任何后端故障不导致游戏崩溃」
 * 的核心原则冲突。
 *
 * @since 0.1.0
 */
public interface GlesCapabilityProvider {

    /** 是否支持 Multi-Draw。ES 上通常为 false，Sodium 会因此降级为循环绘制。 */
    boolean supportsMultiDraw();

    /** 是否支持计算着色器。需要 ES 3.1+ 且驱动实际支持，不能只看版本号。 */
    boolean supportsComputeShaders();

    /** 是否支持持久映射缓冲区（persistent mapping）。 */
    boolean supportsPersistentMapping();

    /** 是否支持实例化渲染。ES 3.0+ 恒为 true，保留此方法供降级开关使用。 */
    boolean supportsInstancing();

    /** 是否支持间接绘制（indirect draw）。需要 ES 3.1+。 */
    boolean supportsIndirectDraw();

    /** 单个材质单元数量上限。用于纹理相关的降级决策。 */
    int getMaxTextureUnits();

    /** 颜色附件数量上限。 */
    int getMaxDrawBuffers();

    /** 纹理边长上限（像素）。 */
    int getMaxTextureSize();

    /** MSAA 采样数上限。为 0 表示不支持 MSAA。 */
    int getMaxSamples();

    /**
     * 对外声称的后端版本字符串。
     *
     * <p>格式必须保持稳定：部分模组会解析该字符串判断版本。
     */
    String getGlesVersion();

    /**
     * 后端是否已成功初始化。为 {@code false} 时所有能力方法返回保守值，
     * 且渲染走原生 GLES 路径（未经本模组接管）。
     */
    boolean isBackendActive();
}
