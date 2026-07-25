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
# 簡體舊寫法。**這一條是相容性回歸測試，不要改成繁體。**
# vault 裡已經有用「待编辑」寫成的既有 Event（例：evt-2026-07-24-dd57bd）。
# 哪天有人把舊寫法從 PLACEHOLDER_RE 拿掉，那些未潤稿的事件會突然通過
# placeholder_content，佔位文字直接上線——這裡就是那個哪天的煞車。
bk_ph, _w2 = _gate.evaluate(fm_ph, "## 事實\n待编辑：待補\n", GATE)
check_true("gate 佔位被擋（簡體舊寫法）",
           "placeholder_content" in bk_ph and "missing_category" in bk_ph)
bk_ph2, _w2b = _gate.evaluate(fm_ph, "## 事實\n待編輯：待補\n", GATE)
check_true("gate 佔位被擋（繁體新寫法）", "placeholder_content" in bk_ph2)
# 產生端與偵測端共用 lib/notes.py 一份常數；新事件寫繁體，偵測端兩種都認。
from lib.notes import PLACEHOLDER, PLACEHOLDER_RE  # noqa: E402
check("新事件佔位詞是繁體", PLACEHOLDER, "待編輯")
check_true("偵測端認得自家產生的佔位詞", bool(PLACEHOLDER_RE.search(PLACEHOLDER)))
check_true("偵測端認得簡體舊寫法", bool(PLACEHOLDER_RE.search("待编辑")))
bk_gen, _w3 = _gate.evaluate(dict(fm_ok, company="industry"), body_ok, GATE)
check_true("gate 泛稱實體被擋", "generic_entity" in bk_gen)

# ── keyword_tokens：確定性 + 虛詞過濾 ──
# 真實案例：evt-2026-07-24-dd57bd 當初拿到的 keywords 是
# ['at','future','summit','ai','outlines','south','its','partners'] —— nvidia 不在裡面。
_T = "At AI Summit, South Korea Outlines Its AI Future With NVIDIA and Partners"
_kw = cluster.keyword_tokens(_T, 8)
# 寫死期望值而不是拿兩次呼叫互比：同一個行程裡比不出雜湊隨機化，
# 要跨行程才看得到。寫死了，任何一次「順序又飄了」都會在這裡紅。
check("keyword 同輸入同輸出", _kw,
      ["ai", "summit", "south", "korea", "outlines", "future", "nvidia", "partners"])
check_true("keyword 濾掉 at/its", "at" not in _kw and "its" not in _kw)
check_true("keyword 留住 nvidia", "nvidia" in _kw)
check_true("keyword 依標題原順序", _kw.index("summit") < _kw.index("nvidia"))
check("keyword 上限生效", len(cluster.keyword_tokens(_T, 3)), 3)
check("keyword 去重", cluster.keyword_tokens("Gemini Gemini Gemini", 8), ["gemini"])
check("keyword 濾純數字", cluster.keyword_tokens("Qwen 3 2026", 8), ["qwen"])
# STOP_WORDS 參與 title_similarity＝參與聚類；分家才不會被關鍵詞的需求帶著改掉聚類。
check_true("兩份停用詞分家", cluster.KEYWORD_STOP_WORDS > cluster.STOP_WORDS)
check("STOP_WORDS 維持 11 個未被擴張", len(cluster.STOP_WORDS), 11)

# ── 當日快照重寫時 backfill / is_new 不能被本輪值抹掉 ──
# 真實案例：2026-07-25 改成每 2 小時一班之後，05:21 那班標了 300 筆 backfill，
# 08:13 那班把同一批全部翻成 false，report 開頭那句「lead_days 與熱度統計應排除」
# 整段消失。檔案還在、筆數一樣、沒有錯誤——典型的靜默失敗，只有這裡會紅。
import json as _json  # noqa: E402
import tempfile as _tf  # noqa: E402
from pathlib import Path as _P  # noqa: E402

_pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pulse-probe.py")
_pspec = _ilu.spec_from_file_location("pulse_probe", _pp)
_probe = _ilu.module_from_spec(_pspec)
_pspec.loader.exec_module(_probe)

with _tf.TemporaryDirectory() as _td:
    _snap = _P(_td) / "src-x.jsonl"
    _snap.write_text(
        _json.dumps({"url_canonical": "https://e.com/a", "backfill": True,
                     "is_new": True, "title": "早上那批"}, ensure_ascii=False)
        + "\n\n{ 這行是壞掉的 JSON\n"
        + _json.dumps({"url_canonical": "https://e.com/b", "backfill": False,
                       "is_new": True, "title": "早上第一次看到"}, ensure_ascii=False)
        + "\n", encoding="utf-8")
    _prior = _probe.load_day_flags(_snap)
    check("壞行與空行不擋整班（只讀到 2 筆）", len(_prior), 2)

    # 第二班：backfill / is_new 都被算成 False，必須被早上的值蓋回來。
    _r1 = {"url_canonical": "https://e.com/a", "backfill": False, "is_new": False}
    _probe.carry_day_flags(_r1, _prior)
    check_true("同日第二班不得抹掉 backfill", _r1["backfill"] is True)
    check_true("同日第二班不得抹掉 is_new", _r1["is_new"] is True)

    # 早上就是 False 的不能因為「沿用」被硬升成 True。
    _r2 = {"url_canonical": "https://e.com/b", "backfill": False, "is_new": False}
    _probe.carry_day_flags(_r2, _prior)
    check_true("沿用是照抄不是硬設 True", _r2["backfill"] is False and _r2["is_new"] is True)

    # 當日第一次出現的項目維持本輪判定——那才是它真正的第一次。
    _r3 = {"url_canonical": "https://e.com/new", "backfill": True, "is_new": True}
    _probe.carry_day_flags(_r3, _prior)
    check_true("當日新項目維持本輪判定", _r3["backfill"] is True and _r3["is_new"] is True)

    check("檔案不存在時回空 dict", _probe.load_day_flags(_P(_td) / "無此檔.jsonl"), {})
    check("sticky 欄位就是這兩個", _probe.DAY_STICKY_FIELDS, ("backfill", "is_new"))

# ── 報告 ──
if FAILS:
    print(f"FAIL — {len(FAILS)} 個：")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("PASS — 所有 3a 測試通過")
sys.exit(0)
