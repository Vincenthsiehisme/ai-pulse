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

**三個桶加起來必須等於掃到的檔案數。** 這支腳本用 if/elif 分桶，任何一個
status 落在三者之外的檔案就不屬於任何一頁——不報錯、不警告，只是不見。
2026-08-13 就這樣少算過一則：一個 frontmatter 被寫壞的 Event（少了 `---`
分隔線），`parse_note` 回空 dict、status 是 None，於是它從三張看板上一起消失，
而腳本印出來的是「published=101 blocked=29 dropped=1」——一個看起來完全正常
的句子。是因為當時剛好知道 dropped 應該是 2 才發現的。

所以最後多一道對帳：掃到幾個檔、分掉幾個，對不上就把漏掉的印出來並非零離開。
非零會讓 data-refresh 那條鏈停在這裡（同一個 `run:` 底下是 `bash -e`），
render 與 commit 都不會發生。那是刻意的：一個讀不進來的 Event 等於它在站上
與看板上同時消失，帶著這種狀態把當天的 101 篇發出去，正是這個 repo 一路在
寫事故報告的那件事。

用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-dashboard.py
依賴：PyYAML。
"""
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import parse_note  # noqa: E402

# 分桶認得的三個 status。改這裡等於改對帳的定義，不要順手加。
BUCKETS = ("published", "review", "dropped")


def unbucketed(rows):
    """rows = [(檔名, status)]。回傳沒有歸到任何一桶的，排序過。

    None 也算漏掉，而且是最重要的那一種：`parse_note` 讀不到 frontmatter 時
    回的是空 dict，`fm.get("status")` 就是 None。那不是「這個檔沒有狀態」，
    是「這個檔壞了」，兩件事在這裡必須長得一樣顯眼。
    """
    return sorted((n, s) for n, s in rows if s not in BUCKETS)


def drop_meta_line(item):
    """dropped.md 每則底下的第一行。空欄位直接不出現。

    原本是 f"- {date} · {company} · {category}"，而 dropped 的 category 常常
    是空的（人按掉它的理由往往就是「沒有一格裝得下」）——串出來的行尾就多一個
    空白，`git am` 每次都吠一句 trailing whitespace。那是雜訊，久了會蓋掉真的警告。
    """
    return "- " + " · ".join(x for x in (item["date"], item["company"], item["category"]) if x)


def main():
    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    dash = vault / "_dashboards"
    dash.mkdir(parents=True, exist_ok=True)

    pub, blk, dropped = [], [], []
    seen = []
    for p in sorted(events_dir.glob("*.md")):
        fm, _ = parse_note(p.read_text("utf-8"))
        seen.append((p.name, fm.get("status")))
        item = {
            "id": fm.get("id"), "title": fm.get("title", fm.get("id")),
            "date": str(fm.get("date") or ""), "company": fm.get("company", ""),
            "category": fm.get("category") or "", "summary": fm.get("summary") or "",
            # heat 可能是 None（一項傳播訊號都沒量到）。不給預設 0：
            # 「沒量」跟「量到 0」是兩件事，見 references/readiness-gate.md。
            "confidence": fm.get("confidence", 0), "heat": fm.get("heat"),
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
            heat_txt = "未量測" if it["heat"] is None else it["heat"]
            meta = f"{it['company']} · {it['category']} · conf {it['confidence']} · heat {heat_txt}"
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
        dl.append(drop_meta_line(it))
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

    # 對帳。三張看板已經寫完才檢查，是為了讓人能同時看到「產出長什麼樣」跟
    # 「哪一則不見了」；非零離開會擋住後面的 render 與 commit。
    missing = unbucketed(seen)
    if missing:
        print(f"[fatal] 掃到 {len(seen)} 個檔，只有 {len(pub) + len(blk) + len(dropped)} 個"
              f"進了看板。以下這些 status 不屬於 {'/'.join(BUCKETS)}：", file=sys.stderr)
        for name, st in missing:
            hint = "（frontmatter 讀不進來——多半是少了 --- 分隔線）" if st is None else ""
            print(f"  {name}  status={st!r} {hint}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
