#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-gate.py — Sprint 3d：readiness gate + auto-publish（純規則，零 LLM）。

移植 agent-pulse pipeline/readiness.ts 的 blocker 清單 + auto-publish.ts：
對每個 status=review 的 Event 逐條檢查硬門禁，全過（0 blocker）→ status: published；
否則把 blockers[] 寫進 frontmatter（blocked 佇列看得到原因）。門檻讀 _config/gate.yaml。

紅線：這一層是**判斷**——由規則決定發不發，零 LLM。未 enrich 的事件必被 placeholder_content
擋住（body 還有「待编辑」），所以雜訊不會混上線。
用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-gate.py [--dry-run]
依賴：PyYAML。
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import dump_frontmatter, parse_note  # noqa: E402

import yaml  # noqa: E402

PLACEHOLDER_RE = re.compile(r"待编辑|待補充|待补充|TBD|TODO|placeholder", re.I)
GENERIC_ENTITY = {"industry", "unknown", "other", "其他", "未知", ""}


def section(body, heading):
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, flags=re.M | re.S)
    return (m.group(1).strip() if m else "")


def evaluate(fm, body, gate):
    r = gate.get("readiness", {})
    min_conf = r.get("min_confidence", 60)
    thin_min = r.get("thin_fact_min_chars", 20)
    heat_th = r.get("heat_threshold", 70)
    heat_min_ind = r.get("heat_min_independent_sources", 2)
    heat_min_plat = r.get("heat_min_platform_breadth", 2)

    blockers = []
    fact = section(body, "事實")
    summary = (fm.get("summary") or "").strip()

    # placeholder：body 任一處還有佔位詞 → 未 enrich
    if PLACEHOLDER_RE.search(body):
        blockers.append("placeholder_content")
    if len(fact) < thin_min or len(summary) < thin_min:
        blockers.append("thin_fact")
    # thin_research_analysis：research 類需有實質分析
    if str(fm.get("category") or "").lower() in ("research", "paper"):
        if len(section(body, "影響")) < 40 or len(section(body, "脈絡")) < 30:
            blockers.append("thin_research_analysis")
    if str(fm.get("company") or "").strip().lower() in GENERIC_ENTITY:
        blockers.append("generic_entity")
    cat = str(fm.get("category") or "").strip()
    if not cat or cat == "industry":
        blockers.append("missing_category")
    if not (fm.get("keywords") or []):
        blockers.append("missing_keywords")
    if not (fm.get("track") or ""):
        blockers.append("missing_track")
    if not (fm.get("evidence") or []):
        blockers.append("missing_evidence")
    if not (fm.get("primary_evidence") or 0):
        blockers.append("missing_primary_evidence")
    if (fm.get("confidence") or 0) < min_conf:
        blockers.append("low_confidence")
    factors = fm.get("score_factors") or {}
    if (fm.get("heat") or 0) >= heat_th and (
        (factors.get("independentSources", 0) < heat_min_ind)
        or (factors.get("platformBreadth", 0) < heat_min_plat)
    ):
        blockers.append("unsupported_heat")

    warnings = []
    if (fm.get("independent_sources") or 0) < 2:
        warnings.append("single-source fact; cross-source corroboration pending")
    return blockers, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    gate = yaml.safe_load((vault / "_config" / "gate.yaml").read_text("utf-8"))
    if not events_dir.exists():
        print("[fatal] 無 Events/ 目錄", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc).isoformat()
    reviewed = published = blocked = 0
    blocker_hist = {}
    published_titles = []

    for p in sorted(events_dir.glob("*.md")):
        fm, body = parse_note(p.read_text("utf-8"))
        if fm.get("status") != "review":
            continue
        reviewed += 1
        blockers, warnings = evaluate(fm, body, gate)
        fm["blockers"] = blockers
        fm["warnings"] = warnings
        if not blockers:
            fm["status"] = "published"
            fm["published_at"] = now
            fm["tags"] = [("published" if t == "review" else t) for t in (fm.get("tags") or [])]
            published += 1
            published_titles.append(fm.get("title", fm.get("id")))
        else:
            blocked += 1
            for b in blockers:
                blocker_hist[b] = blocker_hist.get(b, 0) + 1
        if not args.dry_run:
            p.write_text(f"---\n{dump_frontmatter(fm)}\n---{body if body.startswith(chr(10)) else chr(10)+body}",
                         encoding="utf-8")

    print(f"pulse-gate  reviewed={reviewed}  published={published}  blocked={blocked}"
          f"{'  [dry-run]' if args.dry_run else ''}")
    if published_titles:
        print("  ── published ──")
        for t in published_titles:
            print(f"    ✓ {t[:72]}")
    if blocker_hist:
        print("  ── blocker 分佈 ──")
        for b, n in sorted(blocker_hist.items(), key=lambda x: -x[1]):
            print(f"    {n:3}  {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
