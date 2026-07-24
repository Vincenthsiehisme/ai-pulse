#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test-pulse-score.py — lib/quality.py 與 lib/cluster.py 的離線單元測試（純 stdlib）。

用法：python scripts/test-pulse-score.py
exit 0 全過 / 1 有失敗。改動評分或 fingerprint/facet 規則前後都該跑。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cluster, quality, scoring, voice_clean  # noqa: E402

FAILS = []


def check(name, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")


def check_true(name, cond):
    if not cond:
        FAILS.append(f"{name}: expected True")


# ── fingerprint ──
check("fp gpt-5", cluster.event_fingerprint("OpenAI announces GPT-5"), "openai:gpt:5")
check("fp gpt-4o mini", cluster.event_fingerprint("GPT-4o mini is here"), "openai:gpt:4o-mini")
check("fp gemini 2.5 flash", cluster.event_fingerprint("Gemini 2.5 Flash released"), "google:gemini:2.5-flash")
check("fp claude opus 4.8", cluster.event_fingerprint("Introducing Claude Opus 4.8"), "anthropic:claude:opus:4.8")
check("fp deepseek v3", cluster.event_fingerprint("DeepSeek-V3 benchmark"), "deepseek:v3")
check("fp cjk 通义", cluster.event_fingerprint("通义 Qwen3 发布"), "qwen:3")
check("fp none", cluster.event_fingerprint("Company hires new CFO"), None)

# ── facet ──
check("facet release", cluster.event_facet("OpenAI launches GPT-5"), "release")
check("facet capital", cluster.event_facet("Anthropic raises Series F funding"), "capital")
check("facet pricing", cluster.event_facet("Google cuts Gemini API pricing"), "pricing")
check("facet incident", cluster.event_facet("Major outage hits ChatGPT"), "incident")
check("facet benchmark", cluster.event_facet("New benchmark scores released"), "benchmark")
check("facet zh 融资", cluster.event_facet("智谱完成新一轮融资"), "capital")
check("facet default", cluster.event_facet("Some vague headline about things"), "update")
check("bucket update->release", cluster.event_facet_bucket("update"), "release")

# ── title similarity ──
check_true("sim identical", cluster.title_similarity("GPT-5 released today", "GPT-5 released today") == 1.0)
check_true("sim disjoint", cluster.title_similarity("cat dog bird", "stock market news") == 0.0)
check_true("sim partial in-range", 0.0 < cluster.title_similarity("OpenAI releases GPT-5 model", "OpenAI GPT-5 model launch") < 1.0)

# ── parse_dt ──
check_true("dt rfc822", quality.parse_dt("Thu, 23 Jul 2026 09:23:02 GMT") is not None)
check_true("dt iso", quality.parse_dt("2026-07-23T09:23:02+00:00") is not None)
check_true("dt bad", quality.parse_dt("not a date") is None)
check_true("dt empty", quality.parse_dt("") is None)

# ── effective_role 對映 ──
check("role official vendor", quality.effective_role("official", "vendor", "official"), "primary")
check("role official research", quality.effective_role("official", "research", "official"), "research")
check("role kol expert", quality.effective_role("kol", "individual", "expert"), "expert")
check("role aggregator", quality.effective_role("aggregator", "aggregator", "aggregator"), "aggregator")

# ── score_signal：tier-1 官方研究 vs 聚合薄訊號 ──
TH = {"A": 85, "B": 70, "C": 55, "D": 40}
rich = {
    "title": "Meta AI publishes new results on efficient training methods",
    "summary": "x" * 500,
    "url": "https://research.facebook.com/a-long-canonical-url",
    "published": "2026-07-23T09:00:00+00:00",
    "first_observed_at": "2026-07-23T10:00:00+00:00",
    "author": "Jane Researcher",
    "entity_hits": ["meta", "llama", "agent"],
}
src_research = {"track": "official", "source_category": "research", "role": "official", "tier": 1}
s_rich = quality.score_signal(rich, src_research, quality.parse_dt("2026-07-23T10:00:00+00:00"), TH)
check_true("rich total high", s_rich["total"] >= 70)
check("rich role", s_rich["effective_role"], "research")

thin = {
    "title": "News",
    "summary": "",
    "url": "",
    "published": "",
    "first_observed_at": "2026-07-23T10:00:00+00:00",
    "author": None,
    "entity_hits": [],
}
src_agg = {"track": "aggregator", "source_category": "aggregator", "role": "aggregator", "tier": 3}
s_thin = quality.score_signal(thin, src_agg, quality.parse_dt("2026-07-23T10:00:00+00:00"), TH)
check_true("thin total low", s_thin["total"] < 40)
check_true("thin has flags", "short-title" in s_thin["flags"] and "aggregator-only" in s_thin["flags"])

# ── 3b: eventability_score ──
src_off1 = {"tier": 1, "source_category": "vendor"}
sig_release = {"title": "OpenAI announces GPT-5", "summary": "x" * 50,
               "effective_role": "primary", "quality": 74}
check_true("eventability release+fp high", cluster.eventability_score(sig_release, src_off1) >= 70)
sig_thin = {"title": "A quiet company blog note", "summary": "x" * 10,
            "effective_role": "primary", "quality": 60}
check_true("eventability thin lower", cluster.eventability_score(sig_thin, src_off1) < 70)
src_agg = {"tier": 3, "source_category": "aggregator"}
check("eventability aggregator=0", cluster.eventability_score(
    {"title": "GPT-5 released", "summary": "", "effective_role": "aggregator", "quality": 90}, src_agg), 0)
check("eventability no source=0", cluster.eventability_score(sig_release, None), 0)

# ── 3b: score_event ──
se = scoring.score_event(authority_scores=[90, 65], primary_count=2, independent_count=2,
                         metrics=[], age_hours=10)
check_true("score confidence in range", 0 <= se["confidence"] <= 100)
check_true("score confidence reflects authority+primary", se["confidence"] >= 70)
check_true("score heat low without social", se["heat"] < 40)
check("score factors independent", se["factors"]["independentSources"], 2)
se0 = scoring.score_event(authority_scores=[], primary_count=0, independent_count=0,
                          metrics=[], age_hours=1000)
check_true("score empty low confidence", se0["confidence"] < 40)

# ── 3c: voice_clean（去 AI 口吻後洗）──
c1, _ = voice_clean.clean("這個視頻的質量很高，信息量也大")
check("voice 中國用語", c1, "這個影片的品質很高，資訊量也大")
c2, _ = voice_clean.clean("人工智能發展快速")
check("voice 人工智能", c2, "人工智慧發展快速")
c3, _ = voice_clean.clean("模型發布了,定價也公布了.")
check("voice 半形→全形", c3, "模型發布了，定價也公布了。")
c4, _ = voice_clean.clean("LCP 從 3.2 秒降到 1.8 秒")
check_true("voice 保護小數點", "3.2" in c4 and "1.8" in c4)
c5, changes = voice_clean.clean("這軟件質量不錯")
check_true("voice 回報變更", len(changes) >= 1)

# ── 3d: pulse-gate evaluate（載入含連字號的腳本）──
import importlib.util as _ilu  # noqa: E402
_gp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pulse-gate.py")
_spec = _ilu.spec_from_file_location("pulse_gate", _gp)
_gate = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
GATE = {"readiness": {"min_confidence": 60, "thin_fact_min_chars": 20}}
fm_ok = {"summary": "這是一段夠長的摘要內容超過二十個字元用來測試", "company": "NVIDIA",
         "category": "infra", "track": "基礎設施與成本", "keywords": ["a"], "evidence": [{"x": 1}],
         "primary_evidence": 1, "confidence": 73, "heat": 8, "independent_sources": 1, "score_factors": {}}
body_ok = "## 事實\n這是一段夠長的事實描述內容超過二十個字元有具體資訊。\n\n## 影響\nxxx\n"
bk_ok, _w = _gate.evaluate(fm_ok, body_ok, GATE)
check("gate 乾淨事件=0 blocker", bk_ok, [])
fm_ph = dict(fm_ok, category=None, track=None)
bk_ph, _w2 = _gate.evaluate(fm_ph, "## 事實\n待编辑：待補\n", GATE)
check_true("gate 佔位被擋", "placeholder_content" in bk_ph and "missing_category" in bk_ph)
bk_gen, _w3 = _gate.evaluate(dict(fm_ok, company="industry"), body_ok, GATE)
check_true("gate 泛稱實體被擋", "generic_entity" in bk_gen)

# ── 報告 ──
if FAILS:
    print(f"FAIL — {len(FAILS)} 個：")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("PASS — 所有 3a 測試通過")
sys.exit(0)
