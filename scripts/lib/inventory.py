# -*- coding: utf-8 -*-
"""inventory.py — 變異盤點那一頁裡「清單長度」那個數字的判準。

那一行長這樣，每一輪結尾一句：

    329 → 341。分片 4 片，每片 86 條。

它**四次有三次是憑印象寫的**（2026-08-13、08-16、08-17、08-21）。訂正一個手寫
的數字撐不過三天——這個 repo 自己記過同一件事：`fix/backlog-status-is-hand-written`
那一條，現況表從手寫改成每班重生成，而第一次的修法「把量測時間寫進標題、
請下一個人複量」三小時就失效了。

所以判準搬到這裡：**最後一輪宣稱的那個數字，要等於 `mutations.yaml` 的實際條數。**

為什麼是一個 lib 模組而不是直接寫在 selftest 裡：寫在測試裡的斷言可以被改成
`len(x) == len(x)` 這種恆真式，而**沒有任何測試抓得到一條把自己改成恆真的測試**。
判準在 lib 裡，那個改動就變成「lib 回了錯的東西」，selftest 當場紅。
"""
from __future__ import annotations

import re

# 每一輪結尾那一句。抓的是「→ 之後那個數字」。
_LEN_LINE = re.compile(r"(\d+)\s*→\s*(\d+)。分片")


def declared_lengths(text):
    """盤點那一頁宣稱過的每一輪清單長度，依出現順序。回 [(前, 後), ...]。"""
    return [(int(a), int(b)) for a, b in _LEN_LINE.findall(text)]


def declared_latest(text):
    """最後一輪宣稱的清單長度。一次都沒宣稱過回 None。

    **回 None 而不是回 0。** 那一頁還沒有任何一輪的時候是「沒有宣稱」，
    不是「宣稱有 0 條」——後者會讓一個空的盤點頁跟一個真的 0 條的清單
    長得一樣，而這個 repo 花最多力氣在防的就是那件事（紅線 8）。
    """
    rows = declared_lengths(text)
    return rows[-1][1] if rows else None
