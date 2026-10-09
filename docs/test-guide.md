# 真机测试指南

> 版本：v1（对应首次可测产物）
> 目标：验证 GLES Mod 渲染器在 FCL 中能被识别、能启动、能进入世界
> 预期本次结果：**大概率启动失败或渲染异常** —— 这是正常的，见 §6

---

## 1. 交付物

| 文件 | 大小 | 用途 |
|---|---|---|
| `build/plugin/glesmod-renderer-plugin.apk` | 412.5 KB | **FCL 渲染器插件**，装到手机上 |
| `build/libs/glesmod-1.0.0.jar` | 27.9 KB | NeoForge 模组，放进 `mods/` |
| `build/native/arm64-v8a/libgl_gles.so` | 236.2 KB | native 后端（已打包进 APK，仅供单独调试） |
| `build/native/armeabi-v7a/libgl_gles.so` | 164.7 KB | 同上（32 位设备） |

APK 已包含两个 ABI 的 native 库，并已用 debug 密钥签名（v2 + v3 方案已验证）。

---

## 1.1 修复记录

### 第 2 轮（当前）：启动崩溃 SIGSEGV

**现象**：启动瞬间闪退，看不到任何画面。

**崩溃栈**（来自 FCL 日志）：

```
C  [libc.so]              __strncmp_aarch64+0xbc
C  [libpojavexec.so]      pojavInitOpenGL+0x60
C  [libpojavexec.so]      pojavInit+0x6c
j  org.lwjgl.glfw.GLFW.glfwInit()
j  net.neoforged.fml.earlydisplay.DisplayWindow.initWindow
```

**根因**：FCL 的 `egl_bridge.c` 中，`pojavInitOpenGL()` 无条件解引用
`POJAV_RENDERER`：

```c
const char *renderer = getenv("POJAV_RENDERER");   /* 变量不存在 -> NULL */
if (!strncmp("opengles", renderer, 8)) { ... }     /* strncmp 读 NULL -> SIGSEGV */
```

而 FCL 只为 **v2 插件**从 `Renderer.pojavRendererId` 设置该变量；
本项目用的是 v1 插件格式，该字段为空串，因此变量根本不存在。

**这属于 FCL 侧的缺陷**（未对 `getenv` 的 NULL 返回值做防御），
但插件必须自行规避。

**修复**：在插件 `pojavEnv` 中注入 `POJAV_RENDERER=opengles3`。
该值以 `opengles` 开头，FCL 会选用 GL4ES 风格的 EGL 桥
（`gl_init` / `gl_init_context` / `gl_swap_buffers`），正是本项目需要的。

**附带加固**：native 层的符号解析改为优先显式 `dlopen("libGLESv2.so")`。
原因：FCL 用 `RTLD_LOCAL` 加载 EGL，厂商 GLES 实现
（`libGLESv2_adreno.so`）可能位于独立链接器命名空间，
`dlsym(RTLD_DEFAULT, ...)` 对核心函数并不可靠。

**已加入构建期校验**：`build-plugin.ps1` 现在会检查 `POJAV_RENDERER=opengles*`
与 `LIBGL_ES=3` 是否都已注入，缺失则构建失败。

### 第 1 轮：插件未被 FCL 识别

见 §6.0。根因是缺少 `boatEnv` meta-data，已修复。

---

## 2. 设备与环境前提

| 项 | 要求 |
|---|---|
| Android | 8.0+（minSdk 26） |
| ABI | arm64-v8a（绝大多数现代设备）或 armeabi-v7a |
| GPU | 建议骁龙 835 / Adreno 540 及以上 |
| FCL | 1.3.3.5 或更新（需支持渲染器插件） |
| Minecraft | 1.21.1 + NeoForge |
| 已安装模组 | GLES Mod jar（可选但推荐） |

---

## 3. 安装步骤

### 3.1 安装渲染器插件

```
1. 把 glesmod-renderer-plugin.apk 传到手机
2. 点击安装（需允许「安装未知来源应用」）
3. 安装后桌面**不会**出现图标 —— 这是正常的，它是纯插件
```

> ⚠️ **安装插件后必须完全退出并重启 FCL。**
> FCL 的插件扫描结果有进程内缓存，不重启看不到新插件。
> 这是最常见的「渲染器列表里没有」的原因。

**验证插件已装**：设置 → 应用 → 应能看到 **GLES Mod Renderer**

### 3.2 安装模组

```
把 glesmod-1.0.0.jar 放到实例的 mods/ 目录
```

### 3.3 在 FCL 中选择渲染器

```
FCL → 版本设置 → 「OpenGL 实现方式」（渲染器）
  → 列表中应出现「GLES Mod (native OpenGL ES)」
  → 选中它
```

> **这一步是第一个关键验证点。** 如果列表里没有这一项，说明插件未被识别，
> 请直接跳到 §6 的「插件未被识别」小节。

### 3.4 启动游戏

正常启动，然后收集日志（见 §4）。

---

## 4. 日志采集（重要）

### 4.1 需要收集的文件

| 路径 | 内容 |
|---|---|
| FCL 的 `latest_game.log` | 游戏日志，含模组输出 |
| `<实例目录>/glesmod/status.json` | **native 后端上报的状态**（最关键） |
| logcat 输出 | native 层与驱动的报错 |

### 4.2 status.json 的获取

native 后端会在首次 GL 调用后写入该文件。它位于**游戏工作目录**下：

```
<实例目录>/glesmod/status.json
```

若文件不存在，说明 native 库**从未被加载或从未初始化** —— 这本身就是关键诊断信息。

### 4.3 logcat 采集

```bash
# 需先开启 USB 调试
adb logcat -s GLESMod:* AndroidRuntime:E DEBUG:F libc:F > logcat.txt
```

关键 tag：`GLESMod`（本项目的所有日志都带此前缀）

---

## 5. 验收清单

请逐项确认，并把结果告诉我：

| # | 检查项 | 预期 | 实际 |
|---|---|---|---|
| 1 | APK 能正常安装 | 无报错 | |
| 2 | 设置中出现「GLES Mod Renderer」应用 | 存在 | |
| 3 | FCL 渲染器列表出现「GLES Mod (native OpenGL ES)」 | 存在 | |
| 4 | 选中后可启动游戏 | 能启动 | |
| 5 | 能到主菜单 | 画面正常 | |
| 6 | 能进入世界 | 画面正常 | |
| 7 | 能打开背包 / JEI | 界面正常 | |
| 8 | `status.json` 被生成 | 文件存在 | |
| 9 | `status.json` 中 `active` 为 true | `true` | |
| 10 | 日志中出现 `GLES 后端已激活: ES 3.x` | 有该行 | |
| 11 | 运行 10 分钟不崩溃 | 无崩溃 | |

### 若失败，请额外提供

| 现象 | 需要的额外信息 |
|---|---|
| 启动时闪退 | logcat 中的 `AndroidRuntime` 与 `libc` 段 |
| 黑屏 / 花屏 | 设备型号、GPU 型号、`status.json`（若存在） |
| 卡在启动画面 | FCL 日志中 `Environ` 段（含 `LIBGL_ES` 的值） |
| **渲染器列表中没有本项** | 见 §6.0 |

---

## 6. 预期问题与已知限制

**本次是首次可测产物，请预期会遇到问题。** 以下是已知的、有明确原因的风险。

### 6.0 渲染器未出现（已修复过一轮）

> 首次交付时确实出现了这个问题，原因已定位并修复。
> 如果你拿到的是旧 APK，请重新构建后再试。
>
> **根因**：FCL 的 `RendererPlugin.parseV1()` 要求四个 meta-data 字段
> **缺一不可**，缺任一就静默 `return`，插件被完全忽略且**不产生任何日志**：
>
> ```kotlin
> val rendererString = metaData.getString("renderer")  ?: return
> val des            = metaData.getString("des")       ?: return
> val boatEnvString  = metaData.getString("boatEnv")   ?: return   // ← 当时缺这个
> val pojavEnvString = metaData.getString("pojavEnv")  ?: return
> ```
>
> `boatEnv` 对本项目没有任何用途（它服务于 Pojav 的另一条渲染链路，
> 且在 FCL 中找不到任何消费点），但必须存在且非空 —— 现已填入无害占位值。
>
> **已加入构建期校验**：`fcl-plugin/build-plugin.ps1` 的步骤 [7/7] 会检查
> 这四个字段、`LIBGL_ES=3` 以及两个 ABI 的 `.so` 是否都存在，任一不满足则
> 构建直接失败。这样同类问题不会再静默漏到真机上。

### 如果渲染器仍然不出现

请按顺序排查：

| 步骤 | 检查内容 | 方法 |
|---|---|---|
| 1 | 插件是否安装成功 | 设置 → 应用，应能看到 **GLES Mod Renderer** |
| 2 | 插件是否被 FCL 识别 | FCL 的「插件管理」页（若有此入口）应列出它 |
| 3 | 是否被禁用 | FCL 插件管理页中确认未被禁用（禁用状态会持久化到 DataStore） |
| 4 | FCL 版本是否支持插件 | 需 1.3.3.x 或更新；旧版无插件扫描能力 |
| 5 | MC 版本是否匹配 | 插件声明 `minMCVer`/`maxMCVer` 均为 `1.21.1`；实例不是此版本时不会显示 |
| 6 | 实例是否已选中 | 部分 FCL 版本要求在具体实例的版本设置中查看 |
| 7 | 重启 FCL | 插件扫描有进程内缓存（`scannedApps`），安装后需重启启动器 |

**第 7 项很容易忽略**：FCL 的 `PluginManager` 把扫描结果缓存在内存中，
并注明「卸载/安装在系统侧发生，进程内缓存不会自动感知」。
**安装插件后必须完全退出并重启 FCL**，否则列表不会更新。

### 若仍不行，请提供

```
adb shell pm list packages | grep glesmod
adb shell dumpsys package com.youyimc.glesmod.plugin > pkg.txt
adb logcat -s FCL:* RendererPlugin:* PluginManager:* > fcl-plugin.log
```

---
### 6.0.1 已确认正常的部分（第 2 轮日志证据）

以下项已在真机验证通过，无需再排查：

| 项 | 日志证据 |
|---|---|
| 插件被识别 | `Renderer: GLES Mod` |
| `LIBGL_ES=3` 生效 | `Env: LIBGL_ES=3` |
| 自定义环境变量注入 | `Env: GLESMOD_ABI=1`、`GLESMOD_LOG_LEVEL=2` 等 |
| native 库被 dlopen | `DLOPEN: loading .../libgl_gles.so` |
| native 库进入进程内存 | 崩溃转储内存映射含 `libgl_gles.so` 三个段 |
| LWJGL 指向本库 | `-Dorg.lwjgl.opengl.libname=.../libgl_gles.so` |
| EGL / GLES 已加载 | 内存映射含 `libEGL.so`、`libGLESv2.so`、`libGLESv2_adreno.so` |

因此：**插件机制、环境变量链路、库加载链路均已打通。**
剩余问题集中在 FCL 的 native 初始化与 GL 符号解析上。

---
### 6.1 最高风险：GL 符号覆盖可能不全

native 库导出了 **153 个符号**，覆盖率经过检测为 100%（相对 `symbols.def` 声明）。

但 `symbols.def` 的清单来自**静态分析** MC 1.21.1 的 class 文件。实际运行时，
NeoForge、JEI、Sodium 或驱动自身可能调用清单之外的符号。

**症状**：启动中途崩溃，logcat 中是 `UnsatisfiedLinkError` 或直接 SIGSEGV。

**排查**：查看 `status.json` 的 `missing_symbols` 字段 —— 它记录了调用过但解析失败的符号。

### 6.2 已知风险：EGL 上下文版本

插件通过 `pojavEnv` 注入了 `LIBGL_ES=3`，但**这条链路未在真机验证过**。

**症状**：`status.json` 中 `gles_version` 显示 `2.0`（而非 `3.x`）。

**含义**：上下文被创建为 ES 2，VAO / FBO 等 GL 3.0 功能不可用，MC 1.21.1 会渲染异常。

### 6.3 已知缺失：着色器转换可能不完善

`glShaderSource` 会做桌面 GLSL → GLSL ES 转换，覆盖：
- `#version` 改写为 `320 es`
- 注入 `precision` 声明
- `texture2D` → `texture`
- `gl_FragColor` → 自定义 `out` 变量

**未覆盖**：复杂宏、自定义 `layout` 限定符、几何/细分着色器。

**症状**：着色器编译失败，画面缺失部分元素（如无天空、无实体），日志有 `SHADER` 相关降级。

### 6.4 已知缺失：纹理解包与格式映射未实现

`enum.c` 中的枚举映射表是**故意留空**的。因为自动映射纹理格式会静默产生错误图像，
比不映射更危险。当前策略是原样透传，遇到不兼容格式由 GL 报错。

### 6.5 尚未实现的功能

| 功能 | 状态 |
|---|---|
| 状态缓存（减少冗余 GL 调用） | 未实现（阶段三 P3-01） |
| TBDR 优化 | 未实现（阶段三 P3-02） |
| Sodium 兼容层联动 | 未实现（阶段二 P2-03） |

因此**本次测试请不要安装 Sodium**，先验证原版路径。

---

## 7. 如何回退

若出现无法恢复的问题：

```
FCL → 版本设置 → 「OpenGL 实现方式」→ 改回 GL4ES 或 NG-GL4ES
```

模组 jar 可直接删除，不影响游戏。APK 可卸载。

**回退是安全的**：插件与模组都不会修改游戏本体或世界存档。

---

## 8. 反馈模板

请用以下格式反馈，便于我定位：

```
设备型号：
GPU（设置→关于手机 或 GPU-Z）：
Android 版本：

[ ] 插件安装成功
[ ] FCL 列表出现 GLES Mod
[ ] 能启动到主菜单
[ ] 能进入世界
[ ] status.json 存在
[ ] 10 分钟不崩溃

现象描述：

附件：latest_game.log / status.json / logcat.txt
```

---

## 9. 我能从日志中看出什么

为了让你理解为什么要收集这些，以下是日志到结论的对应关系：

| 日志内容 | 结论 |
|---|---|
| 没有 `GLESMod` 前缀的任何行 | native 库根本没加载 → 检查 FCL 是否选中本渲染器、`.so` 是否在 APK 中 |
| 有 `GLES 后端已激活` | native 初始化成功，能力探测完成 |
| `状态文件已写入` | 通路正常，可读取能力与降级信息 |
| `未检测到 GLES 后端状态文件`（模组输出） | 模组读不到文件 → 可能是工作目录不一致 |
| `降级: GLES 不提供 glXxx` | 有符号未解析 → 影响 `missing_symbols` 列出的功能 |
| `降级: Multi-Draw 不可用` | 正常，原版不用它；装了 Sodium 才会真正生效 |
| logcat 中 `Connection reset` | 与本项目无关，是构建期的网络问题 |

---

## 10. 构建复现

如需自行重新构建：

```powershell
# 全部（native + mod + 插件）
.\build-all.ps1 -WithPlugin

# 只构建 native 库
.\native\build-native.ps1 -Abi arm64-v8a -CheckSymbols

# 只构建插件（复用已有 .so）
.\fcl-plugin\build-plugin.ps1 -SkipNative

# 只构建 mod
.\gradlew.bat build --offline
```

> `--offline` 是必需的：本机无法访问 `maven.neoforged.net`，详见 `AGENTS.md`。
