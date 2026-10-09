# Third-Party Notices

本文件记录 glesmod 项目**使用的第三方成分**及其许可证，以及**不应被再分发**的内容。

适用对象：NeoForge 模组（`glesmod-*.jar`）、FCL 渲染器插件（`glesmod-renderer-plugin.apk`）、
native 共享库（`libgl_gles.so`）。

---

## 0. 本项目自身的许可证

glesmod 采用 **LGPL-3.0-or-later**，正文见仓库根目录 [`LICENSE`](LICENSE)。

```
SPDX-License-Identifier: LGPL-3.0-or-later
```

### 0.1 关于 `LICENSE` 的形态（重要说明）

`LICENSE` 与 **GitHub 官方的 `lgpl-3.0` 识别模板逐字节一致**（7652 字节，
即 FSF 的 `lgpl-3.0.txt`）。这一点是刻意为之：GitHub 的许可证识别是拿文件内容
与它自己的模板做匹配的，任何偏离都可能导致仓库被标记为 `NOASSERTION`
（"找到了 LICENSE 但未识别出"）。

**但请注意**：LGPL-3.0 正文第 3 条是以「并入 GPL-3.0 条款」的方式引用 GPL 的：

> This version of the GNU Lesser General Public License incorporates
> the terms and conditions of version 3 of the GNU General Public License,
> supplemented by the additional permissions listed below.

因此**完整的 `LICENSE` 文本实际还需包含 GPL-3.0 全文**。GitHub 的模板只含
LGPL 正文，这是它的取舍；为兼顾「法律完整性」与「机器可识别」，本项目：

- **`LICENSE`** 采用 GitHub 模板形态（保证 SPDX 被正确识别为 `LGPL-3.0`）；
- **GPL-3.0 全文**以两种方式提供，任取其一即可获得：

  - 官方原文：<https://www.gnu.org/licenses/gpl-3.0.txt>
  - 仓库内副本：`licenses/GPL-3.0.txt`

> 如果你更希望 `LICENSE` 直接包含 GPL-3.0 全文（法律上更自足，但会导致
> GitHub 识别回退为 `NOASSERTION`），可以合并这两份文本 —— 这是**取舍**，
> 当前选择的是「识别正确」优先。

**一个必须知道的识别局限**：GitHub 的 `lgpl-3.0` 模板只能识别出
`LGPL-3.0`，**无法区分** `LGPL-3.0-only` 与 `LGPL-3.0-or-later` ——
因为两者的正文完全相同，差别只在项目如何声明「or later」。
因此仓库页面上会显示 `LGPL-3.0`，而本项目的**实际授权**是
`LGPL-3.0-or-later`，以本文件与本仓库各处 `SPDX-License-Identifier` 的
声明为准。

---

## 1. 随产物分发的第三方成分

以下内容**会进入**我们分发的产物，因此必须声明。

### 1.1 Minecraft Development Kit (MDK) 模板文件

| 项 | 内容 |
|---|---|
| 文件 | `build.gradle`、`settings.gradle`、`gradle.properties`、`gradlew`、`gradlew.bat`、`gradle/wrapper/*`、`.gitattributes` 等 |
| 来源 | [github.com/NeoForged/MDK](https://github.com/NeoForged/MDK) |
| 许可证 | **MIT**，Copyright (c) 2023 NeoForged project |
| 全文 | 见仓库根目录 [`TEMPLATE_LICENSE.txt`](TEMPLATE_LICENSE.txt) |
| 说明 | MIT 只覆盖**模板文件本身**，不覆盖本项目新增的代码。两者不冲突。 |

### 1.2 Minecraft GLSL include 工具函数 ⚠️

| 项 | 内容 |
|---|---|
| 位置 | `native/src/shader.c` → `MOJ_FOG_GLSL` / `MOJ_LIGHT_GLSL` / `MOJ_MATRIX_GLSL` / `MOJ_PROJECTION_GLSL` |
| 来源 | Minecraft: Java Edition 的内置着色器 include（`fog.glsl`、`light.glsl`、`matrix.glsl`、`projection.glsl`） |
| 版权 | Copyright Mojang AB / Microsoft |
| 规模 | 4 个工具函数，合计约 30 行 |

**为什么存在**：Minecraft 使用自己的预处理指令 `#moj_import <fog.glsl>`，而 **GLSL 从未支持该指令**。
若把 `#moj_import` 原样交给驱动，ES 编译器会直接报 `malformed preprocessor directive`。
因此本库内嵌了这 4 个文件的等价实现，以便在遇到该指令时就地展开。

**实测结论（重要）**：在真机上确认，**Minecraft 在把源码交给 GL 之前就会自行展开 `#moj_import`**，
本库 `glShaderSource` 收到的源码里**已经没有该指令**（见 `native/src/shader.c` 中
`expand_moj_imports` 附近的注释）。因此这段内嵌代码**实际上不被触发**，属于防御性保留。

**合规状态**：PENDING。这段代码源自 Minecraft，其再分发受
[Minecraft EULA](https://www.minecraft.net/eula) 与
[Minecraft Brand and Asset Usage Guidelines](https://www.minecraft.net/en-us/usage-guidelines) 约束。
按现有实测结论，它既不被触发、也不是本库功能所必需。

**建议处置**（见 §4 待办 T-1）：移除这 4 个内嵌常量，改为遇到未展开的 `#moj_import` 时
输出诊断并降级。这样可彻底消除本项合规疑点，且不影响实测行为。

---

## 2. 构建期依赖（**不**随产物分发）

以下仅用于构建/测试，不会进入任何分发产物。

| 依赖 | 用途 | 许可证 |
|---|---|---|
| NeoForge 21.1.241 / ModDevGradle 2.0.146 | 模组构建与反编译 | LGPL-2.1-only |
| Parchment 2024.11.17 | 参数名映射 | CC0-1.0 / MIT |
| Gradle 8.x | 构建系统 | Apache-2.0 |
| Android SDK Build-Tools 34.0.0（`aapt2`/`d8`/`zipalign`/`apksigner`） | 打包插件 APK | Apache-2.0 |
| Android NDK 27.2.12479018（Clang、CMake、Ninja、`glslc`） | 编译 `libgl_gles.so`；`glslc` 用于离线校验 GLSL ES | Apache-2.0 / BSD-3-Clause / LLVM |
| JDK 21 | 编译 Java | GPL-2.0-with-classpath-exception |

> `glslc` 只在**开发期离线校验**着色器时调用，不参与运行时，也不随产物分发。

---

## 3. 测试素材（**不**进入代码仓库）

以下内容存在于本地开发目录，但**已被 `.gitignore` 排除**，不随仓库分发。
列出它们是为了说明它们**不构成**本项目的一部分。

| 内容 | 性质 | 为何排除 |
|---|---|---|
| `BSL_v10.1.8.zip`、`bsl3/`~`bsl7/`、`bslsrc/` | **BSL Shaders** 光影包及其导出/转换产物 | 第三方版权作品，无再分发权 |
| `patched_shaders/`、`shader_bsl/`、`bsl_patched/`、`reconv*/` | Iris 导出的着色器与中间产物 | 同上（内容源自 BSL） |
| `shader_dump/` | 从 MC jar 提取的着色器与 `ShaderInstance.java` | 含 **Mojang 代码**，不可再分发 |
| `native/tools/.cache/` | 从 NeoForge jar 提取的源码 | 含 NeoForge 代码（LGPL-2.1-only） |
| `native/tools/fixtures/sodium_chunk_0.8.13.vert` | Sodium 0.8.13 着色器的**逐字副本** | **Polyform Shield License（非 FOSS）**，逐字副本不可再分发；可用 `fetch_sodium_shaders.ps1` 随时重新获取 |
| `native/src/shader.c.bak` | 旧版源码备份 | 陈旧冗余，无保留价值 |

> 相关测试**方法**（而不是素材）已记录在 `docs/test-guide.md`，
> 任何人都可以用自己合法获得的 Minecraft 与光影包复现测试。

### 3.1 测试夹具的来源说明

`native/tools/fixtures/` 下的回归夹具按来源分为三类，
**逐项清单与授权状态见 [`native/tools/fixtures/README.md`](native/tools/fixtures/README.md)**：

| 类别 | 数量 | 授权状态 |
|---|---|---|
| A. 原创最小复现件 | 7 | 本项目 LGPL-3.0-or-later ✅ |
| A2. 源自 Flywheel 的夹具 | 3 | ⚠️ **待决策**，见下 |
| B. 真机产物片段（来源为 BSL 光影包） | 6 | ⚠️ **待决策**，见 fixtures/README.md 的「授权疑点」 |
| B2. 真机产物片段（来源为 Simulated） | 6 | ✅ 来源为设备自产 dump，仅保留触发缺陷的最小构造 |
| C. 第三方逐字副本（Sodium） | 1 | 已从 git 排除 ✅ |

**关于 A2 类（Flywheel 夹具）—— 已补全版权声明 ✅**

| 文件 | 性质 | 上游 | 上游许可证 | 处置 |
|---|---|---|---|---|
| `flywheel_diffuse.frag` | **逐字副本**（verbatim copy） | Engine-Room/Flywheel `assets/flywheel/flywheel/internal/diffuse.glsl` | **MIT**，Copyright (c) 2021-2024 Jozufozu | ✅ 已在文件头附**完整 MIT 许可全文与版权行** |
| `flywheel_int_macro.frag` | 忠实还原（faithful reduction），非逐字 | 同上 `flywheel/internal/wavelet.glsl` | 同上 | ✅ 已补版权行与许可摘要 |
| `flywheel_wavelet_int.frag` | 忠实还原 | 同上 | 同上 | ✅ 已补版权行与许可指引 |

**Flywheel 的许可证全文**（`https://github.com/Engine-Room/Flywheel`，`LICENSE.md`，
经 GitHub API 核实为 MIT）：

```
Copyright (c) 2021-2024 Jozufozu

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

> 三个文件都是全量列举仓库文件时才发现的 —— 它们此前既不在
> `fixtures/README.md` 的分类表里，也不在本文件的清单里。**现已如实补记。**


**关于 B2 类**：`fixtures/device/device_*.frag|vert` 是从**我们自己设备**的
`glesmod/native.log` 里转储出来的着色器源码（由本模组
`dump_shader_source_on_failure()` 在编译失败时写出）。它们对应
`simulated:redstone_accumulator/diode` 与 `simulated:contraption_diagram/outline_diagram`
两个着色器。之所以收录，是因为**它们正是缺陷 A/B 的真机证据**，
没有它们就无法复现那次修复。

⚠️ **风险提示**：这些是 Simulated（Create Aeronautics 内置）的着色器源码片段，
其上游为 `dev.simulated_team.simulated`。取回的 dump 是**完整着色器**
（约 105~1300 行），**不只是最小构造**。这一点与 B 类不同，需要注意：
若要求仓库中不出现任何第三方着色器源码，则应把这 6 个文件一并排除，
代价是缺陷 A/B 的回归门禁失去真机素材（届时需改用人造等价夹具）。

**关于 B 类**：这些夹具是从我们**自己设备**上导出的着色器中摘出的**最小片段**
（仅保留触发类型错误所必需的 1~3 行构造，不含任何着色算法或光影效果实现）。
由于 BSL Shaders 未公开发布明确许可证，其衍生片段的再分发存在不确定性。
**建议的处置方案与备选方案已列在 `fixtures/README.md`，等待项目作者决策。**


---

## 4. 待办

| ID | 事项 | 优先级 |
|---|---|---|
| **T-1** | 移除 `shader.c` 中内嵌的 4 个 Mojang GLSL 工具函数（见 §1.2），改为诊断+降级 | 中 |
| **T-2** | 决定 B 类夹具（源自 BSL 的最小片段）的处置方式：改写为原创 / 保留并声明 / 一并排除。选项与利弊见 `native/tools/fixtures/README.md` | 中 |
| ~~**T-4**~~ | ~~`flywheel_diffuse.frag` 是 Flywheel 的逐字副本，需补版权与许可声明~~ | ✅ **已解决**：三个 Flywheel 夹具均已附 MIT 版权行；逐字副本另附完整许可全文 |
| **T-5** | 决定 B2 类夹具（来自真机 dump 的 Simulated 完整着色器）的处置方式：保留 / 裁剪为最小构造 / 排除 | 中 |
| T-3 | 若将来引入任何第三方库，在此文件补记其许可证 | — |

### 4.1 已完成的合规修正记录

| 日期 | 事项 |
|---|---|
| 2026-10-09 | 新建 `TEMPLATE_LICENSE.txt`（MDK 的 MIT 许可）。本文件 §1.1 与 `.gitignore` 一直引用它，但**文件此前并不存在**。 |
| 2026-10-09 | 补记 A2 类（Flywheel 夹具）并附 MIT 版权与许可全文，关闭 T-4。 |
| 2026-10-09 | 替换 `LICENSE` 为 FSF **当前**官方文本。原文件是旧版排印：三处 URL 仍为 `http://`，且 `why-not-lgpl.html` 的路径已变（旧 `philosophy/`，新 `licenses/`）。这导致 GitHub 的许可证识别返回 `NOASSERTION`（未能匹配任何模板）。**授权内容本身从未改变**，仍是 LGPL-3.0-or-later，只是排印过时。 |


---

## 5. 商标与声明

- **Minecraft** 是 Mojang Studios / Microsoft 的商标。本项目为**非官方**第三方项目，
  与 Mojang Studios 及 Microsoft **无任何关联**，亦未获其认可或赞助。
- 本项目**不包含** Minecraft 的游戏代码或资源。构建时需要用户自行提供合法的 Minecraft 副本
  （由 NeoForge/ModDevGradle 在开发环境中获取）。
- **NeoForge** 是 NeoForged 项目的商标。
- **Iris**、**Sodium**、**BSL Shaders** 等名称归其各自作者所有；本项目仅与其做运行时兼容，
  不复制其代码。

---

## 6. 我们的承诺

1. 本项目**只做运行时接口适配**（GL → GLES 符号映射与转发），**不复制** GL4ES / MobileGlues /
   Zink 的代码。
2. 上表 §3 中被排除的第三方素材**从未**、也**不会**进入 Git 历史。
3. 除 §1.2 已明示的例外外，`native/`、`src/`、`fcl-plugin/` 下的代码均为本项目原创。

如发现本文件有遗漏或错误，请提 issue —— 我们宁可多声明，也不少声明。
