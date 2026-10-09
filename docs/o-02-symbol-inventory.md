# O-02：GL 符号清单与工作量量化

> 日期：2026-09-25
> 状态：✅ **已完成**
> 对应任务：O-02（原为「待整理」，评估 MVP 工作量）
> 数据来源：Khronos OpenGL-Registry `gl.xml` + Minecraft 1.21.1 客户端 jar

---

## 1. 结论摘要

**原版 Minecraft 1.21.1 只使用 89 个 GL 符号，其中 79 个（88.8%）GLES 3.2 原生支持，仅 5 个需要额外适配。**

这比初始估算（316 个符号）小了 **3.5 倍**。薄适配层路线不仅成立，而且工作量远低于预期。

| 指标 | 数值 |
|---|---|
| MC 实际引用的 GL 符号 | **89** |
| 属 GL 3.2 core profile | 84 |
| GLES 3.2 可直接满足 | **79（88.8%）** |
| 需要额外适配 | **5（5.6%）** |
| 需核实归属 | 5（均为 LWJGL API 名，非独立 C 符号） |
| 使用的 LWJGL 绑定类 | GL11、GL13、GL14、GL15、GL20、GL30 |

---

## 2. 关键发现

### 2.1 MC 只使用到 GL 3.0，不使用 3.1/3.2 特性

扫描结果显示 MC 引用的最高绑定类是 `GL30`，**没有引用 `GL31`、`GL32` 或更高版本**。

使用到的 GL 20/30 特性（Sodium 依赖的核心）：

```
GL 2.0（32 个）：着色器全套、glUniform* 各变体、glVertexAttribPointer、glScissor
GL 3.0（15 个）：VAO 全套、FBO 全套、glBlitFramebuffer、glVertexAttribIPointer
```

**这些全部是 GLES 3.0 就有的能力**，因此 ES 3.0 即可满足原版需求，ES 3.2 是充裕的。

### 2.2 原版不使用任何 ES 受限的高阶功能

| 功能 | 原版使用情况 |
|---|---|
| Multi-Draw（`glMultiDraw*`） | ❌ 不使用 |
| 计算着色器 | ❌ 不使用 |
| 间接绘制（Indirect） | ❌ 不使用 |
| 持久映射（`glMapBufferRange`） | ❌ 不使用 |
| 同步对象（`glFenceSync`） | ❌ 不使用 |
| 失效帧缓冲（`glInvalidateFramebuffer`） | ❌ 不使用 |
| 实例化渲染 | ❌ 不使用（原版靠逐次绘制） |
| 着色器存储缓冲（SSBO） | ❌ 不使用 |

**重大意义**：任务书中「P2-04 实现 Multi-Draw、计算着色器、持久映射的降级路由」这些高风险项，**对原版路径完全不是必需的**。它们只在使用 Sodium 时才需要——而 Sodium 会用，所以仍需实现，但可以推迟到阶段二，不阻塞 MVP。

### 2.3 全部 89 个符号清单

**GL 1.1（33 个）**

```
glBindTexture      glBlendFunc        glClear            glClearColor
glClearDepth*      glClearStencil     glColorMask        glDeleteTextures
glDepthFunc        glDepthMask        glDisable          glDrawElements
glDrawPixels*      glEnable           glGenTextures      glGetError
glGetInteger~      glGetString        glGetTexImage*     glGetTexLevelParameteri~
glLogicOp*         glPixelStorei      glPolygonMode*     glPolygonOffset
glReadPixels       glStencilFunc      glStencilMask      glStencilOp
glTexImage2D       glTexParameterf    glTexParameteri    glTexSubImage2D
glViewport
```

**GL 1.3（1 个）**：`glActiveTexture`

**GL 1.4（2 个）**：`glBlendEquation`、`glBlendFuncSeparate`

**GL 1.5（6 个）**：`glBindBuffer`、`glBufferData`、`glDeleteBuffers`、`glGenBuffers`、`glMapBuffer*`、`glUnmapBuffer`

**GL 2.0（32 个）**

```
glAttachShader     glBindAttribLocation   glCompileShader    glCopyTexSubImage2D
glCreateProgram    glCreateShader         glDeleteProgram    glDeleteShader
glDisableVertexAttribArray                glEnableVertexAttribArray
glGetAttribLocation                       glGetProgramInfoLog
glGetProgrami~     glGetShaderInfoLog     glGetShaderi~      glGetUniformLocation
glLinkProgram      glScissor              glUniform1fv       glUniform1i
glUniform1iv       glUniform2fv           glUniform2iv       glUniform3fv
glUniform3iv       glUniform4fv           glUniform4iv       glUniformMatrix2fv
glUniformMatrix3fv glUniformMatrix4fv     glUseProgram       glVertexAttribPointer
```

**GL 3.0（15 个）**

```
glBindFramebuffer  glBindRenderbuffer     glBindVertexArray
glBlitFramebuffer  glCheckFramebufferStatus
glDeleteFramebuffers                      glDeleteRenderbuffers
glDeleteVertexArrays                      glFramebufferRenderbuffer
glFramebufferTexture2D                    glGenFramebuffers
glGenRenderbuffers glGenVertexArrays      glRenderbufferStorage
glVertexAttribIPointer
```

标记说明：
- `*` = 需要额外适配（见 §3）
- `~` = LWJGL API 名，非独立 C 符号（见 §4）

---

## 3. 需要额外适配的 5 个符号

全部由 `com.mojang.blaze3d.platform.GlStateManager` 的私有包装方法引用。已通过调用链追踪确认实际使用场景：

| 符号 | GL 语义 | GLES 3.2 状态 | 适配方案 | 风险 |
|---|---|---|---|---|
| `glClearDepth` | 设置深度清屏值（double） | ES 只有 `glClearDepthf`（float） | 转 float 调用 `glClearDepthf` | **极低** |
| `glMapBuffer` | 映射整个缓冲区 | ES 只有 `glMapBufferRange` | `glMapBufferRange(target, 0, size, access)` | **低** |
| `glLogicOp` | 逻辑运算 | ES 无 | 忽略 + 记降级事件 | **极低** |
| `glPolygonMode` | 面模式（wireframe） | ES 无 | 仅 `GL_FILL` 可忽略；其他降级 | **极低** |
| `glGetTexImage` | 回读纹理像素 | ES 无 | 需绑 FBO + `glReadPixels` | **低**（已确认非关键路径） |

### 3.1 调用链追踪结果（已执行）

用 `native/tools/trace_restricted_calls.py` 追踪，结果如下：

| 包装方法 | 调用者 | 判断 |
|---|---|---|
| `_clearDepth` | `RenderSystem.clearDepth`、`RenderSystem.setupDefaultState`、`ezv.b` | 初始化时调用，非每帧 |
| `_logicOp` | `RenderSystem.logicOp` | 对外暴露的 API，原版不主动调用 |
| `_polygonMode` | `RenderSystem.polygonMode` | 对外暴露的 API，原版不主动调用 |
| `_glMapBuffer` | `RenderSystem$a.c` | 内部工具路径 |
| `_getTexImage` | `faj.a` | **纹理回读路径** |
| `_glDrawPixels` | `faj.f` | **图像写入路径** |

**关键确认**：`faj` 经字符串常量分析确认为 **`NativeImage`**（引用 `TextureUtil`、`STBImage`、`STBImageWrite`，含 `"Could not write image to the PNG file"`、`"Glyph bitmap of size..."` 等字符串）。

因此 `glGetTexImage` 与 `glDrawPixels` **仅在图像/纹理回读场景使用**（如截图、图像加载、字形位图处理），**不在每帧渲染主循环中**。

**结论：这 5 个符号的实现优先级可降为 P2，不影响 MVP 的渲染主路径。** 最坏情况下先 stub 为「记录降级事件 + 无操作」，即可让游戏跑起来。

### 3.2 实现成本评估

| 符号 | 预估代码量 | 优先级 |
|---|---|---|
| `glClearDepth` | ~10 行 | P1 |
| `glMapBuffer` | ~15 行 | P1 |
| `glLogicOp` | ~5 行（stub + 降级） | P2 |
| `glPolygonMode` | ~10 行（区分 `GL_FILL`） | P2 |
| `glGetTexImage` | ~60 行（FBO 回读） | P2 |
| `glDrawPixels` | ~20 行（stub + 降级警告） | P3 |

**总计约 120 行代码，其中 MVP 必需部分仅 ~25 行。**

---

## 4. 需核实的 5 个符号（实为 LWJGL API 名）

| LWJGL 方法 | 实际对应的 C 符号 | 说明 |
|---|---|---|
| `glGetInteger` | `glGetIntegerv` | LWJGL 的类型安全重载，底层仍是 `glGetIntegerv` |
| `glGetProgrami` | `glGetProgramiv` | 同上 |
| `glGetShaderi` | `glGetShaderiv` | 同上 |
| `glGetTexLevelParameteri` | `glGetTexLevelParameteriv` | 同上 |
| `glDrawPixels` | `glDrawPixels` | MC 保留了调用点，但 core profile 下不可用 |

前 4 个是 LWJGL 的方法重载命名（Java 侧按返回类型区分），**native 层只需导出标准 C 名**。

`glDrawPixels` 已确认（见 §3.1）：调用者是 `NativeImage`，属图像处理路径，非渲染主循环。core profile 下该函数不存在，**建议 stub 为记录降级事件 + 无操作**。

---

## 5. 对任务书的影响

### 5.1 需要下修的工作量预期

| 项 | 原预期 | 修正后 |
|---|---|---|
| native 符号导出数量 | 316（GL 3.2 core 全集） | **89** |
| 需额外实现的符号 | 约 82 | **5** |
| MVP 是否依赖 Multi-Draw 降级 | 是（P2-04 为 P0） | **否**（原版不用，可推迟到阶段二） |
| MVP 是否依赖计算着色器降级 | 是（P2-04 为 P0） | **否**（同上） |
| 是否必须支持 ES 3.2 | 是 | **否**，ES 3.0 即可满足原版 |

### 5.2 建议的调整

1. **任务书 P2-04 优先级下修**：Multi-Draw / 计算着色器 / 持久映射的降级路由，从 P0 改为 P1，且明确它们**只服务于 Sodium 路径**，不阻塞 MVP。

2. **符号导出清单以本文件为准**：native 层只导出这 89 个（+ 少量防御性补充），不追求 GL 3.2 core 全集。这大幅降低 P1-04 工作量。

3. **ES 版本目标可放宽**：MVP 目标可为 ES 3.0，ES 3.2 作为增强。这扩大了设备兼容范围（R-11 风险降低）。

4. **`glGetTexImage` 需先确认使用场景**：若在关键路径，需要实现 FBO 回读；若在异常处理路径，可直接降级。

---

## 6. 复现方法

所有数据可由 `native/tools/` 下的脚本复现：

```bash
cd native/tools

# 1. 下载 Khronos 官方注册表
curl -o .cache/gl.xml https://raw.githubusercontent.com/KhronosGroup/OpenGL-Registry/main/xml/gl.xml

# 2. 生成桌面 GL 3.2 core 符号集
py extract_gl_symbols.py --gl-xml .cache/gl.xml --api gl --version 3.2 --profile core --txt-out gl_3.2_core.txt

# 3. 生成 GLES 3.2 符号集
py extract_gl_symbols.py --gl-xml .cache/gl.xml --api gles2 --version 3.2 --profile none --txt-out gles_3.2.txt

# 4. 差集分析（理论工作量）
py compare_symbols.py --gl gl_3.2_core.txt --gles gles_3.2.txt --json-out symbol_diff.json

# 5. 扫描 MC 实际使用（真实工作量）
py scan_mc_gl_usage.py --jar <minecraft_client.jar> \
    --gl-symbols gl_3.2_core.txt --gles-symbols gles_3.2.txt --json-out mc_gl_usage.json
```

MC jar 位于 Gradle 缓存：
`~/.gradle/caches/neoformruntime/artifacts/minecraft_1.21.1_client.jar`

---

## 7. 工具说明

| 脚本 | 用途 |
|---|---|
| `extract_gl_symbols.py` | 从 `gl.xml` 提取指定版本/profile 的 GL 或 GLES 命令集，按维度分类 |
| `compare_symbols.py` | 计算桌面 GL core 与 GLES 的差集，内置已知映射关系表 |
| `scan_mc_gl_usage.py` | 精确解析 MC jar 常量池的 `Methodref`，得到实际调用的 GL 符号及调用方 |
| `trace_restricted_calls.py` | 追踪受限符号的调用链，判断是否在关键路径 |
| `check_symbols.sh` | （待实现，P1-04）检测本项目 `.so` 相对目标符号集的覆盖率 |

---

## 8. 下一步

1. **进入 P1-01** 工程基线改造（清理模板示例代码、配置许可证、建目录）。
2. 将本文件的 89 个符号清单作为 P1-04 的实现依据。
3. `glGetTexImage` / `glDrawPixels` 在 P1-04 中先 stub，标注为 P2 补齐。
