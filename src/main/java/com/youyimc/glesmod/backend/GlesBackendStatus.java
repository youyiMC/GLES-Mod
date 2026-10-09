package com.youyimc.glesmod.backend;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.youyimc.glesmod.GLESMod;
import com.youyimc.glesmod.capability.GlesCapabilities;
import com.youyimc.glesmod.degrade.DegradeEvent;
import com.youyimc.glesmod.degrade.DegradeReason;

/**
 * 读取 native 后端写入的状态文件。
 *
 * <p><b>为什么不走 JNI</b>：native 库（{@code libgl_gles.so}）由启动器通过
 * {@code dlopen} 加载，与 mod 的 JVM 处于不同的库加载路径。若让 native 回调
 * Java，需要处理类加载器隔离与线程 attach 问题，复杂且脆弱。文件是两端都能
 * 稳定访问的通道。
 *
 * <p>文件位置：{@code <游戏工作目录>/glesmod/status.json}，或由环境变量
 * {@code GLESMOD_STATUS_FILE} 覆盖。
 *
 * <p>本类不依赖任何 JSON 库，使用正则解析。理由：文件格式由本项目完全控制，
 * 结构固定且扁平；引入 JSON 库只为解析一个小文件并不划算。解析失败时
 * 返回 {@link GlesCapabilities#INACTIVE}，不抛异常。
 *
 * @since 0.1.0
 */
public final class GlesBackendStatus {

    /** 状态文件相对路径（与 native 侧 GLESMOD_STATUS_RELPATH 保持一致）。 */
    public static final String DEFAULT_RELATIVE_PATH = "glesmod/status.json";

    /** 环境变量名（与 native 侧 GLESMOD_ENV_STATUS_FILE 保持一致）。 */
    public static final String ENV_STATUS_FILE = "GLESMOD_STATUS_FILE";

    /** 与 native 侧 GLESMOD_ABI_VERSION 对应。不匹配时拒绝采用该状态。 */
    public static final int EXPECTED_ABI_VERSION = 1;

    private final boolean loaded;
    private final int abiVersion;
    private final String glesVersion;
    private final List<DegradeEvent> degradeEvents;
    private final List<String> missingSymbols;

    /**
     * 被调用过的安全 stub 符号。
     *
     * <p><b>为什么必须是独立字段，而不能只打一条日志</b>：
     * 这些符号是「GLES 不提供，由我们以空实现导出」的函数。它们被调用意味着
     * <b>对应的功能其实没生效</b>，是判断「哪些功能静默失效」的唯一依据。
     *
     * <p>此前这里只在解析时打一条 WARN，没有存字段，也不出现在
     * {@link #diagnosticReport()} 里 —— 结果是：<b>用户回传的日志里
     * 根本看不到 stub 证据</b>，排查时无从下手。
     * 这是一个「解析了但没传出去」的缺陷，已在审核 R-12 时修复。
     */
    private final List<String> calledStubs;

    private final String sourcePath;
    private final String failureReason;

    private GlesBackendStatus(boolean loaded, int abiVersion, String glesVersion,
                              List<DegradeEvent> degradeEvents,
                              List<String> missingSymbols,
                              List<String> calledStubs,
                              String sourcePath, String failureReason) {
        this.loaded = loaded;
        this.abiVersion = abiVersion;
        this.glesVersion = glesVersion;
        this.degradeEvents = List.copyOf(degradeEvents);
        this.missingSymbols = List.copyOf(missingSymbols);
        this.calledStubs = List.copyOf(calledStubs);
        this.sourcePath = sourcePath;
        this.failureReason = failureReason;
    }

    // ------------------------------------------------------------------
    // 解析
    // ------------------------------------------------------------------

    /**
     * 从默认位置加载状态。
     *
     * @param gameDir 游戏工作目录（NeoForge 的 game directory）
     * @return 状态对象。文件不存在或解析失败时返回 loaded=false 的实例。
     */
    public static GlesBackendStatus load(Path gameDir) {
        String override = System.getenv(ENV_STATUS_FILE);
        Path path;
        if (override != null && !override.isBlank()) {
            path = Paths.get(override);
        } else {
            path = (gameDir == null ? Paths.get(".") : gameDir)
                    .resolve(DEFAULT_RELATIVE_PATH);
        }
        return loadFrom(path);
    }

    /** 从指定路径加载状态。 */
    public static GlesBackendStatus loadFrom(Path path) {
        if (path == null || !Files.isRegularFile(path)) {
            return new GlesBackendStatus(false, 0, "unknown",
                    List.of(), List.of(), List.of(), String.valueOf(path),
                    "状态文件不存在（native 后端未加载或未初始化）");
        }

        String text;
        try {
            text = Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException e) {
            return new GlesBackendStatus(false, 0, "unknown",
                    List.of(), List.of(), List.of(), path.toString(),
                    "读取失败: " + e.getMessage());
        }

        try {
            return parse(text, path.toString());
        } catch (RuntimeException e) {
            return new GlesBackendStatus(false, 0, "unknown",
                    List.of(), List.of(), List.of(), path.toString(),
                    "解析失败: " + e.getMessage());
        }
    }

    // 正则：足够应付本项目自产的扁平结构
    private static final Pattern P_ABI =
            Pattern.compile("\"abi_version\"\\s*:\\s*(\\d+)");
    private static final Pattern P_ACTIVE =
            Pattern.compile("\"active\"\\s*:\\s*(true|false)");
    private static final Pattern P_GLES =
            Pattern.compile("\"gles_version\"\\s*:\\s*\"([^\"]*)\"");
    private static final Pattern P_DEGRADE_LEVEL =
            Pattern.compile("\"degrade_level\"\\s*:\\s*(\\d+)");
    private static final Pattern P_CAP_BOOL =
            Pattern.compile("\"(multi_draw|compute_shader|persistent_mapping|instancing|indirect_draw)\"\\s*:\\s*(true|false)");
    private static final Pattern P_CAP_INT =
            Pattern.compile("\"(max_texture_units|max_draw_buffers|max_texture_size|max_samples|max_vertex_attribs)\"\\s*:\\s*(\\d+)");
    // 降级事件对象：{"reason": "X", "count": N, "detail": "..."}
    private static final Pattern P_EVENT =
            Pattern.compile("\\{\\s*\"reason\"\\s*:\\s*\"([^\"]+)\"\\s*,\\s*"
                    + "\"count\"\\s*:\\s*(\\d+)\\s*,\\s*"
                    + "\"detail\"\\s*:\\s*\"([^\"]*)\"\\s*}");

    /*
     * 符号列表的归属块。
     *
     * 【为什么必须先定位所属块，而不能直接找 "names" 数组】
     * missing_symbols 与 stub_symbols 都是 {"count": N, "names": [...]} 结构。
     * 若直接用 `"names"\s*:\s*\[...\]` 匹配，只会命中第一个（missing_symbols），
     * 导致 stub_symbols 被静默忽略——而 stub 恰恰是「哪些功能实际失效」的关键
     * 信息。因此先把整个块抓出来，再在块内取 names。
     */
    private static final Pattern P_BLOCK_MISSING =
            Pattern.compile("\"missing_symbols\"\\s*:\\s*\\{([^}]*)\\}");
    private static final Pattern P_BLOCK_STUB =
            Pattern.compile("\"stub_symbols\"\\s*:\\s*\\{([^}]*)\\}");

    /** 块内的 names 数组。 */
    private static final Pattern P_NAMES =
            Pattern.compile("\"names\"\\s*:\\s*\\[([^\\]]*)\\]");

    /** 最近若干次 GL 调用（诊断用，崩溃后定位问题）。 */
    private static final Pattern P_LAST_CALLS =
            Pattern.compile("\"last_calls\"\\s*:\\s*\\[([^\\]]*)\\]");

    private static GlesBackendStatus parse(String text, String path) {
        int abi = intOf(P_ABI, text, 0);
        if (abi != EXPECTED_ABI_VERSION) {
            return new GlesBackendStatus(false, abi, "unknown",
                    List.of(), List.of(), List.of(), path,
                    "ABI 版本不匹配：期望 " + EXPECTED_ABI_VERSION + "，实际 " + abi);
        }

        boolean active = "true".equals(boolOf(P_ACTIVE, text));
        String glesVersion = strOf(P_GLES, text, "unknown");
        int degradeLevel = intOf(P_DEGRADE_LEVEL, text, 1);

        String[] glesParts = glesVersion.split("\\.");
        int glesMajor = glesParts.length > 0 ? safeInt(glesParts[0]) : 0;
        int glesMinor = glesParts.length > 1 ? safeInt(glesParts[1]) : 0;

        // 能力位
        boolean multiDraw = false, compute = false, persistent = false;
        boolean instancing = false, indirect = false;
        Matcher mb = P_CAP_BOOL.matcher(text);
        while (mb.find()) {
            boolean v = "true".equals(mb.group(2));
            switch (mb.group(1)) {
                case "multi_draw" -> multiDraw = v;
                case "compute_shader" -> compute = v;
                case "persistent_mapping" -> persistent = v;
                case "instancing" -> instancing = v;
                case "indirect_draw" -> indirect = v;
                default -> { }
            }
        }

        int maxTexUnits = 8, maxDrawBuffers = 1, maxTexSize = 2048;
        int maxSamples = 0, maxAttribs = 16;
        Matcher mi = P_CAP_INT.matcher(text);
        while (mi.find()) {
            int v = safeInt(mi.group(2));
            switch (mi.group(1)) {
                case "max_texture_units" -> maxTexUnits = v;
                case "max_draw_buffers" -> maxDrawBuffers = v;
                case "max_texture_size" -> maxTexSize = v;
                case "max_samples" -> maxSamples = v;
                case "max_vertex_attribs" -> maxAttribs = v;
                default -> { }
            }
        }

        // 能力快照。native 未上报对外声称的 GL 版本，此处固定为 3.2：
        // MC 1.21.1 需要 GL 3.0 特性，声称 3.2 是安全且必要的最小值。
        GlesCapabilities caps = new GlesCapabilities(
                active, glesMajor, glesMinor, 3, 2, degradeLevel,
                multiDraw, compute, persistent, instancing, indirect,
                maxTexUnits, maxDrawBuffers, maxTexSize, maxSamples, maxAttribs);
        GlesCapabilities.publish(caps);

        // 降级事件：native 写的是原因名字符串，这里按名字反查枚举
        List<DegradeEvent> events = new ArrayList<>();
        Matcher me = P_EVENT.matcher(text);
        while (me.find()) {
            String name = me.group(1);
            long count = safeLong(me.group(2));
            String detail = me.group(3);
            DegradeReason reason = reasonByName(name);
            if (reason != null) {
                events.add(new DegradeEvent(reason, count, detail));
            }
        }

        // 缺失符号 / 被调用的 stub 符号。
        // 两者结构相同，必须按所属块分别提取（见 P_BLOCK_MISSING 的说明）。
        List<String> missing = arrayInBlock(P_BLOCK_MISSING, text);
        List<String> calledStubs = arrayInBlock(P_BLOCK_STUB, text);
        if (!calledStubs.isEmpty()) {
            GLESMod.LOGGER.warn("后端提供了 {} 个空实现（功能静默失效）: {}",
                    calledStubs.size(), calledStubs);
        }

        /*
         * 最近若干次 GL 调用。
         *
         * 只在检测到异常（缺失符号或 stub 被调用）时输出，避免正常启动时刷屏。
         * 崩溃后回看日志即可知道最后执行了哪些 GL 调用。
         */
        List<String> lastCalls = arrayOf(P_LAST_CALLS, text);
        if ((!missing.isEmpty() || !calledStubs.isEmpty()) && !lastCalls.isEmpty()) {
            GLESMod.LOGGER.warn("最近 GL 调用序列: {}", lastCalls);
        }

        return new GlesBackendStatus(true, abi, glesVersion, events, missing,
                calledStubs, path, null);
    }

    /**
     * 从形如 {@code "key": { "count": N, "names": [...] }} 的块中提取 names 数组。
     *
     * @param block 定位整个块的模式（必须含一个捕获组，内容为花括号内部）
     * @param text  状态文件全文
     * @return 符号名列表；块不存在或 names 为空时返回空列表
     */
    private static List<String> arrayInBlock(Pattern block, String text) {
        Matcher mb = block.matcher(text);
        if (!mb.find()) {
            return List.of();
        }
        return arrayOf(P_NAMES, mb.group(1));
    }

    /** 从形如 {@code "key": ["a", "b"]} 的位置提取字符串数组。 */
    private static List<String> arrayOf(Pattern p, String text) {
        List<String> out = new ArrayList<>();
        Matcher m = p.matcher(text);
        if (!m.find()) {
            return out;
        }
        for (String raw : m.group(1).split(",")) {
            String s = raw.trim().replace("\"", "");
            if (!s.isEmpty()) {
                out.add(s);
            }
        }
        return out;
    }

    private static DegradeReason reasonByName(String nativeName) {
        for (DegradeReason r : DegradeReason.values()) {
            if (r.name().equals(nativeName)) {
                return r;
            }
        }
        GLESMod.LOGGER.warn("未知的降级原因名: {}", nativeName);
        return null;
    }

    private static int intOf(Pattern p, String text, int fallback) {
        Matcher m = p.matcher(text);
        return m.find() ? safeInt(m.group(1)) : fallback;
    }

    private static String strOf(Pattern p, String text, String fallback) {
        Matcher m = p.matcher(text);
        return m.find() ? m.group(1) : fallback;
    }

    private static String boolOf(Pattern p, String text) {
        Matcher m = p.matcher(text);
        return m.find() ? m.group(1) : "false";
    }

    private static int safeInt(String s) {
        try {
            return Integer.parseInt(s.trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private static long safeLong(String s) {
        try {
            return Long.parseLong(s.trim());
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    // ------------------------------------------------------------------
    // 查询
    // ------------------------------------------------------------------

    /** 状态是否成功加载。 */
    public boolean isLoaded() {
        return loaded;
    }

    /** native 上报的 ABI 版本。 */
    public int getAbiVersion() {
        return abiVersion;
    }

    /** native 上报的 GLES 版本字符串，如 "3.2"。 */
    public String getGlesVersion() {
        return glesVersion;
    }

    /** 已发生的降级事件。 */
    public List<DegradeEvent> getDegradeEvents() {
        return degradeEvents;
    }

    /** 未能解析到实现的 GL 符号名。 */
    public List<String> getMissingSymbols() {
        return missingSymbols;
    }

    /**
     * 被调用过的安全 stub 符号（对应的 GL 功能实际未生效）。
     *
     * <p>审计 R-12 的关键输入：若此列表里出现某个「产生资源」类符号
     * （如 {@code glCreate*} / {@code glTextureStorage*} / {@code glBufferStorage}），
     * 说明调用方走到了它，必须按 {@code glBufferStorage} 的方式修复。
     *
     * @return 不可变列表，永不为 null
     */
    public List<String> getCalledStubs() {
        return calledStubs;
    }

    /** 状态文件路径，用于诊断。 */
    public String getSourcePath() {
        return sourcePath;
    }

    /** 加载失败原因；加载成功时为 null。 */
    public String getFailureReason() {
        return failureReason;
    }

    /**
     * 生成面向玩家的摘要。
     *
     * <p>只包含 {@link DegradeReason#userVisible()} 为 true 的事件，
     * 避免用技术细节淹没玩家。
     */
    public String playerSummary() {
        if (!loaded) {
            return "GLES 后端未激活（" + failureReason + "）。渲染由启动器的兼容层处理。";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("GLES 后端已激活，GLES ").append(glesVersion);
        List<DegradeEvent> visible = degradeEvents.stream()
                .filter(e -> e.reason().userVisible())
                .toList();
        if (visible.isEmpty()) {
            sb.append("，无功能降级。");
        } else {
            sb.append("，以下功能已降级：\n");
            for (DegradeEvent e : visible) {
                sb.append("  - ").append(e.describe()).append('\n');
            }
        }
        return sb.toString();
    }

    /**
     * 生成面向开发者的诊断报告，用于 issue 模板。
     */
    public String diagnosticReport() {
        StringBuilder sb = new StringBuilder();
        sb.append("=== glesmod 诊断报告 ===\n");
        sb.append("状态文件      : ").append(sourcePath).append('\n');
        sb.append("加载成功      : ").append(loaded).append('\n');
        if (!loaded) {
            sb.append("失败原因      : ").append(failureReason).append('\n');
            return sb.toString();
        }
        sb.append("ABI 版本      : ").append(abiVersion).append('\n');
        sb.append("GLES 版本     : ").append(glesVersion).append('\n');
        sb.append("能力快照      : ").append(GlesCapabilities.get()).append('\n');
        sb.append("降级事件 (")
          .append(degradeEvents.size()).append(" 类):\n");
        for (DegradeEvent e : degradeEvents) {
            sb.append("  0x").append(String.format("%04X", e.reason().code()))
              .append(' ').append(e.reason().name())
              .append(" x").append(e.count())
              .append("  ").append(e.detail()).append('\n');
        }
        sb.append("缺失符号 (").append(missingSymbols.size()).append("):\n");
        for (String s : missingSymbols) {
            sb.append("  ").append(s).append('\n');
        }
        /*
         * 被调用的 stub 符号。
         *
         * 与「缺失符号」语义不同，必须分开列出：
         *   缺失符号 = 期望 GLES 提供但没有 -> 指向缺陷
         *   被调用 stub = 我们主动提供的空实现被调用 -> 指向能力边界
         * 两者混在一起会让诊断失去方向。
         */
        sb.append("被调用的空实现 (").append(calledStubs.size()).append("):\n");
        for (String s : calledStubs) {
            sb.append("  ").append(s).append('\n');
        }
        return sb.toString();
    }
}
