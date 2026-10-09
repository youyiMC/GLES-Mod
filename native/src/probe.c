/*
 * probe.c —— 几何错位诊断探针（第 6 版）
 *
 * ======================================================================
 * 【★v5 的结论：探针自己把「附件枚举」写错了（这才是真 bug）★】
 *
 * v4/v5 报告「深度附件查询失败」，我一度当成「默认帧缓冲没有深度缓冲」。
 * 但 v6 周期在 latest.log 里找到了驱动的原话：
 *
 *   framebuffer target 36160 cannot have attachemnts 6145
 *                                        GL_BACK, GL_DEPTH, or GL_STENCIL
 *
 *   36160 = 0x8D40 = GL_FRAMEBUFFER
 *   6145  = 0x1801 = **我传给附件查询的那个值**
 *
 * 0x1801 是 GL_DEPTH —— 深度【格式/位】枚举（glClear/glTexImage2D 那类用），
 * 【不是】附件枚举。附件枚举是 GL_DEPTH_ATTACHMENT = 0x8D00。
 *
 * => v4 与 v5 的「深度附件读取失败」**全部是我自己的笔误**，
 *    不是驱动不支持、也不是帧缓冲没有深度。
 *    「深度是否存在 / 多少位」这条线索**从未真正测过**，本轮才第一次能测。
 *
 * ======================================================================
 * 【v5 第一次拿到「顶点数据」这一手证据 —— 结果：完全正常】
 *
 *   vbo=8667 大小=768 字节 stride=32
 *   顶点0: Pos=(3.438,  4.000, 15.562) UV0=(0.366, 0.932) Color=(255,255,255,255)
 *   顶点1: Pos=(3.438,  4.000, 15.438) UV0=(0.366, 0.936) Color=(...)
 *   顶点2: Pos=(3.562,  4.000, 15.438) UV0=(0.368, 0.936) Color=(...)
 *
 * 解读：三个顶点共面（y 全 = 4.000）、x/z 差 1/8 格（0.125），
 * 正是「方块顶面的半个 quad」；UV0 差约 0.004 = 1/256（图集一像素），
 * 颜色全白。**这是完全正确的方块顶点数据。**
 * => 「顶点数据被写坏」的假设**排除**。加上此前已排除的
 *    布局/状态/变换/符号/着色器，几何数据链已全部清白。
 *
 * ======================================================================
 * 【v6 结果：枚举修对了，但探针自身还有第二个 bug】
 *
 *   ✅ 附件枚举修正生效：驱动**不再**报
 *      "framebuffer target 36160 cannot have attachemnts 6145"；
 *      深度附件类型第一次读成功：类型=GL_TEXTURE（而不是 0xFFFFFFFF）。
 *
 *   ⚠️ 但 v6 报出「深度附件 内部格式=0x1908(GL_RGBA) 尺寸=1024x512」——
 *      对深度附件荒谬。根因仍是**探针自己**：
 *        (1) glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, ...) 量的是
 *            「当前绑定的纹理」，而 dump_env 从没绑定附件挂的那个纹理；
 *        (2) 0x821B / 0x821C 被当成「附件宽/高」，其实那是
 *            GL_MAJOR_VERSION / GL_MINOR_VERSION，根本不是尺寸 pname。
 *
 * ======================================================================
 * 【v7 修正】
 *   1. 查深度/颜色附件的内部格式与尺寸前，先 glBindTexture 绑定
 *      附件对象（FRAMEBUFFER_ATTACHMENT_OBJECT_NAME），查完还原绑定。
 *   2. 颜色附件与深度附件**分开**量（v6 两者混用了同一批局部变量）。
 *   3. 去掉错误的 0x821B/0x821C 尺寸查询。
 *   4. name_internal_format 补齐 GL_RGBA/RGB/RGB8/RGB565/RGBA4/RGB5_A1/SRGB8
 *      ——否则 v6 那种「0x1908」只能打印裸 hex。
 *   5. 追加状态：深度写掩码 / 多边形偏移 / 剪切 / sRGB / 采样数。
 *
 * ======================================================================
 * 【v7 结果：颜色目标尺寸假设被排除；深度附件读数异常】
 *
 *   ✅ 颜色附件：对象=9 内部格式=GL_RGBA8 尺寸=2670x1200
 *      与视口 (0,0,2670,1200) **完全一致** -> 「渲染目标被缩放/偏移」假设排除。
 *   ⚠️ 深度附件读作「内部格式=GL_RGBA(0x1908) 尺寸=0x0」——
 *      **尺寸 0x0 说明该纹理对象根本没有分配存储**，所以它不是 MC 真正的
 *      深度纹理（我们没有上 PBO 回读，只能判定「探针查到的对象不对」，
 *      不能据此断定「没有深度缓冲」）。EGL_CONFIG_ID 依旧取不到。
 *
 * ======================================================================
 * 【v8 目标：用户新反馈指向「纹理/光照图」这条世界专属路径】
 *
 *   用户原话：「完整方块**只有在物品栏和手持的时候**是正常的，
 *             放置到世界里也一样材质出错。」
 *
 *   这是本项目最有价值的一条对比，因为：
 *     - 物品栏方块 = GUI 路径（正交、无光照图）
 *     - 手持方块   = 实体路径，且 MC 用 **full-bright 光照图**（全白）
 *     - 世界方块   = 区块地形路径，**唯一真正采样真实光照图(Sampler2)的路径**
 *   若光照图（Sampler2）或方块图集（Sampler0）的「采样器<->纹理单元」
 *   对应关系出问题，那么**只有世界方块**会整体颜色/材质错乱，
 *   而物品栏与手持因走 full-bright 而**完全看不出来** —— 与用户描述吻合。
 *
 *   v8 修法：新增 dump_texture_state()，对**每个程序**各打一次：
 *     - 该程序里 Sampler0..3 各解析到哪个纹理单元（glGetUniformiv）
 *     - 0..3 号单元实际绑定的 2D 纹理、尺寸、内部格式
 *   从而可直接对比「GUI 程序」与「区块地形程序」的绑定差异。
 *
 * ======================================================================
 * 【v6 要回答的问题】既然数据链全对，那问题只能在更下游：
 *   (a) 渲染目标（主世界帧缓冲）本身 —— 深度附件类型/位数/尺寸
 *   (b) 渲染目标尺寸与视口是否一致
 *   (c) 深度约定与裁剪状态（DEPTH_RANGE / 是否 glClipControl 之类）
 *
 * 修法：
 *   1. **修正附件枚举**：0x1801 -> 0x8D00（GL_DEPTH_ATTACHMENT），
 *      并在其为空时补试 GL_DEPTH_STENCIL_ATTACHMENT(0x821A)。
 *   2. 环境转储**只做一次**（v5 会随区块程序数量重复 4 次，日志冗余）。
 *   3. 保留 v5 的顶点缓冲实测（一次性）。
 *
 * ======================================================================
 * 【历史结论（保留备查）】
 *   v3：区块程序 stride=32，偏移 0/12/16/24/28 连续自洽 -> 布局假设排除。
 *       运行期符号对账显示 **存根(S) 被调用 0 次** -> 静默丢调用假设排除。
 *   v4：修掉身份误判（只有 ChunkOffset 才是区块判据）；
 *       实测 ProjMat = 标准透视（m10≈-1.0004, m11=-1.0），非 reversed-Z。
 *   v5：顶点缓冲实测 -> **顶点数据完全正常**。
 *
 * ======================================================================
 * 【为什么采样时机必须是「每个程序自己的第一次绘制」】
 * v1、v2 都栽在这里（用全局时间/计数门槛，采到加载期界面）。
 * 本版仍保持：为每个程序各存一份，在该程序自己首次绘制时采样。
 */

#include "gl_internal.h"

#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#define PROBE_RESOLVE_OR_RETURN(dst, name, ret)          \
    do {                                                 \
        if ((dst) == NULL) {                             \
            (dst) = (void *)glesym_resolve(name);        \
            if ((dst) == NULL) {                         \
                glesmod_report_missing(name);            \
                return ret;                              \
            }                                            \
        }                                                \
    } while (0)

/* ------------------------------------------------------------------ */

#define PROBE_MAX_PROGS   64
#define PROBE_NAME_LEN    48
#define PROBE_MAX_UNIFORMS 20
#define PROBE_MAX_ATTRIBS  12

typedef struct {
    /* --- 身份 --- */
    unsigned int prog;              /* 0 = 空槽位 */
    int          identified;        /* 是否已转储 uniform/属性清单 */

    /* --- 本秒统计 --- */
    unsigned long draws;
    unsigned long indexed;          /* 累计索引数 */
    int           max_count;
    int           min_count;

    /* --- 采样到的状态（该程序首次绘制时） --- */
    int depth_test, depth_func, depth_mask;
    int cull_face, cull_mode, front_face;
    int blend, blend_src, blend_dst;

    /* --- uniform 名清单（用于识别程序身份） --- */
    char uni[PROBE_MAX_UNIFORMS][PROBE_NAME_LEN];
    int  uni_count;

    /* --- 属性名清单 --- */
    char attrib[PROBE_MAX_ATTRIBS][PROBE_NAME_LEN];
    int  attrib_count;

    /* --- 顶点属性布局（该程序首次绘制时） --- */
    int va_enabled[8];
    int va_size[8], va_type[8], va_stride[8], va_norm[8];
    long va_offset[8];

    /* --- 关键 uniform 的「实际数值」（v4 新增） ---
     * v3 已证明顶点布局与状态都正确，那么「形状对、朝向/位置/透视错」
     * 只剩变换（矩阵 / ChunkOffset）一条路。这里在**该程序自己第一次绘制时**
     * 用 glGetUniformfv 直接读回 uniform 的值 —— 此刻该程序就是当前程序，
     * 读到的必然就是这次绘制真正用的值。 */
    int   has_ckoff, has_mv, has_proj;
    float ckoff[3];      /* ChunkOffset */
    float mv_trans[4];   /* ModelViewMat 平移列 m[12..15] */
    float proj_zw[6];    /* ProjMat m0 m5 m10 m11 m14 m15 */
} prog_rec;

static prog_rec g_rec[PROBE_MAX_PROGS];

static int           g_probe_on = -1;

/*
 * 探针快速路径标志。非 0 = 初始化与探针开关都已固定，可直接走稳态。
 *
 * 与 g_probe_on 分开是因为语义不同：
 *   g_probe_on  = 探针是否启用（由 GLESMOD_GEOM_PROBE 决定，进程内不变）
 *   g_probe_ready = 是否可以不再做任何一次性检查
 * 后者还要求初始化真正结束（见 glDrawElements 内的说明）。
 */
static volatile int  g_probe_ready = 0;

static unsigned long g_sec_draws = 0;
static long long     g_last_sec_ms = 0;

/* ------------------------------------------------------------------ */

static long long now_ms(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0;
    return (long long)ts.tv_sec * 1000LL + (long long)(ts.tv_nsec / 1000000L);
}

/* 查询失败必须显式区分，不能让失败退化成看起来合理的数字 */
static int get_int_safe(void (*fn)(GLenum, GLint *), GLenum pname) {
    typedef GLenum (*get_err_t)(void);
    static get_err_t get_err = NULL;
    static int tried = 0;

    if (!tried) { tried = 1; get_err = (get_err_t)glesym_resolve("glGetError"); }
    if (fn == NULL) return -1;

    GLint v = -1;
    if (get_err != NULL) { (void)get_err(); }
    fn(pname, &v);
    if (get_err != NULL) { if (get_err() != 0) return -1; }
    return (int)v;
}

static const char *name_depth_func(int v) {
    switch (v) {
        case 0x0200: return "NEVER";   case 0x0201: return "LESS";
        case 0x0202: return "EQUAL";   case 0x0203: return "LEQUAL";
        case 0x0204: return "GREATER"; case 0x0205: return "NOTEQUAL";
        case 0x0206: return "GEQUAL";  case 0x0207: return "ALWAYS";
        default: return NULL;
    }
}
static const char *name_cull_mode(int v) {
    switch (v) {
        case 0x0404: return "FRONT";
        case 0x0405: return "BACK";
        case 0x0408: return "FRONT_AND_BACK";
        default: return NULL;
    }
}
static const char *name_front_face(int v) {
    switch (v) { case 0x0900: return "CW"; case 0x0901: return "CCW";
                 default: return NULL; }
}
static const char *name_blend(int v) {
    switch (v) {
        case 0x0000: return "ZERO"; case 0x0001: return "ONE";
        case 0x0300: return "SRC_COLOR"; case 0x0301: return "1-SRC_COLOR";
        case 0x0302: return "SRC_ALPHA"; case 0x0303: return "1-SRC_ALPHA";
        case 0x0304: return "DST_ALPHA"; case 0x0305: return "1-DST_ALPHA";
        case 0x0306: return "DST_COLOR"; case 0x0307: return "1-DST_COLOR";
        default: return NULL;
    }
}
static const char *name_gl_type(int v) {
    switch (v) {
        case 0x1400: return "BYTE";  case 0x1401: return "UNSIGNED_BYTE";
        case 0x1402: return "SHORT"; case 0x1403: return "UNSIGNED_SHORT";
        case 0x1404: return "INT";   case 0x1405: return "UNSIGNED_INT";
        case 0x1406: return "FLOAT"; case 0x140B: return "HALF_FLOAT";
        case 0x8B50: return "FLOAT_VEC2"; case 0x8B51: return "FLOAT_VEC3";
        case 0x8B52: return "FLOAT_VEC4";
        case 0x8B53: return "INT_VEC2";   case 0x8B54: return "INT_VEC3";
        case 0x8B55: return "INT_VEC4";
        case 0x8B5E: return "SAMPLER_2D";
        case 0x8B5A: return "FLOAT_MAT2"; case 0x8B5B: return "FLOAT_MAT3";
        case 0x8B5C: return "FLOAT_MAT4";
        default: return NULL;
    }
}

static void fmt_enum(char *out, size_t n, int v, const char *(*namer)(int)) {
    if (v < 0) { snprintf(out, n, "n/a"); return; }
    const char *nm = namer ? namer(v) : NULL;
    if (nm) snprintf(out, n, "%s", nm);
    else    snprintf(out, n, "0x%04X", v);
}

/* ------------------------------------------------------------------ */
/* 找出该程序是否含某个 uniform（用名字前缀判断身份）                   */
/* ------------------------------------------------------------------ */

static int has_token(const prog_rec *r, const char *needle) {
    for (int i = 0; i < r->uni_count; i++) {
        if (strstr(r->uni[i], needle) != NULL) return 1;
    }
    for (int i = 0; i < r->attrib_count; i++) {
        if (strstr(r->attrib[i], needle) != NULL) return 1;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* EGL 配置探测（v4 新增）—— 「有没有深度缓冲」的权威来源              */
/*                                                                      */
/* 为什么必须查 EGL：GL 侧的 GL_DEPTH_BITS 在 ES 3.0 起已废弃，          */
/* 附件查询又只针对 FBO（默认帧缓冲 0 在某些驱动上查不到）。            */
/* 唯一权威来源是 EGL 自己的 config：                                    */
/*   eglGetCurrentContext -> eglQueryContext(EGL_CONFIG_ID)             */
/*   -> eglGetConfigAttrib(EGL_DEPTH_SIZE / EGL_STENCIL_SIZE)           */
/*                                                                      */
/* 本库不链接 libEGL（见 CMakeLists 注释），故用 dlsym 动态取。          */
/* ------------------------------------------------------------------ */

static void dump_egl_config_once(void) {
    typedef void *(*egl_get_current_ctx_t)(void);
    typedef int   (*egl_query_ctx_t)(void *, int, int *);
    typedef int   (*egl_get_config_attrib_t)(void *, void *, int, int *);
    typedef void *(*egl_get_current_disp_t)(void);

    static int   done = 0;
    if (done) return;
    done = 1;

    /*
     * 【v5 修正】v4 只试了 RTLD_DEFAULT / dlopen("libEGL.so", RTLD_LOCAL)，
     * 两者都可能拿到「另一个 EGL 实例」或干脆失败 —— 于是 EGL_CONFIG_ID
     * 取不到，整段探测被跳过。
     *
     * FCL 用 RTLD_LOCAL 加载 EGL（见 ctxbridges/egl_loader.c），
     * 其符号**不进全局表**；而 libGLESv2.so 与 EGL 是配套加载的。
     * 因此这里按「多个候选句柄依次尝试」的方式找，命中即用：
     *   1) dlopen("libEGL.so")  —— Android 上通常与启动器指向同一份
     *   2) RTLD_DEFAULT
     *   3) libGLESv2.so（部分实现把 eglQueryContext 也导出在这里）
     */
    void *cands[3];
    int   ncand = 0;
    void *h1 = dlopen("libEGL.so", RTLD_NOW | RTLD_LOCAL);
    if (h1) cands[ncand++] = h1;
    cands[ncand++] = RTLD_DEFAULT;
    void *h3 = dlopen("libGLESv2.so", RTLD_NOW | RTLD_LOCAL);
    if (h3) cands[ncand++] = h3;

    egl_get_current_ctx_t   get_ctx  = NULL;
    egl_get_current_disp_t  get_disp = NULL;
    egl_query_ctx_t         q_ctx    = NULL;
    egl_get_config_attrib_t get_cfg  = NULL;

    for (int i = 0; i < ncand; i++) {
        egl_get_current_ctx_t c1 = (egl_get_current_ctx_t)dlsym(cands[i], "eglGetCurrentContext");
        egl_get_current_disp_t d1 = (egl_get_current_disp_t)dlsym(cands[i], "eglGetCurrentDisplay");
        egl_query_ctx_t        q1 = (egl_query_ctx_t)dlsym(cands[i], "eglQueryContext");
        egl_get_config_attrib_t g1 = (egl_get_config_attrib_t)dlsym(cands[i], "eglGetConfigAttrib");
        if (c1 && q1 && g1) {
            get_ctx = c1; get_disp = d1; q_ctx = q1; get_cfg = g1;
            break;
        }
    }

    if (get_ctx == NULL || q_ctx == NULL || get_cfg == NULL) {
        glesmod_log("[probe]   EGL 查询函数不可用，跳过 EGL 配置探测");
        return;
    }

    void *ctx = get_ctx();
    /* eglGetCurrentDisplay 缺失时用 EGL_DEFAULT_DISPLAY(0) 兜底 */
    void *dpy = get_disp ? get_disp() : NULL;
    if (dpy == NULL) dpy = (void *)0;

    if (ctx == NULL) {
        glesmod_log("[probe]   当前无 EGL 上下文，跳过 EGL 配置探测");
        return;
    }

    /* 0x3028 = EGL_CONFIG_ID —— 用数值常量，避免引入 EGL 头文件 */
    int cfg_id = -1;
    q_ctx(ctx, 0x3028 /* EGL_CONFIG_ID */, &cfg_id);
    if (cfg_id < 0) {
        glesmod_log("[probe]   无法取得 EGL_CONFIG_ID，跳过 EGL 配置探测");
        return;
    }

    int depth = -1, stencil = -1, red = -1, green = -1, blue = -1, alpha = -1;
    int samples = -1, surface_type = -1, renderable = -1;

#define A(attr, out) \
    do { if (get_cfg(dpy, (void *)(intptr_t)cfg_id, (attr), &(out)) != 1) (out) = -1; } while (0)

    A(0x3025 /* EGL_DEPTH_SIZE   */, depth);
    A(0x3026 /* EGL_STENCIL_SIZE */, stencil);
    A(0x3024 /* EGL_RED_SIZE     */, red);
    A(0x3023 /* EGL_GREEN_SIZE   */, green);
    A(0x3022 /* EGL_BLUE_SIZE    */, blue);
    A(0x3021 /* EGL_ALPHA_SIZE   */, alpha);
    A(0x3031 /* EGL_SAMPLES      */, samples);
    A(0x3033 /* EGL_SURFACE_TYPE */, surface_type);
    A(0x3040 /* EGL_RENDERABLE_TYPE */, renderable);
#undef A

    char buf[400];
    snprintf(buf, sizeof(buf),
             "[probe]   EGL 配置 id=%d: DEPTH_SIZE=%d STENCIL_SIZE=%d "
             "RGBA=(%d,%d,%d,%d) SAMPLES=%d",
             cfg_id, depth, stencil, red, green, blue, alpha, samples);
    glesmod_log(buf);

    snprintf(buf, sizeof(buf),
             "[probe]   EGL SURFACE_TYPE=0x%04X RENDERABLE=0x%04X",
             surface_type, renderable);
    glesmod_log(buf);

    if (depth == 0) {
        glesmod_log("[probe]   !! EGL_DEPTH_SIZE = 0：启动器申请的 EGL 配置"
                    "根本没有深度缓冲。深度测试无法生效，"
                    "这就是几何前后关系错乱的根本原因。");
    }
}

/* ------------------------------------------------------------------ */
/* 环境级信息，只转储一次（v4 新增）                                    */
/*                                                                      */
/* 【为什么必须查「默认帧缓冲到底有没有深度附件」】                      */
/*   这是目前唯一能同时解释全部症状的假设：                              */
/*     · 深度测试失效 -> 面的前后遮挡关系全乱 -> 看上去是                */
/*       「形状没拉伸，但透视 / 面朝向 / 位置同时错」                    */
/*     · GUI / 粒子 / F3 线 都是「按序绘制 + 混合」的路径，              */
/*       本来就不依赖深度，所以它们**看起来正常**                       */
/*     · 物品栏里完整立方体六面都在，顺序错也几乎看不出；                */
/*       而不完整方块（堆肥桶 / 栅栏）面少且互相遮挡 -> 一眼就错         */
/*                                                                      */
/*   注意 ES 3.0 起 GL_DEPTH_BITS 已不是合法的 pname（会返回 -1），      */
/*   正确做法是查帧缓冲附件：                                            */
/*     glGetFramebufferAttachmentParameteriv(GL_FRAMEBUFFER, GL_DEPTH,   */
/*         GL_FRAMEBUFFER_ATTACHMENT_DEPTH_SIZE, &bits)                  */
/* ------------------------------------------------------------------ */

/*
 * 深度/颜色内部格式的可读化。
 *
 * 【为什么必须查内部格式而不是 DEPTH_SIZE】
 *   v4 用 glGetFramebufferAttachmentParameteriv(GL_DEPTH,
 *   GL_FRAMEBUFFER_ATTACHMENT_DEPTH_SIZE) 去量深度位数 —— 结果返回错误。
 *   原因：该 pname 只对 **renderbuffer** 附件有效；MC 的深度附件是
 *   **纹理**（glFramebufferTexture2D 挂上去的），因此必须改查
 *   附件对象本身的内部格式（GL_TEXTURE_INTERNAL_FORMAT /
 *   GL_RENDERBUFFER_INTERNAL_FORMAT）。
 */
static const char *name_internal_format(int v) {
    switch (v) {
        case 0x1902: return "GL_DEPTH_COMPONENT(未定宽)";
        case 0x81A5: return "GL_DEPTH_COMPONENT16 【只有16位!】";
        case 0x81A6: return "GL_DEPTH_COMPONENT24";
        case 0x81A7: return "GL_DEPTH_COMPONENT32F";
        case 0x84F9: return "GL_DEPTH_STENCIL";
        case 0x88F0: return "GL_DEPTH24_STENCIL8";
        case 0x8CAD: return "GL_DEPTH32F_STENCIL8";
        case 0x8058: return "GL_RGBA8";
        case 0x8C43: return "GL_SRGB8_ALPHA8";
        /* v7 补充：这些是 v6 误报出来的（0x1908 = GL_RGBA 未定宽），
         * 以及颜色附件的常见未定宽/定宽格式 */
        case 0x1908: return "GL_RGBA(未定宽)";
        case 0x1907: return "GL_RGB(未定宽)";
        case 0x1906: return "GL_ALPHA(未定宽)";
        case 0x8051: return "GL_RGB8";
        case 0x8056: return "GL_RGBA4";
        case 0x8057: return "GL_RGB5_A1";
        case 0x8D62: return "GL_RGB565";
        case 0x8C41: return "GL_SRGB8";
        default: return NULL;
    }
}

static const char *name_attach_type(int v) {
    switch (v) {
        case 0x0000: return "GL_NONE（没挂东西！）";
        case 0x1702: return "GL_TEXTURE";
        case 0x8D41: return "GL_RENDERBUFFER";
        case 0x8218: return "GL_FRAMEBUFFER_DEFAULT";
        default: return NULL;
    }
}

/*
 * 【v6 关键修正 —— 附件枚举用错了，这是个真 bug】
 *
 * v4/v5 都用 0x1801 当作「深度附件」传给
 * glGetFramebufferAttachmentParameteriv / glFramebufferTexture2D 系列。
 * 但 0x1801 是 **GL_DEPTH**（深度 **格式/位** 枚举，用于 glClear 等），
 * 而附件枚举是 **GL_DEPTH_ATTACHMENT = 0x8D00**。
 *
 * 证据（不需要猜，驱动原话）：latest.log 里与本库查询同时间戳出现
 *   framebuffer target 36160 cannot have attachemnts 6145 GL_BACK, GL_DEPTH, or GL_STENCIL
 * 其中 36160 = 0x8D40 = GL_FRAMEBUFFER，6145 = 0x1801 = 我传的那个错值。
 * 也就是说：**v4 和 v5 的「深度附件查询全部失败」是我自己的枚举写错，
 * 而不是「默认帧缓冲没有深度缓冲」。** 这条证据链必须重走。
 *
 * 正确的 ES 附件枚举：
 *   GL_DEPTH_ATTACHMENT          0x8D00
 *   GL_STENCIL_ATTACHMENT        0x8D20
 *   GL_DEPTH_STENCIL_ATTACHMENT  0x821A
 *   GL_COLOR_ATTACHMENT0         0x8CE0
 */
#define PROBE_ATTACH_DEPTH      0x8D00
#define PROBE_ATTACH_STENCIL    0x8D20
#define PROBE_ATTACH_DEPTH_STEN 0x821A
#define PROBE_ATTACH_COLOR0     0x8CE0

/*
 * 【v8 新增】纹理单元 / 采样器 uniform 实测
 *
 * 为什么加这一段：用户新反馈「完整方块只有**在物品栏和手持时**正常，
 * 放置到世界里就材质出错」。这条对比极其关键 ——
 *   物品栏 / 手持：GUI / 实体路径，**不经过区块地形着色器**
 *   放置到世界：区块地形路径（rendertype_solid/cutout/translucent…）
 * 两者差在：区块地形着色器用 Sampler0（方块图集）+ Sampler2（光照图），
 * 且几何带 ChunkOffset。GUI/物品路径不用光照图。
 *
 * 所以「世界错、物品栏对」高度指向 **纹理单元 ↔ 采样器 的对应关系**：
 *   - 若 Sampler2（光照图）解析到的单元上绑的不是 16x16 光照图，
 *     方块的颜色/明暗就会整体错乱（GUI/物品不吃光照图，故看不出问题）
 *   - 若 Sampler0 指向的单元绑错纹理，方块贴图就整体错
 * 这里把「每个单元绑了什么纹理、多大」和「采样器 uniform 指向哪个单元」
 * 一次性打出来，直接用驱动自己的状态回答，不靠推断。
 */
static void dump_texture_state(void) {
    typedef void   (*active_tex_t)(GLenum);
    typedef void   (*get_iv_t)(GLenum, GLint *);
    typedef void   (*get_tex_par_t)(GLenum, GLint, GLenum, GLint *);
    typedef GLint  (*get_uni_loc_t)(GLuint, const GLchar *);
    typedef void   (*get_uni_iv_t)(GLuint, GLint, GLint *);

    static active_tex_t  active_tex  = NULL;
    static get_iv_t      get_iv      = NULL;
    static get_tex_par_t get_tex_par = NULL;
    static get_uni_loc_t get_uni_loc = NULL;
    static get_uni_iv_t  get_uni_iv  = NULL;
    static int tried = 0;

    if (!tried) {
        tried = 1;
        active_tex  = (active_tex_t)glesym_resolve("glActiveTexture");
        get_iv      = (get_iv_t)glesym_resolve("glGetIntegerv");
        get_tex_par = (get_tex_par_t)glesym_resolve("glGetTexLevelParameteriv");
        get_uni_loc = (get_uni_loc_t)glesym_resolve("glGetUniformLocation");
        get_uni_iv  = (get_uni_iv_t)glesym_resolve("glGetUniformiv");
    }
    if (get_iv == NULL) return;

    char buf[360];

    /* --- 当前程序里 Sampler0..3 各自解析到哪个纹理单元 --- */
    GLint prog = 0;
    get_iv(0x8B8D /* GL_CURRENT_PROGRAM */, &prog);
    if (prog > 0 && get_uni_loc != NULL && get_uni_iv != NULL) {
        static const char *snames[4] = { "Sampler0", "Sampler1", "Sampler2", "Sampler3" };
        char list[200];
        size_t n = 0;
        list[0] = '\0';
        for (int i = 0; i < 4; i++) {
            GLint loc = get_uni_loc((GLuint)prog, snames[i]);
            if (loc < 0) continue;
            GLint unit = -1;
            get_uni_iv((GLuint)prog, loc, &unit);
            n += (size_t)snprintf(list + n, sizeof(list) - n, "%s=%d ", snames[i], unit);
            if (n >= sizeof(list)) { list[sizeof(list) - 1] = '\0'; break; }
        }
        snprintf(buf, sizeof(buf), "[probe]   采样器uniform(程序%d): %s", prog, list);
        glesmod_log(buf);
    }

    /* --- 每个纹理单元实际绑定的 2D 纹理及其尺寸 --- */
    GLint prev_active = 0;
    get_iv(0x84E0 /* GL_ACTIVE_TEXTURE */, &prev_active);
    for (int u = 0; u < 4; u++) {
        if (active_tex) active_tex((GLenum)(0x84C0 /* GL_TEXTURE0 */ + u));
        GLint tex = 0;
        get_iv(0x8069 /* GL_TEXTURE_BINDING_2D */, &tex);
        GLint w = -1, h = -1, fmt = -1;
        if (tex > 0 && get_tex_par != NULL) {
            get_tex_par(0x0DE1, 0, 0x1000 /* WIDTH  */, &w);
            get_tex_par(0x0DE1, 0, 0x1001 /* HEIGHT */, &h);
            get_tex_par(0x0DE1, 0, 0x1003 /* INTERNAL_FORMAT */, &fmt);
        }
        snprintf(buf, sizeof(buf),
                 "[probe]   纹理单元 %d: 绑定纹理=%d 尺寸=%dx%d 内部格式=0x%04X",
                 u, tex, w, h, fmt);
        glesmod_log(buf);
    }
    if (active_tex) active_tex((GLenum)prev_active);
}

/*
 * 【v9 新增】把**当前绑定的帧缓冲的全部附件**系统性地列一遍。
 *
 * 为什么要换成「全列」而不是继续逐个猜：
 *   v4..v8 连续 5 轮都在「猜某一个附件枚举 / 某一个 pname」，
 *   每次都被驱动用含糊错误顶回来，最后发现全是探针自己的错。
 *   用户新线索（「旁观模式能看到没被正确剔除的面」「生物正反面交叠」）
 *   指向**深度缓冲没在起作用** —— 但 v8 读到「深度附件 尺寸=0x0、
 *   内部格式=GL_RGBA」这种自相矛盾的值，说明我查的对象不对。
 *
 * 做法：对 COLOR_ATTACHMENT0..3 / DEPTH / STENCIL / DEPTH_STENCIL 逐个查
 *   OBJECT_TYPE(0x8CD0) / OBJECT_NAME(0x8CD1) / COMPONENT_TYPE(0x8CD2)，
 *   并用 glIsTexture/glIsRenderbuffer 验证对象名是否**真实存在**。
 *   这样一次就能看清「到底挂了什么、对象是不是真的」，
 *   而不是再次把某个查询失败误读成「驱动没有深度缓冲」。
 */
static void dump_all_attachments(void) {
    typedef void   (*get_fbo_attach_t)(GLenum, GLenum, GLenum, GLint *);
    typedef GLboolean (*is_tex_t)(GLuint);
    typedef GLboolean (*is_rb_t)(GLuint);
    typedef GLenum (*get_err_t)(void);

    static get_fbo_attach_t get_fbo_att = NULL;
    static is_tex_t         is_tex      = NULL;
    static is_rb_t          is_rb       = NULL;
    static get_err_t        get_err     = NULL;
    static int tried = 0;

    if (!tried) {
        tried = 1;
        get_fbo_att = (get_fbo_attach_t)glesym_resolve("glGetFramebufferAttachmentParameteriv");
        is_tex      = (is_tex_t)glesym_resolve("glIsTexture");
        is_rb       = (is_rb_t)glesym_resolve("glIsRenderbuffer");
        get_err     = (get_err_t)glesym_resolve("glGetError");
    }
    if (get_fbo_att == NULL) return;

    static const struct { const char *nm; GLenum e; } A[] = {
        { "COLOR0",        0x8CE0 },
        { "COLOR1",        0x8CE1 },
        { "DEPTH",         0x8D00 },
        { "STENCIL",       0x8D20 },
        { "DEPTH_STENCIL", 0x821A },
    };

    char buf[300];
    for (unsigned i = 0; i < sizeof(A) / sizeof(A[0]); i++) {
        GLint type = -2, name = -2, comp = -2;

        if (get_err) (void)get_err();
        get_fbo_att(0x8D40, A[i].e, 0x8CD0 /* OBJECT_TYPE */, &type);
        if (get_err && get_err() != 0) type = -1;

        if (type < 0) {
            snprintf(buf, sizeof(buf),
                     "[probe]   附件 %-13s: 查询失败（枚举或 pname 非法）", A[i].nm);
            glesmod_log(buf);
            continue;
        }
        if (type == 0 /* GL_NONE */) {
            snprintf(buf, sizeof(buf),
                     "[probe]   附件 %-13s: GL_NONE（没挂任何东西）", A[i].nm);
            glesmod_log(buf);
            continue;
        }

        (void)get_err();
        get_fbo_att(0x8D40, A[i].e, 0x8CD1 /* OBJECT_NAME */, &name);
        if (get_err && get_err() != 0) name = -1;
        (void)get_err();
        get_fbo_att(0x8D40, A[i].e, 0x8CD2 /* COMPONENT_TYPE */, &comp);
        if (get_err && get_err() != 0) comp = -1;

        int is_t = (is_tex && name > 0) ? (int)is_tex((GLuint)name) : -1;
        int is_r = (is_rb  && name > 0) ? (int)is_rb((GLuint)name)  : -1;

        snprintf(buf, sizeof(buf),
                 "[probe]   附件 %-13s: 类型=0x%04X 对象=%d 分量类型=0x%04X "
                 "| glIsTexture=%d glIsRenderbuffer=%d",
                 A[i].nm, type, name, comp, is_t, is_r);
        glesmod_log(buf);
    }
}

/*
 * 【v9 核心实验】深度缓冲「到底有没有在存数据」的直接验证。
 *
 * 依据：用户新线索 ——
 *   「旁观模式注意到似乎有未被正确剔除的面」
 *   「同时看到了生物实体的正面和背面材质交叠」
 * 这两句合起来几乎就是**深度测试失效**的定义：
 *   后面的面没有被前面的面挡住 → 正反面同时可见、本该被遮的面露出来。
 *
 * 但 v8 读到的「深度附件 内部格式=GL_RGBA 尺寸=0x0」自相矛盾，
 * 不能据此下结论。所以这里换一种**不依赖附件查询**的办法：
 *   世界渲染进行一段时间后，直接从当前帧缓冲回读若干深度像素。
 *     - 若深度缓冲有效且被写入：应能读到 < 1.0 的值（有近处几何）
 *     - 若读回全是 1.0（或读取直接报错）：深度写入/绑定很可能没生效
 *   glReadPixels(GL_DEPTH_COMPONENT) 是 ES 3.0+ 的合法用法，
 *   它绕开了「附件枚举 / pname 猜错」这一类探针自身的坑。
 */
static void probe_depth_readback_once(void) {
    typedef void   (*read_pixels_t)(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *);
    typedef void   (*get_iv_t)(GLenum, GLint *);
    typedef GLenum (*get_err_t)(void);

    static read_pixels_t read_pixels = NULL;
    static get_iv_t      get_iv      = NULL;
    static get_err_t     get_err     = NULL;
    static int tried = 0;
    static int done  = 0;

    if (done) return;
    done = 1;

    if (!tried) {
        tried = 1;
        read_pixels = (read_pixels_t)glesym_resolve("glReadPixels");
        get_iv      = (get_iv_t)glesym_resolve("glGetIntegerv");
        get_err     = (get_err_t)glesym_resolve("glGetError");
    }
    if (read_pixels == NULL || get_iv == NULL) return;

    int vp[4] = {0, 0, 0, 0};
    get_iv(0x0BA2 /* GL_VIEWPORT */, vp);

    /* GL_DEPTH_BITS(0x0D56) 在 ES 3.x 已不保证有效，读一下仅作参考 */
    int depth_bits = -1;
    (void)get_err();
    get_iv(0x0D56, &depth_bits);
    if (get_err && get_err() != 0) depth_bits = -1;

    /* GL_DEPTH_CLEAR_VALUE(0x0B73)：本库的 glClearDepth 是**定制实现**
     * （double -> float），若转换写坏，整个深度缓冲的基准值就是错的，
     * 之后所有深度比较都会紊乱 —— 正好解释「正反面交叠 / 该遮的没遮住」。 */
    {
        typedef void (*get_fv_t)(GLenum, GLfloat *);
        get_fv_t get_fv = (get_fv_t)glesym_resolve("glGetFloatv");
        if (get_fv != NULL) {
            GLfloat clearv = -1.0f;
            (void)get_err();
            get_fv(0x0B73 /* GL_DEPTH_CLEAR_VALUE */, &clearv);
            if (get_err && get_err() != 0) clearv = -1.0f;
            char cb[220];
            snprintf(cb, sizeof(cb),
                     "[probe] 深度清除值: %.6f (原始位=0x%08X，期望 1.0f/0x3F800000)",
                     clearv, *(unsigned *)(void *)&clearv);
            glesmod_log(cb);
        }
    }

    if (vp[2] <= 0 || vp[3] <= 0) return;

    /*
     * 【v10 移除：深度回读实验】
     *
     * v9 曾在这里调 glReadPixels(GL_DEPTH_COMPONENT, GL_FLOAT) 去直接验证
     * 深度缓冲是否在存数据。但这个**组合本身就是 ES 非法的** ——
     * 驱动会回一句和 MC 原生问题**一模一样**的
     *     'the combination of format 6402 and type 5126 is unsupported'
     * 于是日志里再也分不清「是 MC 还在犯错」还是「是我探针在犯错」。
     * 本轮实测就吃了这个亏：修好之后仍看到 1 条该报错，查下去才发现
     * 时间戳正好在探针回读之后 —— **是我自己制造的**。
     *
     * 而且这个实验本身已经没必要了：dump_all_attachments() 已经能证明
     *   原名 10 → glIsTexture=1, 内部格式=0x81A6(DEPTH_COMPONENT24),
     *   尺寸=2670x1200（与视口一致）
     * 深度纹理**真实存在且有完整存储**，这正是修复生效的直接证据。
     *
     * 教训：**探针绝不能调用与被诊断对象相同的非法 API** ——
     * 否则证据会被自己污染。
     */
    (void)read_pixels;
    (void)depth_bits;
    (void)get_err;
    (void)get_iv;
    (void)vp;
}

static void dump_env(const char *tag) {
    typedef void   (*get_iv_t)(GLenum, GLint *);
    typedef GLenum (*check_fbo_t)(GLenum);
    typedef void   (*get_fbo_attach_t)(GLenum, GLenum, GLenum, GLint *);
    typedef void   (*bind_tex_t)(GLenum, GLuint);
    typedef void   (*get_tex_par_t)(GLenum, GLint, GLenum, GLint *);
    typedef void   (*bind_rb_t)(GLenum, GLuint);
    typedef void   (*get_rb_par_t)(GLenum, GLenum, GLint *);
    typedef GLenum (*get_err_t)(void);

    static get_iv_t         get_iv      = NULL;
    static check_fbo_t      check_fbo   = NULL;
    static get_fbo_attach_t get_fbo_att = NULL;
    typedef GLboolean (*is_tex_t)(GLuint);
    typedef GLboolean (*is_rb_t)(GLuint);

    static bind_tex_t       bind_tex    = NULL;
    static get_tex_par_t    get_tex_par = NULL;
    static bind_rb_t        bind_rb     = NULL;
    static get_rb_par_t     get_rb_par  = NULL;
    static get_err_t        get_err     = NULL;
    static is_tex_t         is_tex      = NULL;   /* v9：附件对象有效性自证 */
    static is_rb_t          is_rb       = NULL;
    static int              env_done    = 0;

    /* 只转储一次（v5 会按区块程序数量重复 4 次，日志冗余） */
    if (env_done) return;
    env_done = 1;

    if (get_iv == NULL)      get_iv      = (get_iv_t)glesym_resolve("glGetIntegerv");
    if (check_fbo == NULL)   check_fbo   = (check_fbo_t)glesym_resolve("glCheckFramebufferStatus");
    if (get_fbo_att == NULL) get_fbo_att = (get_fbo_attach_t)glesym_resolve("glGetFramebufferAttachmentParameteriv");
    if (bind_tex == NULL)    bind_tex    = (bind_tex_t)glesym_resolve("glBindTexture");
    if (get_tex_par == NULL) get_tex_par = (get_tex_par_t)glesym_resolve("glGetTexLevelParameteriv");
    if (bind_rb == NULL)     bind_rb     = (bind_rb_t)glesym_resolve("glBindRenderbuffer");
    if (get_rb_par == NULL)  get_rb_par  = (get_rb_par_t)glesym_resolve("glGetRenderbufferParameteriv");
    if (get_err == NULL)     get_err     = (get_err_t)glesym_resolve("glGetError");
    if (is_tex == NULL)      is_tex      = (is_tex_t)glesym_resolve("glIsTexture");
    if (is_rb == NULL)       is_rb       = (is_rb_t)glesym_resolve("glIsRenderbuffer");
    if (get_iv == NULL) return;

    int fbo = get_int_safe(get_iv, 0x8CA6 /* GL_FRAMEBUFFER_BINDING */);
    int vp[4] = {0, 0, 0, 0};
    get_iv(0x0BA2 /* GL_VIEWPORT */, vp);

    /* 帧缓冲完整性：非 0x8CD5 就是「不完整」，渲染本身就是破的 */
    int status = -1;
    if (check_fbo != NULL) status = (int)check_fbo(0x8D40 /* GL_FRAMEBUFFER */);

    /* 附件查询：返回 -1 表示该查询本身失败（pname 非法等）
     *
     * 【v6 修正 —— 见文件顶部 PROBE_ATTACH_* 宏处的详述】
     *   v4/v5 把 0x1801 当成深度附件枚举传给附件查询，而 0x1801 是
     *   GL_DEPTH（格式/位枚举）。正确值是 GL_DEPTH_ATTACHMENT = 0x8D00。
     *   驱动在 latest.log 里直接报了这一点（"cannot have attachemnts 6145"），
     *   所以 v4/v5 得到的「深度附件查询失败」是**探针自己的 bug**，
     *   不能据此断定「默认帧缓冲没有深度缓冲」。
     *
     *   另外把视口尺寸和附件的真实尺寸做对比：
     *   若附件尺寸 ≠ 视口尺寸，就会出现「渲染位置整体偏移 / 缩放」，
     *   也正是「形状对但位置错」的典型成因。 */
    int dt = -1, ct = -1;
    int rs = -1, gs = -1, bs = -1, as = -1;
    int obj_w = -1, obj_h = -1;                /* 参与「与视口比对」的尺寸 */
    int depth_tex = 0, depth_rbo = 0;
    int depth_fmt = -1;
    int col_obj = 0;                           /* 颜色附件对象名（v7 新增） */
    int col_w = -1, col_h = -1, col_fmt = -1;  /* 颜色附件尺寸/格式（v7 新增） */

#define Q(attach, pname, out)                                        \
    do {                                                             \
        if (get_err) (void)get_err();                                \
        get_fbo_att(0x8D40, (attach), (pname), &(out));              \
        if (get_err && get_err() != 0) (out) = -1;                   \
    } while (0)

    if (get_fbo_att != NULL) {
        Q(PROBE_ATTACH_DEPTH,  0x8CD0 /* OBJECT_TYPE  */, dt);
        Q(PROBE_ATTACH_COLOR0, 0x8CD0 /* OBJECT_TYPE  */, ct);
        /* 颜色附件信息（对纹理附件这些 pname 才有效） */
        Q(PROBE_ATTACH_COLOR0, 0x8212 /* RED_SIZE     */, rs);
        Q(PROBE_ATTACH_COLOR0, 0x8213 /* GREEN_SIZE   */, gs);
        Q(PROBE_ATTACH_COLOR0, 0x8214 /* BLUE_SIZE    */, bs);
        Q(PROBE_ATTACH_COLOR0, 0x8215 /* ALPHA_SIZE   */, as);
        /* 【v7 修正】v6 在这里查 0x821B / 0x821C 当作「附件宽 / 高」——
         * 但这两个 pname 其实是 GL_MAJOR_VERSION / GL_MINOR_VERSION，
         * 根本不是附件参数（ES 里也没有「附件尺寸」这个 pname）。
         * 尺寸只能从**附件对象本身**取（见下方「先绑定再查」）。 */
        Q(PROBE_ATTACH_COLOR0, 0x8CD1 /* OBJECT_NAME */, col_obj);
    }
#undef Q

    /* 若 GL_DEPTH_ATTACHMENT 为空，MC 很可能用的是合并的
     * GL_DEPTH_STENCIL_ATTACHMENT（DEPTH24_STENCIL8），单独试一次。 */
    if (dt <= 0 && get_fbo_att != NULL && get_err != NULL) {
        GLint ds_type = -1;
        (void)get_err();
        get_fbo_att(0x8D40, PROBE_ATTACH_DEPTH_STEN, 0x8CD0, &ds_type);
        if (get_err() == 0 && ds_type > 0) {
            dt = ds_type;
            glesmod_log("[probe]   （深度来自 GL_DEPTH_STENCIL_ATTACHMENT）");
        }
    }

    /* ---- 深度附件：按「挂的是什么对象」分别取内部格式 ---- */
    if (get_fbo_att != NULL && get_err != NULL) {
        /* 先拿到附件对象的名字（纹理名 / renderbuffer 名） */
        GLint depth_obj = 0;
        (void)get_err();
        get_fbo_att(0x8D40, PROBE_ATTACH_DEPTH,
                    0x8CD1 /* FRAMEBUFFER_ATTACHMENT_OBJECT_NAME */, &depth_obj);
        if (get_err() != 0) depth_obj = 0;

        /* 【v9 自证】对象名到底是不是一个「真实存在的纹理/RBO」？
         * 若 glIsTexture 返回假，说明我们查错了对象（或附件确实为空），
         * 此时任何后续格式读数都不可信 —— 必须先证明这一点再解读。 */
        {
            int is_t = (is_tex && depth_obj > 0) ? (int)is_tex((GLuint)depth_obj) : -1;
            int is_r = (is_rb  && depth_obj > 0) ? (int)is_rb((GLuint)depth_obj)  : -1;
            char b[220];
            snprintf(b, sizeof(b),
                     "[probe]   深度附件自证: 对象名=%d glIsTexture=%d glIsRenderbuffer=%d",
                     (int)depth_obj, is_t, is_r);
            glesmod_log(b);
            if (is_t == 0 && is_r == 0) {
                glesmod_log("[probe]   !! 该对象名既不是纹理也不是 RBO —— "
                            "读数无效，不能据此判断深度位数");
            }
        }

        if (dt == 0x1702 /* GL_TEXTURE */ && depth_obj > 0 && get_tex_par != NULL) {
            depth_tex = 1;
            /* 【v7 关键修正】必须先绑定附件挂的那个纹理对象，否则
             * glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, ...) 查到的是
             * 「当前恰好绑定的无关纹理」。v6 实测得到 0x1908=GL_RGBA /
             * 1024x512，对深度附件显然荒谬 —— 正是漏了这一步绑定。 */
            GLint prev_bind = 0;
            if (get_iv) get_iv(0x8069 /* GL_TEXTURE_BINDING_2D */, &prev_bind);
            if (bind_tex) bind_tex(0x0DE1, (GLuint)depth_obj);
            (void)get_err();
            get_tex_par(0x0DE1 /* GL_TEXTURE_2D */, 0,
                        0x1003 /* GL_TEXTURE_INTERNAL_FORMAT */, &depth_fmt);
            if (get_err() != 0) depth_fmt = -1;
            /* 顺带取真实尺寸，用于和视口比对 */
            GLint tex_w = -1, tex_h = -1;
            (void)get_err();
            get_tex_par(0x0DE1, 0, 0x1000 /* WIDTH  */, &tex_w);
            if (get_err() != 0) tex_w = -1;
            (void)get_err();
            get_tex_par(0x0DE1, 0, 0x1001 /* HEIGHT */, &tex_h);
            if (get_err() != 0) tex_h = -1;
            if (bind_tex) bind_tex(0x0DE1, (GLuint)prev_bind);   /* 还原原绑定 */
            if (tex_w > 0) obj_w = tex_w;   /* 用纹理实测尺寸参与「与视口比对」 */
            if (tex_h > 0) obj_h = tex_h;
            {
                char b2[220];
                snprintf(b2, sizeof(b2),
                         "[probe]   深度纹理: 名字=%d 内部格式=0x%04X 尺寸=%dx%d",
                         (int)depth_obj, depth_fmt, tex_w, tex_h);
                glesmod_log(b2);
            }
        } else if (dt == 0x8D41 /* GL_RENDERBUFFER */ && depth_obj > 0 && get_rb_par != NULL) {
            depth_rbo = 1;
            (void)get_err();
            get_rb_par(0x8D41, 0x8D44 /* GL_RENDERBUFFER_INTERNAL_FORMAT */, &depth_fmt);
            if (get_err() != 0) depth_fmt = -1;
            GLint rb_w = -1, rb_h = -1;
            (void)get_err();
            get_rb_par(0x8D41, 0x8D42 /* WIDTH  */, &rb_w);
            if (get_err() != 0) rb_w = -1;
            (void)get_err();
            get_rb_par(0x8D41, 0x8D43 /* HEIGHT */, &rb_h);
            if (get_err() != 0) rb_h = -1;
            if (rb_w > 0) obj_w = rb_w;
            if (rb_h > 0) obj_h = rb_h;
            {
                char b2[220];
                snprintf(b2, sizeof(b2),
                         "[probe]   深度 RBO: 名字=%d 内部格式=0x%04X 尺寸=%dx%d",
                         (int)depth_obj, depth_fmt, rb_w, rb_h);
                glesmod_log(b2);
            }
        } else {
            depth_fmt = -1;
        }
    }

    /* ---- 颜色附件：同样必须「先绑定再查」（v7 新增） ----
     * v6 的「颜色附件 尺寸」其实是深度纹理路径顺手写下的值（两者混用），
     * 必须单独、正确地量一次，否则「与视口比对」的结论不可信。 */
    if (get_fbo_att != NULL && get_err != NULL && col_obj > 0) {
        if (ct == 0x1702 /* GL_TEXTURE */ && get_tex_par != NULL) {
            GLint prev_bind = 0;
            if (get_iv) get_iv(0x8069 /* GL_TEXTURE_BINDING_2D */, &prev_bind);
            if (bind_tex) bind_tex(0x0DE1, (GLuint)col_obj);
            (void)get_err(); get_tex_par(0x0DE1, 0, 0x1003, &col_fmt);
            if (get_err() != 0) col_fmt = -1;
            (void)get_err(); get_tex_par(0x0DE1, 0, 0x1000, &col_w);
            if (get_err() != 0) col_w = -1;
            (void)get_err(); get_tex_par(0x0DE1, 0, 0x1001, &col_h);
            if (get_err() != 0) col_h = -1;
            if (bind_tex) bind_tex(0x0DE1, (GLuint)prev_bind);
            /* 颜色附件尺寸才是与视口比对的正确基准 */
            if (col_w > 0) obj_w = col_w;
            if (col_h > 0) obj_h = col_h;
            {
                char b2[220];
                snprintf(b2, sizeof(b2),
                         "[probe]   颜色纹理: 名字=%d 内部格式=0x%04X 尺寸=%dx%d",
                         col_obj, col_fmt, col_w, col_h);
                glesmod_log(b2);
            }
        } else if (ct == 0x8D41 /* GL_RENDERBUFFER */ && get_rb_par != NULL) {
            if (bind_rb) bind_rb(0x8D41, (GLuint)col_obj);
            (void)get_err(); get_rb_par(0x8D41, 0x8D44, &col_fmt);
            if (get_err() != 0) col_fmt = -1;
            (void)get_err(); get_rb_par(0x8D41, 0x8D42, &col_w);
            if (get_err() != 0) col_w = -1;
            (void)get_err(); get_rb_par(0x8D41, 0x8D43, &col_h);
            if (get_err() != 0) col_h = -1;
            if (col_w > 0) obj_w = col_w;
            if (col_h > 0) obj_h = col_h;
        }
    }

    char buf[420];
    snprintf(buf, sizeof(buf),
             "[probe] 环境(%s): FBO=%d 完整性=0x%04X(0x8CD5=完整) 视口=(%d,%d,%d,%d)",
             tag, fbo, status, vp[0], vp[1], vp[2], vp[3]);
    glesmod_log(buf);

    {
        char t1[40], t2[40];
        const char *n;
        n = name_attach_type(dt);
        if (n) snprintf(t1, sizeof(t1), "%s", n); else snprintf(t1, sizeof(t1), "0x%04X", dt);
        n = name_attach_type(ct);
        if (n) snprintf(t2, sizeof(t2), "%s", n); else snprintf(t2, sizeof(t2), "0x%04X", ct);

        {
            char f2[64];
            const char *nmc = name_internal_format(col_fmt);
            if (nmc) snprintf(f2, sizeof(f2), "%s", nmc);
            else     snprintf(f2, sizeof(f2), "0x%04X", col_fmt);
            snprintf(buf, sizeof(buf),
                     "[probe]   颜色附件: 类型=%s 对象=%d 内部格式=%s "
                     "位深=(%d,%d,%d,%d) 尺寸=%dx%d",
                     t2, col_obj, f2, rs, gs, bs, as, obj_w, obj_h);
            glesmod_log(buf);
        }

        if (depth_fmt >= 0) {
            char f[64];
            const char *nm = name_internal_format(depth_fmt);
            if (nm) snprintf(f, sizeof(f), "%s", nm);
            else    snprintf(f, sizeof(f), "0x%04X", depth_fmt);

            snprintf(buf, sizeof(buf),
                     "[probe]   深度附件: 类型=%s 内部格式=%s (纹理=%d RBO=%d)",
                     t1, f, depth_tex, depth_rbo);
            glesmod_log(buf);
        } else {
            snprintf(buf, sizeof(buf),
                     "[probe]   深度附件: 类型=%s 内部格式=查询失败(depth_tex=%d depth_rbo=%d)",
                     t1, depth_tex, depth_rbo);
            glesmod_log(buf);
        }

        if (dt == 0 /* GL_NONE */) {
            glesmod_log("[probe]   !! 默认帧缓冲没有深度附件 -> 深度测试必然失效");
        } else if (depth_fmt == 0x81A5 /* GL_DEPTH_COMPONENT16 */) {
            glesmod_log("[probe]   !! 深度只有 16 位 -> 薄几何（栅栏 / 堆肥桶等"
                        "非整格方块）前后关系必然错乱；整格方块因厚度大而看不出来");
        }
        if (obj_w > 0 && vp[2] > 0 && (obj_w != vp[2] || obj_h != vp[3])) {
            snprintf(buf, sizeof(buf),
                     "[probe]   !! 附件尺寸(%dx%d) 与视口(%dx%d) 不一致 "
                     "-> 渲染会被缩放/偏移",
                     obj_w, obj_h, vp[2], vp[3]);
            glesmod_log(buf);
        }
    }

    /* ---- 额外状态：深度约定 / 多边形偏移 / sRGB / 多重采样（v7 新增） ---- */
    if (get_iv != NULL) {
        int wmask   = get_int_safe(get_iv, 0x0B72 /* GL_DEPTH_WRITEMASK      */);
        int po_fill = get_int_safe(get_iv, 0x8037 /* GL_POLYGON_OFFSET_FILL   */);
        int scissor = get_int_safe(get_iv, 0x0C11 /* GL_SCISSOR_TEST         */);
        int srgb    = get_int_safe(get_iv, 0x8DB9 /* GL_FRAMEBUFFER_SRGB     */);
        int samples = get_int_safe(get_iv, 0x80A9 /* GL_SAMPLES              */);
        snprintf(buf, sizeof(buf),
                 "[probe]   状态: 深度写掩码=%d 多边形偏移填充=%d 剪切=%d "
                 "sRGB=%d 采样数=%d",
                 wmask, po_fill, scissor, srgb, samples);
        glesmod_log(buf);
    }

    /* EGL 配置探测（「有没有深度缓冲」的权威来源，见函数头注释） */
    dump_egl_config_once();
}

/* ------------------------------------------------------------------ */
/* 读回三个关键 uniform 的实际数值（v4 新增）                           */
/* ------------------------------------------------------------------ */

static void dump_key_uniforms(prog_rec *r) {
    typedef GLint (*get_uni_loc_t)(GLuint, const GLchar *);
    typedef void  (*get_uni_fv_t)(GLuint, GLint, GLfloat *);
    static get_uni_loc_t get_uni_loc = NULL;
    static get_uni_fv_t  get_uni_fv  = NULL;
    static int tried = 0;

    if (!tried) {
        tried = 1;
        get_uni_loc = (get_uni_loc_t)glesym_resolve("glGetUniformLocation");
        get_uni_fv  = (get_uni_fv_t)glesym_resolve("glGetUniformfv");
    }
    if (get_uni_loc == NULL || get_uni_fv == NULL) return;

    GLfloat v[16];
    GLint   loc;
    char    buf[360];

    loc = get_uni_loc((GLuint)r->prog, "ChunkOffset");
    if (loc >= 0) {
        memset(v, 0, sizeof(v));
        get_uni_fv((GLuint)r->prog, loc, v);
        r->has_ckoff = 1;
        r->ckoff[0] = v[0]; r->ckoff[1] = v[1]; r->ckoff[2] = v[2];
        snprintf(buf, sizeof(buf),
                 "[probe]   ChunkOffset = (%.3f, %.3f, %.3f)",
                 v[0], v[1], v[2]);
        glesmod_log(buf);
    }

    loc = get_uni_loc((GLuint)r->prog, "ModelViewMat");
    if (loc >= 0) {
        memset(v, 0, sizeof(v));
        get_uni_fv((GLuint)r->prog, loc, v);
        r->has_mv = 1;
        r->mv_trans[0] = v[12]; r->mv_trans[1] = v[13];
        r->mv_trans[2] = v[14]; r->mv_trans[3] = v[15];
        snprintf(buf, sizeof(buf),
                 "[probe]   ModelViewMat 平移列 = (%.3f, %.3f, %.3f, %.3f)",
                 v[12], v[13], v[14], v[15]);
        glesmod_log(buf);
    }

    loc = get_uni_loc((GLuint)r->prog, "ProjMat");
    if (loc >= 0) {
        memset(v, 0, sizeof(v));
        get_uni_fv((GLuint)r->prog, loc, v);
        r->has_proj = 1;
        r->proj_zw[0] = v[0];  r->proj_zw[1] = v[5];  r->proj_zw[2] = v[10];
        r->proj_zw[3] = v[11]; r->proj_zw[4] = v[14]; r->proj_zw[5] = v[15];
        snprintf(buf, sizeof(buf),
                 "[probe]   ProjMat m0=%.4f m5=%.4f m10=%.4f m11=%.4f "
                 "m14=%.4f m15=%.4f",
                 v[0], v[5], v[10], v[11], v[14], v[15]);
        glesmod_log(buf);
    }
}

/* ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ */
/* 顶点缓冲实测（v5 新增）—— 「上传给驱动的顶点数据到底是什么」          */
/*                                                                      */
/* 为什么这是最后一块拼图：                                              */
/*   v3/v4 已证明：顶点布局对、状态对、着色器对、uniform 值对、无丢调用。*/
/*   唯一没被直接看过的是 **VBO 里的字节**。若顶点数据本身没问题，        */
/*   那么「形状对、位置/朝向错」就只能来自变换或更下游。                 */
/*                                                                      */
/* 做法：在该程序首次绘制时，用 glMapBufferRange(GLES_MAP_READ) 把         */
/*   当前 ARRAY_BUFFER 的头 96 字节读回来。按该程序的 stride 解析前 3 个   */
/*   顶点，打印 Position / Color / UV0，直接看数据是否合理。             */
/*                                                                      */
/* 只做一次、只读 96 字节、立刻 unmap —— 开销可忽略。                    */
/* ------------------------------------------------------------------ */

/* 把头部字节按 stride 解析成「顶点字段」打印（Position/Color/UV0） */
static void dump_vertex_bytes(const prog_rec *r,
                              const unsigned char *p, int nbytes, int stride,
                              int vbo, int size) {
    char b[360];
    (void)vbo; (void)size;   /* 头一行已由 dump_vertex_data_once 打印 */

    int nv = nbytes / (stride > 0 ? stride : 1);
    if (nv > 3) nv = 3;

    for (int i = 0; i < nv; i++) {
        const unsigned char *v = p + (size_t)i * (size_t)stride;

        /* 按该程序的属性布局解析（size/type 已由 v3 证实与 MC 一致） */
        float pos[3] = {0, 0, 0};
        float uv0[2] = {0, 0};
        unsigned char col[4] = {0, 0, 0, 0};
        int ok_pos = 0, ok_col = 0, ok_uv = 0;

        for (int a = 0; a < 8; a++) {
            if (!r->va_enabled[a]) continue;
            int off = (int)r->va_offset[a];
            if (off < 0 || off >= stride) continue;
            const unsigned char *q = v + off;

            if (r->va_type[a] == 0x1406 /* FLOAT */ && r->va_size[a] == 3 && !ok_pos) {
                memcpy(pos, q, 12);
                ok_pos = 1;
            } else if (r->va_type[a] == 0x1406 /* FLOAT */ && r->va_size[a] == 2 && !ok_uv) {
                memcpy(uv0, q, 8);
                ok_uv = 1;
            } else if (r->va_type[a] == 0x1401 /* UNSIGNED_BYTE */ && r->va_size[a] == 4 && !ok_col) {
                memcpy(col, q, 4);
                ok_col = 1;
            }
        }

        snprintf(b, sizeof(b),
                 "[probe]     顶点%d: Pos=(%.3f, %.3f, %.3f) UV0=(%.3f, %.3f) "
                 "Color=(%u, %u, %u, %u)",
                 i, pos[0], pos[1], pos[2], uv0[0], uv0[1],
                 col[0], col[1], col[2], col[3]);
        glesmod_log(b);
    }
}

static void dump_vertex_data_once(const prog_rec *r) {
    typedef void *  (*map_range_t)(GLenum, GLintptr, GLsizeiptr, GLbitfield);
    typedef GLboolean (*unmap_t)(GLenum);
    typedef void    (*get_iv_t)(GLenum, GLint *);
    typedef void    (*get_buf_par_t)(GLenum, GLenum, GLint *);

    static int tried = 0;
    static map_range_t   map_range   = NULL;
    static unmap_t       unmap       = NULL;
    static get_iv_t      get_iv      = NULL;
    static get_buf_par_t get_buf_par = NULL;
    /* 【v7】改为「每个程序各转储一次」，而不是全局一次。
     *   原因：用户反馈「整格方块正常、非整格方块（栅栏/堆肥桶）错位」。
     *   这些几何**在同一个区块网格里、由同一个程序绘制**，唯一差别是
     *   局部厚度。只有把 solid / cutout / translucent 各自的顶点都看一遍，
     *   才能判断是「数据差异」还是「深度精度/状态」问题。 */
    static int dumped[PROBE_MAX_PROGS];

    {
        int slot = (int)(r - g_rec);
        if (slot < 0 || slot >= PROBE_MAX_PROGS) return;
        if (dumped[slot]) return;
        dumped[slot] = 1;
    }
    if (!tried) {
        tried = 1;
        map_range   = (map_range_t)glesym_resolve("glMapBufferRange");
        unmap       = (unmap_t)glesym_resolve("glUnmapBuffer");
        get_iv      = (get_iv_t)glesym_resolve("glGetIntegerv");
        get_buf_par = (get_buf_par_t)glesym_resolve("glGetBufferParameteriv");
    }
    if (map_range == NULL || unmap == NULL || get_iv == NULL) return;

    /* 需要该程序正在用的 VBO 与 stride：stride 从属性 0 取（同一次绘制内一致） */
    GLint vbo = 0, size = 0;
    get_iv(0x8894 /* GL_ARRAY_BUFFER_BINDING */, &vbo);
    if (vbo <= 0) return;
    if (get_buf_par) {
        get_buf_par(0x8892 /* GL_ARRAY_BUFFER */, 0x8764 /* GL_BUFFER_SIZE */, &size);
    }

    int stride = r->va_stride[0];
    if (stride <= 0) return;

    const GLsizeiptr want = 96;   /* 够放 3 个 stride<=32 的顶点 */
    GLbitfield bits = 0x0001 /* GL_MAP_READ_BIT */;
    void *p = map_range(0x8892 /* GL_ARRAY_BUFFER */, 0, want, bits);
    if (p == NULL) {
        char b[200];
        snprintf(b, sizeof(b),
                 "[probe]   顶点缓冲实测: 无法 map（vbo=%d size=%d）", (int)vbo, (int)size);
        glesmod_log(b);
        return;
    }

    /* 打印该程序的身份，便于把「程序 N」和 solid/cutout 对上号 */
    {
        char b[160];
        snprintf(b, sizeof(b), "[probe]   程序 %u 顶点缓冲实测: vbo=%d 大小=%d stride=%d",
                 r->prog, (int)vbo, (int)size, stride);
        glesmod_log(b);
    }

    dump_vertex_bytes(r, (const unsigned char *)p, (int)want, stride,
                      (int)vbo, (int)size);

    (void)unmap(0x8892 /* GL_ARRAY_BUFFER */);
}

/* 识别并转储一个程序的身份（uniform / 属性 / 顶点布局 / 状态）         */
/* ------------------------------------------------------------------ */

/*
 * 为什么用「活跃 uniform 名」来识别程序：
 *   MC 每个渲染色器都有一组固定命名的 uniform ——
 *     ProjMat / ModelViewMat  -> 所有 3D 路径都有
 *     ChunkOffset             -> 区块地形（关键特征）
 *     OverlayColor / UV1      -> 实体
 *     FogShape / FogStart     -> 世界几何
 *     ScreenSize              -> GUI / 全屏
 *   把名字列出来，程序身份就自明了，不需要猜着色器 ID 的映射关系。
 */
static void identify_prog(prog_rec *r) {
    typedef void   (*get_prog_iv_t)(GLuint, GLenum, GLint *);
    typedef void   (*get_active_uni_t)(GLuint, GLuint, GLsizei, GLsizei *,
                                       GLint *, GLenum *, GLchar *);
    typedef void   (*get_active_attr_t)(GLuint, GLuint, GLsizei, GLsizei *,
                                        GLint *, GLenum *, GLchar *);
    typedef void   (*get_iv_t)(GLenum, GLint *);
    typedef void   (*get_va_iv_t)(GLuint, GLenum, GLint *);
    typedef void   (*get_va_ptr_t)(GLuint, GLenum, void **);
    typedef GLenum (*get_err_t)(void);

    static get_prog_iv_t      get_prog_iv   = NULL;
    static get_active_uni_t   get_active_u  = NULL;
    static get_active_attr_t  get_active_a  = NULL;
    static get_iv_t           get_iv        = NULL;
    static get_va_iv_t        get_va_iv     = NULL;
    static get_va_ptr_t       get_va_ptr    = NULL;
    static get_err_t          get_err       = NULL;
    static int tried = 0;

    if (!tried) {
        tried = 1;
        get_prog_iv  = (get_prog_iv_t)glesym_resolve("glGetProgramiv");
        get_active_u = (get_active_uni_t)glesym_resolve("glGetActiveUniform");
        get_active_a = (get_active_attr_t)glesym_resolve("glGetActiveAttrib");
        get_iv       = (get_iv_t)glesym_resolve("glGetIntegerv");
        get_va_iv    = (get_va_iv_t)glesym_resolve("glGetVertexAttribiv");
        get_va_ptr   = (get_va_ptr_t)glesym_resolve("glGetVertexAttribPointerv");
        get_err      = (get_err_t)glesym_resolve("glGetError");
    }

    /* ---- 1. 状态 ---- */
    if (get_iv != NULL) {
        r->depth_test = get_int_safe(get_iv, 0x0B71);
        r->depth_func = get_int_safe(get_iv, 0x0B74);
        r->depth_mask = get_int_safe(get_iv, 0x0B72);
        r->cull_face  = get_int_safe(get_iv, 0x0B44);
        r->cull_mode  = get_int_safe(get_iv, 0x0B45);
        r->front_face = get_int_safe(get_iv, 0x0B46);
        r->blend      = get_int_safe(get_iv, 0x0BE2);
        r->blend_src  = get_int_safe(get_iv, 0x80C9);  /* BLEND_SRC_RGB */
        r->blend_dst  = get_int_safe(get_iv, 0x80C8);  /* BLEND_DST_RGB */
    }

    /* ---- 2. 活跃 uniform 名 ---- */
    if (get_prog_iv != NULL && get_active_u != NULL && get_err != NULL) {
        GLint n = 0;
        if (get_err) (void)get_err();
        get_prog_iv((GLuint)r->prog, 0x8B86 /* ACTIVE_UNIFORMS */, &n);
        if (get_err() == 0 && n > 0) {
            if (n > PROBE_MAX_UNIFORMS) n = PROBE_MAX_UNIFORMS;
            for (GLint i = 0; i < n; i++) {
                GLchar nm[PROBE_NAME_LEN] = {0};
                GLsizei len = 0; GLint sz = 0; GLenum ty = 0;
                get_active_u((GLuint)r->prog, (GLuint)i, PROBE_NAME_LEN - 1,
                             &len, &sz, &ty, nm);
                if (len > 0) {
                    snprintf(r->uni[r->uni_count], PROBE_NAME_LEN, "%s", nm);
                    r->uni_count++;
                }
                if (r->uni_count >= PROBE_MAX_UNIFORMS) break;
            }
        }
    }

    /* ---- 3. 活跃属性名 ---- */
    if (get_prog_iv != NULL && get_active_a != NULL && get_err != NULL) {
        GLint n = 0;
        if (get_err) (void)get_err();
        get_prog_iv((GLuint)r->prog, 0x8B89 /* ACTIVE_ATTRIBUTES */, &n);
        if (get_err() == 0 && n > 0) {
            if (n > PROBE_MAX_ATTRIBS) n = PROBE_MAX_ATTRIBS;
            for (GLint i = 0; i < n; i++) {
                GLchar nm[PROBE_NAME_LEN] = {0};
                GLsizei len = 0; GLint sz = 0; GLenum ty = 0;
                get_active_a((GLuint)r->prog, (GLuint)i, PROBE_NAME_LEN - 1,
                             &len, &sz, &ty, nm);
                if (len > 0) {
                    snprintf(r->attrib[r->attrib_count], PROBE_NAME_LEN, "%s", nm);
                    r->attrib_count++;
                }
                if (r->attrib_count >= PROBE_MAX_ATTRIBS) break;
            }
        }
    }

    /* ---- 4. 顶点属性布局（此刻正在生效的那一套） ---- */
    if (get_va_iv != NULL) {
        for (GLuint i = 0; i < 8; i++) {
            GLint en = 0;
            get_va_iv(i, 0x8622 /* ENABLED */, &en);
            r->va_enabled[i] = (en == 1) ? 1 : 0;
            if (!r->va_enabled[i]) continue;
            GLint sz = 0, st = 0, ty = 0, nm = 0;
            void *ptr = NULL;
            get_va_iv(i, 0x8623 /* SIZE */, &sz);
            get_va_iv(i, 0x8624 /* STRIDE */, &st);
            get_va_iv(i, 0x8625 /* TYPE */, &ty);
            get_va_iv(i, 0x886A /* NORMALIZED */, &nm);
            if (get_va_ptr != NULL) get_va_ptr(i, 0x8645 /* POINTER */, &ptr);
            r->va_size[i] = sz; r->va_stride[i] = st;
            r->va_type[i] = ty; r->va_norm[i] = nm;
            r->va_offset[i] = (long)(intptr_t)ptr;
        }
    }

    /* ---- 5. 输出 ---- */
    {
        char buf[420];
        char df[16], cm[16], ff[16], bs[24], bd[24];
        fmt_enum(df, sizeof(df), r->depth_func, name_depth_func);
        fmt_enum(cm, sizeof(cm), r->cull_mode,  name_cull_mode);
        fmt_enum(ff, sizeof(ff), r->front_face, name_front_face);
        fmt_enum(bs, sizeof(bs), r->blend_src,  name_blend);
        fmt_enum(bd, sizeof(bd), r->blend_dst,  name_blend);

        snprintf(buf, sizeof(buf),
                 "[probe] === 程序 %u 首次绘制，身份识别 ===\n"
                 "[probe]   状态: DEPTH_TEST=%d FUNC=%s MASK=%d | "
                 "CULL=%d MODE=%s FACE=%s | BLEND=%d SRC=%s DST=%s",
                 r->prog, r->depth_test, df, r->depth_mask,
                 r->cull_face, cm, ff, r->blend, bs, bd);
        glesmod_log(buf);
    }
    {
        /* uniform 名单：一行放不完就分多行 */
        char buf[400];
        int n = snprintf(buf, sizeof(buf), "[probe]   uniforms(%d):", r->uni_count);
        for (int i = 0; i < r->uni_count; i++) {
            if (n < 0 || (size_t)n >= sizeof(buf) - 2) break;
            n += snprintf(buf + n, sizeof(buf) - (size_t)n, " %s", r->uni[i]);
        }
        if (n > 0 && (size_t)n < sizeof(buf)) glesmod_log(buf);
    }
    {
        char buf[400];
        int n = snprintf(buf, sizeof(buf), "[probe]   attribs(%d):", r->attrib_count);
        for (int i = 0; i < r->attrib_count; i++) {
            if (n < 0 || (size_t)n >= sizeof(buf) - 2) break;
            n += snprintf(buf + n, sizeof(buf) - (size_t)n, " %s", r->attrib[i]);
        }
        if (n > 0 && (size_t)n < sizeof(buf)) glesmod_log(buf);
    }
    for (int i = 0; i < 8; i++) {
        if (!r->va_enabled[i]) continue;
        char buf[220];
        char tn[24];
        fmt_enum(tn, sizeof(tn), r->va_type[i], name_gl_type);
        snprintf(buf, sizeof(buf),
                 "[probe]   顶点属性 %d: size=%d type=%s stride=%d norm=%d offset=%ld",
                 i, r->va_size[i], tn, r->va_stride[i], r->va_norm[i],
                 r->va_offset[i]);
        glesmod_log(buf);
    }

    {
        /* 用 uniform/属性名判断这是哪条渲染路径。
         *
         * 【v4 修的一个误判】
         *   v3 把「含 Sampler2」也算作区块地形的特征，结果程序 69/72/75/84/87
         *   （带 Light0_Direction + Normal + UV1）被误标成「区块地形」。
         *   那些其实是实体 / 物品的 rendertype_* 路径 —— 它们同样用 Sampler2 光照贴图。
         *
         *   现在改成：只有 **ChunkOffset** 才是区块地形的判据（MC 里仅
         *   rendertype_solid / cutout / cutout_mipped / translucent / tripwire
         *   这 5 个着色器有 ChunkOffset），实体的特征则优先按 Light/Normal/UV1 判。 */
        char buf[420];
        const char *role;
        if (has_token(r, "ChunkOffset")) {
            role = "区块地形 chunk（有 ChunkOffset）";
        } else if (has_token(r, "Light0_Direction") || has_token(r, "OverlayColor")
                   || (has_token(r, "Normal") && has_token(r, "UV1"))) {
            role = "实体 / 物品 entity（Light/Normal/UV1）";
        } else if (has_token(r, "ScreenSize") || has_token(r, "ProjMat") == 0) {
            role = "GUI / 全屏后处理（无 ProjMat）";
        } else if (has_token(r, "ModelViewMat")) {
            role = "世界几何（ModelViewMat + ProjMat）";
        } else {
            role = "未知";
        }
        snprintf(buf, sizeof(buf), "[probe]   推断身份: %s", role);
        glesmod_log(buf);

        /* ---- 6b. 世界阶段的环境自检（v5 关键修正） ----
         *
         * v4 把环境探测挂在了「第一次 glDrawElements」上 —— 那是**加载期的
         * 2D 界面绘制**，此时 MC 还没建主帧缓冲（FBO=1 是它自己的临时对象，
         * 所以深度附件查询全部无效）。
         *
         * 正确的时机是**第一次区块地形绘制**：此刻渲染目标必然是 MC 的主
         * 世界帧缓冲，查到的深度/尺寸才是「真正决定画面」的那一份。 */
        if (has_token(r, "ChunkOffset")) {
            dump_env("首次区块绘制时");
            dump_vertex_data_once(r);
            dump_all_attachments();   /* v9：一次列清所有附件 */
        }

        /* ---- 8. 纹理单元 / 采样器实测（v8 新增） ----
         * 对**每个程序**各打一次：这样能直接对比
         *   「GUI/物品程序」与「区块地形程序」的采样器↔单元绑定是否一致。
         * 用户反馈「世界方块错、物品栏/手持正常」时，这一对比就是关键证据。 */
        dump_texture_state();
    }

    /* ---- 7. 关键 uniform 的实际数值（v4 新增） ---- */
    dump_key_uniforms(r);

    r->identified = 1;
}

/* ------------------------------------------------------------------ */

static prog_rec *rec_for(unsigned int prog) {
    for (int i = 0; i < PROBE_MAX_PROGS; i++) {
        if (g_rec[i].prog == prog) return &g_rec[i];
    }
    for (int i = 0; i < PROBE_MAX_PROGS; i++) {
        if (g_rec[i].prog == 0) {
            prog_rec *r = &g_rec[i];
            memset(r, 0, sizeof(*r));
            r->prog = prog;
            r->depth_func = r->cull_mode = r->front_face = -1;
            r->blend_src = r->blend_dst = -1;
            return r;
        }
    }
    return NULL;
}

static void flush_second(long long t) {
    if (t == 0) return;
    if (g_last_sec_ms == 0) { g_last_sec_ms = t; return; }
    if (t - g_last_sec_ms < 1000) return;

    if (g_sec_draws > 0) {
        char buf[120];
        snprintf(buf, sizeof(buf),
                 "[probe] === 上一秒合计 %lu 次三角形绘制 ===", g_sec_draws);
        glesmod_log(buf);

        for (int i = 0; i < PROBE_MAX_PROGS; i++) {
            prog_rec *r = &g_rec[i];
            if (r->prog == 0 || r->draws == 0) continue;
            char b[320];
            long avg = (r->draws > 0) ? (long)(r->indexed / r->draws) : 0;
            snprintf(b, sizeof(b),
                     "[probe]   程序 %u: draw=%lu 索引=%lu count %d~%d 平均=%ld",
                     r->prog, r->draws, r->indexed,
                     r->min_count, r->max_count, avg);
            glesmod_log(b);
        }
    }

    for (int i = 0; i < PROBE_MAX_PROGS; i++) {
        g_rec[i].draws = 0;
        g_rec[i].indexed = 0;
        g_rec[i].min_count = 0;
        g_rec[i].max_count = 0;
    }
    g_sec_draws = 0;
    g_last_sec_ms = t;
}

/* ------------------------------------------------------------------ */

/*
 * 探针主体。**必须 noinline** —— 这是热路径的关键。
 *
 * 【实测依据】native/tools/hotpath_cost.py 反汇编 optimized 产物发现：
 * 只要探针代码内联在 glDrawElements 里，编译器就必须为**每一次**绘制
 * 保留 496 字节栈帧、12 个 callee-saved 寄存器，以及栈保护金丝雀
 * （mrs TPIDR_EL0 / stur / ldr 三条）：
 *
 *     1  stp x29, x30, [sp, #-0x60]!   <- 96 字节栈帧
 *     2-6 stp x28..x19, ...            <- 10 个 callee-saved 寄存器
 *     7  mov x29, sp
 *     8  sub sp, sp, #0x1f0            <- 又减 496 字节
 *     9  mrs x24, TPIDR_EL0            <- 栈保护金丝雀
 *    12  ldr x8, [x24, #0x28]
 *    17  stur x8, [x29, #-0x10]        <- 写入金丝雀
 *
 * 一共 17 条指令的纯序言，**而探针默认是关闭的**（GLESMOD_GEOM_PROBE=0），
 * 这段代码在正常情况下一次都不会执行。把它拆成不内联的函数后，
 * 序言成本移到那条几乎不会走的路径上。
 *
 * glDrawElements 是区块绘制里逐条调用的函数，因此这里的收益是
 * 直接落在每帧总时长上的。
 */
#if defined(__GNUC__)
__attribute__((noinline))
#endif
static void probe_on_draw(GLenum mode, GLsizei count) {
    typedef void (*get_iv_t)(GLenum, GLint *);
    static get_iv_t get_iv = NULL;

    /* 只有三角面（且 count 有效）才值得统计 */
    if (mode != 0x0004 /* GL_TRIANGLES */ || count <= 0) return;

    if (get_iv == NULL) get_iv = (get_iv_t)glesym_resolve("glGetIntegerv");
    GLint prog = 0;
    if (get_iv != NULL) get_iv(0x8B8D /* CURRENT_PROGRAM */, &prog);

    prog_rec *r = rec_for((unsigned int)prog);
    if (r != NULL) {
        /*
         * 首次见到这个程序 -> 立刻识别它。
         * 此刻的 uniform / 顶点布局 / 状态必然属于这个程序的绘制，
         * 不存在"采样时机不对"的可能。
         *
         * 【v5 修正】环境探测（帧缓冲深度/尺寸/EGL）改由 identify_prog
         * 在「首个区块地形程序」时触发 —— 那才是世界渲染目标就绪的时刻。
         * v4 挂在加载期第一次绘制上，拿到的是 MC 的临时 FBO，全部无效。
         */
        if (!r->identified) identify_prog(r);

        r->draws++;
        r->indexed += (unsigned long)count;
        if (r->max_count < count) r->max_count = count;
        if (r->min_count == 0 || r->min_count > count) r->min_count = count;
    }
    g_sec_draws++;
    flush_second(now_ms());

    /* 【v9】世界已经画了一会儿之后，做一次深度回读实测。
     * 等到累计绘制超过一定量再测，确保此刻屏幕上确实有世界几何，
     * 从而「读到全 1.0」才有诊断意义（否则可能是空场景）。 */
    if (g_sec_draws > 200) probe_depth_readback_once();
}

void glDrawElements(GLenum mode, GLsizei count, GLenum type,
                    const void *indices) {
    typedef void (*fn_t)(GLenum, GLsizei, GLenum, const void *);
    static fn_t real = NULL;

    /*
     * 稳态热路径：一次全局变量读取 + 一次条件分支。
     *
     * 【优化前】稳态每次调用要执行：
     *      glesmod_lazy_init();          <- 跨编译单元 PLT 调用 + 栈帧
     *      if (g_probe_on < 0) { ...读环境变量、可能打日志... }
     *      if (g_probe_on && ...) { ...探针主体（内联）... }
     *      PROBE_RESOLVE_OR_RETURN(...)
     *   反汇编实测稳态 36 条指令，且序言被迫保留 496 字节栈帧与
     *   栈保护金丝雀（原因见 probe_on_draw 的注释）。
     *
     * 【优化后】稳态只走：
     *      if (!g_probe_ready) { ...一次性检查... }
     *      if (g_probe_on) { probe_on_draw(...); }   <- 默认不跳，noinline
     *      (real(...))                               <- 直接间接调用
     *
     * 【为什么可以把「初始化」与「探针开关」合并成一次判断】
     *   探针开关 GLESMOD_GEOM_PROBE 由启动器在 dlopen 前通过环境变量注入，
     *   进程生命周期内**不会改变**；初始化也只会真正结束一次。
     *   两者都是「一次性状态」，因此读过一次即可永久确定。
     */
    if (__builtin_expect(g_probe_ready, 1) == 0) {
        glesmod_lazy_init();

        if (g_probe_on < 0) {
            g_probe_on = glesmod_env_int(GLESMOD_ENV_GEOM_PROBE, 0);
            glesmod_log(g_probe_on
                ? "[probe] 几何诊断探针 v10 已开启（已移除自伤的深度回读）"
                : "[probe] 探针未开启；glDrawElements 纯转发");
        }

        /*
         * 只有初始化真正结束（且非深度追踪）才允许进入快速路径。
         *
         * 直接复用 glesmod_hotpath_ready —— 它的语义恰好就是「初始化已结束
         * 且无需每次钩子」，由 glesmod_lazy_init() 维护。这样不必再引入
         * 一个平行的条件判断，也不会出现两份可能不同步的判据。
         */
        if (glesmod_hotpath_ready) {
            g_probe_ready = 1;
        }
    }

    if (g_probe_on) {
        probe_on_draw(mode, count);
    }

    PROBE_RESOLVE_OR_RETURN(real, "glDrawElements", );

    real(mode, count, type, indices);
}
