# P2-05：Embeddium 软依赖适配评估

> 状态：✅ **评估完成 —— 已真机验证通过（1 设备 / 1 轮）**
> 日期：2026-09-29
> 对应任务：P2-05
> 关联文档：`docs/p2-04-degrade-routing.md`（降级路由）、`docs/o-02-symbol-inventory.md`（符号清单）
> **本文档所有 Embeddium 结论均来自其 21.1 分支源码一手材料（见 §6 附录 A 的逐条出处），未做推测。**

> ### 修订记录
>
> | 版本 | 日期 | 变更 |
> |---|---|---|
> | v1 | 2026-09-29 | 初版：完成代码审查，发现 §4 的高危项 |
> | v2 | 2026-09-29 | §4 的高危项已修复并构建验证（`glBufferStorage` 从静默 stub 改为定制实现） |
> | v3 | 2026-09-29 | **新增 §9：真机验证结果** —— 旧构建实跑 Embeddium 无问题，并查明高危项**为何未触发** |

---

## 1. 结论摘要

| 问题 | 结论 |
|---|---|
| Embeddium 是否有 MC 1.21.1 的 NeoForge 版本？ | ✅ **有**，`1.0.15+mc1.21.1` |
| 是否与我们的 NeoForge 版本兼容？ | ✅ 无需 Embeddium 侧改动（它要求 NeoForge ≥ 21.1.61，我们跑 21.1.241） |
| 许可证是否允许我们做软依赖检测？ | ✅ **LGPL-3.0-only**，比 Sodium 的 Polyform Shield **更宽松** |
| 是否应列为主开发目标？ | ❌ **否**，仍以 Sodium 0.8.13-neoforge 为主目标（理由见 §3） |
| 是否已真机验证？ | ✅ **是** —— 2026-09-29，无渲染错误，帧率与 Sodium 相当（详见 §9） |
| 是否存在真实崩溃风险？ | ⚠️ **风险真实存在，但实测未触发** —— 见 §4（机制）与 §9.3（为何未触发） |

**一句话**：Embeddium 在 1.21.1 上是**存在且可用**的。**真机实测通过**（无渲染错误，帧率与 Sodium 相当）。
它的"高级暂存缓冲"路径会申请桌面 GL 专有特性、且**没有任何 ES 回退判断** —— 这是一个**真实的机制缺陷**，
但**实测未触发**，因为 LWJGL 在我们的 ES 后镜下不会上报 `OpenGL44` / `GL_ARB_buffer_storage`（见 §9.3）。
我们**仍主动修复了**这条路径（即使暂不可达），因为它的失败模式是崩溃（见 §5.1）。

---

## 2. Embeddium 事实核查（一手材料）

### 2.1 版本与平台

| 项 | 值 | 来源 |
|---|---|---|
| 模组 ID | `embeddium` | Modrinth API |
| 最新 1.21.1 版本 | **1.0.15+mc1.21.1** | Modrinth API（2025-01-24 发布，738,705 次下载） |
| `environment` | `client_only` | Modrinth API |
| 支持 loader | `fabric`, `forge`, `neoforge` | Modrinth API |
| 仓库分支 | `21.1/neoforge`（另有 21.0/21.2/21.4 等） | GitHub API |
| `minecraft_version` | `1.21.1` | 分支 `gradle.properties` |
| `mod_version` | `1.0.15` | 分支 `gradle.properties` |
| `forge_version` | `21.1.61` | 分支 `gradle.properties` |
| 许可证 | **LGPL-3.0-only** | Modrinth API + 项目自述 |

> **注意**：Modrinth 页面上的 `source_url` / `issues_url` 指向 `FiniteReality/embeddium`，而 GitHub 分支列表中也出现 `FiniteReality/embeddium` 作为 `commit.url` 的前缀。
> 这是**上游仓库迁移**后的结果。代码身份以 `FiniteReality/embeddium` 为准。

### 2.2 与 Sodium 的谱系关系

Embeddium **不是** Sodium 的包装，而是**从 Sodium 代码库分叉**而来：

> "Embeddium is ... based on the **last FOSS-licensed version of the Sodium codebase**, and includes additional bugfixes & features for better mod compatibility."
> "All performance improvements from **Sodium 0.5.8 and earlier**"
> —— Embeddium 项目自述

这解释了一个关键差异：

| | Sodium 0.8.13 | Embeddium 1.0.15 |
|---|---|---|
| 谱系 | 现代（0.8.x） | 基于 **Sodium 0.5.8 及更早** |
| 许可证 | Polyform Shield（**非 FOSS**） | LGPL-3.0-only（**FOSS**） |
| 目标 MC | 1.21.1（原生） | 1.21.1（向后移植） |

**结论**：Embeddium 在 1.21.1 上是"**老核心 + 新版本适配**"的组合，而非与 Sodium 0.8.13 对等的现代实现。

---

## 3. 为什么仍以 Sodium 为主目标

| 理由 | 说明 |
|---|---|
| **谱系更现代** | Sodium 0.8.13 是当代实现；Embeddium 继承的是 0.5.8 时代的内核 |
| **已有真机验证** | Sodium 0.8.13 已通过完整真机测试（`FULLY_SUPPORTED`，零降级，零渲染错误） |
| **任务书基线** | `开发任务书.txt` v2 已锁定 `0.8.13-neoforge（1.21.1）` |
| **官方 NeoForge 侧支持** | Sodium 0.8.13 直接产出 neoforge 变体（`mc1.21.1-0.8.13-neoforge`） |
| **Embeddium 定位是"兼容性优先"** | 它的卖点是 FRAPI 集成与 mod 兼容性，不是极限性能 |

**Embeddium 的正确定位：备选方案 / 兼容性对照项**，而非并列主目标。

---

## 4. ★ 核心发现：Embeddium 的暂存缓冲路径会撞上我们的 stub ★

这是本次评估最重要的产出。以下是**完整的一手代码证据链**。

### 4.1 Embeddium 侧：一条会主动申请桌面 GL 专有特性的路径

**第 1 步 —— 暂存缓冲的创建有一个"高级/回退"二选一：**

```java
// RenderRegionManager.java
private static StagingBuffer createStagingBuffer(CommandList commandList) {
    if (Embeddium.options().advanced.useAdvancedStagingBuffers
            && MappedStagingBuffer.isSupported(RenderDevice.INSTANCE)) {
        return new MappedStagingBuffer(commandList);
    }
    return new FallbackStagingBuffer(commandList);
}
```

**第 2 步 —— `isSupported` 只问"缓冲存储功能是否可用"：**

```java
// MappedStagingBuffer.java
public static boolean isSupported(RenderDevice instance) {
    return instance.getDeviceFunctions().getBufferStorageFunctions() != BufferStorageFunctions.NONE;
}
```

**第 3 步 —— `pickBest` 的判定条件：只认桌面 GL 4.4 或 `ARB_buffer_storage`。**

```java
// BufferStorageFunctions.java
public static BufferStorageFunctions pickBest(RenderDevice device) {
    GLCapabilities capabilities = device.getCapabilities();

    if (capabilities.OpenGL44) {
        return CORE;
    } else if (capabilities.GL_ARB_buffer_storage) {
        return ARB;
    } else {
        return NONE;                    // ← ES 上期望走这里
    }
}
```

**第 4 步 —— 高级路径要求"持久映射 + 客户端存储"：**

```java
// MappedStagingBuffer.java
private static final EnumBitField<GlBufferStorageFlags> STORAGE_FLAGS =
        EnumBitField.of(GlBufferStorageFlags.PERSISTENT,
                        GlBufferStorageFlags.CLIENT_STORAGE,   // ← 桌面 GL 专有
                        GlBufferStorageFlags.MAP_WRITE);

private static final EnumBitField<GlBufferMapFlags> MAP_FLAGS =
        EnumBitField.of(GlBufferMapFlags.PERSISTENT,
                        GlBufferMapFlags.INVALIDATE_BUFFER,
                        GlBufferMapFlags.WRITE,
                        GlBufferMapFlags.EXPLICIT_FLUSH);

public MappedStagingBuffer(CommandList commandList, int capacity) {
    GlImmutableBuffer buffer = commandList.createImmutableBuffer(capacity, STORAGE_FLAGS);
    GlBufferMapping map = commandList.mapBuffer(buffer, 0, capacity, MAP_FLAGS);
    ...
}
```

**第 5 步 —— 若映射失败，直接抛异常（不降级）：**

```java
// GLRenderDevice.java
ByteBuffer buf = GL32C.glMapBufferRange(
        GlBufferTarget.ARRAY_BUFFER.getTargetParameter(), offset, length,
        flags.getBitField());

if (buf == null) {
    throw new RuntimeException("Failed to map buffer");   // ← 硬失败
}
```

### 4.2 我们的侧：`glBufferStorage` 是一个**静默 stub**

`native/symbols.def` 第 425 行：

```
S void glBufferStorage(GLenum p0, GLsizeiptr p1, const void * p2, GLbitfield p3)
```

`S` = 安全 stub。它的实际行为（`native/src/generated_forwarders.c`）：

```c
GLESMOD_EXPORT void glBufferStorage(GLuint p0, ...)
{
    GLESMOD_TRACE("glBufferStorage");
    glesmod_report_stub("glBufferStorage");   /* 记录 + 返回零值 */
}
```

**即：不分配任何存储，直接返回。** GLES 3.2 核心确实**没有** `glBufferStorage`（它是 GL 4.4 / `ARB_buffer_storage` 的功能），所以 stub 本身在能力上是对的。

### 4.3 两条链合起来会发生什么

```
Embeddium 判定 isSupported() == true
        ↓
new MappedStagingBuffer()
        ↓
createImmutableBuffer(16MB, {PERSISTENT, CLIENT_STORAGE, MAP_WRITE})
        ↓
glBufferStorage(...) ──► 我们的 stub：什么都不做，缓冲区【没有任何存储】
        ↓
mapBuffer(buffer, 0, 16MB, {PERSISTENT, INVALIDATE, WRITE, EXPLICIT_FLUSH})
        ↓
glMapBufferRange(...) ──► 缓冲区无存储 → GL_INVALID_OPERATION → 返回 NULL
        ↓
throw new RuntimeException("Failed to map buffer")
        ↓
★ 游戏崩溃（区块渲染初始化阶段）★
```

**要害在于**：`getBufferStorageFunctions()` 在 ES 上**本该**返回 `NONE`（走 `FallbackStagingBuffer`，安全），
但这个返回值取决于 **LWJGL 的 `GLCapabilities.OpenGL44` 与 `GL_ARB_buffer_storage` 两个标志**。
若 LWJGL 因为某种原因把它们置为 `true`，Embeddium 就会走进上面这条崩溃链 —— 而我们**当前无法优雅承接**，因为 `glBufferStorage` 是静默 stub，不是有效实现。

### 4.4 这个风险的真实边界（必须诚实说明）

**我没有实测过 Embeddium 在真机上的行为。** 因此必须明确区分：

| 陈述 | 确信度 |
|---|---|
| Embeddium 的 `pickBest` 只认 `OpenGL44` / `GL_ARB_buffer_storage` | ✅ **确定**（源码原文） |
| 高级路径用 `PERSISTENT` + `CLIENT_STORAGE`，映射失败抛异常 | ✅ **确定**（源码原文） |
| 我们的 `glBufferStorage` 是静默 stub，不分配存储 | ✅ **确定**（`symbols.def` 原文） |
| **LWJGL 在我们的 ES 后端下是否会上报 `OpenGL44=true`** | ❓ **未知，需实测** |

**关键未知项**：`native/src/core.c` 中我们对外声称的桌面 GL 版本是 **3.2**：

```c
g_caps.gl_major = 3;
g_caps.gl_minor = 2;
```

但这个 `g_caps` 是**写进 `status.json` 给 Java 模组看的**，**不改变 `glGetString(GL_VERSION)` 的返回值** ——
后者是**直接转发**（`F` 类型），返回的仍是驱动原话 `"OpenGL ES 3.2 ..."`。

因此 LWJGL 解析的是 `"OpenGL ES 3.2 ..."`。**LWJGL 如何把 ES 版本串映射到 `GLCapabilities.OpenGL44` 字段，需要实测才能定论**（这是一个可验证的、具体的实验）。

### 4.5 对照：为什么 Sodium 0.8.13 没出这个问题

真机日志（Sodium 路径）显示：

```
降级事件 (0 类):
"stub_symbols": { "count": 0, "names": [] }
```

`stub_symbols` **为空**意味着 **Sodium 从未调用过任何 stub** —— 包括 `glBufferStorage`。

这与 Embeddium 形成鲜明对比：Sodium 0.8.13 对 ES 环境的处理是**探测到 ES 就换路径**，
而 Embeddium（继承 0.5.8 内核）的 `pickBest` **只检查桌面 GL 标志，完全没有考虑 ES 场景**。

> 这也从反面印证了 §5.2（P2-04 文档）的结论：`degrade_events` 为空不是矛盾，而是**模组自己做了能力协商**。

---

## 5. 建议的处置

### 5.1 ✅ 已实施：`glBufferStorage` 已从静默 stub 改为有效实现

**原问题**：静默 stub 的行为是"什么都不做 + 记一条降级"。这在一个**有存储语义要求的调用**上是危险的 ——
调用方拿到"成功"的假象（void 返回，无错误），后续操作才在别处以一个**完全不相关**的方式失败（`Failed to map buffer`）。
这违反了本项目自己的原则：

> 任何无法实现的路径都必须「不崩溃 + 记录降级事件」。

**已实施的改法**：`glBufferStorage` 从 `S`（安全 stub）改为 `C`（定制实现），实际行为：

1. 用 `glBufferData(target, size, data, GL_DYNAMIC_DRAW)` **真实分配存储**；
2. 若 `flags` 含 `GL_MAP_PERSISTENT_BIT`(0x0040) 或 `GL_MAP_COHERENT_BIT`(0x0080)，
   记一条 `PERSISTENT_MAP_UNSUPPORTED` 降级事件，如实说明"持久语义无法提供"。

**收益**：即便调用方要了它拿不到的语义，**后续 `glMapBufferRange` 至少能成功**（只是非持久），
从而把"崩溃"转化为"性能降级"。

**关于取舍**：这确实意味着"申请了持久映射的调用方"会拿到一个**不符合其声明语义的映射**。
这是一个**善意的降级**，而非静默欺骗 —— 因为我们同时**明确记录了降级事件**，用户在日志与
`status.json` 里都能看到。选择它的理由是：**不这样做，行为就是崩溃**；而崩溃是本项目的第一优先级禁区。

**为什么用 `glBufferData` 而不是 `GL_EXT_buffer_storage`**：该扩展在驱动上支持度参差，探测它需要
`glGetStringi` 查扩展列表。用 `glBufferData`（ES 2.0 起必有）能保证一定成功，代价是失去不可变存储语义 ——
但那本来就不是我们能提供的。少一次扩展探测，多一分确定性。

### 5.1b ✅ 顺带修复：`glMapBufferRange` 剥离 ES 非法的映射位

`glBufferStorage` 修好后，`glMapBufferRange` 成了新的隐患点：
Embeddium 的 `MAP_FLAGS` 含 `GL_MAP_PERSISTENT_BIT`，而这个位在 ES 上**非法**。
原样转发会让驱动返回 `GL_INVALID_OPERATION`，映射失败 → 同样崩溃。

因此 `glMapBufferRange` 也从 `F`（直接转发）改为 `C`（定制实现）：**掩掉** `GL_MAP_PERSISTENT_BIT`(0x0040)、
`GL_MAP_COHERENT_BIT`(0x0080)、`GL_CLIENT_STORAGE_BIT`(0x0200) 后转发，并记降级事件。

**为什么掩掉是安全的**：这三位表达的都是"性能承诺"而非"数据正确性要求"：

| 位 | 掩掉后的后果 |
|---|---|
| `PERSISTENT` | 映射不能长期保持 → 每次映射即可，**仍正确** |
| `COHERENT` | 需显式 flush → 由驱动保守同步，**仍正确** |
| `CLIENT_STORAGE` | 存储位置偏好失效 → 纯性能提示，**仍正确** |

掩掉只会让驱动走更保守（可能更慢）的路径，**不会算错数据**。
我们**没有**改动任何影响正确性的位（`READ` / `WRITE` / `INVALIDATE` / `FLUSH`）。

> 注意：这里**只掩位，不清理 GL 错误队列**。理由同 `glTexParameterf` ——
> `glGetError` 是 FIFO 队列，主动抽干会吞掉此前的真实错误，掩盖故障。

### 5.2 可选：把 Embeddium 纳入检测但标记为"未验证"

`CompatDetector` 已包含 Embeddium 分支，当前逻辑正确：

```java
// Embeddium：目前没有针对 1.21.1 的验证结论
return new CompatTarget(modId, version,
        CompatTarget.SupportLevel.CONSERVATIVE,
        "尚未验证，使用保守策略");
```

**建议保持 `CONSERVATIVE`**，直到真机实测通过。

### 5.3 待实测清单（供你决定是否投入）

| # | 实验 | 判据 | 现状 |
|---|---|---|---|
| 1 | 装 Embeddium 1.0.15+mc1.21.1，启动进世界 | 是否崩在 `Failed to map buffer` | ✅ **已做（§9）：未崩溃，无视觉问题** |
| 2 | 查 `glesmod/status.json` 的 `stub_symbols` 与 `degrade_events` | 是否出现 `glBufferStorage` 相关降级 | ⏳ **待用新构建做**（旧构建下两者都为空，不足以判定） |
| 3 | 用**新构建**再跑一次 | 应同样正常 | ⏳ 待做 |

### 5.4 构建期防护：新增导出符号校验门禁

为避免"改了代码但产物是陈旧的"这一类问题（本项目已因此浪费过一整轮真机测试），
新增 `native/tools/verify_exported_symbols.py`，并接入 `build-all.ps1` 的 `[4/5]` 步骤。

它用 NDK 自带的 `llvm-nm` 直接查 `.so` 的**动态符号表**，校验：

| 校验项 | 判据 |
|---|---|
| 定制实现符号是否导出 | `glBufferStorage` / `glMapBufferRange` / `glMultiDraw*` 等 17 个必须存在 |
| 导出函数总数 | 不得低于下界（当前实测 869） |

**为什么必须这样做**：构建系统自己的输出**不能**作为"产物是最新的"的证据。
本轮实际出现过：

```
[2/7] Building C object CMakeFiles/gl_gles.dir/src/custom.c.o     <- 确实编译了
ninja: no work to do                                              <- 没编译
```

而我在两次之间**又改过一次 `custom.c`**。文件时间戳虽然后于源码，但那描述的是构建系统的内部记账，
**不是二进制里到底有什么**。查动态符号表是唯一不依赖构建系统自述的判据。

---

## 6. 附录 A：一手材料出处

| 结论 | 来源 |
|---|---|
| Embeddium 1.0.15+mc1.21.1 存在，client_only，LGPL-3.0-only | Modrinth API `GET /v2/project/embeddium` |
| 1.21.1 版本列表（1.0.15 为最新，2025-01-24） | Modrinth API `GET /v2/project/embeddium/version?game_versions=["1.21.1"]&loaders=["neoforge"]` |
| `minecraft_version=1.21.1`、`mod_version=1.0.15`、`forge_version=21.1.61` | 分支 `21.1/neoforge` 的 `gradle.properties` |
| 分支列表含 `21.1/neoforge`、`21.0/neoforge`、`21.2/snapshot`、`21.4/neoforge` | GitHub API `GET /repos/FiniteReality/embeddium/branches` |
| 基于 "last FOSS-licensed version of Sodium" / "Sodium 0.5.8 and earlier" | Embeddium 项目自述（Modrinth body） |
| `createStagingBuffer` 的二选一逻辑 | `impl/render/chunk/region/RenderRegionManager.java` |
| `isSupported()` 判定 | `impl/gl/arena/staging/MappedStagingBuffer.java` |
| `pickBest()` 只认 `OpenGL44` / `GL_ARB_buffer_storage` | `impl/gl/functions/BufferStorageFunctions.java` |
| `STORAGE_FLAGS` 含 `PERSISTENT` + `CLIENT_STORAGE` | `impl/gl/arena/staging/MappedStagingBuffer.java` |
| `glMapBufferRange` 返回 NULL 时抛 `RuntimeException` | `impl/gl/device/GLRenderDevice.java` |
| `GL32C.nglMultiDrawElementsBaseVertex` 用于区块渲染 | `impl/gl/device/GLRenderDevice.java` |
| `glBufferStorage` 在我们的 `symbols.def` 中**曾**为 `S`（stub） | `native/symbols.def`（v1 时第 425 行）；v2 起改为 `C` |
| Embeddium 侧存在的回退类 | `impl/gl/arena/staging/FallbackStagingBuffer.java` |
| 修复后符号已导出 | `llvm-nm` 实测：两个 ABI 的 `libgl_gles.so` 均含 `glBufferStorage` 与 `glMapBufferRange`，导出函数 869 个 |

## 7. 附录 B：Embeddium 使用的 GL 符号与我们降级路由的对应

从 `GLRenderDevice.java` 提取的实际调用：

| Embeddium 调用 | 我们的处理 | 状态 |
|---|---|---|
| `GL30C.glBindVertexArray` | 直接转发 | ✅ |
| `GL20C.glBufferData` | 直接转发 | ✅ |
| `GL31C.glCopyBufferSubData` | 直接转发（ES 3.0 有） | ✅ |
| `GL32C.glMapBufferRange` | 直接转发 | ⚠️ 视 flags 而定 |
| `GL32C.glUnmapBuffer` | 直接转发 | ✅ |
| `GL32C.glFlushMappedBufferRange` | 直接转发 | ✅ |
| `GL32C.glFenceSync` | 直接转发（ES 3.0 有） | ✅ |
| `GL32C.nglMultiDrawElementsBaseVertex` | **`C` 定制：循环拆解** | ✅ 已实现 |
| `BufferStorageFunctions.createBufferStorage` | `CORE`→`glBufferStorage` / `ARB`→`ARBBufferStorage.glBufferStorage` | ✅ **已改为真实分配 + 降级** |

**`ARBBufferStorage.glBufferStorage` 同样映射到我们的 `glBufferStorage`**（LWJGL 的 ARB 变体在 native 侧是同一个符号名）。
因此**无论 Embeddium 选 `CORE` 还是 `ARB`，都会落到同一个实现** ——
这既是 §4 风险判断的依据，也说明 §5.1 的一处修复同时覆盖了两条路径。

---

## 8. 结论

1. **Embeddium 在 1.21.1 上确实存在且可用**（1.0.15+mc1.21.1，LGPL-3.0-only，client_only）。
2. **但仍以 Sodium 0.8.13 为主目标**：Sodium 谱系更现代、已真机验证、且是任务书基线；Embeddium 的内核继承自 Sodium 0.5.8 时代。
3. **★ 发现一个真实的一手代码级风险 ★**：Embeddium 的"高级暂存缓冲"路径会申请桌面 GL 4.4 专有的持久映射 + 客户端存储，其 `pickBest()` **完全没有考虑 ES 场景**。若 LWJGL 上报了 `OpenGL44` 或 `GL_ARB_buffer_storage`，该路径会把我们的**静默 `glBufferStorage` stub** 当作成功，进而在 `glMapBufferRange` 处以 `RuntimeException` 硬崩溃。
4. **已修复**：`glBufferStorage` 改为"真实分配存储 + 记录降级"，`glMapBufferRange` 改为"剥离 ES 非法映射位后转发"。两者都从静默失败转为**显式降级**，把"崩溃"转化为"性能降级"。构建验证：两个 ABI 的产物均导出了这两个符号（共 869 个导出函数）。
5. **零成本的第一步**：查一次 `status.json` —— 修复后 `stub_symbols` 不应再含 `glBufferStorage`，而 `degrade_events` 应出现 `PERSISTENT_MAP_UNSUPPORTED`。

---

## 9. 真机验证结果（2026-09-29）

### 9.1 测试条件

| 项 | 值 |
|---|---|
| 日期 | 2026-09-29 |
| 加载的优化模组 | **Embeddium 1.0.15+mc1.21.1**（`embeddium-1.0.15+mc1.21.1.jar`） |
| 启动器 | **ZalithLauncher2 2.4.9_hotfix1** |
| 设备 | Xiaomi houji 23127PN0CC / SM8650 / Adreno 750 / Android 16 |
| 渲染器 | **本项目（GLES Mod）** |
| **重要**：使用的构建 | ⚠️ **旧构建**（晚于本轮修复，因此**不含** `glBufferStorage` 的定制实现） |

> ⚠️ 最后一行很关键：**这次测试跑的是仍有隐患的那个构建**。
> 也就是说，测试结果不能用来证明"修复有效"，而应用来回答一个更重要的问题：
> **那条崩溃链为什么根本没被走到？**

### 9.2 测试结果

| 观察项 | 结果 |
|---|---|
| **视觉问题** | ✅ **无任何视觉问题** |
| **帧率** | ✅ **与 Sodium 基本一致** |
| **崩溃** | ✅ 无 |
| 区块渲染 | ✅ 正常 |
| 地形缓冲路径 | ✅ 走的是 `FallbackStagingBuffer`（见 §9.3） |

**日志证据**（`latest(6).log`）：

```
[INFO] OpenGL Version: OpenGL ES 3.2 V@0762.36 (...) (Date:05/16/25)
[INFO] GLES 后端已激活，GLES 3.2，无功能降级。
[INFO] 优化模组: embeddium 1.0.15+mc1.21.1 -> CONSERVATIVE（尚未验证，使用保守策略）
[INFO]   - Multi-Draw（Sodium 区块渲染会降级为逐次绘制，性能略降）
...
[INFO] OpenGL debug message: ... 'EsxBufferObject::Map - Ignoring EsxBufferMapUnsyncedBit'
...
[INFO] Dullbo加入了游戏
[INFO] Dullbo退出了游戏          <- 正常退出，非崩溃
```

**没有** `Failed to map buffer`，**没有** 任何异常。

### 9.3 ★ 为什么那条崩溃链没有被走到 ★

这是本次测试最有价值的信息。三条独立证据指向同一结论：

#### 证据 1：`EsxBufferObject::Map` 出现 → 走的是回退路径

日志里有且仅有一条：

```
EsxBufferObject::Map - Ignoring EsxBufferMapUnsyncedBit
```

- `GL_MAP_UNSYNCHRONIZED_BIT`(0x0020) 是 **`FallbackStagingBuffer` 路径才会有**的映射标志
  （它把数据传到临时缓冲，再用 `glCopyBufferSubData` 搬到目标）
- **`MappedStagingBuffer` 用的是 `PERSISTENT` + `INVALIDATE_BUFFER` + `EXPLICIT_FLUSH`，
  根本不含 `UNSYNCHRONIZED`**

⇒ **Embeddium 实际走的是 `FallbackStagingBuffer`**，即 `MappedStagingBuffer.isSupported()` 返回了 `false`。

#### 证据 2：`%d` 未格式化 → 印证是回退路径的动态映射

```
Warning: high level of unsubmitted work.Pending memory %d (%3d%%) allocations
```

`%d` **没有被替换成数字**。这说明调用方传的是**字面量字符串**，而不是格式化后的结果。
与证据 1 结合：这是一条由回退路径触发的、未经格式化的驱动提示。

#### 证据 3：Embeddium 的开关默认值是 `true` → 风险在默认配置下就存在暴露面

```java
// EmbeddiumOptions.java
public static class AdvancedSettings {
    public boolean useAdvancedStagingBuffers = true;      // ← 默认开启
    ...
}
```

⇒ 用户**不需要改任何设置**，`createStagingBuffer()` 的 `useAdvancedStagingBuffers` 条件就已满足。
**唯一的保护就是 `MappedStagingBuffer.isSupported()`。**

### 9.4 结论：`pickBest()` 返回 `NONE`，与设计预期一致

```
MappedStagingBuffer.isSupported(device)
  = getBufferStorageFunctions() != NONE
  = pickBest(device) != NONE
      ↓
  pickBest 检查的是：capabilities.OpenGL44  /  capabilities.GL_ARB_buffer_storage
      ↓
  实测：两者均为 false
      ↓
  返回 NONE  ⇒ isSupported() == false
      ↓
  createStagingBuffer() 走 FallbackStagingBuffer  ✅ 安全
      ↓
  glBufferStorage / glMapBufferRange(PERSISTENT)  从未被调用
      ↓
  旧的静默 stub 因此从未暴露  ⇒ 旧的构建也能正常跑
```

**这正好验证了 §4.4 里那个"关键未知项"**：
> 问：LWJGL 在我们的 ES 后端下是否会上报 `OpenGL44=true`？
> **答：不会。**

**机制层面也说得通**：`glGetString(GL_VERSION)` 是**直接转发**（`F` 类型），
返回的是驱动原话 `"OpenGL ES 3.2 ..."`。LWJGL 从**驱动返回的字符串**推导能力标志，
因此它看到的是 ES 3.2、不是 GL 4.4。我们写进 `status.json` 的 `reportedGl=3.2` 只给 Java 模组看，
**不影响 LWJGL 的能力推导** —— 这正是我们想要的行为。

### 9.5 这次测试对修复意义的重新定性

| 判定 | 说明 |
|---|---|
| **风险是真的吗？** | ✅ **是**。`pickBest()` 完全没有 ES 回退判断，这是**上游代码的机制缺陷** |
| **当前会触发吗？** | ❌ **不会**。证据显示 LWJGL 不上报 `OpenGL44` / `GL_ARB_buffer_storage` |
| **那修复还有意义吗？** | ✅ **有，但意义需重新表述** —— 见下方 |

**修复的真实价值**，按重要性排序：

1. **它把"崩溃"变成"降级"，代价极低** —— 若将来某个启动器、某个 LWJGL 版本、
   或某个中间层让 `OpenGL44` 变成 `true`，修复后的代码会**优雅降级并记录事件**，而不是崩在
   `Failed to map buffer`。
2. **它修复了一个"契约谎言"** —— 这与是否有调用方无关。`glBufferStorage` 的契约是分配存储，
   静默 stub 让调用方拿到"成功"的假象。**这是代码正确性问题，不能靠"目前没人调用"来豁免。**
3. **它让失败模式可观测** —— 修复后若这条路径真被走到，会在日志里留下
   `PERSISTENT_MAP_UNSUPPORTED` 事件，而不是一句无从下手的 `Failed to map buffer`。

> **同时必须承认**：按"实测结果优先"的原则，我此前把这条风险描述为
> "Embeddium 会崩溃"是**过度断言的**。准确的表述应当是：
> **"存在一条会崩溃的代码路径；是否需要修复取决于 LWJGL 的能力上报，而实测显示当前不会走到。"**
> 这正是 §4.4"关键未知项"想表达的意思 —— 我当时把它标为未知，但在权衡建议里
> 把语气写强了。**这是一个应当避免的表达偏向。**

### 9.6 后续动作

| 动作 | 优先级 | 说明 |
|---|---|---|
| 用**新构建**再跑一次 Embeddium | 中 | 预期：**同样无问题**，且 `stub_symbols` 不含 `glBufferStorage`（因为已不是 stub） |
| 若新构建也正常 | — | 可将 Embeddium 从 `CONSERVATIVE` 提升为 `FULLY_SUPPORTED`（需连着测 2~3 次） |
| 保留 §4 的分析 | — | 作为"上游机制缺陷"的记录，供将来 `OpenGL44` 一旦变为 true 时参考 |

---

## 10. 附：本次测试中观察到的其他事项

### 10.1 `ShaderInstance` 采样器警告（与本项目无关）

```
[WARN] Shader rendertype_entity_translucent_emissive could not find sampler named Sampler2
```

这是 **MC 自身的着色器定义问题**：`rendertype_entity_translucent_emissive`
的 JSON 声明了 `Sampler2`，但编译出的程序里没有它（只有 `Sampler0`/`Sampler1`）。
**在 Sodium 路径下也同样出现**，不是本项目引入的。

### 10.2 `SCLP` 汉化包污染 Embeddium 类（第三方问题）

日志里 10 余条：

```
[ERROR] [Embeddium-MixinTaintDetector]: Mod mixin into Embeddium internals detected.
        This instance is now tainted.
[WARN]  Mod(s) [sclp] are modifying Embeddium class org.embeddedt.embeddium.impl.gui.EmbeddiumVideoOptionsScreen
```

`SCLP`（Sodium/Embeddium 汉化包）用 Mixin 注入了 Embeddium 的内部类，
导致 Embeddium 自己标记为 "tainted"。
**这是 SCLP 与 Embeddium 版本不匹配**（日志里大量 `ClassNotFoundException`
说明 SCLP 在找 `net.caffeinemc.mods.sodium.*`，而实际装的是 `net.embeddedt.embeddium.*`）。

**影响**：仅影响选项界面的汉化，**不影响渲染**。属第三方模组兼容性问题，非本项目职责。

### 10.3 `Namespace collision detected, using slow path`（约 50 次）

这是 Adreno 驱动的性能提示，**不产生错误**。数量级与 Sodium 路径相当（同为数十次量级），
属驱动侧行为，已在 `docs/p2-07-compatibility-matrix.md` §4.4 记录。

