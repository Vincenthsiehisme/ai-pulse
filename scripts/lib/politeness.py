# -*- coding: utf-8 -*-
"""politeness.py —— 抓取禮貌的門檻與判準。規格：references/crawl-politeness.md。

我們抓的每一個站都是別人的。這裡的兩個數字不是效能取捨，是禮貌——
**429 是唯一一種「錯在我們自己」的狀態碼**。

為什麼是一個 lib 而不是 selftest 裡的兩條斷言：同 `lib/inventory.py` 的理由，
**沒有任何測試抓得到一條把自己改成恆真的測試**（M350 教的）。
`acase(A, B)` 改成 `acase(B, B)` 是全綠的；判準在 lib 裡，同一個改動變成
「lib 回了錯的東西」，當場紅。

為什麼 cron 的解析不在這裡：`lib/clock.py` 已經在拆五個欄位了
（`daily_utc_hour` / `runs_per_day`）。再寫一份的話兩份會在某個邊角上分岔，
而分岔的那天不會有東西紅——那是這個 repo 的頭號病。
這一支只放**政策**（門檻多少、什麼算問題），解析一律向 clock 借。

這一版明確不管的（紅線 8，寫下來不假裝有蓋到）：
  - 每條來源自己的 `frequency` 欄位——那是 sources.yaml 的事，今天沒有人守
  - 實際發出的請求數——判準讀設定檔，不讀流量
  - 429 有沒有真的發生——那要接來源健康那一層，是另一輪的題目
"""
from __future__ import annotations

import re

from . import clock

# 寫 `_corpus/` 的那條鏈，一天最多幾班。
#
# 這個 1 不是效能上限，是禮貌上限：2026-07-25~27 曾臨時調成一天 12 班，
# 而收班靠的是一個單次觸發的排程任務——「警報自己把自己關掉」的那個形狀。
MAX_RUNS_PER_DAY = 1

# 每條來源的 robots.txt 最多這麼久重驗一次。
#
# 調小的代價是每班多打每一個站的 robots.txt 一次。7 是原始設定值，
# 2026-07-25 曾被調成 1。
MIN_ROBOTS_STALE_DAYS = 7

# `--stale-days N`。**故意不接受 `--stale-days=N`**：這個 repo 的 workflow
# 全部寫成空白分隔，接受兩種寫法等於允許同一個旋鈕有兩種長相，而下一個人
# 改了其中一種、另一種沒跟著改的時候，判準會說「兩處同值」。
_STALE_RE = re.compile(r"--stale-days\s+(\d+)")


def robots_stale_days(text: str) -> list[int]:
    """→ 這份 workflow 文字裡所有 `--stale-days` 的值，照出現順序。

    回 list 不回 set：**「兩處同值」是判準的一部分**，去重會把它消掉。
    """
    return [int(m.group(1)) for m in _STALE_RE.finditer(text)]


def too_frequent(text: str) -> list[tuple[str, int]]:
    """→ [(cron 字串, 一天幾班)]，超過 MAX_RUNS_PER_DAY 的每日班。

    不是每日班的（週班、月班）`runs_per_day` 回 None，這裡跳過——不歸這條管。
    """
    out = []
    for e in clock.cron_entries(text):
        n = clock.runs_per_day(e["expr"])
        if n is not None and n > MAX_RUNS_PER_DAY:
            out.append((e["expr"], n))
    return out


def problems(text: str) -> list[str]:
    """→ 這份 workflow 的抓取禮貌問題，一條一句。空 list ＝ 合格。

    回**人看得懂的句子**而不是錯誤碼：這幾條紅起來的時候，讀的人要能直接
    知道該把哪個數字改回多少，不必再回頭翻規格。
    """
    out = []
    for expr, n in too_frequent(text):
        out.append(f"cron `{expr}` 一天跑 {n} 班，上限是 {MAX_RUNS_PER_DAY} 班"
                   f"——那是在用 {n} 倍的頻率打人家的站")
    days = robots_stale_days(text)
    if days:
        if len(set(days)) > 1:
            out.append(f"`--stale-days` 出現 {len(days)} 次而值不一致（{days}）"
                       f"——同一份 robots.txt 在同一班裡被用兩種節奏對待，"
                       f"那是設定漂移不是取捨")
        low = sorted({d for d in days if d < MIN_ROBOTS_STALE_DAYS})
        if low:
            out.append(f"`--stale-days` 有 {low} 小於 {MIN_ROBOTS_STALE_DAYS}"
                       f"——每班會多打每一個站的 robots.txt")
    return out
