package com.youyimc.glesmod.capability;

/**
 * 后端能力快照。
 *
 * <p>启动完成后固定，可安全地在任意线程读取。
 *
 * <p><b>数据来源</b>：native 后端在首次 GL 调用时探测能力，写入
 * {@code glesmod/status.json}。本类由 {@link GlesBackendStatus} 解析该文件后构造。
 * 之所以走文件而非 JNI，是因为 native 库由启动器（FCL）加载，与 mod 的 JVM
 * 类加载路径不同，直接回调 Java 会引入类加载与线程复杂性。
 *
 * @since 0.1.0
 */
public final class GlesCapabilities {

    /** 后端未激活时的保守快照：所有支持位为 false，容量取最小值。 */
    public static final GlesCapabilities INACTIVE = new GlesCapabilities(
            false, 0, 0, 0, 0, 0,
            false, false, false, false, false,
            8, 1, 2048, 0, 16);

    private static volatile GlesCapabilities instance = INACTIVE;

    private final boolean active;
    private final int glesMajor;
    private final int glesMinor;
    private final int reportedGlMajor;
    private final int reportedGlMinor;
    private final int degradeLevel;

    private final boolean multiDraw;
    private final boolean computeShader;
    private final boolean persistentMapping;
    private final boolean instancing;
    private final boolean indirectDraw;

    private final int maxTextureUnits;
    private final int maxDrawBuffers;
    private final int maxTextureSize;
    private final int maxSamples;
    private final int maxVertexAttribs;

    public GlesCapabilities(boolean active,
                            int glesMajor, int glesMinor,
                            int reportedGlMajor, int reportedGlMinor,
                            int degradeLevel,
                            boolean multiDraw, boolean computeShader,
                            boolean persistentMapping, boolean instancing,
                            boolean indirectDraw,
                            int maxTextureUnits, int maxDrawBuffers,
                            int maxTextureSize, int maxSamples,
                            int maxVertexAttribs) {
        this.active = active;
        this.glesMajor = glesMajor;
        this.glesMinor = glesMinor;
        this.reportedGlMajor = reportedGlMajor;
        this.reportedGlMinor = reportedGlMinor;
        this.degradeLevel = degradeLevel;
        this.multiDraw = multiDraw;
        this.computeShader = computeShader;
        this.persistentMapping = persistentMapping;
        this.instancing = instancing;
        this.indirectDraw = indirectDraw;
        this.maxTextureUnits = maxTextureUnits;
        this.maxDrawBuffers = maxDrawBuffers;
        this.maxTextureSize = maxTextureSize;
        this.maxSamples = maxSamples;
        this.maxVertexAttribs = maxVertexAttribs;
    }

    /** 获取当前快照。永不返回 null。 */
    public static GlesCapabilities get() {
        return instance;
    }

    /** 供状态加载器在解析完成后发布。 */
    public static void publish(GlesCapabilities caps) {
        instance = (caps == null) ? INACTIVE : caps;
    }

    /** 后端是否已成功初始化。为 false 时所有能力返回保守值，渲染走原生 GLES。 */
    public boolean isBackendActive() {
        return active;
    }

    /** 实际 GLES 版本主版本号，如 3。 */
    public int getGlesMajor() {
        return glesMajor;
    }

    /** 实际 GLES 版本次版本号，如 2。 */
    public int getGlesMinor() {
        return glesMinor;
    }

    /**
     * 对外声称的版本字符串。
     *
     * <p>格式必须保持稳定：部分模组会解析它判断功能可用性。此处的值声明为
     * 桌面 GL 版本（而非 ES 版本），因为 MC 与多数模组按桌面 GL 语义判断。
     */
    public String getGlesVersion() {
        return String.format("OpenGL ES %d.%d (reported as GL %d.%d)",
                glesMajor, glesMinor, reportedGlMajor, reportedGlMinor);
    }

    /** 降级档位：0=保守 1=默认 2=激进。 */
    public int getDegradeLevel() {
        return degradeLevel;
    }

    /** 是否支持 Multi-Draw。ES 上通常为 false，Sodium 会因此降级为循环绘制。 */
    public boolean supportsMultiDraw() {
        return multiDraw;
    }

    /** 是否支持计算着色器。需要 ES 3.1+ 且驱动实际支持。 */
    public boolean supportsComputeShaders() {
        return computeShader;
    }

    /** 是否支持持久映射缓冲区。 */
    public boolean supportsPersistentMapping() {
        return persistentMapping;
    }

    /** 是否支持实例化渲染。 */
    public boolean supportsInstancing() {
        return instancing;
    }

    /** 是否支持间接绘制。 */
    public boolean supportsIndirectDraw() {
        return indirectDraw;
    }

    public int getMaxTextureUnits() {
        return maxTextureUnits;
    }

    public int getMaxDrawBuffers() {
        return maxDrawBuffers;
    }

    public int getMaxTextureSize() {
        return maxTextureSize;
    }

    public int getMaxSamples() {
        return maxSamples;
    }

    public int getMaxVertexAttribs() {
        return maxVertexAttribs;
    }

    @Override
    public String toString() {
        return "GlesCapabilities{"
                + "active=" + active
                + ", gles=" + glesMajor + "." + glesMinor
                + ", reportedGl=" + reportedGlMajor + "." + reportedGlMinor
                + ", degradeLevel=" + degradeLevel
                + ", multiDraw=" + multiDraw
                + ", computeShader=" + computeShader
                + ", persistentMapping=" + persistentMapping
                + ", instancing=" + instancing
                + ", indirectDraw=" + indirectDraw
                + ", maxTextureUnits=" + maxTextureUnits
                + ", maxDrawBuffers=" + maxDrawBuffers
                + ", maxTextureSize=" + maxTextureSize
                + ", maxSamples=" + maxSamples
                + ", maxVertexAttribs=" + maxVertexAttribs
                + '}';
    }
}
