# -*- coding: utf-8 -*-
"""identity.py — 夜班鏈 commit 用的 git 身份，單一真相源。

`ai-pulse-enrich` 跟 `data-refresh.yml` 那班的 `ai-pulse-bot` 是兩個名字：
兩條鏈在作者欄上要分得開，`pulse-monitor.py` 的 `night_shift_commit_days()`
就是靠作者欄位辨認哪些 commit 屬於夜班那條鏈。

2026-09-18 發現這個常數同時被 `pulse-monitor.py` 與 `pulse-nightly.py` 用到，
卻只在前者定義——後者的 `do_commit()` 直接引用一個從沒 import 過的名字，
只要真的在 main 上跑到有資料要 commit 就會 NameError。收成一個模組，
兩邊都從這裡 import，不要各自維護一份同樣的字串。
"""
from __future__ import annotations

NIGHT_SHIFT_AUTHOR = "ai-pulse-enrich"
