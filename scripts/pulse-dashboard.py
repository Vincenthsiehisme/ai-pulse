#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-dashboard.py — 產出純 markdown 索引頁（不需 Dataview 外掛）。

掃 Events/，寫 _dashboards/published.md（已發布，乾淨檢視）、_dashboards/blocked.md
（被門禁擋下 + 原因）與 _dashboards/dropped.md（人工判定不追 + 理由）。
讓你有一個乾淨入口，不用一則則翻 Events/。

**dropped.md 存在的唯一理由是：不讓「人工放棄」變成靜默丟棄。**
status: dropped 在 gate / enrich-prep / render / monitor 眼中都是隱形的——它不進門禁、
不排隊等潤稿、不上站、也不算未潤稿。少了這一頁，人工按掉的東西就會從整個系統的視野
裡消失，而「東西為什麼不見了」是這套系統最貴的一種問題。所以它必須有一頁列著，
連理由一起列。

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

    pub, blk, dropped = [], [], []
    for p in sorted(events_dir.glob("*.md")):
        fm, _ = parse_note(p.read_text("utf-8"))
        item = {
            "id": fm.get("id"), "title": fm.get("title", fm.get("id")),
            "date": str(fm.get("date") or ""), "company": fm.get("company", ""),
            "category": fm.get("category") or "", "summary": fm.get("summary") or "",
            "confidence": fm.get("confidence", 0), "heat": fm.get("heat", 0),
            "blockers": fm.get("blockers") or [],
            "dropped_at": str(fm.get("dropped_at") or ""),
            "dropped_by": str(fm.get("dropped_by") or ""),
            "drop_reason": str(fm.get("drop_reason") or ""),
        }
        if fm.get("status") == "published":
            pub.append(item)
        elif fm.get("status") == "review":
            blk.append(item)
        elif fm.get("status") == "dropped":
            dropped.append(item)

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

    # dropped.md — 人工按掉的。理由整段照抄，不摘要：摘要過的理由日後看不出當初在想什麼。
    dropped.sort(key=lambda x: x["dropped_at"], reverse=True)
    dl = [f"# 人工判定不追（{len(dropped)}）", "",
          "> status: dropped。**這些不是被門禁擋下，是人看過之後決定不追。**",
          "> 檔案與證據都留著，只是不進門禁、不排潤稿、不上站。",
          "> 情況變了（例如出現第二個獨立來源）就把 status 改回 review，它會重新走一次門禁。", ""]
    for it in dropped:
        dl.append(f"## [[Events/{it['id']}|{it['title']}]]")
        dl.append(f"- {it['date']} · {it['company']} · {it['category']}")
        dl.append(f"- 按掉的人／機制：{it['dropped_by'] or '（未記錄）'}"
                  f"　時間：{it['dropped_at'] or '（未記錄）'}")
        dl.append(f"- 當時的 blockers：{', '.join(it['blockers']) or '（無）'}")
        dl.append(f"- 理由：{it['drop_reason'] or '**（未寫理由——沒寫理由的 drop 等於靜默丟棄，請補上）**'}")
        dl.append("")
    (dash / "dropped.md").write_text("\n".join(dl), encoding="utf-8")

    print(f"pulse-dashboard  published={len(pub)}  blocked={len(blk)}  dropped={len(dropped)}")
    print(f"  → {dash / 'published.md'}")
    print(f"  → {dash / 'blocked.md'}")
    print(f"  → {dash / 'dropped.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
