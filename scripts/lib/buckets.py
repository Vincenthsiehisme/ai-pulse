# -*- coding: utf-8 -*-
"""buckets.py — 「每一份檔案都要落在某一桶」這件事的共用形狀。單一真相源。

2026-08-13 的事故：一個 Event 的 frontmatter 被寫壞（少了 `---` 分隔線），
`parse_note` 回空 dict、status 是 None，於是它從 published / blocked / dropped
三張看板一起消失——而 `pulse-dashboard.py` 印出來的是
「published=101 blocked=29 dropped=1」，一個看起來完全正常的句子。

補的守衛是「分完桶之後，把沒有落進任何一桶的印出來並回離開碼 1」。
2026-08-14 每日精選那條鏈要用同一個守衛，而它的桶名完全不同
（draft / reviewed / rejected / stale，不是 published / review / dropped）。

**形狀共用，詞彙各自帶。** 複製第二份的話，兩邊會各自長出自己的邊角行為，
而這一段碼的全部價值就是「它在每一張看板上都一模一樣」。
"""
from __future__ import annotations


def unbucketed(rows, buckets):
    """rows = [(名字, status)]；`buckets` 是這張看板認得的 status。
    回傳沒有歸到任何一桶的，排序過。

    `None` 也算漏掉，而且是最重要的那一種：`parse_note` 讀不到 frontmatter 時
    回的是空 dict，`fm.get("status")` 就是 None。那不是「這個檔沒有狀態」，
    是「這個檔壞了」，兩件事在這裡必須長得一樣顯眼。

    **不要在這裡把未知 status 歸進某一桶**（例如「不認得就當 draft」）。
    那會讓一個打錯字的 status 安靜地變成一個合法狀態，而這支函式存在的
    唯一理由就是不讓那件事發生。
    """
    known = set(buckets)
    return sorted((n, s) for n, s in rows if s not in known)
