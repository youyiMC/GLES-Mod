#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poll_license_recognition.py -- 轮询 GitHub 是否已识别 LICENSE。

为什么需要轮询
==============
GitHub 的许可证识别是**异步**的：推送后由后台任务扫描 LICENSE 并写入
仓库元数据。它可能滞后数分钟，期间 API 会一直返回 `NOASSERTION`。
所以"刚推完看不到"不能判定修复失败，必须给它时间。

判据：`license.spdx_id`
    NOASSERTION  -> 找到了 LICENSE 文件，但内容没匹配上任何模板
                     （注意：这**不同于** license 为 null，后者表示
                      连 LICENSE 文件都没找到）
    其他值       -> 识别成功
"""

import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

API = "https://api.github.com/repos/youyiMC/GLES-Mod"
HDRS = {
    "User-Agent": "glesmod-license-check",
    "Accept": "application/vnd.github+json",
}

MAX_TRIES = int(os.environ.get("POLL_TRIES", "10"))
INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))


def fetch():
    req = urllib.request.Request(API, headers=HDRS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    last = None
    for i in range(1, MAX_TRIES + 1):
        try:
            d = fetch()
        except Exception as e:  # noqa: BLE001
            print("第 %d 次: 请求失败 %s" % (i, e))
            time.sleep(INTERVAL)
            continue

        lic = d.get("license")
        if lic is None:
            spdx, name = "(null)", "连 LICENSE 文件都没找到"
        else:
            spdx, name = lic.get("spdx_id"), lic.get("name")

        print("第 %d 次 (%s): spdx_id=%-14s name=%s"
              % (i, time.strftime("%H:%M:%S"), spdx, name))
        last = spdx

        if spdx and spdx != "NOASSERTION":
            print()
            print("★ 识别成功：%s" % spdx)
            return 0

        if i < MAX_TRIES:
            time.sleep(INTERVAL)

    print()
    print("轮询结束，仍未识别（最后状态: %s）" % last)
    print("若持续如此，说明不是延迟问题，需要另找原因。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
