# 真机测试日志分析

> 目的：记录每次真机测试的**实际证据**与结论，避免重复排查已确认的事项。
> 与 `docs/test-guide.md`（操作指南）互补，本文件是**诊断记录**。

---

## 测试 #1 —— 2026-09-25

### 设备

| 项 | 值 |
|---|---|
| 设备 | Xiaomi houji 23127PN0CC |
| SoC | SM8650（骁龙 8 Gen 3） |
| 架构 | arm64 |
| Android | 16（SDK 36） |
| GPU 驱动 | Adreno（`libGLESv2_adreno.so`） |
| FCL | versionCode 1316 |
| JVM | OpenJDK 21.0.1（FCL 内置 JRE21） |
| NeoForge | 21.1.241 |
| MC | 1.21.1 |

### 结果：启动崩溃（SIGSEGV）

崩溃在 Minecraft 主类执行前，发生在 NeoForge 的早期显示窗口初始化阶段。

```
[LWJGL] Failed to load a library.
#
#  SIGSEGV (0xb) at pc=0x00000078edcc517c, pid=11201, tid=25060
#  Problematic frame:
#  C  [libc.so+0x6c17c]  __strncmp_aarch64+0xbc
#
siginfo: si_signo: 11 (SIGSEGV), si_code: 1 (SEGV_MAPERR), si_addr: 0x0000000000000000

Native frames:
C  [libc.so+0x6c17c]        __strncmp_aarch64+0xbc
C  [libpojavexec.so+0x7a90] pojavInit+0x6c
j  org.lwjgl.system.JNI.invokeI
j  org.lwjgl.glfw.GLFW.glfwInit()
j  net.neoforged.fml.earlydisplay.DisplayWindow.initWindow
```

寄存器证据：

```
R30 = pojavInitOpenGL+0x60   ← 崩溃处位于 pojavInitOpenGL
```

`si_addr: 0x0` 表示访问了空指针，配合 `__strncmp_aarch64` 说明
`strncmp` 的某个参数为 NULL。

### 根因

FCL 的 `FCL/src/main/jni/egl_bridge.c`：

```c
int pojavInitOpenGL()
{
    const char *renderer = getenv("POJAV_RENDERER");
    if (!strncmp("opengles", renderer, 8)) {   // renderer == NULL -> 崩溃
        pojav_environ->config_renderer = RENDERER_GL4ES;
        set_gl_bridge_tbl();
    }
    ...
}
```

`POJAV_RENDERER` 在本环境变量映射中**不存在**：

```
Env: POJAVEXEC_EGL=libEGL.so
Env: LIBGL_ES=3
Env: GLESMOD_ABI=1
Env: GLESMOD_ENABLE=1
Env: GLESMOD_DEGRADE_LEVEL=1
Env: GLESMOD_LOG_LEVEL=2
Env: MOD_ANDROID_RUNTIME=...
Env: INST_NEOFORGE=1
（无 POJAV_RENDERER）
```

不存在的理由见 FCL `Renderer` 数据类的字段注释：

```kotlin
/** v2 插件渲染器的 POJAV_RENDERER 值；内置与 v1 插件渲染器为空串（不设置该环境变量） */
val pojavRendererId: String = ""
```

而 `FCLauncher.addRendererEnvInner()` 对 v1 插件分支从不设置该变量：

```kotlin
if (!renderer.getPath().isEmpty()) {          // 插件分支
    if (!renderer.getPojavRendererId().isEmpty()) {
        envMap.put("POJAV_RENDERER", renderer.getPojavRendererId())
    }                                          // v1 -> 空串 -> 不设置
    ...
    return                                     // 直接返回，后续内置逻辑不执行
}
```

**结论：这是 FCL 的缺陷**（`getenv` 返回值未做 NULL 检查），
但只要插件注入该变量即可规避。

### 修复

在插件 `pojavEnv` 中增加 `POJAV_RENDERER=opengles3`：

```
POJAV_RENDERER=opengles3:LIBGL_ES=3:GLESMOD_ABI=1:GLESMOD_ENABLE=1:GLESMOD_DEGRADE_LEVEL=1:GLESMOD_LOG_LEVEL=2
```

取值依据：只要以 `opengles` 开头，`pojavInitOpenGL()` 就会：

1. 设置 `config_renderer = RENDERER_GL4ES`
2. 调用 `set_gl_bridge_tbl()`，把 `br_init` / `br_init_context` /
   `br_make_current` / `br_swap_buffers` 指向 `gl_*` 系列实现
   （见 `ctxbridges/bridge_tbl.h`）

这正是我们需要的行为：GL4ES 风格的 EGL 桥会按 `POJAVEXEC_EGL` 加载 EGL，
并按 `LIBGL_ES` 创建对应版本的上下文。

`pojavInitOpenGL()` 后续还会检查若干具体字符串：

```c
if (!strcmp(renderer, "gallium_virgl"))     { ... }
if (!strcmp(renderer, "vulkan_zink"))       { ... }
if (!strcmp(renderer, "gallium_freedreno")) { ... }
if (!strcmp(renderer, "custom_gallium"))    { ... }
```

`opengles3` 不匹配其中任何一个，因此不会误入 VirGL / Zink / Freedreno 分支。

### 附带加固：符号解析顺序

分析崩溃转储的内存映射后，发现一个**尚未暴露但必然会踩**的问题：

```
761d0f2000-761d20e000 r--p  /vendor/lib64/egl/libGLESv2_adreno.so
761d20e000-761d557000 r-xp  /vendor/lib64/egl/libGLESv2_adreno.so
761e156000-761e15c000 r--p  /vendor/lib64/egl/libEGL_adreno.so
7142: 79103d3000-79103e5000 r--p  /system/lib64/libGLESv2.so
```

FCL 加载 EGL 时使用 `RTLD_LOCAL`：

```c
/* FCL ctxbridges/egl_loader.c */
void* dl_handle = loader_dlopen(eglName, "libEGL.so", RTLD_LOCAL|RTLD_LAZY);
```

`RTLD_LOCAL` 意味着该库的符号**不会**进入全局命名空间，
且厂商实现（`libGLESv2_adreno.so`）常位于独立的链接器命名空间。
因此原先的 `dlsym(RTLD_DEFAULT, "glDrawElements")` 可能返回 NULL。

修复：`native/src/core.c` 的 `glesym_resolve()` 改为三级回退：

| 顺序 | 方式 | 适用 |
|---|---|---|
| 1 | `dlopen("libGLESv2.so")` 后 `dlsym` | 核心函数（最可靠） |
| 2 | `eglGetProcAddress` | 扩展函数（规范允许对核心函数返回 NULL） |
| 3 | `dlsym(RTLD_DEFAULT)` | 兜底 |

---

### 已确认正常的部分

**这一轮测试虽然崩溃，但验证了大量关键链路**，以下项目无需再排查：

| 验证项 | 日志证据 |
|---|---|
| 插件被 FCL 识别 | `Renderer: GLES Mod` |
| 插件声明被解析 | `（Renderer 名称来自 des 字段）` |
| `LIBGL_ES=3` 注入成功 | `Env: LIBGL_ES=3` |
| 自定义环境变量注入成功 | `Env: GLESMOD_ABI=1`、`GLESMOD_LOG_LEVEL=2` |
| 本模组被 NeoForge 加载 | `glesmod-1.0.0 \| glesmod \| 1.0.0 \| NEO_FORGED` |
| native 库被 dlopen | `DLOPEN: loading .../com.youyimc.glesmod.plugin-.../lib/arm64/libgl_gles.so` |
| native 库进入进程地址空间 | 崩溃转储含 `libgl_gles.so` 的 r-xp / r--p / rw-p 三个段 |
| LWJGL 已指向本库 | `-Dorg.lwjgl.opengl.libname=.../libgl_gles.so` |
| 插件库目录进入 `LD_LIBRARY_PATH` | `Env: LD_LIBRARY_PATH=...com.youyimc.glesmod.plugin.../lib/arm64:...` |
| EGL 已加载 | 内存映射含 `/system/lib64/libEGL.so` |
| GLES 已加载 | 内存映射含 `/system/lib64/libGLESv2.so` 与 `libGLESv2_adreno.so` |

**重要结论：插件机制、环境变量注入、native 库加载三条链路已全部打通。**
问题只出现在 FCL 的 native 初始化逻辑与（潜在的）GL 符号解析上。

另外注意 `-Dorg.lwjgl.opengl.libname` 这一项 —— 说明 FCL 不只是
`dlopen` 我们的库，还通过该属性让 LWJGL 直接按路径加载它。
这比原先理解的机制更直接，也意味着**符号解析失败会立即表现为
`UnsatisfiedLinkError` 而非静默降级**。

---

## 测试 #2 —— 2026-09-25（挂起而非崩溃）

### 结果：无崩溃，但启动挂起 30 秒后超时

与测试 #1 对比：**`POJAV_RENDERER` 修复已生效，SIGSEGV 消失。**
进度明显推进：

| 阶段 | 测试 #1 | 测试 #2 |
|---|---|---|
| 插件被识别 | ✅ | ✅ |
| `pojavInit` / EGL 桥 | ❌ 崩溃 | ✅ 通过 |
| 初始化 LWJGL | — | ✅ `Backend library: LWJGL 3.3.6-snapshot` |
| 载入游戏资源 | — | ✅ `Setting user: youyiMC` |
| early display 窗口 | — | ❌ **等待 30 秒超时** |

关键日志：

```
[21:52:08] Trying GL version 4.6
[21:52:08] Requested GL version 4.6 got version 4.0      ← GL 可用
[21:52:18] [Render thread] Backend library: LWJGL 3.3.6-snapshot
[21:52:18] [Render thread] Setting user: youyiMC
[21:52:19] Failed to fetch user properties (401)          ← 离线模式，无害
                    ↓ 完全静默 29 秒 ↓
[21:52:48] [EARLYDISPLAY] Failed to initialize the mod loading system and display.
           We seem to be having trouble initializing the window, waited for 30 seconds
```

**「完全静默」是决定性线索**：不是崩溃（无 SIGSEGV、无异常栈），
而是某个线程被永久阻塞。

### 根因：非递归互斥锁的自我死锁

`native/src/core.c` 中的调用链：

```c
glesmod_lazy_init()
  → pthread_mutex_lock(&g_lock)      // ① 获取锁
  → probe_capabilities()
      → glesym_resolve("glGetString")
          → pthread_mutex_lock(&g_lock)  // ② 同一把非递归锁 → 永久阻塞
```

`pthread_mutex_t` 的默认类型是 `PTHREAD_MUTEX_NORMAL`（bionic 上非递归）。
**同一线程重复加锁不是「未定义行为」而已——在 Android 上必然挂起。**

触发时机完全吻合：early display 阶段会调用 `glShaderSource` 编译进度条着色器，
而那是 11 个「定制实现」之一，**会**调用 `glesmod_lazy_init()`。

这也解释了为何日志里能看到 GL 版本：`glGetString` 是纯转发函数，
原先不触发初始化，所以能正常工作；一旦走到定制函数就死锁。

### 修复

1. 初始化改用 `pthread_once`，**不再持有 `g_lock`**
2. 把「配置初始化」（无 GL 依赖）与「能力探测」（需 EGL 上下文）拆开：
   `pthread_once(do_config_init)` + 带重试上限的 `maybe_probe()`
3. 全部转发函数注入 `glesmod_lazy_init()`（提高可诊断性，见下）

### 同时修复的三个隐患

**(a) 探测失败会无限重试**

转发函数都调用 `lazy_init` 后，若探测持续失败，每次 GL 调用都会执行
一次 `probe_capabilities()`（含真实 `glGetString`）。
MC 每帧 10^4–10^5 次 GL 调用 → 严重卡顿。
已加 `MAX_PROBE_ATTEMPTS = 50` 上限，超限后记降级事件并输出状态文件。

**(b) 符号自我递归**

LWJGL 通过 `-Dorg.lwjgl.opengl.libname` 以 `RTLD_GLOBAL` 加载我们的库，
我们的 `gl*` 符号会进入全局符号表。原 `dlsym(RTLD_DEFAULT, name)`
兜底可能**返回我们自己的转发函数**，形成无限递归直至栈溢出。
已加 `is_own_symbol()`（基于 `dladdr`）拦截。

**(c) stderr 阻塞风险**

去掉了 `fflush(stderr)`；逐符号解析日志提到 level 3（默认关闭）。

### 可诊断性改进

测试 #2 的日志里**没有任何 `GLESMod` 前缀的输出**，无法判断库是否
真的在调用链上。原因是生成的转发函数不调用 `lazy_init`，
而 MC 恰好没走到那些定制函数。

现已让 **142 个转发函数全部调用 `glesmod_lazy_init()`**：
任何一次 GL 调用都会触发初始化，成功后写出 `status.json`
并输出一行「GLES 后端已激活」日志。

---

## 测试 #3 —— 2026-09-25（后端首次成功启动）

### 结果：后端完全启动，但因符号覆盖不足而崩溃

**本轮是重大突破：前三轮的阻塞问题全部解决。**

```
[GLESMod] 已打开 libGLESv2.so (0x62860afc9f190053)
[GLESMod] 检测到 GL_VERSION: "OpenGL ES 3.2 V@0762.36 (GIT@4a4a7d07e5, ...)" -> ES 3.2
[GLESMod] 符号 glMultiDrawElements 在全局表中指向本库自身，已忽略（ES 可能不提供该函数）
[GLESMod] GLES 后端已激活: ES 3.2, 对外声称 GL 3.2, 降级档位 1（第 1 次尝试）
[GLESMod] 状态文件已写入: glesmod/status.json
```

逐项验证：

| 验证项 | 结果 |
|---|---|
| native 库被加载 | ✅ |
| `dlopen("libGLESv2.so")` 成功 | ✅ `0x62860afc9f190053` |
| 能力探测成功 | ✅ 识别为 ES 3.2 |
| 自我递归防护生效 | ✅ `glMultiDrawElements` 被正确识别为自身符号 |
| 状态文件写出 | ✅ `glesmod/status.json` |
| **死锁修复生效** | ✅ 第 1 次尝试即成功，无挂起 |
| 进入游戏初始化 | ✅ 走到 `Minecraft.<init>` |

### 根因：符号覆盖不足

```
java.lang.NullPointerException: A required function is missing: glGetStringi
	at org.lwjgl.system.APIUtil.requiredFunctionMissing(APIUtil.java:147)
	at org.lwjgl.system.APIUtil.apiGetFunctionAddress(APIUtil.java:141)
	at org.lwjgl.opengl.GL.createCapabilities(GL.java:514)
	at net.neoforged.fml.earlydisplay.DisplayWindow.initRender(DisplayWindow.java:207)
```

**方法错误**：O-02 的分析只统计了「Minecraft 的 class 文件直接调用的 GL 符号」，
得出 89 个。但 **LWJGL 自身在 `GL.createCapabilities()` 时还需要一批函数**。
在 core profile 下枚举扩展靠 `glGetStringi`，缺它就直接 NPE 硬崩溃。

**缺口规模**：GL 3.2 core 全集 316 个，当时只导出了 242 个。

### 修复：导出全集，未实现的一律给安全 stub

| 类型 | 数量 | 处理 |
|---|---|---|
| `F` 转发 | 232 | GLES 有同名函数 |
| `S` 安全 stub | 74 | GLES 无此函数，返回零值 + 记降级，**不崩溃** |
| `C` 定制 | 10 | 映射到其他 GLES 函数（见 custom.c） |

**核心原则：导出空实现优于不导出。**

| 做法 | 结果 |
|---|---|
| 不导出 | LWJGL 解析失败 → 抛 NPE → 游戏直接退出（无法捕获） |
| 导出为 stub | LWJGL 拿到有效指针 → 返回零值 + 记降级 → 游戏继续运行 |

新增工具：
- `native/tools/gen_symbols_def.py` —— 从 gl.xml 生成全集清单
- `gen_gl_forwarders.py` 新增 stub 生成与返回类型校验

### 附带修复的两个解析 bug

**(a) 参数名歧义**

生成器靠「最后一个词是否小写开头」区分类型与变量名。
`GLintptr p0` 被误拆成 `GLi` + `ptr`，`GLboolean` 变成 `GLo` + `olean`。

修复：生成 symbols.def 时统一用 `p0/p1/p2` 命名参数，类型仍取自 gl.xml。
提取类型改为读 `<ptype>` 子元素，不再用字符串替换。

**(b) 返回类型未登记**

提示：生成器现在会在生成前校验所有返回类型是否已登记到 `ZERO_VALUES`，
缺失则直接报错退出，避免生成出非法代码（如非 void 函数缺少 return）。

---

## 排查手段备忘

### 从日志快速定位崩溃阶段

| 日志位置 | 含义 |
|---|---|
| 有 `Renderer: xxx` 但无 `DLOPEN` | 死在启动参数组装前 |
| 有 `DLOPEN` 但无 `ModLauncher running` | 死在 JVM/JLI 初始化 |
| 有 `ModLauncher running` 但无 `fml.earlydisplay` | 死在模组发现阶段 |
| 崩在 `pojavInitOpenGL` | `POJAV_RENDERER` 相关问题 |
| 崩在 `gl_init_context` / `eglCreateContext` | EGL / 上下文版本问题 |
| 有 `GLESMod` tag 日志 | native 层的 `glesmod_lazy_init()` 已执行 |

### 关键日志抓取命令

```bash
# 本模组的 native 层日志（所有输出都带 GLESMod 前缀）
adb logcat -s GLESMod:*

# FCL 自身的启动日志
adb logcat -s FCL:*

# 崩溃与 JNI 错误
adb logcat -s AndroidRuntime:E DEBUG:F libc:F
```

### 崩溃转储位置

JVM 崩溃时会在**游戏工作目录**生成 `hs_err_pid<pid>.log`：

```
/storage/emulated/0/Minecraft/.minecraft/versions/<实例名>/hs_err_pid<pid>.log
```

该文件包含寄存器值、内存映射、线程栈，是定位 SIGSEGV 的首选材料。

---

## 测试 #4 —— 待执行

### 前四轮的问题与状态

| 轮次 | 现象 | 根因 | 状态 |
|---|---|---|---|
| #1 | 渲染器列表无本项 | 缺 `boatEnv` meta-data | ✅ 已修 |
| #2 | 启动 SIGSEGV | 缺 `POJAV_RENDERER` 环境变量 | ✅ 已修 |
| #3 | 挂起 30 秒 | 非递归锁自我死锁 | ✅ 已修 |
| #3 | `glGetStringi` 缺失崩溃 | 符号覆盖只算 MC 调用，漏了 LWJGL 所需 | ✅ 已修 |

### 本轮预期验证项

- [ ] 通过 `GL.createCapabilities()`（这是上轮的失败点）
- [ ] NeoForge 早期显示窗口能渲染
- [ ] 到达 Minecraft 主菜单
- [ ] 能进入世界
- [ ] `glesmod/status.json` 中的 `stub_symbols` 为空或很少

### 若本轮出现新崩溃，优先检查

1. **`status.json` 的 `stub_symbols` 列表** —— 哪些 GL 函数被降级了。
   若非空且游戏画面异常，说明对应功能失效。
2. **`hs_err_pid*.log`** —— 若有 SIGSEGV，看 `si_addr` 与寄存器。
   `si_addr: 0x0` 通常是空指针（多为未初始化的函数指针）。
3. **`GLESMod` tag 日志** —— 是否出现新的「符号 xxx 在全局表中指向本库自身」
   或「GLES 不提供 xxx」。
4. **画面表现** —— 若画面部分缺失（如无天空、无实体），
   对照 `stub_symbols` 列表定位是哪个功能被降级。

### 已知会被 stub 的符号（预期内）

以下 GL 3.2 core 符号在 GLES 3.2 中不存在，已导出为安全 stub。
原版 MC 不使用它们（见 `docs/o-02-symbol-inventory.md`），
但**若第三方模组使用，对应功能会静默失效**：

| 类别 | 代表符号 |
|---|---|
| 固定功能管线 | `glVertexAttrib1d`、`glVertexAttrib4s` 等系列 |
| 纹理（1D/3D 部分路径） | `glTexImage1D`、`glTexSubImage1D`、`glTexImage3DMultisample` |
| 双精度查询 | `glGetDoublev`、`glGetVertexAttribdv` |
| 变换反馈 | `glBeginTransformFeedback`、`glTransformFeedbackVaryings` |
| 条件渲染 | `glBeginConditionalRender`、`glEndConditionalRender` |
| 其他 | `glPointSize`、`glLogicOp`、`glClipPlane`、`glColorMaski` |

---

## 测试 #4 —— 2026-09-25 ~ 09-29（多轮，累计）

> **说明**：测试 #4 之后实际发生了**多轮**真机验证（Sodium 跑通、着色器崩溃修复、
> Embeddium 验证、P3-01 验证），但此前未逐一记录。本节把它们**汇总成一条时间线**，
> 并保留每轮的可复核证据。详细分析见 `docs/p2-07-compatibility-matrix.md`、
> `docs/p2-05-embeddium-assessment.md`、`docs/p3-01-hotpath-optimization.md`。

### 4.1 累计时间线

| 轮次 | 现象 | 根因 | 状态 |
|---|---|---|---|
| 4-a | 主菜单可达，但**深度测试完全失效**（面不被剔除、正反面交叠） | 桌面 GL 允许 `GL_DEPTH_COMPONENT`(0x1902) 作 internalformat，**ES 不允许** → 深度纹理根本没被分配 | ✅ 翻译为 `GL_DEPTH_COMPONENT24` |
| 4-b | **进入世界崩溃**（`Shader compilation failed`） | Sodium 区块着色器三处转换器缺口：① 缺 GLSL ES 采样器精度 ② `uvecN`/`uint` 与 float 混算 ③ **`uvec3 * float标量`** | ✅ 三处全修（**三轮才定位**） |
| 4-c | 修好后仍崩溃 | 测试的是**陈旧 APK**（安装路径签名逐字节相同 ⇒ 未重装） | ✅ 加构建戳；后续加导出符号门禁 |
| 4-d | `pname 34049` 噪声 70 次 | `GL_TEXTURE_LOD_BIAS` 是桌面专属 pname | ✅ 过滤，70 → 0 |
| 4-e | Sodium 0.8.13 满血运行 | — | ✅ `FULLY_SUPPORTED`，零降级，零渲染错误 |
| 4-f | Embeddium 1.0.15 验证 | — | ✅ 无视觉问题，帧率与 Sodium 相当 |
| 4-g | **FPS 只有 120** | **FCL 1.3.1.6 过旧**（1.3.3.2 才「解除帧率锁定」） | ⚠️ 非本项目问题，升级 FCL 即可 |

### 4.2 测试 #4-g 之后的性能事实

| 启动器 | FPS | 说明 |
|---|---|---|
| ZalithLauncher2 2.4.9_hotfix1 | **300 ~ 400** | 高于「≥ GL4ES 基线 70%」的验收要求 |
| FCL 1.3.1.6 | 120（= 120Hz 面板刷新率） | FCL 旧版 BufferQueue 处于同步模式，`dequeueBuffer` 按 vsync 阻塞 |

> 详见 `docs/p2-07-compatibility-matrix.md` §5.1。

---

## 测试 #5 —— 2026-09-29（P3-01 热路径优化后的首次验证）

### 设备与环境

| 项 | 值 |
|---|---|
| 设备 | Xiaomi houji 23127PN0CC / SM8650 / Adreno 750 / Android 16 |
| 启动器 | **ZalithLauncher2 2.4.9_hotfix1** |
| MC / NeoForge | 1.21.1 / 21.1.241 |
| 优化模组 | **Sodium 0.8.13+mc1.21.1** + **Sodium Extra 0.9.4+mc1.21.1** |
| 其他模组 | SCLP 3.17.8（汉化包） |
| 日志 | `latest(8).log`（34.9 KB） |

### 5.1 构建版本核验（★ 先做这一步）

```
=== glesmod 诊断报告 ===
降级事件 (0 类):
缺失符号 (0):
被调用的空实现 (0):
```

**`被调用的空实现 (0):` 这一行只存在于本次修复后的构建** —— 它来自
「`calledStubs` 被解析却未传入诊断报告」的修复（见 `docs/r-12-stub-audit.md` §4）。

**⇒ 确认设备上跑的确实是新构建。** 这一步不能省：
此前有过「测试陈旧 APK」白耗一轮的教训，而文件时间戳**只反映构建系统记账**，
不反映二进制内容。日志里「某一行存在」才是内容的直接证据。

### 5.2 结果：全部通过

| 检查项 | 结果 |
|---|---|
| 崩溃（SIGSEGV） | ✅ 0 |
| 着色器编译失败 | ✅ 0 |
| `Failed to map buffer` | ✅ 0 |
| 未捕获异常 | ✅ 0 |
| 降级事件 | ✅ **0 类** |
| 缺失符号 | ✅ **0** |
| 被调用的空实现 | ✅ **0** |

```
[INFO] GLES 后端已激活，GLES 3.2，无功能降级。
[INFO] 优化模组: sodium 0.8.13+mc1.21.1 -> FULLY_SUPPORTED（已验证版本，使用专用策略）
[INFO] OpenGL Version: OpenGL ES 3.2 V@0762.36 (...), Qualcomm
```

**游戏时长**：17:27:15 进入世界 → 17:27:48 退出，**约 33 秒**，全程无异常。

> **三项判据全为 0 的含义**：渲染路径**没有踩到任何未实现或降级的功能**。
> 这是本次改动的正确性证据 —— P3-01 消除了每个 GL 调用的固定开销，
> 而三项计数与改动前完全一致，说明**没有改变任何 GL 语义**。

### 5.3 P3-01 的验证结论

| 维度 | 结论 |
|---|---|
| **正确性** | ✅ 通过。零降级 / 零缺失 / 零空实现，与改动前一致 |
| **性能收益** | ❓ **本轮未测量 FPS** |

#### 5.3.1 横向对比数据（用户补充）

> **原版环境**下，**GLES Mod + Sodium** 与 **MobileGlues + Sodium**、
> **Zink 渲染器 + Sodium** 的帧率**几乎没有差别**。

**含义与边界**：

| 维度 | 判读 |
|---|---|
| 与其他渲染器**并列** | ✅ 可声称 |
| **超越**其他渲染器 | ❌ **不可声称** |
| 相对**改动前**的提升 | ❌ **无数据** |

**★ 这条数据推翻了我之前的一处表述 ★**

我曾在 `status-report.md` §7.3 写过「GL4ES 在同类设备上通常为 30~60 FPS」，
并据此声称本项目「远超基线」。**该对比已删除**：

| 问题 | 说明 |
|---|---|
| 参照对象不对 | GL4ES 是**旧一代**翻译层；当前主流已是 **MobileGlues / Zink** |
| 数据来源不实 | 「30~60 FPS」是我凭印象写的，**无一手测量来源** |
| 结论过强 | 参照数不可靠 ⇒「远超」不成立 |
| 与用户实测冲突 | 实测三者**几乎没有差别** |

⇒ 正确表述：**「与其他主流渲染器相当」**，不是「超越」。

**这个结果不意外**：MobileGlues 与 Zink 都在 native 层，与本项目**同一层次**，
且都直接调用 GPU 驱动。在**原版 + Sodium** 这类负载下表现相近是符合预期的。

**本项目的差异化点不在帧率**，而在于：
- **不引入中间层** —— 直接输出 ES 3.2（Zink 需经 Vulkan 再翻译一层）
- **能力协商的可见性** —— 降级事件可查（`status.json`）

> ⚠️ **必须明确的未验证项**：
> - 「无差别」仅限**原版 + Sodium**，其他负载（光影、大模组包、高视距）未测
> - 「无差别」**没有具体数值**，只知道「几乎」
> - **相对改动前的提升完全无数据**（未做同场景对照）

### 5.4 驱动噪声（与历史基线对比）

| 项 | 本轮 | 基线（4-f 轮） | 判读 |
|---|---|---|---|
| `Namespace collision` | **12** | ~50 | ✅ 下降（且远低于最初的 27229） |
| `EsxBufferMapUnsyncedBit` | 1 | 1 | ✅ 持平 |
| `less than 3 vertices` | 5 | 4 | ✅ 持平（退化绘制，MC 侧行为） |
| `high level of unsubmitted work` | 1 | 1 | ✅ 持平 |
| `Abnormally high render area` | 0 | 7 | ✅ 本轮未出现 |
| `Reset max power request` | 0 | 6 | ✅ 本轮未出现 |

**全部持平或改善，无一项恶化。**

> **关于 `Namespace collision` 从 ~50 降到 12**：这是 Adreno 驱动的性能提示
> （同命名空间内的对象冲突，走慢路径）。数量下降与驱动自身的状态有关，
> **不能归因于本次改动**（我们没有改动任何对象命名相关的逻辑）。
> 记录在此以保持基线的完整性，不做过强解释。

### 5.5 第三方模组问题（非本项目职责）

| 项 | 次数 | 判读 |
|---|---|---|
| SCLP Mixin 注入报错 | 13 | SCLP 与 Sodium 版本不匹配（见下） |
| SCLP 找不到类 | 10 | 同上 |
| `could not find sampler named Sampler2` | 1 | **MC 自身**的着色器定义问题 |

**关于 SCLP**：日志显示它在尝试 Mixin 注入
`org.embeddedt.embeddium.*` 与 `net.caffeinemc.mods.sodium.*` 的多个类，全部失败：

```
[WARN] Error loading class: org/embeddedt/embeddium/impl/util/PlatformUtil (ClassNotFoundException)
[WARN] @Mixin target ... was not found sclp.mixins.json:...
[ERROR] [mixin/] Write access detected to @Final field name:... in sclp.mixins.json:sodium.MixinPageBuilderImpl
```

**根因**：SCLP 3.17.8 是针对**另一个 Sodium/Embeddium 版本组合**构建的汉化包，
其 Mixin 目标类在当前组合下不存在。

**影响**：仅影响**选项界面汉化**，**不影响渲染**。
属第三方模组兼容性问题，非本项目职责。

**关于 `Sampler2`**：`rendertype_entity_translucent_emissive` 的 JSON 声明了
`Sampler2`，但编译出的程序里没有它。这是 **MC 自身**的问题 ——
在 Sodium 路径下同样出现，与本项目无关。

### 5.6 本轮新增的核对工具

| 文件 | 作用 |
|---|---|
| `native/tools/verify_run.py` | 对最新 `latest(N).log` 做逐项核对（版本 / 致命错误 / 降级 / 噪声 / 第三方） |
| `run-verify-run.ps1` | 无参包装（task runner 会剥离引号） |

**为什么需要它**：本轮做核对时发现，**每次都要手工回答同样四个问题**
（是不是新构建、有没有致命错误、降级情况、噪声是否恶化）。
固化成脚本后，每次用户回传日志只需一条命令，
且**「是不是新构建」这个判据可以显式登记**，不会再靠印象判断。

