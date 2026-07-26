# -*- coding: utf-8 -*-
"""narrative_guard.py — 敘述層的確定性擋線：不准把沒量到的熱度講成數字。

規格：references/narrative-layer.md。判準與豁免詞都寫在那裡，改這裡之前先改那裡（紅線 9）。

只做一件事：找出「量化熱度宣稱」。要不要擋由呼叫端決定——
vault 裡真的有量到的 heat 時，這種句子是合法的（見規格「heat 真的量到之後」）。
"""
from __future__ import annotations

import re

# 「熱度」這件事在文字裡的兩種寫法。heat 用 \b 免得掃到 heated / wheat。
_KEYWORD = re.compile(r"\bheat\b|熱度", re.IGNORECASE)

# 關鍵字之後看這麼多個字元。太短會漏掉「heat 偏低（8–14）」，太長會掃進下一句。
_WINDOW = 12

# 窗口裡出現這些詞代表句子本身就在講「沒量到」，不是在引用一個數字。
_NEGATIONS = ("未量測", "量不到", "沒量到", "未接線")

_DIGIT = re.compile(r"\d")

_FM_HEAT = re.compile(r"^heat:\s*(\S+)\s*$", re.M)


def vault_has_measured_heat(vault) -> bool:
    """vault 裡有沒有任何一則 Event 的 heat 是數字。

    只讀 frontmatter，不解析全文——這是一個「有沒有」的問題，不是「多少」。
    """
    from pathlib import Path

    for f in sorted(Path(vault).glob("Events/*.md")):
        text = f.read_text("utf-8")
        if not text.startswith("---"):
            continue
        fm = text.split("---", 2)[1]
        m = _FM_HEAT.search(fm)
        if not m:
            continue
        try:
            float(m.group(1))
        except ValueError:
            continue
        return True
    return False


def find_heat_claims(text: str) -> list[str]:
    """回傳所有命中的窗口原文（含關鍵字），沒有就回空 list。"""
    if not text:
        return []
    hits = []
    for m in _KEYWORD.finditer(text):
        window = text[m.start():m.end() + _WINDOW]
        if not _DIGIT.search(window[m.end() - m.start():]):
            continue
        if any(neg in window for neg in _NEGATIONS):
            continue
        hits.append(window)
    return hits
