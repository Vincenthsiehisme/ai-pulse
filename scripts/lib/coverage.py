# -*- coding: utf-8 -*-
"""coverage.py — 這則 Event 發生的時候，我們看得到嗎。判準單一真相源。

為什麼要有這個檔：`Events/*.md` 的日期只有 `happened_at` 一個來源，也就是
**外面世界**那個時鐘。所以一則 07-07 的事件，畫面上看不出我們是 07-07 就在追、
還是 07-26 首抓時才把它撈回來的。2026-07-27 實測 36 則已發布事件裡有 30 則
屬於後者——時間軸看起來像三週的持續觀測，實際是首抓時撈回的存量。

判準住這裡而不是散在 `pulse-cluster` 與 `pulse-render` 兩邊，理由跟
`lib/dictgaps.py` 那份一模一樣：抄一份的失敗形態這個 repo 已經量過三次，
兩邊在判準沒動過的日子裡給一樣的答案，正好在有人改了其中一邊的那天分岔，
**而不會有任何東西變紅**。

完整規格見 `references/event-timestamps.md`〈第三個現場：呈現層〉。

不讀磁碟、不讀時鐘、不呼叫任何模型。時間戳由呼叫端餵進來。
"""
from __future__ import annotations

from .quality import parse_dt   # 共用日期解析（容忍 RFC822 與 ISO8601）

OBSERVED = "observed"
BACKFILLED = "backfilled"
UNKNOWN = "unknown"

#: 封閉集。新增狀態要同時改規格、這裡、selftest 與 mutation。
COVERAGE_STATES = (OBSERVED, BACKFILLED, UNKNOWN)


def observable_from(evidence, first_fetch):
    """→ 這則事件**最早可能被我們看到**的時刻（aware datetime），量不到回 None。

    只取**該事件證據來源**的 `first_fetch_at`，不取整個 watch set 的最小值。
    理由是可 explain：每一則都能指到具體來源與具體日期——「證據來自 src-X，
    我們 07-26 才第一次抓它，而事情 07-14 就發生了」。用整個 watch set 會得到
    一個沒有人能逐則複查的門檻，而且幾乎所有事件都會變成 observed——
    **一個讓數字變好看、又不會讓任何測試變紅的改法**，所以它有自己的一格變異。

    任一來源缺 `first_fetch_at` → 回 None（整則判 unknown）。不是跳過那一條
    去算其餘的最小值：跳過會讓「有一條來源我們不知道何時開始看」被稀釋成
    「其他來源看得到就算看得到」，那是往說謊的方向倒。
    """
    sids = [(e or {}).get("source_id") for e in (evidence or [])]
    if not sids:
        return None
    stamps = []
    for sid in sids:
        dt = parse_dt((first_fetch or {}).get(sid))
        if dt is None:
            return None
        stamps.append(dt)
    return min(stamps)


def coverage_of(happened_at, evidence, first_fetch):
    """→ `observed` / `backfilled` / `unknown`。

    `observed`   事情發生時，綁在這則上的來源我們已經在抓了。
    `backfilled` 事情發生在那之前——這是首抓時撈回的存量，不是我們追到的。
    `unknown`    量不到（缺 happened_at、沒有證據、或任一來源沒有 first_fetch_at）。

    **`unknown` 不得併進 `observed`**（紅線 8：量不到就說量不到）。併進去的話，
    任何 `state.json` 的缺格都會靜靜變成「我們當時在看」。所以 `first_fetch`
    整個沒傳進來時，答案是 unknown 而不是 observed——預設值倒向誠實那一邊。

    邊界：`happened_at` 正好等於首抓時刻算 `observed`。首抓那一瞬間之後發布的
    東西我們確實看得到；之前的則否，這跟訊號層 `is_backfill`（每條來源的第一次
    抓取整批算存量）是同一條線。
    """
    happened = parse_dt(happened_at)
    start = observable_from(evidence, first_fetch)
    if happened is None or start is None:
        return UNKNOWN
    return OBSERVED if happened >= start else BACKFILLED
