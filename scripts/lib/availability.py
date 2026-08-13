# -*- coding: utf-8 -*-
"""availability.py — 一筆證據「沒有內容」的三種原因。規格：references/evidence-availability.md。

2026-08-13 的夜間鏈潤 `evt-2026-08-11-797106`（Introducing Grok Bot）時寫出：

    ## 脈絡 / 影響 / 判斷   （證據不足，待補）
    ## 下一個訊號  xAI 是否釋出 Grok Bot 的功能說明…

而那份說明早就釋出了，就在 `https://x.ai/bot`——**那個連結躺在這一則自己的
證據列裡**。系統在等一個它手上已經有的東西，而且會一直等下去。

原因是語料裡那兩筆的 summary 是空字串，而空的理由不是頁面沒內容，是
`src-xai-news` 的 license_note 標了 `ai-input=no`：**我們選擇不取。**
那是政策決定，被寫成了證據狀態。

這個模組把那三種原因分開。判準全部來自 `_config/sources.yaml`，是純規則。
"""

# 三種狀態。改這裡等於改對讀者說的話，不要順手加。
HAS_TEXT = "has_text"     # 這一筆有摘要，內容在手上
UNFETCHED = "unfetched"   # 沒摘要，但來源允許摘錄 → 我們的缺口，該去修抓取端
WITHHELD = "withheld"     # 沒摘要，來源不允許摘錄 → 政策，把話寫對就好

# 站方公開宣告不希望內容被當成 AI 的輸入。這條不是我們畫的線，不能改。
_AI_INPUT_NO = "ai-input=no"


def evidence_availability(source_cfg, summary):
    """一筆證據為什麼沒有內容。回 (狀態, 理由)。

    `source_cfg` 是 `_config/sources.yaml` 裡那一條來源的 dict；`summary` 是
    語料裡那一筆的摘要。

    順序有意義：**先看手上有沒有東西，再看為什麼沒有。** 反過來的話，
    一條 license 很嚴但這次剛好給了摘要的來源會被判成不能用。

    找不到來源設定時回 `unfetched` 並在理由裡說出來——那是設定檔的問題，
    要被看見。不要因為「查不到就當成不能用」而靜靜跳過：
    那會讓一條漏登記的來源長得跟站方拒絕一模一樣。
    """
    if str(summary or "").strip():
        return HAS_TEXT, ""
    if not source_cfg:
        return UNFETCHED, "找不到這條來源的設定，查不出是不能取還是沒取到"
    note = str(source_cfg.get("license_note") or "")
    if _AI_INPUT_NO in note:
        return WITHHELD, "站方宣告 ai-input=no，不把內容當成 AI 的輸入"
    if source_cfg.get("excerpt_fetch") or "excerpt" in note:
        return UNFETCHED, "來源允許摘錄，但這一筆沒取到——是我們這邊的缺口"
    return WITHHELD, "license_note 限「標題＋連結」，這是我們自己的保守約束"


def writing_hint(state):
    """給潤稿端的一句話：這種狀態該怎麼寫。規格見 evidence-availability〈三種寫法〉。

    `unfetched` 明確回「不要寫進文章」：那是我們的故障，該進診斷、該有人去修，
    不該變成給讀者的一句「證據不足」。
    """
    return {
        HAS_TEXT: "內容在手上，照證據寫。",
        UNFETCHED: ("不要寫進文章。這是我們沒抓到，屬於故障不屬於證據狀態；"
                    "文章裡就當這一則只有標題。"),
        WITHHELD: ("寫出來並且給連結：說明為什麼我們不轉述、原文在哪裡。"
                   "不要寫成「證據不足」——那會告訴讀者沒有更多可知道的，而那是假的。"),
    }.get(state, "")


def event_availability(rows):
    """一則事件的所有證據合起來是什麼狀況。

    `rows` 是 [(source_cfg, summary), ...]。回 dict：每種狀態各幾筆，
    以及**這一則需不需要在文章裡放原文連結**（有任何一筆 withheld 就要）。
    """
    seen = {HAS_TEXT: 0, UNFETCHED: 0, WITHHELD: 0}
    reasons = []
    for cfg, summary in rows:
        state, why = evidence_availability(cfg, summary)
        seen[state] += 1
        if why:
            reasons.append(why)
    return {
        "counts": seen,
        # 有一筆是政策不取用，文章就欠讀者一個連結與一句解釋。
        "needs_source_link": seen[WITHHELD] > 0,
        "reasons": sorted(set(reasons)),
    }
