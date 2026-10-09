# licenses/

本目录存放**本项目自身许可证的完整构成**，以及指向官方原文的指引。

## 为什么 `LICENSE` 放在仓库根目录，而 GPL-3.0 全文放在这里

本项目采用 **LGPL-3.0-or-later**。

LGPL-3.0 正文的第 3 条以「并入」的方式引用 GPL-3.0：

> This version of the GNU Lesser General Public License incorporates
> the terms and conditions of version 3 of the GNU General Public License,
> supplemented by the additional permissions listed below.

因此**法律上完整的许可证文本 = LGPL-3.0 正文 + GPL-3.0 正文**。

但 GitHub 的自动许可证识别（licensee）是把仓库根目录的 `LICENSE` 与
**它内置的模板**做匹配的，而它的 `lgpl-3.0` 模板**只含 LGPL 正文**
（7652 字节，与 FSF 的 `lgpl-3.0.txt` 一致）。如果 `LICENSE` 里额外附上
GPL-3.0 全文（约 35 KB），识别就会失败并回退为 `NOASSERTION`
—— 仓库页面上不会显示许可证标识。

**取舍：**

| 方案 | 优点 | 缺点 |
|---|---|---|
| 根 `LICENSE` = 仅 LGPL 正文（**本仓库当前做法**） | GitHub 正确识别为 `LGPL-3.0`；与官方模板逐字节一致 | 根目录单独一份文本不足以自足 |
| 根 `LICENSE` = LGPL + GPL 全文 | 单文件法律自足 | GitHub 识别失败（`NOASSERTION`） |

本项目选择**前者**，并用本目录补齐法律完整性。

## 文件

| 文件 | 内容 | 来源 |
|---|---|---|
| `GPL-3.0.txt` | GNU General Public License v3.0 全文（LGPL-3.0 第 3 条所并入的条款） | <https://www.gnu.org/licenses/gpl-3.0.txt> |
| [`../LICENSE`](../LICENSE) | GNU Lesser General Public License v3.0 正文 | <https://www.gnu.org/licenses/lgpl-3.0.txt> |

## 如何获得完整文本

任取其一：

1. **合并**：把 `../LICENSE` 与 `GPL-3.0.txt` 依次拼接，即得完整许可文本。
2. **官方原文**：直接取
   <https://www.gnu.org/licenses/lgpl-3.0.txt> 与
   <https://www.gnu.org/licenses/gpl-3.0.txt>。

## 第三方成分

本项目的第三方成分、构建期依赖，以及**刻意排除在仓库之外**的素材
（BSL 光影包、Sodium、Sable 等），逐项列在
[`../THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md)。
