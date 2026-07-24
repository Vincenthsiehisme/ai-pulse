# -*- coding: utf-8 -*-
"""scoring.py — Event 評分（移植 agent-pulse src/domain/scoring.ts，純規則）。

confidence = authority·0.62 + min(獨立,4)·7 + min(primary,2)·10
heat       = log(作者)·30 + log(推文)·20 + min(獨立,5)·8 + min(平台,4)·7 + min(地區,3)·6 + freshness·0.08
  （本階段尚未收集社群指標 → 作者/推文/平台/地區皆 0，heat 主要來自獨立數與 freshness，偏低屬正常，
   熱度要等 M3 KOL/社群線才會起來。）
value      = conf·0.3 + impact·0.3 + heat·0.25 + freshness·0.15
freshness  = 100·exp(-ageHours/96)

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
    heat = _clamp(
        _logscale(authors, 80) * 30
        + _logscale(tweets, 300) * 20
        + min(independent_count, 5) * 8
        + min(platforms, 4) * 7
        + min(regions, 3) * 6
        + freshness * 0.08
    )
    impact = _clamp(impact_hint if impact_hint is not None else 55)
    value = _clamp(confidence * 0.3 + impact * 0.3 + heat * 0.25 + freshness * 0.15)

    return {
        "confidence": confidence,
        "heat": heat,
        "impact": impact,
        "value": value,
        "factors": {
            "authority": authority,
            "corroboration": min(independent_count * 20, 100),
            "primaryEvidence": min(primary_count * 50, 100),
            "uniqueAuthors": authors,
            "independentSources": independent_count,
            "platformBreadth": platforms,
            "regionBreadth": regions,
            "velocity": _clamp(_logscale(tweets, 300) * 100),
            "freshness": freshness,
            "crossRegion": cross_region,
        },
    }
