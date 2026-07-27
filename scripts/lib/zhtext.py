"""zhtext.py — 「英文原文 → 中文譯文」這件事的共用機械層。單一真相源。

為什麼要有這個檔：2026-07-27 要把 Event 標題也翻成中文，而榜單描述那一套
（`pulse-github-desc-apply.py`）已經把該擋的都擋好了——綁原文雜湊、真的有中文、
長度封頂、AI 腔黑名單、voice_clean 後洗。抄第二份是最省事的作法。

抄下去的失敗形態這個 repo 已經量過五次（`lib/sources.py`、`lib/entities.py`、
`lib/dictgaps.py`、`lib/tracks.py`、以及那份手寫的未接線清單）：兩份在規則沒動過
的日子裡給一樣的答案，正好在有人往黑名單加一個字的那天分岔，而**不會有任何東西
變紅**——兩邊各自都跑得很順，只是一邊擋、一邊放。

所以判準住這裡，兩個消費者（榜單描述、Event 標題）共用。
**這一層不產生任何文字，只驗章與後洗。**

長度上限由呼叫端給：榜是一行字的版面（60），Event 標題可以長一點（40 但語意
密度不同）。**上限不寫死在這裡**，因為它是版面決定的，不是語言決定的。
"""
from __future__ import annotations

import hashlib
import re

from . import voice_clean

# 零容忍的 AI 腔套話。留短、留死——需要語境判斷的留給潤稿端，這裡只擋一看就知道
# 是模型填充物的那幾句。擋詞表長了會開始誤傷真句子，那比漏擋糟。
BANNED = [
    "值得關注", "值得期待", "無限可能", "廣泛應用", "強大的功能", "一站式",
    "賦能", "助力", "打造", "旨在", "隨著", "在當今", "備受矚目", "引領",
]

CJK = re.compile(r"[一-鿿]")


def src_hash(text: str) -> str:
    """原文 → 短雜湊。空字串也給得出穩定值。

    譯文一律綁在**當下那句原文**上。原文變了、雜湊對不上 → 譯文自動失效退回原文，
    並重新排進待譯清單。少了這一步，畫面上會掛著一句看起來很合理、其實在講舊版本
    的中文——那比沒有中文糟得多。
    """
    return hashlib.sha1((text or "").strip().encode("utf-8")).hexdigest()[:12]


def valid_for(entry: dict | None, src: str) -> str | None:
    """存下來的那筆譯文對這句原文還算不算數 → 中文字串或 None。

    三個條件都要：有這一筆、`zh` 非空、`src_hash` 對得上。任一不成立回 None，
    **呼叫端就退回原文**——退回原文是安全的，掛一句過期的中文不是。
    """
    if not entry:
        return None
    zh = (entry.get("zh") or "").strip()
    if not zh:
        return None
    return zh if entry.get("src_hash") == src_hash(src) else None


def validate(raw, max_len: int, src_present: bool = True,
             len_note: str = "", missing_note: str = ""):
    """→ (清理後的中文, 退件原因, 後洗紀錄)。過關時原因為 None。

    `voice_clean.clean` 回的是 (文字, 改動清單)——改動清單要一路帶回去印出來，
    **後洗改了什麼不能只有機器自己知道**。

    退件不是靜靜丟掉，是印出來並列進退件清單（呼叫端負責印）。靜默丟棄是這個
    系統最危險的失敗模式。

    `len_note` / `missing_note` 讓呼叫端補上**它自己那一層的理由**——「超過 60 字」
    對榜單的意思是「版面是一行」，對 Event 標題的意思不一樣。判準共用，
    解釋不共用：一句解釋不到位的退件訊息，會讓下一個人以為是規則寫錯了。
    """
    zh, changes = voice_clean.clean(str(raw or "").strip())
    zh = re.sub(r"\s+", " ", zh).strip().rstrip("。")
    if not zh:
        return "", "空白", changes
    if not CJK.search(zh):
        return zh, "沒有任何中文字（英文原樣貼回來不算翻譯）", changes
    if len(zh) > max_len:
        return zh, f"超過 {max_len} 字{len_note}", changes
    hit = [w for w in BANNED if w in zh]
    if hit:
        return zh, f"含 AI 腔套話：{'、'.join(hit)}", changes
    if not src_present:
        return zh, missing_note or "找不到對應的原文（下次 prep 會再排進來）", changes
    return zh, None, changes
