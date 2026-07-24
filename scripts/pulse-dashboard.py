#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-dashboard.py — 產出純 markdown 索引頁（不需 Dataview 外掛）。

掃 Events/，寫 _dashboards/published.md（已發布，乾淨檢視）與 _dashboards/blocked.md
（被門禁擋下 + 原因）。讓你有一個乾淨入口，不用一則則翻 Events/。

用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-dashboard.py
依賴：PyYAML。
"""
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import parse_note  # noqa: E402


def main():
    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    dash = vault / "_dashboards"
    dash.mkdir(parents=True, exist_ok=True)

    pub, blk = [], []
    for p in sorted(events_dir.glob("*.md")):
        fm, _ = parse_note(p.read_text("utf-8"))
        item = {
            "id": fm.get("id"), "title": fm.get("title", fm.get("id")),
            "date": str(fm.get("date") or ""), "company": fm.get("company", ""),
            "category": fm.get("category") or "", "summary": fm.get("summary") or "",
            "confidence": fm.get("confidence", 0), "heat": fm.get("heat", 0),
            "blockers": fm.get("blockers") or [],
        }
        if fm.get("status") == "published":
            pub.append(item)
        elif fm.get("status") == "review":
            blk.append(item)

    # published.md — 依日期分組、新的在前
    pub.sort(key=lambda x: x["date"], reverse=True)
    lines = [f"# 已發布事件（{len(pub)}）", "",
             "> 由 pulse-dashboard.py 自動產生，只列 status: published。", ""]
    by_date = defaultdict(list)
    for it in pub:
        by_date[it["date"]].append(it)
    for d in sorted(by_date, reverse=True):
        lines.append(f"## {d}")
        for it in by_date[d]:
            meta = f"{it['company']} · {it['category']} · conf {it['confidence']} · heat {it['heat']}"
            lines.append(f"- **[[Events/{it['id']}|{it['title']}]]** — {meta}")
            if it["summary"]:
                lines.append(f"  {it['summary']}")
        lines.append("")
    (dash / "published.md").write_text("\n".join(lines), encoding="utf-8")

    # blocked.md — 依 blocker 種類
    blk.sort(key=lambda x: (x["company"] != "industry", x["date"]), reverse=True)
    b = [f"# 被門禁擋下（{len(blk)}）", "",
         "> status: review，未通過 readiness gate。多為行銷 PR 或非 AI 政策噪音。", ""]
    for it in blk:
        b.append(f"- **[[Events/{it['id']}|{it['title'][:70]}]]** — {it['company']}"
                 f" — blockers: {', '.join(it['blockers'])}")
    (dash / "blocked.md").write_text("\n".join(b), encoding="utf-8")

    print(f"pulse-dashboard  published={len(pub)}  blocked={len(blk)}")
    print(f"  → {dash / 'published.md'}")
    print(f"  → {dash / 'blocked.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
