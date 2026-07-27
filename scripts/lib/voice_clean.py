# -*- coding: utf-8 -*-
"""voice_clean.py — 去 AI 口吻的「確定性後洗層」（speak-human-tw 的機械規則子集）。

定位：enrich 由 Cowork 依 speak-human-tw 規則「寫」出人話 prose 後，本層再做一道
可測、可重現的機械清理，抓殘留的中國用語與半形標點。**只做零容忍、無歧義的替換**；
需要語境判斷的（優化 / 支持 / 落地 / 文檔…）留給 Cowork 在寫的時候處理，這裡不碰。

規則來源：speak-human-tw 技能自己的 taiwan-localization 規則表（中國用語替換表 + 全形
標點硬規則）。那份表在技能裡、不在本 repo——寫成 `references/…` 會讀起來像本 repo 有
一個同名檔案，實際上沒有。
"""
from __future__ import annotations

import re

# 零容忍、無歧義的中國用語 → 台灣用語（長詞在前，避免部分覆蓋）
CN_TW = [
    ("人工智能", "人工智慧"),
    ("數據庫", "資料庫"),
    ("服務器", "伺服器"),
    ("短視頻", "短影音"),
    ("視頻", "影片"),
    ("質量", "品質"),
    ("信息", "資訊"),
    ("網絡", "網路"),
    ("軟件", "軟體"),
    ("硬件", "硬體"),
    ("屏幕", "螢幕"),
    ("鼠標", "滑鼠"),
    ("打印", "列印"),
    ("默認", "預設"),
    ("兼容", "相容"),
    ("卸載", "移除"),
    ("反饋", "回饋"),
    ("水平", "水準"),
    ("立馬", "馬上"),
    ("性價比", "CP 值"),
    ("顏值", "外型"),
    ("靠譜", "可靠"),
    ("給力", "到位"),
    ("智能", "智慧"),  # 人工智能已先處理；其餘 智能X → 智慧X
]

_CJK = "一-鿿"
_FULL = {",": "，", ".": "。", ":": "：", ";": "；", "!": "！", "?": "？", "(": "（", ")": "）"}
_cjk_re = re.compile(f"[{_CJK}]")


def _halfwidth_to_full(text):
    """把緊鄰 CJK 字的半形標點轉全形；數字小數點(3.2)、URL、純英文不動。"""
    chars = list(text)
    n = len(chars)
    changed = 0
    for i, ch in enumerate(chars):
        if ch in _FULL:
            prev = chars[i - 1] if i > 0 else ""
            nxt = chars[i + 1] if i + 1 < n else ""
            if _cjk_re.match(prev) or _cjk_re.match(nxt):
                chars[i] = _FULL[ch]
                changed += 1
    return "".join(chars), changed


def clean(text):
    """回 (cleaned, changes)。changes = [(類型, 原, 改)]，供事後摘要。"""
    if not text:
        return text, []
    changes = []
    out = text
    for cn, tw in CN_TW:
        if cn in out:
            changes.append(("中國用語", cn, tw))
            out = out.replace(cn, tw)
    # 三個句點 → 全形刪節號
    if "..." in out:
        out = re.sub(r"\.{3,}", "⋯⋯", out)
        changes.append(("標點", "...", "⋯⋯"))
    out2, npunct = _halfwidth_to_full(out)
    if npunct:
        changes.append(("標點", f"半形×{npunct}", "全形"))
    return out2, changes
