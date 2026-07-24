# -*- coding: utf-8 -*-
"""quality.py — 訊號五維品質評分（移植 agent-pulse src/pipeline/quality.ts）。

去AI化(=去 AI 口吻)在本層的意義：本層是**判斷層，純規則、零 LLM**——這正是讀法二
下也保留的部分。五維上限與 grade 門檻由 gate.yaml 給（docs-first：門檻在設定檔，公式在碼）。

五維：authority / richness / freshness / originality / completeness（各自上限見 gate.yaml.quality.weights）

欄位對映（本 vault 的 _corpus 記錄 → agent-pulse 的 CollectedSignal 評分輸入）：
  tags       ← entity_hits（pulse-probe 已抽的實體命中，當作 signal 的 tags）
  role       ← 由 track + source_category + role 推導 effective_role（見下）
  authority  ← 由 tier 推導（本 schema 無 authorityScore 欄位，tier 決定）
  now        ← 該筆的 first_observed_at（收集時間），讓 freshness 可重現、不吃 wall-clock
  category / metrics / origin ← 本階段尚無，缺項按規則扣分（全體一致，不偏頗）
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


def effective_role(track, source_category, role):
    """把本 vault 的 track/source_category/role 對映到評分需要的角色語彙。

    agent-pulse 的 role = primary/research/expert/media/heat/aggregator；
    本 vault 用 track(official/kol/aggregator) + source_category + role。
    """
    if track == "aggregator":
        return "aggregator"
    if track == "kol":
        return "social" if role == "social" else "expert"
    # track == official（一手發布）
    if source_category == "research":
        return "research"
    return "primary"


def authority_score_from_tier(tier):
    """本 schema 無 authorityScore 欄位；由 tier 給確定性起始值。"""
    try:
        t = int(tier)
    except (TypeError, ValueError):
        return 50
    return {1: 90, 2: 65, 3: 40}.get(t, 50)


def parse_dt(s):
    """容忍 RFC822（RSS pubDate）與 ISO8601；回 aware datetime 或 None。"""
    if not s:
        return None
    s = str(s).strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    return None


# ─── 五維 ────────────────────────────────────────────────────────────────

def _authority(role, authority_score):
    base = authority_score if authority_score is not None else 50
    normalized = min(25, round(base / 4))
    bonus = {"primary": 3, "research": 2, "expert": 1}.get(role, 0)
    return min(25, normalized + bonus)


def _richness(title, summary, tags):
    score = 0
    slen = len(summary or "")
    tlen = len(title or "")
    if slen > 800:
        score += 10
    elif slen > 400:
        score += 7
    elif slen > 100:
        score += 4
    else:
        score += 1
    if 20 < tlen < 150:
        score += 8
    elif tlen > 10:
        score += 4
    else:
        score += 1
    n = len(tags or [])
    if n >= 3:
        score += 4
    elif n >= 1:
        score += 2
    # metrics（互動數）：本 vault 尚未收集 → 恆缺，少 3 分，全體一致
    return min(25, score)


def _freshness(published_at, now):
    pub = parse_dt(published_at)
    if pub is None or now is None:
        return 10
    hours = (now - pub).total_seconds() / 3600.0
    if hours <= 1:
        return 20
    if hours <= 6:
        return 18
    if hours <= 24:
        return 15
    if hours <= 72:
        return 10
    if hours <= 168:
        return 6
    if hours <= 720:
        return 3
    return 1


def _originality(role, origin):
    if role in ("primary", "research"):
        return 15
    if role == "expert":
        return 12
    if origin and origin.get("url"):
        return 10
    if origin and origin.get("kind") == "social" and origin.get("handle"):
        return 8
    if role in ("aggregator", "heat"):
        return 4
    return 7


def _completeness(url, title, summary, published_at, category, tags, author):
    score = 0
    if len(url or "") > 10:
        score += 3
    if len(title or "") > 5:
        score += 3
    if len(summary or "") > 50:
        score += 3
    if parse_dt(published_at) is not None:
        score += 3
    if category and category != "industry":
        score += 1
    if len(tags or []) > 0:
        score += 1
    if author:
        score += 1
    return min(15, score)


def to_grade(total, thresholds):
    """thresholds = gate.yaml quality.grade_thresholds {A,B,C,D}。"""
    if total >= thresholds["A"]:
        return "A"
    if total >= thresholds["B"]:
        return "B"
    if total >= thresholds["C"]:
        return "C"
    if total >= thresholds["D"]:
        return "D"
    return "F"


def detect_flags(dims, role, published_at, category, title, tags):
    flags = []
    if dims["authority"] < 8:
        flags.append("low-authority")
    if dims["richness"] < 8:
        flags.append("thin-content")
    if dims["freshness"] < 5:
        flags.append("stale")
    if role == "aggregator" or dims["originality"] < 5:
        flags.append("aggregator-only")
    if parse_dt(published_at) is None:
        flags.append("missing-date")
    if not category or category == "industry":
        flags.append("missing-category")
    if len(title or "") < 10:
        flags.append("short-title")
    if len(tags or []) == 0:
        flags.append("no-tags")
    return flags


def score_signal(rec, source, run_now, thresholds):
    """rec = _corpus jsonl 記錄；source = sources.yaml 條目；
    run_now = 該次執行的參考時間（僅在 record 無 first_observed_at 時 fallback）。
    freshness 以該筆 first_observed_at（收集時間）為基準，確保可重現。
    """
    role = effective_role(source.get("track"), source.get("source_category"), source.get("role"))
    auth = authority_score_from_tier(source.get("tier"))
    tags = rec.get("entity_hits") or []
    title = rec.get("title")
    summary = rec.get("summary")
    published = rec.get("published")
    category = rec.get("category")  # 本階段恆 None
    now = parse_dt(rec.get("first_observed_at")) or run_now
    dims = {
        "authority": _authority(role, auth),
        "richness": _richness(title, summary, tags),
        "freshness": _freshness(published, now),
        "originality": _originality(role, rec.get("origin")),
        "completeness": _completeness(rec.get("url"), title, summary, published, category, tags, rec.get("author")),
    }
    total = int(round(sum(dims.values())))
    return {
        "total": total,
        "dimensions": dims,
        "grade": to_grade(total, thresholds),
        "flags": detect_flags(dims, role, published, category, title, tags),
        "effective_role": role,
    }
