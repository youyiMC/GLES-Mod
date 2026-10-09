# 能力接口契约

> 状态：**草案待评审**（O-01 已闭环，见 §7）
> 版本：v0.3（2026-09-25）
> 对应任务：P2-01
> 关联文档：`docs/architecture.md`

本文档定义 Java 层与 native 层之间、以及本项目与外部模组之间的能力契约。**这是唯一允许跨层的接口**，任何新增能力都必须先更新本文档。

---

## 1. 设计原则

| 原则 | 说明 |
|---|---|
| **只读快照** | 能力在初始化后确定，运行时不改变。避免并发修改与「能力漂移」导致的渲染错误 |
| **不抛异常** | 能力查询永远返回有效值（未知能力返回保守值），不抛异常。渲染路径上的异常会导致崩溃 |
| **降级可见** | 每次降级都产生一个可查询的事件记录，玩家与开发者都能看到「什么功能被禁用了」 |
| **保守优先** | 无法确定能力时返回 `false`，宁可降级不用，不可假设可用 |
| **分层明确** | Java↔native 的 JNI 接口与 mod↔mod 的 Java 接口是两个不同的契约，不可混用 |

---

## 2. 接口分层

```
┌──────────────────────────────────────────────────────┐
│ 第三方模组 / Sodium 兼容层                            │
│   查询 GlesCapabilities（纯 Java，无 JNI）             │
├──────────────────────────────────────────────────────┤
│ glesmod Java 层                                       │
│   GlesCapabilityProvider（对外）                      │
│   GlesCapabilities（不可变快照，缓存）                 │
│   DegradeEventLog（降级事件）                          │
├──────────────────────────────────────────────────────┤
│ JNI 边界（仅启动时握手，三次调用）                      │
├──────────────────────────────────────────────────────┤
│ native 层                                             │
│   能力表 gles_caps_t（只读）                           │
└──────────────────────────────────────────────────────┘
```

**关键约束**：第三方模组**永远不直接调用 JNI**。它们只读 Java 层的 `GlesCapabilities` 快照。这样即使 native 层崩溃或未加载，第三方模组仍能正常工作。

---

## 3. 对外 Java 接口

### 3.1 能力提供者

```java
package com.youyimc.glesmod.capability;

/**
 * 能力查询入口。实现保证线程安全、无阻塞、不抛异常。
 *
 * <p>该接口是 {@code glesmod} 对外的唯一稳定契约。第三方模组应通过
 * {@link GlesCapabilities#get()} 获取快照，而非自行调用 JNI。
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

    /** 是否支持多个颜色附件（MRT）。 */
    boolean supportsMultipleDrawBuffers();

    /** 是否支持 glTexStorage2D / glTexStorage3D。 */
    boolean supportsTextureStorage();

    /** 是否支持各向异性过滤。 */
    boolean supportsAnisotropicFiltering();

    /** 单个材质单元数量上限。用于纹理相关的降级决策。 */
    int getMaxTextureUnits();

    /** 颜色附件数量上限。 */
    int getMaxDrawBuffers();

    /** 纹理边长上限（像素）。 */
    int getMaxTextureSize();

    /** MSAA 采样数上限。为 0 表示不支持 MSAA。 */
    int getMaxSamples();

    /**
     * 对外声称的后端版本字符串，格式 {@code "OpenGL ES 3.2 (glesmod 0.1.0)"}。
     *
     * <p><b>注意</b>：部分模组会解析该字符串判断版本。格式必须保持稳定，
     * 且应声明为与桌面 GL 兼容的版本号，避免模组误判功能缺失。
     */
    String getGlesVersion();

    /**
     * 后端是否已成功初始化。为 {@code false} 时所有能力方法返回保守值，
     * 且渲染走兼容层（GL4ES）路径。
     */
    boolean isBackendActive();

    /**
     * 能力快照的获取时间戳。用于诊断「能力在启动后才查询」的时序问题。
     */
    long getSnapshotTimestamp();
}
```

### 3.2 不可变快照

```java
package com.youyimc.glesmod.capability;

/**
 * 能力的不可变快照。启动完成后固定，可安全地在任意线程读取。
 *
 * <p>若后端未激活，{@link #get()} 返回 {@link #INACTIVE}，其所有
 * {@code supports*} 方法均为 {@code false}，容量字段为保守值。
 */
public final class GlesCapabilities implements GlesCapabilityProvider {

    /** 后端未激活时的保守快照。 */
    public static final GlesCapabilities INACTIVE = /* 全 false，保守容量 */ null;

    private static volatile GlesCapabilities instance = INACTIVE;

    /** 获取当前快照。永不返回 null。 */
    public static GlesCapabilities get() {
        return instance;
    }

    /* ... 接口实现，字段全部 final ... */

    /** 供 JNI 回调，仅在初始化时调用一次。 */
    static void publish(GlesCapabilities caps) {
        instance = caps;
    }
}
```

### 3.3 降级事件

```java
package com.youyimc.glesmod.degrade;

/**
 * 一次功能降级的记录。
 *
 * @param code       降级原因码，见 {@link DegradeReason}
 * @param feature    被降级的功能名，如 {@code "Multi-Draw"}
 * @param fallback   实际使用的替代方案，如 {@code "循环 glDrawElements"}
 * @param count      发生次数。同一原因的降级会聚合，避免日志刷屏
 * @param firstNanos 首次发生时间（相对模组初始化）
 * @param lastNanos  最近一次发生时间
 * @param userVisible 是否应展示给普通玩家（技术性过强的降级只记入日志文件）
 */
public record DegradeEvent(
        DegradeReason code,
        String feature,
        String fallback,
        long count,
        long firstNanos,
        long lastNanos,
        boolean userVisible
) {}
```

```java
package com.youyimc.glesmod.degrade;

/**
 * 降级原因码。新增原因必须同步更新 {@code docs/capability-interface.md}。
 *
 * <p>码值一经发布不可更改，只能废弃。第三方模组可能依赖它们做判断。
 */
public enum DegradeReason {
    MULTI_DRAW_UNSUPPORTED(0x0001, "Multi-Draw 不可用", true),
    COMPUTE_SHADER_UNSUPPORTED(0x0002, "计算着色器不可用", true),
    PERSISTENT_MAP_UNSUPPORTED(0x0003, "持久映射不可用", false),
    INDIRECT_DRAW_UNSUPPORTED(0x0004, "间接绘制不可用", false),
    PERSISTENT_MAP_UNSTABLE(0x0005, "持久映射不稳定，已回退", false),
    SHADER_CONVERSION_FAILED(0x0006, "着色器转换失败", true),
    SHADER_UNSUPPORTED_FEATURE(0x0007, "着色器使用了 ES 不支持的特性", true),
    TEXTURE_UNIT_LIMIT(0x0008, "纹理单元不足", false),
    DRIVER_BLACKLISTED(0x0009, "设备驱动在黑名单中", true),
    BACKEND_INIT_FAILED(0x0010, "GLES 后端初始化失败", true),
    FALLBACK_TO_COMPAT_LAYER(0x0011, "已回退到兼容层", true);

    private final int code;
    private final String description;
    private final boolean userVisible;

    DegradeReason(int code, String description, boolean userVisible) {
        this.code = code;
        this.description = description;
        this.userVisible = userVisible;
    }

    public int code() { return code; }
    public String description() { return description; }
    public boolean userVisible() { return userVisible; }

    /** 供 native 层使用的反查，未知码返回 {@code BACKEND_INIT_FAILED}。 */
    public static DegradeReason fromCode(int code) {
        for (DegradeReason r : values()) {
            if (r.code == code) return r;
        }
        return BACKEND_INIT_FAILED;
    }
}
```

### 3.4 事件日志

```java
package com.youyimc.glesmod.degrade;

/**
 * 降级事件的收集与查询。线程安全。
 *
 * <p>事件按原因码聚合。同一原因只保留一条记录，{@code count} 累加。
 * 这样即使降级发生在每帧的渲染循环里，日志也不会被淹没。
 */
public final class DegradeEventLog {

    /** 所有已发生的降级事件，按首次发生顺序排列。 */
    public static List<DegradeEvent> all() { /* ... */ }

    /** 仅返回应展示给玩家的降级事件。 */
    public static List<DegradeEvent> userVisible() { /* ... */ }

    /** 查询特定原因是否发生过。 */
    public static boolean hasOccurred(DegradeReason reason) { /* ... */ }

    /** 生成面向玩家的摘要文本，用于启动日志与配置界面。 */
    public static String summary() { /* ... */ }

    /** 生成面向开发者的详细报告，用于 issue 模板。 */
    public static String diagnosticReport() { /* ... */ }
}
```

---

## 4. JNI 契约

JNI 只在启动阶段调用**三次**，之后不再跨越边界。

| 顺序 | 函数 | 时机 | 用途 |
|---|---|---|---|
| 1 | `nativeHandshake(int modVersion)` | 模组初始化 | 版本协商，返回 native ABI 版本 |
| 2 | `nativeQueryCapabilities()` | 上述成功后 | 返回能力位与容量字段 |
| 3 | `nativeApplyConfig(int degradeLevel, int flags)` | 读取配置后 | 下发降级档位与回退开关 |

### 4.1 能力查询返回值

为避免 JNI 对象封送开销与生命周期问题，能力以**原始类型数组**传递，而非 JNI 对象：

```java
private static native int[] nativeQueryCapabilities();

/*
 * 返回数组布局（长度固定 20）：
 *   [0]  abi_version
 *   [1]  es_major
 *   [2]  es_minor
 *   [3]  gl_major          // 对外声称的版本
 *   [4]  gl_minor
 *   [5]  flag_bits          // 位掩码，见下表
 *   [6]  max_texture_units
 *   [7]  max_draw_buffers
 *   [8]  max_texture_size
 *   [9]  max_samples
 *   [10] max_vertex_attribs
 *   [11] max_uniform_components
 *   [12] flags_extended     // 扩展能力位，预留
 *   [13..19] 保留，必须为 0
 * 若后端未初始化，返回长度为 0 的数组。
 */
```

**`flag_bits` 位定义**：

| 位 | 名称 | 含义 |
|---|---|---|
| 0 | `FLAG_BACKEND_ACTIVE` | 后端已激活 |
| 1 | `FLAG_MULTI_DRAW` | 支持 Multi-Draw |
| 2 | `FLAG_COMPUTE_SHADER` | 支持计算着色器 |
| 3 | `FLAG_PERSISTENT_MAP` | 支持持久映射 |
| 4 | `FLAG_INSTANCING` | 支持实例化 |
| 5 | `FLAG_INDIRECT_DRAW` | 支持间接绘制 |
| 6 | `FLAG_MULTI_DRAW_BUFFERS` | 支持 MRT |
| 7 | `FLAG_TEXTURE_STORAGE` | 支持纹理存储 |
| 8 | `FLAG_ANISOTROPY` | 支持各向异性过滤 |
| 9 | `FLAG_DEBUG_OUTPUT` | 支持 KHR_debug |
| 10 | `FLAG_DRIVER_BLACKLISTED` | 驱动被列入黑名单 |
| 11–31 | 保留 | 必须为 0 |

### 4.2 版本协商

```java
/** native ABI 版本。Java 层与 native 层不匹配时拒绝激活后端。 */
private static final int REQUIRED_ABI_VERSION = 1;

static {
    int abi = nativeHandshake(GlesMod.ABI_VERSION);
    if (abi != REQUIRED_ABI_VERSION) {
        // 版本不匹配：记录降级事件，后端不激活，游戏走兼容层
        DegradeEventLog.record(DegradeReason.BACKEND_INIT_FAILED,
                "native ABI 版本不匹配: 期望 " + REQUIRED_ABI_VERSION + ", 实际 " + abi);
        GlesCapabilities.publish(GlesCapabilities.INACTIVE);
    }
}
```

**设计理由**：jar 与 `.so` 是分开分发的（一个在 mods 目录，一个在启动器库目录），两者版本可能不同步。**必须显式协商版本，不匹配时安全降级**，而不是尝试兼容或直接崩溃。

### 4.3 降级事件上报

native 层不回调 Java（避免在渲染线程中触发 GC 与类加载）。事件在查询时批量拉取：

```java
/**
 * 拉取自上次调用以来新增的降级事件。
 * 每次调用清空 native 侧缓冲，建议在加载界面与定期 tick 时调用。
 *
 * 返回扁平化数组，每 5 个 int 表示一个事件：
 *   [reason_code, count, first_nanos_lo, last_nanos_lo, reserved]
 */
private static native int[] nativePollDegradeEvents();
```

> 使用 `int` 而非 `long` 承载时间戳会溢出。实际实现应将时间戳拆为两个 int（高/低位），或改为相对初始化的毫秒数。**此处为草案，需在实现前确定时间表示**。

---

## 5. 配置契约

```json
{
  "gles_backend": {
    "enabled": true,
    "degrade_level": 1,
    "multi_draw": false,
    "compute_shaders": false,
    "persistent_mapping": true,
    "instancing": true,
    "indirect_draw": true,
    "max_draw_buffers": 4,
    "fallback_to_gl4es": true,
    "log_degrade_events": true,
    "device_blacklist_override": false
  }
}
```

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 总开关。关闭后完全不加载 native 后端 |
| `degrade_level` | int | `1` | `0`=保守（能降则降）`1`=默认 `2`=激进（能用则用） |
| `multi_draw` | bool | `false` | 强制开关，覆盖自动探测。**仅在确知设备支持时开启** |
| `compute_shaders` | bool | `false` | 同上 |
| `persistent_mapping` | bool | `true` | 同上。ES 3.2 理论支持但驱动质量参差 |
| `instancing` | bool | `true` | 同上 |
| `indirect_draw` | bool | `true` | 同上 |
| `max_draw_buffers` | int | `4` | 上限裁剪，用于规避某些驱动的 MRT 问题 |
| `fallback_to_gl4es` | bool | `true` | 未覆盖的 GL 调用是否回退到 GL4ES |
| `log_degrade_events` | bool | `true` | 是否输出详细降级日志 |
| `device_blacklist_override` | bool | `false` | 忽略设备黑名单（调试用，风险自负） |

**语义约定**：
- 配置中的功能开关为 **`false` = 强制禁用**，`true` = **允许使用**（仍需通过能力探测）。这样「配置为 true 但设备不支持」不会导致崩溃。
- `degrade_level` 与单项开关同时存在时，**单项开关优先**。

**优先级**（从高到低）：

```
FCL 插件环境变量 (GLESMOD_*)  >  NeoForge 配置文件  >  能力自动探测  >  内置默认值
```

> 环境变量与 mod 配置可能同时存在（插件与 mod 同时安装时）。约定环境变量为**最终覆盖值**，因为它由用户在 FCL 界面显式选择，意图更明确。此规则待确认（见 §10 C-07）。
>
> 命名映射：配置字段用 snake_case（`degrade_level`），环境变量用大写下划线（`GLESMOD_DEGRADE_LEVEL`），语义一一对应。

---

## 6. 与 FCL 渲染器插件的契约

> 本节基于已核实的 FCL 源码（O-01 闭环）。

### 6.1 插件配置契约

FCL 通过插件 APK 内 `@string/config` 资源的 JSON 读取渲染器定义（`RendererConfigV2`）：

| 字段 | 本项目取值 | 说明 |
|---|---|---|
| `displayName` | `"GLES Mod"` | FCL 设置项中显示的名称 |
| `rendererId` | `"glesmod"` | 唯一标识 |
| `rendererGLPath` | `"libgl_gles.so"` | 本项目提供的 GL 库 |
| `rendererEGLPath` | `"libEGL.so"` | 复用系统 EGL。**本项目不接管 EGL** |
| `dlopenLibPaths` | `["libgl_gles_core.so"]` | 核心库与入口库分离时使用 |
| `env` | 见 §7.2 | 可配置环境变量 |
| `minMCVer` / `maxMCVer` | `"1.21.1"` | 版本约束 |

### 6.2 环境变量契约

FCL 支持 4 种环境变量类型，本项目的用法如下：

| FCL 类型 | 用途 | 本项目示例 |
|---|---|---|
| `NormalEnv` | 固定值，用户不可改 | `LIBGL_ES=3`（**必需**，见下）、`GLESMOD_ABI=1` |
| `SelectableEnv` | 预设选项中选择 | `GLESMOD_DEGRADE_LEVEL`（0/1/2） |
| `ToggleableEnv` | 开关 | `GLESMOD_STATE_CACHE`、`GLESMOD_LOG_DEGRADE` |
| `CustomizableEnv` | 用户自由输入 | `GLESMOD_BLACKLIST_OVERRIDE`（调试用） |

**⚠️ `LIBGL_ES=3` 是必需项（O-09）**

FCL 对内置渲染器会自动设置 `LIBGL_ES`（GL4ES 设 `2`、NG-GL4ES 设 `3`），但**对插件渲染器不设置**——`FCLauncher.addRendererEnvInner()` 在插件分支直接 `return`。而 `gl_bridge.c` 依赖它决定 EGL 上下文版本：

```c
int libgl_es = strtol(getenv("LIBGL_ES"), NULL, 0);
if (libgl_es < 0 || libgl_es > INT16_MAX) libgl_es = 2;  /* 默认回退到 ES 2 */
const EGLint egl_context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, libgl_es, EGL_NONE};
```

若遗漏，上下文版本会回退到 ES 2，与 ES 3.2 目标不符。必须作为 `NormalEnv` 声明（用户不可改）。

**其他设计约束**：

1. **环境变量是配置的第二入口。** 同一项配置在 FCL 插件与 NeoForge mod 中可能有不同名称。必须以环境变量为**最终覆盖值**，且两边语义保持一致（`false` = 强制禁用，`true` = 允许使用）。
2. **环境变量在 `dlopen` 前设置**，因此 native 层在 `JNI_OnLoad` / 首次初始化时就能读取，无需等待 Java 层下发。
3. **不引入只有插件路径才支持的能力**，避免两条路径行为不一致。
4. **不用 `LIBGL_ES` 之外的 FCL 保留变量名**，避免与启动器内部逻辑冲突。

### 6.3 边界声明

| 边界 | 本项目做法 |
|---|---|
| EGL / 上下文创建 | **不接管**。复用系统 `libEGL.so`，符合任务书非目标 |
| 窗口 / Surface | 不创建、不修改 |
| 环境变量命名空间 | 统一前缀 `GLESMOD_`，避免与启动器及其他插件冲突（`LIBGL_ES` 是 FCL 保留变量，必须设置但不得占用其他保留名） |
| GL 符号集 | **必须导出完整**。FCL 会 `dlopen` 我们的库并对其做 `dlsym`（见 `architecture.md` §2.5） |

> ✅ **O-08 已闭环（2026-09-25）**：已核实 FCL 源码，其 EGL 为系统 `libEGL.so`（厂商 EGL，直接对接 GLES 驱动），**非 ANGLE，无双重翻译风险**。链路为：`我们的 libgl_gles.so（GL→ES 映射）→ 系统 libEGL.so + 厂商 GLES 驱动（原生执行）`。

---

## 7. 与 Sodium / Embeddium 的契约
本项目**不修改** Sodium 代码，只通过公开可观测的运行时信息做软依赖联动。

```java
package com.youyimc.glesmod.compat;

/**
 * 检测到的优化模组及其兼容状态。
 */
public record CompatTarget(
        String modId,            // "sodium" / "embeddium"
        String version,          // 实际检测到的版本
        SupportLevel level,      // 兼容级别
        String reason            // 判定理由，用于日志
) {
    public enum SupportLevel {
        /** 已知版本，应用专用兼容策略 */
        FULLY_SUPPORTED,
        /** 版本未知或未测试，应用保守策略 */
        CONSERVATIVE,
        /** 版本过低或已确认不兼容，不联动 */
        UNSUPPORTED
    }
}
```

**不做的事**（明确列出以避免越界）：

| 不做 | 原因 |
|---|---|
| 不反射调用 Sodium 的内部类 | 内部实现随时可能变动，会因版本更新崩溃 |
| 不使用 Mixin 注入 Sodium 内部方法 | 同上，且会造成难以诊断的冲突 |
| 不复制 Sodium 源码 | 许可证（Polyform Shield）不允许 |
| 不在缺失 Sodium 时改变行为 | 软依赖，缺失即走原版路径 |

**兼容矩阵**（待补充，对应 P2-07）：

| Sodium 版本 | MC 版本 | 兼容级别 | 已知问题 |
|---|---|---|---|
| 0.8.13-neoforge | 1.21.1 | 待测试 | — |
| 其他 0.8.x | 1.21.1 | `CONSERVATIVE` | 未测试，保守策略 |
| < 0.8 | — | `UNSUPPORTED` | 内部结构差异大 |

---

## 8. 错误码与诊断

| 场景 | 行为 | 玩家可见 |
|---|---|---|
| native 库未找到 | 记录 `BACKEND_INIT_FAILED`，走兼容层，游戏正常启动 | 否（仅日志） |
| ABI 版本不匹配 | 同上 | 否 |
| 能力查询返回空数组 | 使用 `GlesCapabilities.INACTIVE`，全部降级 | 否 |
| 设备在黑名单 | 记录 `DRIVER_BLACKLISTED`，走兼容层 | 是（一次性提示） |
| 着色器转换失败 | 记录 `SHADER_CONVERSION_FAILED`，该着色器交回模组处理 | 是（一次性提示） |
| 渲染输出异常 | **不做自动检测**（无法可靠判断），由用户反馈 | — |

**核心原则：任何后端故障都不应导致游戏崩溃。** 最坏情况是回退到兼容层并告知用户。

---

## 9. 版本演进规则

| 变更类型 | ABI 版本 | 兼容性 |
|---|---|---|
| 新增能力位（使用保留位） | 不变 | 向后兼容，旧 Java 层忽略新位 |
| 修改 `flag_bits` 已用位含义 | +1 | 不兼容，需同步发布 |
| 修改 `nativeQueryCapabilities` 数组布局 | +1 | 不兼容 |
| 新增 `DegradeReason` 枚举值 | 不变 | 向后兼容 |
| 修改已有 `DegradeReason` 码值 | **不允许** | 废弃旧值，新增新值 |
| 新增配置字段 | 不变 | 向后兼容，缺省即默认值 |
| 新增环境变量 | 不变 | 向后兼容，未设置则用默认值 |
| 修改已有环境变量的语义 | **不允许** | 新增变量替代旧变量，旧变量废弃 |

---

## 10. 待确认事项

| 编号 | 事项 | 影响 |
|---|---|---|
| C-01 | 时间戳在 JNI 中的表示方式（int 溢出问题，见 §4.3） | P1-03 |
| C-02 | 配置字段是否需兼容任务书 v1 的 `gles_compat` 命名 | P2-01 |
| C-03 | `getGlesVersion()` 对外的版本字符串格式是否需与实际驱动一致 | P2-03 |
| C-04 | 是否需要为第三方模组提供**主动注册**能力需求的反向接口（目前设计为只读查询） | 阶段三 |
| C-05 | Embeddium 在 1.21.1 上的可用版本与兼容策略 | P2-05 |
| ~~C-06~~ | ~~`rendererEGLPath` 是否允许留空~~ | ✅ 已定：填 `libEGL.so`，不接管 EGL |
| C-07 | 环境变量与 mod 配置的优先级规则（当前设计为环境变量优先） | P1-05, P2-01 |
