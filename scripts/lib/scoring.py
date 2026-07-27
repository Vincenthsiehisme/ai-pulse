# -*- coding: utf-8 -*-
"""scoring.py — Event 評分（移植 agent-pulse src/domain/scoring.ts，純規則）。

confidence = authority·0.62 + min(獨立,4)·7 + min(primary,2)·10
heat       = log(作者)·30 + log(推文)·20 + min(獨立,5)·8 + min(平台,4)·7 + min(地區,3)·6 + freshness·0.08
             **只在四項傳播輸入至少一項非零時才算**；一項都沒有就回 None（理由見下）。
value      = heat 有值 → conf·0.30 + impact·0.30 + heat·0.25 + freshness·0.15
             heat 為空 → conf·0.40 + impact·0.40 +             freshness·0.20
freshness  = 100·exp(-ageHours/96)

heat 為什麼可以是 None（2026-07-26 的決定，規格見 references/readiness-gate.md）：

  公式六項裡有四項要社群傳播證據——作者數、推文數、平台廣度、地域廣度，合計 63 分。
  這四項在 vault 全部 51 個 Event 上都是 0，而且不是「資料還沒進來」：pulse-cluster.py
  呼叫本函式時第四個參數直接寫死 `metrics=[]`，那條線從來沒有接過。剩下會動的只有
  min(獨立,5)·8 與 freshness·0.08，實測 heat 落在 8–32，理論上限 48。

  也就是說，欄位名稱說的是傳播熱度，量到的是「獨立來源數 + 新鮮度」。紅線 8 說
  量不到就寫量不到，所以：一項傳播訊號都沒有時 heat 是 None，不是一個數字。
  **不印 0**——0 看起來像「量過了，很冷」，那是更難察覺的一種謊。

  `factors["propagationSignals"]` 記下四項裡有幾項非零，讓「什麼都沒量到」成為寫在
  磁碟上的事實，而不是要下游從四個 0 自己推論。pulse-gate.py 的 `unmeasured_heat`
  會擋下「有 heat 數字但 propagationSignals 為 0」的 Event——包含未來有人把無條件
  計算加回來的那一天。

  沒有做的兩件事，理由寫在 references/readiness-gate.md：不降 gate 的 70（會讓一條
  跟傳播無關的數字去觸發熱度防線），不把 63 分重新分配給還活著的兩項（值域補滿只會
  讓「這不是熱度」更難被發現）。

獨立數的計算不在本檔（在 pulse-cluster.py），且依本系統紅線第 5 條用 **distinct media_group**
（比 agent-pulse 原碼的 distinct source_id 嚴格：同 media_group 不算兩個獨立來源）。
"""
from __future__ import annotations

import math


def _clamp(v):
    return max(0, min(100, int(round(v))))


def _logscale(v, denom):
    return 0.0 if v <= 0 else min(1.0, math.log1p(v) / math.log1p(denom))


def score_event(authority_scores, primary_count, independent_count, metrics, age_hours, impact_hint=55):
    authority = max(authority_scores) if authority_scores else 20
    authors = max([0] + [m.get("authors", 0) or 0 for m in metrics])
    tweets = max([0] + [m.get("tweets", 0) or 0 for m in metrics])
    platforms = len({p for m in metrics for p in (m.get("platforms") or [])})
    regions = len({r for m in metrics for r in (m.get("regions") or [])})
    cross_region = regions >= 2
    freshness = _clamp(100 * math.exp(-max(0, age_hours) / 96))

    confidence = _clamp(
        authority * 0.62
        + min(independent_count, 4) * 7
        + min(primary_count, 2) * 10
    )
    # 四項傳播輸入裡有幾項真的量到東西。全 0 ＝ 沒有任何傳播證據，
    # 那 heat 就沒有東西可算——不是算出一個低分，是算不出來。
    propagation_signals = sum(1 for v in (authors, tweets, platforms, regions) if v > 0)
    # 「有沒有量過」與「量到的值是多少」是兩件事。metrics 空＝這一則從來沒有
    # 傳播資料進來過，那四個因子不是 0，是不知道。
    measured = bool(metrics)
    heat = _clamp(
        _logscale(authors, 80) * 30
        + _logscale(tweets, 300) * 20
        + min(independent_count, 5) * 8
        + min(platforms, 4) * 7
        + min(regions, 3) * 6
        + freshness * 0.08
    ) if propagation_signals else None
    impact = _clamp(impact_hint if impact_hint is not None else 55)
    value = _clamp(
        confidence * 0.30 + impact * 0.30 + heat * 0.25 + freshness * 0.15
        if heat is not None else
        # heat 缺席時把它那 0.25 按比例分回還在的三項（0.30/0.30/0.15 ÷ 0.75）。
        # 不是「丟掉 0.25」——那會讓 value 的上限變成 75，跟舊資料不可比。
        confidence * 0.40 + impact * 0.40 + freshness * 0.20
    )

    return {
        "confidence": confidence,
        "heat": heat,
        "impact": impact,
        "value": value,
        "factors": {
            "authority": authority,
            "corroboration": min(independent_count * 20, 100),
            "primaryEvidence": min(primary_count * 50, 100),
            # 這五格跟 heat 走同一條規矩：**一項傳播訊號都沒量到時不編數字。**
            #
            # 上面第 22 行的 docstring 早就寫著「讓『什麼都沒量到』成為寫在資料裡
            # 的事實」，而 heat 也照做了（`if propagation_signals else None`）。
            # 但這四個因子本身仍然回 0——`max([0] + [...])` 對空 metrics 就是 0，
            # `len(set())` 也是 0。實測後果：**41 / 41 則已發布頁把它們印成粗體 0**，
            # 就在同一張卡片上寫著「未量測」的 heat 旁邊。
            #
            # 0 跟 None 在這裡是兩件完全不同的事：0 是「量過了，一個作者都沒有」，
            # None 是「我們從來沒量過」。`lib/scoring.py` 自己的話是
            # 「0 看起來像『量過了，很冷』，那是更難察覺的一種謊」。
            #
            # `crossRegion` 一起改：`regions >= 2` 在沒量測時回 False，
            # 而 False 讀起來是「確定不跨區」——同一隻病，換成布林。
            #
            # **刻意不動 confidence / heat / impact / value 的算法。** 那四個數字
            # 一動，全站分數就會重排——2026-07-27 已經有一次「順手重算」把 55 則
            # 事件的 value 全部改掉的事故。這裡改的只有「怎麼回報量不到」。
            "uniqueAuthors": authors if measured else None,
            "independentSources": independent_count,
            "platformBreadth": platforms if measured else None,
            "regionBreadth": regions if measured else None,
            "velocity": _clamp(_logscale(tweets, 300) * 100) if measured else None,
            "freshness": freshness,
            "crossRegion": cross_region if measured else None,
            "propagationSignals": propagation_signals,
        },
    }
