package com.youyimc.glesmod;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import com.youyimc.glesmod.backend.GlesBackendStatus;
import com.youyimc.glesmod.capability.GlesCapabilities;
import com.youyimc.glesmod.compat.CompatDetector;
import com.youyimc.glesmod.degrade.DegradeEvent;

import net.minecraft.client.Minecraft;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.event.lifecycle.FMLClientSetupEvent;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.gui.ConfigurationScreen;
import net.neoforged.neoforge.client.gui.IConfigScreenFactory;

/**
 * 客户端入口。
 *
 * <p>在客户端初始化时读取 native 后端状态，并输出：
 * <ul>
 *   <li>玩家可读的摘要（后端是否激活、哪些功能降级）</li>
 *   <li>开发者诊断报告（能力快照、降级事件、缺失符号）</li>
 *   <li>兼容模组检测结果（Sodium / Embeddium）</li>
 * </ul>
 *
 * <p>此外还会在游戏运行期间<b>持续轮询</b>状态文件，把启动之后新产生的降级事件
 * 推送到日志。见 {@link #pollBackendStatus()}。
 *
 * @since 0.1.0
 */
@Mod(value = GLESMod.MODID, dist = Dist.CLIENT)
@EventBusSubscriber(modid = GLESMod.MODID, value = Dist.CLIENT)
public class GLESModClient {

    /** 缓存最近一次加载的状态，供其他模组或调试命令查询。 */
    private static volatile GlesBackendStatus status;

    /**
     * 启动时已经报告过的降级事件详情，用于避免运行期轮询重复刷屏。
     *
     * <p>按 detail 字符串去重而非按「原因码」：同一个原因码（如
     * {@code UNSUPPORTED_FUNCTION}）可能对应许多互不相同的问题，
     * 按码去重会把真正的新问题一起吞掉。
     */
    private static final Set<String> REPORTED_DEGRADES = new java.util.HashSet<>();

    /** 轮询节流：每 N 次客户端 tick 检查一次，避免每帧读文件。 */
    private static final int POLL_INTERVAL_TICKS = 100;
    private static int pollTicks;

    public GLESModClient(ModContainer container) {
        container.registerExtensionPoint(IConfigScreenFactory.class, ConfigurationScreen::new);
    }

    @SubscribeEvent
    static void onClientSetup(FMLClientSetupEvent event) {
        event.enqueueWork(GLESModClient::reportBackendStatus);
    }

    /**
     * 运行期轮询 native 状态文件，把新出现的降级事件写入日志。
     *
     * <p><b>为什么必须有这个：</b>本模组诊断报告的打印时机是
     * {@link FMLClientSetupEvent}，即游戏启动阶段。但许多问题发生在<b>之后</b> ——
     * 典型例子：Iris 在玩家点「应用光影」时才去建 FBO，失败时已经比启动晚了几十秒。
     * 而 native 侧只有在 {@code glCheckFramebufferStatus} 看到不完整 FBO 时
     * 才会写下那条关键的附件明细。
     *
     * <p>结果是：诊断信息写进了 {@code status.json}，却<b>永远没有机会被打印</b>，
     * 排查者只能看到 Iris 自己那句「Status: 36055」。
     *
     * <p>这不仅是一个便利问题。本项目的 stderr 通道在部分启动器（已确认 ZalithLauncher2）
     * 下完全不被收集，因此 {@code status.json} 是本模组诊断信息的<b>唯一</b>可靠出口。
     * 只有把它定期转成日志，「让证据可见」才真正成立。
     *
     * <p>节流到每 {@value #POLL_INTERVAL_TICKS} tick 一次（约 5 秒），
     * 读一个几 KB 的 JSON 文件的开销可以忽略。
     */
    @SubscribeEvent
    static void onClientTick(ClientTickEvent.Post event) {
        if (!Config.ENABLED.getAsBoolean()) {
            return;
        }
        if (!Config.POLL_STATUS.getAsBoolean()) {
            return;
        }
        if (++pollTicks < POLL_INTERVAL_TICKS) {
            return;
        }
        pollTicks = 0;
        pollBackendStatus();
    }

    private static void pollBackendStatus() {
        GlesBackendStatus fresh;
        try {
            fresh = GlesBackendStatus.load(resolveGameDir());
        } catch (Throwable t) {
            // 轮询绝不能影响游戏运行；失败就当这一轮没读到
            GLESMod.LOGGER.debug("轮询后端状态失败: {}", t.toString());
            return;
        }

        if (!fresh.isLoaded()) {
            return;
        }
        status = fresh;

        /*
         * 只报告「此前没报告过」的降级事件。
         * 首次轮询时把启动阶段已打印过的一并记入，避免重复。
         */
        List<String> novelties = new ArrayList<>();
        for (DegradeEvent e : fresh.getDegradeEvents()) {
            String key = e.reason().name() + "|" + e.detail();
            if (REPORTED_DEGRADES.add(key)) {
                novelties.add(e.reason().name() + " x" + e.count() + "  " + e.detail());
            }
        }

        if (!novelties.isEmpty()) {
            GLESMod.LOGGER.warn("运行期新增降级事件 ({}):", novelties.size());
            for (String s : novelties) {
                GLESMod.LOGGER.warn("  {}", s);
            }
        }

        /*
         * 空实现（stub）被调用同样要看运行期 —— 只有进入世界、用了某个模组功能后
         * 才可能踩到。这是判断「哪些 GL 功能实际没生效」的唯一依据，
         * 因此用 WARN 而不是 debug。
         */
        if (!fresh.getCalledStubs().isEmpty()) {
            GLESMod.LOGGER.warn("后端提供了 {} 个空实现且已被调用（对应 GL 功能实际未生效）: {}",
                    fresh.getCalledStubs().size(), fresh.getCalledStubs());
        }
    }

    private static void reportBackendStatus() {
        if (!Config.ENABLED.getAsBoolean()) {
            GLESMod.LOGGER.info("模组已禁用，跳过后端状态检查。");
            return;
        }

        Path gameDir = resolveGameDir();
        GlesBackendStatus loaded = GlesBackendStatus.load(gameDir);
        status = loaded;

        // 玩家摘要始终输出：这是「降级功能有明确日志」的验收要求
        GLESMod.LOGGER.info("{}", loaded.playerSummary());

        if (!loaded.isLoaded()) {
            if (Config.WARN_IF_INACTIVE.getAsBoolean()) {
                GLESMod.LOGGER.warn(
                        "未检测到 GLES 后端状态文件（{}）。原因：{}",
                        loaded.getSourcePath(), loaded.getFailureReason());
                GLESMod.LOGGER.warn(
                        "这通常意味着：1) 未在 FCL 中选择 GLES Mod 渲染器；"
                        + " 2) 插件未安装；3) 游戏启动时 native 库尚未初始化。");
                GLESMod.LOGGER.warn("渲染将走启动器的兼容层（GL4ES / ANGLE），功能正常但性能较低。");
                GLESMod.LOGGER.warn(
                        "排查建议：用 adb logcat -s GLESMod:* 查看 native 层日志。"
                        + " 若完全没有任何 GLESMod 输出，说明 native 库未被加载；"
                        + " 若看到「能力探测连续失败」，说明 EGL 上下文未就绪。");
            }
            return;
        }

        GlesCapabilities caps = GlesCapabilities.get();
        GLESMod.LOGGER.info("后端能力: {}", caps);

        /*
         * 被调用的空实现（stub）—— 必须显式告警，不能只放在 debug 级报告里。
         *
         * 这一项是判断「哪些 GL 功能实际没生效」的唯一依据：GLES 不提供的符号
         * 由我们以空实现导出（否则 LWJGL 解析失败会抛 NPE 崩溃），
         * 所以它们一旦被调用，对应功能就是静默失效。
         *
         * 用 WARN 而非 INFO：这是需要用户注意的异常状态，不是常规信息。
         * 此前它只存在于诊断报告（且未存字段），导致日志里看不到任何 stub 证据，
         * 排查时只能靠推断 —— 已修复。
         */
        if (!loaded.getCalledStubs().isEmpty()) {
            GLESMod.LOGGER.warn("后端提供了 {} 个空实现且已被调用（对应 GL 功能实际未生效）: {}",
                    loaded.getCalledStubs().size(), loaded.getCalledStubs());
            GLESMod.LOGGER.warn("若其中包含 glCreate*/glTextureStorage*/glBufferStorage 这类"
                    + "「产生资源」的符号，请提交 issue 并附上完整日志。");
        }

        if (Config.VERBOSE_LOG.getAsBoolean()) {
            // 诊断报告用 debug 级别：信息量大，默认不刷屏
            GLESMod.LOGGER.info("--- 诊断报告 ---\n{}", loaded.diagnosticReport());
        }

        /*
         * 把启动时已打印的降级事件登记进去，供运行期轮询去重。
         * 否则下一次轮询会把它们当成「新增」再报一遍。
         */
        for (DegradeEvent e : loaded.getDegradeEvents()) {
            REPORTED_DEGRADES.add(e.reason().name() + "|" + e.detail());
        }

        // 兼容模组检测
        CompatDetector.detectAndReport(caps);
    }

    /**
     * 解析游戏工作目录。
     *
     * <p>native 侧写入的 {@code glesmod/status.json} 是相对于游戏工作目录的
     * 相对路径，因此这里也需要同一基准。
     */
    private static Path resolveGameDir() {
        try {
            Minecraft mc = Minecraft.getInstance();
            if (mc != null && mc.gameDirectory != null) {
                return mc.gameDirectory.toPath();
            }
        } catch (Throwable t) {
            // 理论上不应发生；发生时不影响主流程
            GLESMod.LOGGER.debug("无法从 Minecraft 获取工作目录: {}", t.toString());
        }
        return Path.of(".");
    }

    /** 获取最近一次加载的状态；未加载时为 null。 */
    public static GlesBackendStatus getStatus() {
        return status;
    }
}
