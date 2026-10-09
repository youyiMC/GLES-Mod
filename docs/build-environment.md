# 构建环境说明

> 本文件记录**本机特有的构建约束**与绕过方式。
> 这些不是设计选择，而是环境限制导致的必要妥协。换机器时请重新评估。

---

## 1. 关键约束：NeoForged Maven 不可达

**现象**：`https://maven.neoforged.net/releases/` 连接被重置。

```
$ curl -I https://maven.neoforged.net/releases/
curl: (35) Recv failure: Connection was reset
```

PowerShell、curl、Python urllib 均失败；重试 3 次全部失败；无系统代理。
同一网络下 `repo1.maven.org`、`dl.google.com`、`github.com` 均正常。

**这不是 TLS 配置问题**，是网络层阻断。

### 1.1 替代源探测结果

| 源 | 结果 |
|---|---|
| `maven.neoforged.net` | ❌ 连接重置 |
| BMCLAPI `neoform-runtime` | ❌ 404（未镜像该 artifact） |
| BMCLAPI `neoforge` | ❌ 403（防盗链，仅 POM 可 HEAD） |
| 阿里云 `gradle-plugin` | ❌ HEAD 返回 200 但 GET 返回 404 |
| 腾讯云 `gradle-plugins` | ❌ 同样只代理部分制品 |
| `maven.parchmentmc.org` | ✅ 可用 |
| **本地 Gradle 缓存** | ✅ 可用（见下） |

### 1.2 采用的方案：使用缓存中已有的版本组合

关键发现是插件版本与 `neoform-runtime` 版本有绑定关系：

| moddev-gradle | 需要 neoform-runtime | 缓存状态 |
|---|---|---|
| 2.0.147 | 2.0.31 | ❌ 未缓存 |
| **2.0.146** | **2.0.27** | ✅ 已缓存 |

因此锁定 **`moddev-gradle 2.0.146`** + **`neoforge 21.1.241`**。

**代价**：NeoForge 版本从 21.1.251 降级到 21.1.241。

如果用户手机上的 NeoForge 是 21.1.251，mod 可能因版本范围不匹配而拒绝加载。
`neoforge.mods.toml` 中的 `versionRange="[${neo_version},)"` 已由模板生成，
上限开放，因此**向下兼容**（低版本 mod 可在高版本 NeoForge 上加载）通常成立。

### 1.3 恢复网络的步骤

若将来能访问 `maven.neoforged.net`：

1. 把 `build.gradle` 中 `moddev-gradle` 改回最新版（如 `2.0.147`）
2. 把 `gradle.properties` 中 `neo_version` 改回 `21.1.251`
3. 移除 `settings.gradle` 与 `build.gradle` 中的镜像仓库（或保留，无害）
4. 移除构建命令中的 `--offline`

### 1.4 手动预热缓存（无网络但需换版本时）

若需在离线环境使用某个版本，可先在**有网络的机器**上构建一次，
然后复制以下目录：

```
~/.gradle/caches/modules-2/files-2.1/net.neoforged/
~/.gradle/caches/neoformruntime/
```

---

## 2. 必须关闭 Gradle 配置缓存

`gradle.properties` 中设 `org.gradle.configuration-cache=false`。

**原因**：`moddev-gradle 2.0.146` 的 `CreateMinecraftArtifacts` 任务在 Gradle 9.2.1
下无法序列化，报错：

```
Configuration cache state could not be cached: field `__javaExecutor__` of task
`:createMinecraftArtifacts`: error writing value of type
'org.gradle.api.internal.provider.DefaultProperty'
```

这是插件与 Gradle 版本的兼容问题，非本项目代码导致。
代价是每次构建多花 3–5 秒做配置阶段。

---

## 3. 必须使用 `--offline`

`gradlew build` 必须加 `--offline`。

**原因**：不加时，`createMinecraftArtifacts` 会尝试联系 `maven.neoforged.net`
验证制品。由于连接被重置，Gradle 报出的却是一个**误导性错误**：

```
Error while evaluating property 'artifactManifestEntries' of task ':createMinecraftArtifacts'
```

这个错误完全没有提到网络问题，排查成本很高。加 `--offline` 后使用缓存，构建成功。

> 若将来网络恢复，应移除 `--offline`。

---

## 4. PowerShell 脚本必须为纯 ASCII

`native/build-native.ps1`、`fcl-plugin/build-plugin.ps1`、`build-all.ps1`
均刻意只使用 ASCII 字符。

**原因**：Windows PowerShell 5.1 用系统 ANSI 代码页（中文系统为 GBK）读取 `.ps1`。
含中文的脚本会被错误解码，导致语法错误，例如：

```
字符串缺少终止符: "。
赋值表达式无效。赋值运算符输入必须是能够接受赋值的对象
```

注释与字符串中的中文都会触发。若需要中文注释，请改用 `.psm1` 并加 BOM，
或使用 PowerShell 7+（默认 UTF-8）。

---

## 5. 调用 native 工具需特殊处理

PowerShell 5.1 会把**任何** stderr 输出包装为 `ErrorRecord`。
在 `$ErrorActionPreference = "Stop"` 下，即使工具成功执行且已用 `2>&1` 重定向，
脚本仍会中止。

`keytool` 与 `apksigner` 都会向 stderr 写正常进度信息，因此它们**总是**表现为失败。

**解决方式**：`fcl-plugin/build-plugin.ps1` 中的 `Invoke-NativeTool` 函数，
它临时放宽 `ErrorActionPreference`、把两个流都重定向到日志文件，
并且**只依据退出码**判断成败。

---

## 6. javac 需通过 @argfile 调用

直接把参数列表传给 `javac` 时，Windows PowerShell 会错误传递参数
（观察到一个多余的 `:` 被当作标志）：

```
javac.exe : 错误: 无效的标记: :
```

**解决方式**：把参数写入 `build/logs/javac.args`，用 `javac "@file"` 调用。
argfile 中的路径需使用正斜杠。

---

## 7. Android SDK / NDK

本机安装位置与版本：

| 组件 | 版本 |
|---|---|
| Android SDK | `C:\Android\Sdk` |
| cmdline-tools | latest（`11076708`） |
| build-tools | 34.0.0 |
| platforms | android-34 |
| CMake | 3.22.1 |
| NDK | 27.2.12479018 |

安装命令（供换机参考）：

```powershell
$env:ANDROID_HOME = "C:\Android\Sdk"
# cmdline-tools 需先手动下载解压到 $ANDROID_HOME\cmdline-tools\latest
$sm = "$env:ANDROID_HOME\cmdline-tools\latest\bin\sdkmanager.bat"
$sm --sdk_root=$env:ANDROID_HOME --licenses
$sm --sdk_root=$env:ANDROID_HOME "platform-tools" "platforms;android-34" `
    "build-tools;34.0.0" "cmake;3.22.1" "ndk;27.2.12479018"
```

---

## 8. 环境变量

构建脚本依赖以下变量（脚本内有默认值，但显式设置更可靠）：

| 变量 | 用途 | 默认值 |
|---|---|---|
| `JAVA_HOME` | Gradle 与 javac | `C:\Program Files\Java\jdk-21.0.12` |
| `ANDROID_HOME` | SDK / NDK 定位 | `C:\Android\Sdk` |

本机可用 JDK：`jdk-17`、`jdk-21.0.12`。
**必须用 21**，因为 MC 1.21.1 要求 Java 21。

---

## 9. 已知的环境相关坑

| 现象 | 原因 | 处理 |
|---|---|---|
| `git` 报 "not a git repository" | 仓库未初始化 | 见 §10 |
| `cd` 命令找不到 | PATH 被某个工具会话临时修改 | 重设 PATH 或换终端 |
| 终端命令无输出 | 某些长命令在 sync 模式下会阻塞 | 改用 async 模式 |
| `python` 无版本输出 | Windows Store 的 stub | 使用 `py` launcher |
| gradle wrapper 首次运行慢 | 需下载 Gradle 9.2.1（129 MB） | 一次性 |

---

## 10. 版本控制

**仓库尚未初始化 git。** 需要时：

```powershell
git init
git add -A
git commit -m "初始提交：GLES Mod 骨架与 native 后端"
```

`.gitignore` 已由模板提供，但需补充以下条目：

```
# 构建产物
build/native/
build/plugin/
native/build/
fcl-plugin/build/
fcl-plugin/debug.keystore

# 工具缓存
native/tools/.cache/

# 日志
*.log
```

> `fcl-plugin/debug.keystore` 是自签名调试密钥，**不应提交**。
> 它会在首次构建时自动生成。
