#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-narrative-prep.py — 找出「有新事件」的主線，打包成敘事刷新 worklist（確定性）。

紅線：哪條主線要重寫 now/next，由**事件集合的簽章變化**決定，不由 LLM 判斷。
  某主線的 published 事件集合（slug 集合）雜湊 != 上次記錄 → 這條 dirty。

輸出：
  _probe/narrative-worklist.json    只含 dirty 主線 + 打底事件 + 現有 thesis/now/next
  _probe/narrative-signatures.json  全部有事件主線的當前簽章（apply 成功後轉存為 state）

用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-narrative-prep.py
依賴：PyYAML。
"""
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import parse_note  # noqa: E402

import yaml  # noqa: E402

TRACKS = [("model-research", "模型能力與研究"), ("agent-refactor", "Agent 與軟體重構"),
          ("product-market", "產品與商業驗證"), ("infra-cost", "基礎設施與成本"),
          ("capital-evolution", "資本與公司演化"), ("global-map", "全球創新版圖")]
NAME2SLUG = {name: slug for slug, name in TRACKS}
ALIAS = {"模型能力與研究": "模型能力與研究", "基礎設施與成本": "基礎設施與成本",
         "產品與商業驗證": "產品與商業驗證", "資本與公司演化": "資本與公司演化",
         "Agent與軟體重構": "Agent 與軟體重構", "全球創新版圖": "全球創新版圖"}


def slug_of_track(track):
    return NAME2SLUG.get(ALIAS.get((track or "").strip(), ""))


def signature(slugs):
    return hashlib.sha1("|".join(sorted(slugs)).encode("utf-8")).hexdigest()[:16]


def main():
    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    if not events_dir.exists():
        print("[fatal] 無 Events/ 目錄", file=sys.stderr)
        return 2

    by_track = defaultdict(list)
    for p in sorted(events_dir.glob("*.md")):
        fm, _ = parse_note(p.read_text("utf-8"))
        if fm.get("status") != "published":
            continue
        slug = slug_of_track(fm.get("track"))
        if not slug:
            continue
        by_track[slug].append({
            "slug": fm.get("slug") or fm.get("id"), "date": str(fm.get("date") or ""),
            "company": fm.get("company", ""), "title": fm.get("title", ""),
            "summary": fm.get("summary", ""), "confidence": fm.get("confidence", 0),
            # 給敘述層看的。heat 沒量到時送 "未量測"，不送 0——送 0 的話 LLM 會
            # 寫出「熱度低、還沒共振」這種結論，那是拿沒量過的東西當論據
            # （紅線 2 與 8）。_config/narratives.yaml 裡已經有這樣寫成的句子。
            "heat": "未量測" if fm.get("heat") is None else fm.get("heat"),
        })

    narr_file = vault / "_config" / "narratives.yaml"
    narr = {}
    if narr_file.exists():
        narr = (yaml.safe_load(narr_file.read_text("utf-8")) or {}).get("tracks") or {}

    state_file = vault / "_probe" / "narrative-state.json"
    prev = json.loads(state_file.read_text("utf-8")) if state_file.exists() else {}

    signatures = {}
    worklist = []
    for slug, name in TRACKS:
        evs = by_track.get(slug, [])
        if not evs:
            continue
        evs.sort(key=lambda x: x["date"], reverse=True)
        sig = signature([e["slug"] for e in evs])
        signatures[slug] = sig
        if sig == prev.get(slug):
            continue  # 事件集合沒變 → 不重寫
        cur = narr.get(slug) or {}
        worklist.append({
            "slug": slug, "name": name,
            "current_thesis": cur.get("thesis", ""),
            "current_now": cur.get("now", ""),
            "current_next": cur.get("next", ""),
            "events": evs,
        })

    out_dir = vault / "_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "narrative-worklist.json").write_text(
        json.dumps(worklist, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "narrative-signatures.json").write_text(
        json.dumps(signatures, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"pulse-narrative-prep  有事件主線={len(signatures)}  待重寫(dirty)={len(worklist)}")
    for w in worklist:
        print(f"  · {w['slug']}（{w['name']}）：{len(w['events'])} 則事件")
    print(f"  → {out_dir / 'narrative-worklist.json'}")
    if not worklist:
        print("  今晚沒有主線事件集合變動，敘事不需重寫。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
