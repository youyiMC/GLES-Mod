/*
 * glesmod_logfile.h -- 原生日志文件的公共入口
 *
 * 【为什么需要这个头文件】
 *   log_to_file() 原本是 core.c 内部的 static 函数，只有 core.c 自己能用。
 *   但 custom.c 也需要「写驱动错误文本到日志文件」——
 *   这是定位真机着色器编译失败的关键证据。
 *   把它导出为 glesmod_log_to_file()，供各源文件复用。
 *
 * LGPL-3.0-or-later
 */

#ifndef GLESMOD_LOGFILE_H
#define GLESMOD_LOGFILE_H

/* 把一行文本追加到 glesmod/native.log（带时间戳）。 */
void glesmod_log_to_file(const char *text);

#endif /* GLESMOD_LOGFILE_H */
