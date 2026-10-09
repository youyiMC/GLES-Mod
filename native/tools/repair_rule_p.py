# -*- coding: utf-8 -*-
"""
Repair the half-written rule-P block in native/src/shader.c.

The previous edit left:
  * an unterminated block comment ("/* 右半 " swallowing the following code)
  * a stray call to int_expr_start_extent() that does not exist
  * a design that tried to parse arbitrary expressions (too risky)

This script replaces the whole region (the int_expr_start doc-comment through
the end of fix_mixed_int_uint) with a correct, deliberately conservative
implementation:

    <single-token operand> OP <single-token operand>

where a token is: identifier | uint(..) | int(..) | integer literal.
Rewrite only when one side is definitely uint and the other definitely int.
"""
import io
import re
import sys

PATH = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\native\src\shader.c'

with io.open(PATH, 'r', encoding='utf-8', newline='') as f:
    text = f.read()

lines = text.split('\n')

# --- locate the region -------------------------------------------------
start = None
for i, l in enumerate(lines):
    if '取以 m 为末尾（不含）的 int 表达式的**起始位置**' in l:
        start = i - 1                 # the '/*' line just above
        break
if start is None:
    print('FAIL: could not find int_expr_start doc comment')
    sys.exit(1)
if lines[start].strip() != '/*':
    # be tolerant: back up to the nearest '/*'
    j = start
    while j > 0 and lines[j].strip() != '/*':
        j -= 1
    start = j

end = None
for i, l in enumerate(lines):
    if '阴影采样器精度（ES 下必须显式声明）' in l and i > start:
        end = i
        break
if end is None:
    print('FAIL: could not find the 阴影采样器 precision section')
    sys.exit(1)

print('replacing lines %d..%d' % (start + 1, end))
print('  first old line: %s' % lines[start][:70])
print('  last  old line: %s' % lines[end - 1][:70])

NEW = r'''/* ================= 规则 P：混合 int/uint 二元运算（补 uint() 转换） ================= */

/*
 * 【为什么需要 —— Flywheel instancing 的最后一处阻塞】
 *   真机（2026-10-05 14:24，shader=220）报：
 *       ERROR: 15:79: '-' : no operation '-' exists that takes a left-hand
 *              operand of type 'gl_VertexID int' and a right operand of
 *              type 'in uint'
 *       ERROR: 15:79: 'assign' : cannot convert from 'gl_VertexID int' to 'uint'
 *     --> flywheel:internal/common.vert
 *     79 |     flw_vertexId = gl_VertexID - baseVertex;
 *   其中 `gl_VertexID` 是 int（内建），`baseVertex` 是 `in uint`。
 *   桌面 GLSL 允许 int 与 uint 混算，GLSL ES **完全禁止**。
 *
 * 【语义无歧义 —— 已用 SPIR-V 逐指令证明】
 *   本规则一直没做，是担心「转 int 还是转 uint」有歧义。
 *   实测（native/tools/probe_mixed_int_uint.ps1 = glslang 前端 + spirv-dis）：
 *       桌面 #version 460:  uint r = i0 + u0;
 *         %13 = OpBitcast %uint %12      <- int 按位重解释为 uint
 *         %17 = OpIAdd   %uint %13 %16
 *       ES   #version 320 es: uint r = uint(i0) + u0;
 *         %13 = OpBitcast %uint %12      <- **完全相同**
 *         %17 = OpIAdd   %uint %13 %16
 *   两条序列逐指令一致。规范亦如此：混合大小相同的两种整型时，
 *   有符号操作数隐式转换为无符号。
 *   因此补 `uint(...)` 是**语义等价**的改写，不是近似。
 *   （OpBitcast 等价 C 的 `(unsigned)i`；负数变为 2^32-|i|。）
 *
 * 【为什么只给 int 侧补，而不是两侧都转 int】
 *   虽然 `uint(int(a) OP int(b))` 也合法，但对无符号量按有符号比较
 *   会改变结果（`0xFFFFFFFFu` 会变成 -1），与桌面不一致。
 *   补 `uint()` 才是逐位等价的。
 *
 * 【运算符范围（glslc 实测，ES 3.20）】
 *   需转换：+ - * / % & | ^ 与比较 < > <= >= == !=
 *   不需转换：<< >>（右操作数为 int **合法**，不得动）
 *   复合赋值同理： += -= *= /= %= &= |= ^= 需转换； <<= >>= 合法。
 *   && || 不处理：uint 本身不是 bool，补 uint() 修不好（同规则 N）。
 *
 * 【安全设计：只处理「可单独识别的单 token 操作数」】
 *   本规则**不**解析任意复杂表达式 —— 那需要完整类型系统，是刻意回避的。
 *   它只识别两侧各为一个「完整 token」的形态：
 *       <token> OP <token>
 *   token 定义为：标识符（查表） / uint(..) / int(..) / 整数字面量。
 *   两侧类型已知且**一为 uint、一为 int** 时才改写。
 *   其余一律原样输出（宁可漏改，不可误改）。
 *   这样 `gl_VertexID - baseVertex` 被覆盖，而 `intVar < intVar2`、
 *   `uvecA * f`、任意含算术的复合表达式都绝不会被误碰。
 */

/* 操作数类型 */
#define OPERAND_NONE 0
#define OPERAND_INT  1
#define OPERAND_UINT 2

/*
 * 从 p 开始向前识别一个「单 token 操作数」。
 * 成功时把操作数末尾（不含）写入 *pe 并返回其类型；否则返回 OPERAND_NONE。
 */
static int operand_kind_forward(const char *p, const char *end,
                                const char **pe) {
    const char *q = p;
    while (q < end && (*q == ' ' || *q == '\t' ||
                       *q == '\n' || *q == '\r')) q++;
    if (q >= end) return OPERAND_NONE;

    /* 整数字面量（含 0xFF 这种十六进制） */
    if (isdigit((unsigned char)*q)) {
        const char *t = q;
        while (t < end && (isalnum((unsigned char)*t))) t++;
        if (t == q) return OPERAND_NONE;
        if (t[-1] == 'u' || t[-1] == 'U') { *pe = t; return OPERAND_UINT; }
        for (const char *z = q; z < t; z++) {
            if (*z == '.' || *z == 'e' || *z == 'E') return OPERAND_NONE;
        }
        *pe = t;
        return OPERAND_INT;
    }

    if (!is_ident_char(*q)) return OPERAND_NONE;

    const char *b = q;
    while (q < end && is_ident_char(*q)) q++;
    size_t nl = (size_t)(q - b);

    /* 后面紧跟 '(' -> 构造函数 / 函数调用 */
    const char *r = q;
    while (r < end && (*r == ' ' || *r == '\t' ||
                       *r == '\n' || *r == '\r')) r++;
    if (r < end && *r == '(') {
        int kind = OPERAND_NONE;
        if (nl == 4 && strncmp(b, "uint", 4) == 0) kind = OPERAND_UINT;
        else if (nl == 3 && strncmp(b, "int", 3) == 0) kind = OPERAND_INT;
        if (kind == OPERAND_NONE) return OPERAND_NONE;   /* 其它调用：不猜 */
        int d = 0;
        const char *t = r;
        while (t < end) {
            if (*t == '(') d++;
            else if (*t == ')') { d--; if (d == 0) { t++; break; } }
            t++;
        }
        if (d != 0) return OPERAND_NONE;
        *pe = t;
        return kind;
    }

    /* 纯标识符：查两张名字表 */
    if (uint_ident_find(b, nl)) { *pe = q; return OPERAND_UINT; }
    if (g_src_int_ready && int_ident_find(&g_src_int_idents, b, nl)) {
        *pe = q; return OPERAND_INT;
    }
    return OPERAND_NONE;
}

/*
 * 向后识别一个「单 token 操作数」（以 m 为末尾、不含）。
 * 成功时把操作数起点写入 *ps 并返回类型；否则返回 OPERAND_NONE。
 */
static int operand_kind_backward(const char *m, const char *s, const char **ps) {
    const char *t = m;
    while (t > s && (t[-1] == ' ' || t[-1] == '\t' ||
                     t[-1] == '\n' || t[-1] == '\r')) t--;
    if (t <= s) return OPERAND_NONE;

    /* 以 ')' 结尾：可能是 uint(..) / int(..)，也可能是别的调用 */
    if (t[-1] == ')') {
        const char *q = t;
        int d = 0;
        while (q > s) {
            if (q[-1] == ')') { d++; q--; continue; }
            if (q[-1] == '(') { if (d == 0) break; d--; q--; continue; }
            q--;
        }
        if (q <= s || q[-1] != '(') return OPERAND_NONE;
        const char *u = q - 1;
        while (u > s && (*u == ' ' || *u == '\t')) u--;
        const char *we = u;
        while (u > s && is_ident_char(u[-1])) u--;
        size_t ul = (size_t)(we - u);
        if (ul == 4 && strncmp(u, "uint", 4) == 0) { *ps = u; return OPERAND_UINT; }
        if (ul == 3 && strncmp(u, "int", 3) == 0)  { *ps = u; return OPERAND_INT;  }
        return OPERAND_NONE;        /* 其它调用：不猜 */
    }

    if (is_ident_char(t[-1]) && !isdigit((unsigned char)t[-1])) {
        /* 标识符（可能带 .x/.y swizzle，但标量无分量 -> 取基名） */
        size_t bl = 0;
        const char *base = lhs_base_ident(t, s, &bl);
        if (bl == 0) return OPERAND_NONE;
        if (isdigit((unsigned char)base[0])) return OPERAND_NONE;
        if (uint_ident_find(base, bl)) { *ps = base; return OPERAND_UINT; }
        if (g_src_int_ready && int_ident_find(&g_src_int_idents, base, bl)) {
            *ps = base; return OPERAND_INT;
        }
        return OPERAND_NONE;
    }

    /* 数字/十六进制字面量 */
    if (isdigit((unsigned char)t[-1]) ||
        ((t[-1] >= 'a' && t[-1] <= 'f') || (t[-1] >= 'A' && t[-1] <= 'F'))) {
        const char *u = t;
        while (u > s && (isalnum((unsigned char)u[-1]))) u--;
        size_t ul = (size_t)(t - u);
        if (ul == 0) return OPERAND_NONE;
        if (u[ul - 1] == 'u' || u[ul - 1] == 'U') { *ps = u; return OPERAND_UINT; }
        for (size_t z = 0; z < ul; z++) {
            if (u[z] == '.' || u[z] == 'e' || u[z] == 'E') return OPERAND_NONE;
        }
        *ps = u;
        return OPERAND_INT;
    }
    return OPERAND_NONE;
}

/*
 * 规则 P 主体：按字节扫描，在每个候选运算符处向前/向后各识别一个单 token
 * 操作数；若一为 uint、一为 int，则给 int 侧包上 `uint(...)`。
 *
 * 处理顺序：先把（可能被包裹的）左右操作数写回，再跳过已消费区间。
 * 因为左右都只取「单 token」，跳过范围精确，不会漏掉后续运算符。
 */
static void fix_mixed_int_uint(sbuf *out, const char *src) {
    const char *end = src + strlen(src);
    const char *p = src;

    while (p < end) {
        /* 预处理器行整行原样复制（#define/#line 等不得改写） */
        {
            const char *nl = memchr(p, '\n', (size_t)(end - p));
            const char *line_end = nl ? nl : end;
            if (line_starts_with_directive(p, line_end)) {
                size_t n = (size_t)(line_end - p) + (nl ? 1 : 0);
                sbuf_put(out, p, n);
                p += n;
                continue;
            }
        }

        const char *skipped = skip_comment_or_string(p, end);
        if (skipped != NULL) {
            sbuf_put(out, p, (size_t)(skipped - p));
            p = skipped;
            continue;
        }

        char c = *p;
        int oplen = 0;
        int is_shift = 0;

        if (c == '+' || c == '-' || c == '*' || c == '/' || c == '%' ||
            c == '&' || c == '|' || c == '^') {
            if (c == '+' || c == '-') {
                if ((p + 1 < end && p[1] == c) || (p > src && p[-1] == c)) {
                    oplen = 0;                      /* ++ / -- 与一元 +/- */
                } else if (p + 1 < end && p[1] == '=') {
                    oplen = 2;                      /* += -= */
                } else {
                    oplen = 1;
                }
            } else if (c == '&' && p + 1 < end && p[1] == '&') {
                oplen = 0;                          /* && 要求 bool，不处理 */
            } else if (c == '|' && p + 1 < end && p[1] == '|') {
                oplen = 0;                          /* || 同上 */
            } else if (p + 1 < end && p[1] == '=') {
                oplen = 2;                          /* *= /= %= &= |= ^= */
            } else {
                oplen = 1;
            }
        } else if (c == '<' || c == '>') {
            if (p + 1 < end && p[1] == c) {
                is_shift = 1; oplen = 2;            /* << >> 合法，不处理 */
            } else if (p + 1 < end && p[1] == '=') {
                oplen = 2;                          /* <= >= 与 <<= >>= */
                if (p > src && p[-1] == c) oplen = 0;
            } else {
                oplen = 1;                          /* < > */
                if (p > src && p[-1] == c) oplen = 0;
            }
        } else if (c == '=') {
            if (p + 1 < end && p[1] == '=') oplen = 2;      /* == */
            else oplen = 1;                                 /* = */
        } else if (c == '!') {
            if (p + 1 < end && p[1] == '=') oplen = 2;      /* != */
        }

        if (oplen == 0 || is_shift) {
            sbuf_put(out, p, 1);
            p++;
            continue;
        }

        const char *ls = NULL;
        int lk = operand_kind_backward(p, src, &ls);
        if (lk == OPERAND_NONE) {
            sbuf_put(out, p, 1);
            p++;
            continue;
        }

        const char *re = NULL;
        int rk = operand_kind_forward(p + oplen, end, &re);
        if (rk == OPERAND_NONE) {
            sbuf_put(out, p, 1);
            p++;
            continue;
        }

        /* 只有「一为 uint、一为 int」才有改写必要 */
        if (!((lk == OPERAND_UINT && rk == OPERAND_INT) ||
              (lk == OPERAND_INT  && rk == OPERAND_UINT))) {
            sbuf_put(out, p, 1);
            p++;
            continue;
        }

        /*
         * 普通赋值 `=` 单独把关：它表达的是「把 int 赋给 uint 变量」，
         * 与混合运算同源，但左值必须是**声明的 uint 变量名本身**
         * （不能是 uint(...) 之类的表达式，那本来就是 uint）。
         */
        if (oplen == 1 && c == '=') {
            int plain = 1;
            for (const char *z = ls; z < p; z++) {
                if (!is_ident_char(*z)) { plain = 0; break; }
            }
            if (!(plain && uint_ident_find(ls, (size_t)(p - ls)))) {
                sbuf_put(out, p, 1);
                p++;
                continue;
            }
        }

        /*
         * 写回。三种形态：
         *   int 侧在左： uint(<左>) OP <右>
         *   int 侧在右： <左> OP uint(<右>)
         * 注意左操作数原文在 [ls, p) 内（含尾部空白），需原样保留空白。
         */
        if (lk == OPERAND_INT) {
            /* 左操作数原文 = [ls, p)，其中 ls..(左操作数末尾) 是 token，
               其后是空白。分别取出 token 与空白，以便包住 token 而保留空白。 */
            const char *tokEnd = p;
            while (tokEnd > ls && (tokEnd[-1] == ' ' || tokEnd[-1] == '\t' ||
                                   tokEnd[-1] == '\n' || tokEnd[-1] == '\r')) {
                tokEnd--;
            }
            sbuf_puts(out, "uint(");
            sbuf_put(out, ls, (size_t)(tokEnd - ls));
            sbuf_puts(out, ")");
            sbuf_put(out, tokEnd, (size_t)(p - tokEnd));     /* 保留空白 */
            sbuf_put(out, p, (size_t)oplen);
            sbuf_put(out, re, 0);                           /* 见下方统一处理 */
            sbuf_put(out, p + oplen, (size_t)(re - (p + oplen)));
        } else {
            /* 左操作数原样；右操作数包 uint() */
            sbuf_put(out, ls, (size_t)(p - ls));
            sbuf_put(out, p, (size_t)oplen);
            sbuf_puts(out, "uint(");
            sbuf_put(out, p + oplen, (size_t)(re - (p + oplen)));
            sbuf_puts(out, ")");
        }

        p = re;
    }
}

'''

lines[start:end] = NEW.split('\n')
text = '\n'.join(lines)

with io.open(PATH, 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print('done; new line count = %d' % len(lines))
