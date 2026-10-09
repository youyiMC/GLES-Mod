/*
 * Table-terminator self-check.
 *
 * ================== 为什么需要这个文件 ==================
 *
 * 真机 SIGSEGV（2026-10-06，Flywheel shader=220）：
 *     # Problematic frame:
 *     # C  [libc.so+0x6bf90]  __strlen_aarch64+0x10
 *
 * 根因：`FLOAT_BUILTIN_FNS[]` 漏了 `NULL` 终止符，而所有遍历点都写成
 *     for (int i = 0; FLOAT_BUILTIN_FNS[i] != NULL; i++) {
 *         size_t n = strlen(FLOAT_BUILTIN_FNS[i]);   // <-- 越界后读野指针
 *     }
 * 越过数组末尾后把相邻内存当作 `const char *` 解引用，在 strlen 上崩溃。
 *
 * 【为什么宿主机单测没有发现】
 *   x86-64 上同样的越界刚好落在可读内存里，于是"通过"了。
 *   更糟的是：**崩溃点取决于编译器把哪张表放在它后面**，
 *   所以它时而崩、时而不崩 —— 这类缺陷无法靠"跑一遍看看"来保证。
 *
 * 【本文件的做法】
 *   把「每张以 NULL 结尾的表在第 N 个元素内确实终止」写成**机械化的断言**，
 *   在每次跑单测时执行。新增/修改表时若漏了终止符，这里立刻报错。
 *
 * 编译：
 *     gcc -O1 -std=c11 -Wall -I native/src -I native/include \
 *         -o termcheck native/tools/test_table_terminators.c \
 *         native/src/shader.c -lm
 * 运行：退出码 0 = 通过，1 = 有表未终止。
 */
#include <stdio.h>
#include <string.h>

/*
 * shader.c 里的表都是 `static`，外部链接不可见。
 * 因此这里不直接引用它们，而是**重新解析源码**做静态检查 ——
 * 这反而更强：它检查的是真实源文件，不依赖任何导出符号。
 */

#define MAX_LINE 4096
#define MAX_TABLES 64
#define MAX_NAME 128
/* 任何一张表若在这么多元素内还没终止，就判定为漏了终止符 */
#define SCAN_LIMIT 256

typedef struct {
    char name[MAX_NAME];
    int  decl_line;
    int  found_null;      /* 表内出现独立的 NULL 元素 */
    int  uses_sizeof;     /* 用 sizeof(TABLE) 遍历 -> 不需要终止符 */
    int  entries;
} table_info;

static int is_ident_char(int c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}

int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : "native/src/shader.c";
    FILE *fh = fopen(path, "rb");
    if (fh == NULL) {
        fprintf(stderr, "cannot open %s\n", path);
        return 2;
    }

    table_info tabs[MAX_TABLES];
    int ntab = 0;
    int lineno = 0;
    int in_table = 0;         /* 正在收集哪张表 */
    int depth = 0;            /* 花括号深度 */
    int bad = 0;
    int checked = 0;

    char line[MAX_LINE];
    while (fgets(line, sizeof(line), fh) != NULL) {
        lineno++;

        if (!in_table) {
            /*
             * 匹配 `const char *const NAME[] = {`（允许前置 static）。
             * 刻意不匹配 `struct { ... } KWS[]` 那种复合类型 ——
             * 它们用 sizeof 遍历，不依赖终止符。
             */
            const char *kw = strstr(line, "const char *const ");
            const char *br = strstr(line, "[] = {");
            if (kw != NULL && br != NULL && br > kw) {
                const char *nm = kw + strlen("const char *const ");
                int n = 0;
                while (is_ident_char(nm[n]) && n < MAX_NAME - 1) n++;
                if (n > 0 && ntab < MAX_TABLES) {
                    memcpy(tabs[ntab].name, nm, (size_t)n);
                    tabs[ntab].name[n] = '\0';
                    tabs[ntab].decl_line = lineno;
                    tabs[ntab].found_null = 0;
                    tabs[ntab].uses_sizeof = 0;
                    tabs[ntab].entries = 0;
                    in_table = 1;
                    depth = 0;
                }
            }
            continue;
        }

        /* 收集当前表：数花括号、找 NULL、数条目 */
        /*
         * 找 NULL 必须扫描**整行**，不能只认「整行就是 NULL」。
         *
         * 真机崩溃的那张表（FLOAT_BUILTIN_FNS）在修复后写成
         *     "texture", "textureLod", "textureProj",
         *     "exp2", "fma",
         *     NULL
         * 而 kFloatLodFns 是
         *     "textureCubeLod", "texture", NULL
         * 终止符与条目**同一行**。旧版只认前者，于是对后者误报。
         */
        for (const char *p = line; *p != '\0'; p++) {
            if (strncmp(p, "NULL", 4) == 0 &&
                (p == line || !is_ident_char(p[-1])) &&
                !is_ident_char(p[4])) {
                tabs[ntab].found_null = 1;
            }
        }
        for (const char *p = line; *p != '\0'; p++) {
            if (*p == '{') depth++;
            else if (*p == '}') {
                depth--;
                if (depth <= 0) {
                    /*
                     * 表结束。**这里不能急着报错** ——
                     * 此时还不知道该表是用 sizeof 还是 NULL 惯用法遍历的
                     * （那要等第二趟扫描）。诊断统一在最后一趟输出，
                     * 否则会出现「明明用 sizeof 的表也被报缺终止符」的误报。
                     */
                    ntab++;
                    in_table = 0;
                    break;
                }
            }
        }
        if (!in_table) continue;

        /* 数 `"..."` 条目 */
        for (const char *p = line; *p != '\0'; p++) {
            if (*p == '"') {
                tabs[ntab].entries++;
                p++;
                while (*p != '\0' && *p != '"') {
                    if (*p == '\\' && p[1] != '\0') p++;
                    p++;
                }
                if (*p == '\0') break;
            }
        }
    }

    /*
     * 第二趟：判断每张表是否**需要**终止符。
     *
     * 【判据 —— 必须精确，否则误报会把真问题淹掉】
     *   需要终止符 <=> 源码里存在 `TABLE[...] != NULL` 形式的循环条件，
     *   也就是 NULL 惯用法遍历。
     *
     *   反之，用下面两种方式遍历的表**不需要**终止符：
     *       sizeof(TABLE) / sizeof(TABLE[0])
     *       LIST_LEN(TABLE)          <- 本项目大量使用这个宏
     *   实测踩到的误报：ES_SAMPLER_PRECISION_TYPES / FLOAT_CTORS /
     *   INT_CTORS / KWS 用 sizeof 或 LIST_LEN（配合 name_in_list），
     *   它们**本来就不该有** NULL 元素；先前按"有没有 NULL"来判，
     *   于是把 4 张正确的表报成缺陷，真正的 FLOAT_BUILTIN_FNS 反而被淹没。
     */
    rewind(fh);
    lineno = 0;
    {
        char line[MAX_LINE];
        while (fgets(line, sizeof(line), fh) != NULL) {
            lineno++;
            /* 本行是否含 `!= NULL` */
            if (strstr(line, "!= NULL") == NULL) continue;
            /*
             * 逐个表名检查：本行是否出现 `NAME[`（即按元素索引访问）。
             * 这样 `TABLE[i] != NULL`、`TABLE[fi] != NULL` 都能命中，
             * 而 `foo != NULL`（指针判空）不会命中任何表。
             */
            for (int i = 0; i < ntab; i++) {
                char probe[MAX_NAME + 4];
                snprintf(probe, sizeof(probe), "%s[", tabs[i].name);
                if (strstr(line, probe) != NULL) {
                    tabs[i].uses_sizeof = 1;   /* 复用该字段表示「需终止符」 */
                }
            }
        }
    }
    fclose(fh);

    printf("=== table terminator check: %s ===\n", path);
    printf("%-30s %-7s %-10s %-8s %s\n",
           "table", "line", "traversal", "entries", "status");
    printf("%s\n",
           "-----------------------------------------------------------------");
    for (int i = 0; i < ntab; i++) {
        const int need = tabs[i].uses_sizeof;
        if (need) checked++;
        printf("%-30s %-7d %-10s %-8d %s\n",
               tabs[i].name, tabs[i].decl_line,
               need ? "NULL-term" : "indexed",
               tabs[i].entries,
               need ? (tabs[i].found_null ? "ok" : "*** NO TERMINATOR ***")
                    : "n/a");
        if (need && !tabs[i].found_null) bad++;
    }
    printf("%s\n",
           "-----------------------------------------------------------------");
    printf("tables found: %d, requiring a NULL terminator: %d\n", ntab, checked);
    if (bad > 0) {
        printf("\nFAIL: %d table(s) missing a NULL terminator.\n", bad);
        printf("This is the shape that SIGSEGVs in __strlen_aarch64 on device\n");
        printf("(a table traversed via `[i] != NULL` needs a NULL sentinel).\n");
        return 1;
    }
    printf("\nOK: every NULL-terminated table has its terminator.\n");
    return 0;
}
