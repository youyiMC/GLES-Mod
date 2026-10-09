package com.youyimc.glesmod;

import org.slf4j.Logger;

import com.mojang.logging.LogUtils;

import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent;

/**
 * GLES Mod 的主入口。
 *
 * <p>本模组的定位是「渲染后端适配层」：配合 FCL 渲染器插件替换启动器的
 * {@code libGL.so}，使 Minecraft 在 Android 上直接使用原生 OpenGL ES，
 * 绕过 GL4ES / ANGLE 的翻译层。
 *
 * <p>模组自身<b>不参与高频渲染路径</b>。它的职责是：
 * <ul>
 *   <li>读取 native 后端写入的状态文件（能力、降级事件）</li>
 *   <li>输出玩家可读的启动日志与诊断信息</li>
 *   <li>与 Sodium / Embeddium 做软依赖联动</li>
 * </ul>
 *
 * @since 0.1.0
 */
@Mod(GLESMod.MODID)
public class GLESMod {

    /** 模组 ID，必须与 neoforge.mods.toml 及 gradle.properties 中的 mod_id 一致。 */
    public static final String MODID = "glesmod";

    /** native ABI 版本。与 native 侧 GLESMOD_ABI_VERSION 对应。 */
    public static final int ABI_VERSION = 1;

    public static final Logger LOGGER = LogUtils.getLogger();

    public GLESMod(IEventBus modEventBus, ModContainer modContainer) {
        modEventBus.addListener(this::commonSetup);
        modContainer.registerConfig(ModConfig.Type.COMMON, Config.SPEC);
    }

    private void commonSetup(FMLCommonSetupEvent event) {
        LOGGER.info("GLES Mod 初始化中（native ABI v{}）", ABI_VERSION);
        if (!Config.ENABLED.getAsBoolean()) {
            LOGGER.info("模组已在配置中禁用，将不进行后端状态检查。");
        }
    }
}
