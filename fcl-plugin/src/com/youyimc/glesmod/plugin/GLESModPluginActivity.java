package com.youyimc.glesmod.plugin;

import android.app.Activity;
import android.os.Bundle;

/**
 * FCL 渲染器插件的最小宿主 Activity。
 *
 * <p><b>本 Activity 永远不会被启动</b>。它存在的唯一原因是 Android 的包可见性
 * 模型：FCL 的 {@code PluginManager} 通过
 * {@code queryIntentActivities(Intent(ACTION_MAIN))} 扫描插件，该方法只返回
 * 含有匹配 {@code ACTION_MAIN} 的 activity 的包。若 APK 中没有声明任何
 * activity，插件将无法被 FCL 发现。
 *
 * <p>真正的渲染工作由 {@code libgl_gles.so} 完成——FCL 通过
 * {@code ApplicationInfo.nativeLibraryDir} 拼接路径后 {@code dlopen} 它。
 *
 * <p>实现上刻意保持极简：不引用任何资源，不依赖 R 类，因此构建脚本无需
 * 编译 aapt2 生成的 R.java。
 *
 * @since 0.1.0
 */
public final class GLESModPluginActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 防御性处理：万一被误启动，立即退出，不显示任何界面。
        finish();
    }
}
