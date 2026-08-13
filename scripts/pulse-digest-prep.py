#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-digest-prep.py — 每日精選的確定性選材。規格：references/digest-framework.md。

挑出當天可用的材料、算出兩兩之間的圖距離、列出待回答的訊號，打包成 worklist
交給 Cowork 寫成一篇有主線的文章。**這一支不寫任何散文，也不決定要寫哪一條線。**

為什麼輸出的不是「今天最高分的 N 則」：
    實測過。8/12 那天 `value` 的排序是 71 / 71 / 69 / 68，而手寫那篇的骨幹
    是排最後那則（NVIDIA 融資）跟第三則（OpenAI 企業研究）——兩則在圖上不相連。
    `value` 量的是「這則證據有多硬」，不是「這則對讀者多重要」，
    它選不出頭條。所以這裡給的是**候選組合與它們的關係線索**，判斷留給人。

輸出：_probe/digest-worklist.json
用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-digest-prep.py [--date YYYY-MM-DD]
依賴：PyYAML。
"""
import argparse
import json
import os
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import clock  # noqa: E402  唯一一個可以取日期的地方，見 references/timezones.md
from lib.atomicwrite import atomic_write_text  # noqa: E402
from lib.notes import parse_note  # noqa: E402

# 「這一格是空的」在 frontmatter 裡有好幾種長相。**一定要一起處理。**
# 2026-08-13 算距離時踩過：`fingerprint: null` 用正則讀出來是字串 "null"，
# 於是兩則都沒有 fingerprint 的事件被判成「同一件事」，317 組配對裡
# 有 229 組（72%）是這樣來的假結果，而那個數字看起來完全合理。
_EMPTY = {"", "null", "none", "None", "~"}


def blank(v):
    """frontmatter 的值算不算空。YAML 的 null 會是 None，正則讀的會是 "null"。"""
    if v is None:
        return True
    return str(v).strip() in _EMPTY


def pair_distance(a, b):
    """兩則事件在關聯圖上的距離，回 (距離, 共用了什麼)。

    規格見 references/digest-framework.md〈選材〉。三檔的意思完全不同：

      1   同 fingerprint → **這根本是同一件事**，該合併成一段，不是寫成一篇
      2   同公司／主線／類別／來源／關鍵詞 → 同題材，併起來容易變成清單
      ≥4  沒有共同鄰居 → 是候選，不是障礙

    距離大不是缺點。實測 8/12 那篇的骨幹正好是一組 ≥4 的配對，
    而唯一一組距離 2 的（同主線）在文章裡最沒話講。
    """
    shared = []
    if not blank(a.get("fingerprint")) and a.get("fingerprint") == b.get("fingerprint"):
        return 1, ["同 fingerprint"]
    ac, bc = a.get("company"), b.get("company")
    if not blank(ac) and ac == bc and ac != "industry":
        shared.append(f"同公司：{ac}")
    if not blank(a.get("track")) and a.get("track") == b.get("track"):
        shared.append(f"同主線：{a['track']}")
    if not blank(a.get("category")) and a.get("category") == b.get("category"):
        shared.append(f"同類別：{a['category']}")
    src = sorted(set(a.get("source_ids") or []) & set(b.get("source_ids") or []))
    if src:
        shared.append("同來源：" + "、".join(src))
    kw = sorted(set(a.get("keywords") or []) & set(b.get("keywords") or []))
    if kw:
        shared.append("共用關鍵詞：" + "、".join(kw))
    return (2, shared) if shared else (4, [])


def all_within_distance_two(pairs):
    """整批素材是不是全部落在距離 2 以內。

    是的話多半是清單不是論證——「今天模型研究線有三則」不是一篇文章。
    這是**警訊不是退件**：真的有話講的同題材組合存在，只是少。
    只有一則時回 False：一則沒有配對，談不上「全部很近」。
    """
    if not pairs:
        return False
    return all(p["distance"] <= 2 for p in pairs)


def event_next_signal(e):
    """一則事件「當初說要看什麼」。**讀 body 的〈下一個訊號〉，不讀 frontmatter。**

    2026-08-13 實測：107 則已上線事件裡，frontmatter 的 `next_signal` 有值的是
    **0 則**，而 body 的〈下一個訊號〉有內容的是 **107 則**。那一格欄位存在、
    有消費者（就是這一支）、但從來沒有生產者——`references/source-capabilities.md`
    早就把它列為「欄位存在但沒有人填」的前例之一，只是沒有人回頭接線。

    不把兩邊同步起來，是因為同步就有兩份可能不一致的同一句話。潤稿層是人在維護的
    那一份，就以它為準（同樣的理由見 pulse-enrich-apply 為什麼不再把 rule-tag
    烙進 prose：判斷層不能有兩個時鐘）。frontmatter 那一格該接線或該刪，
    是另一個決定，不在這一支裡做。
    """
    return (e.get("layers") or {}).get("下一個訊號", "")


def pending_signals(events, today, min_age_days=3):
    """列出「我們說過要看什麼、而它還沒被證實」的事件。

    這是五種文章關係裡**唯一機器抓得到的一種**（兌現／落空）。
    規格見 digest-framework〈關係型別〉。

    **不在這裡比對今天的事件有沒有命中那個訊號。** 2026-08-13 實測過用
    實體＋時間窗做這種比對：107 則裡 81% 會命中，而命中的是「同公司不同事」
    （Grok Build Mode ↔ xAI 渦輪機訴訟）。一條 81% 開火而大多是錯的規則，
    會讓每一篇看起來都比實際上更有根據。所以只把清單攤開，命中與否由人認。
    """
    out = []
    for e in events:
        sig = event_next_signal(e)
        if blank(sig) or "待編輯" in sig:
            continue
        if (e.get("independent_sources") or 0) >= 2:
            continue          # 已經有第二個聲音了，不算「還沒兌現」
        age = _days_between(e.get("date"), today)
        if age is None or age < min_age_days:
            continue
        out.append({"id": e["id"], "title": e.get("title_zh") or e.get("title"),
                    "date": e.get("date"), "days_since": age,
                    "next_signal": sig})
    out.sort(key=lambda r: -r["days_since"])
    return out


def _days_between(d, today):
    try:
        a = datetime.strptime(str(d)[:10], "%Y-%m-%d")
        b = datetime.strptime(str(today)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    return (b - a).days


def pick_retrospective(events, featured, today):
    """空日取材：挑一則回頭看的事件。回 (事件, 用了哪條規則)；挑不到回 (None, 理由)。

    首選規則是「當初說要觀察 X、而 X 還沒發生」——它把空日變成
    「我們說過的話有沒有兌現」的日子，而不是隨便撈一則舊聞充版面。

    弱規則是「最高 value 且沒在任何一期出現過」。留著它是因為首選規則有可能挑不到
    ——例如所有還沒用過的事件都已經有第二個獨立來源了。
    **哪一條規則生效要寫進輸出**，不然讀的人分不出今天是哪一種空日。
    """
    fresh = [e for e in events if e["id"] not in featured]
    if not fresh:
        return None, "所有已上線事件都已經在某一期出現過"
    due = pending_signals(fresh, today)
    if due:
        by_id = {e["id"]: e for e in fresh}
        return by_id[due[0]["id"]], "pending_signal"
    ranked = sorted(fresh, key=lambda e: (-(e.get("value") or 0), e.get("date") or ""))
    return ranked[0], "highest_value_unfeatured"


def load_events(vault):
    out = []
    for p in sorted((vault / "Events").glob("*.md")):
        fm, body = parse_note(p.read_text("utf-8"))
        if fm.get("status") != "published":
            continue
        ev = fm.get("evidence") or []
        out.append({
            "id": fm.get("id"), "path": p.name,
            "title": fm.get("title"), "title_zh": fm.get("title_zh"),
            "date": str(fm.get("date") or ""), "company": fm.get("company"),
            "track": fm.get("track"), "category": fm.get("category"),
            "fingerprint": fm.get("fingerprint"), "facet": fm.get("facet"),
            "value": fm.get("value"), "confidence": fm.get("confidence"),
            "independent_sources": fm.get("independent_sources") or 0,
            "tier_evidence": fm.get("tier_evidence"),
            "keywords": list(fm.get("keywords") or []),
            "warnings": list(fm.get("warnings") or []),
            "summary": fm.get("summary") or "",
            # 不放 frontmatter 的 next_signal：那一格 0/107 有值，放進來就是假欄位。
            # 真的那一份在 layers["下一個訊號"]，見 event_next_signal()。
            "source_ids": [x.get("source_id") for x in ev if x.get("source_id")],
            "evidence": [{"source_id": x.get("source_id"), "url": x.get("url"),
                          "title": x.get("title")} for x in ev],
            "layers": {name: _section(body, name) for name in
                       ("事實", "脈絡", "影響", "判斷", "下一個訊號")},
        })
    return out


def _section(body, heading):
    import re
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body,
                  flags=re.M | re.S)
    return m.group(1).strip() if m else ""


def load_featured(vault):
    """已經在某一期用過的事件 id。Digests/ 還不存在時回空集合。"""
    out = set()
    d = vault / "Digests"
    if not d.exists():
        return out
    for p in d.glob("*.md"):
        fm, _ = parse_note(p.read_text("utf-8"))
        out.update(fm.get("sources") or [])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="預設為今天（UTC）")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    today = args.date or clock.utc_today().isoformat()
    events = load_events(vault)
    featured = load_featured(vault)

    items = [e for e in events if e["date"] == today]
    mode = "normal"
    retro_rule = None
    if not items:
        mode = "retrospective"
        pick, retro_rule = pick_retrospective(events, featured, today)
        items = [pick] if pick else []

    pairs = []
    for a, b in combinations(items, 2):
        dist, shared = pair_distance(a, b)
        pairs.append({"a": a["id"], "b": b["id"], "distance": dist, "shared": shared})

    work = {
        "date": today,
        "mode": mode,
        "retrospective_rule": retro_rule,
        "items": items,
        "pairs": pairs,
        # 警訊不是退件。整批都很近時提醒寫的人：這可能是清單不是論證。
        "all_within_distance_two": all_within_distance_two(pairs),
        "pending_signals": pending_signals(events, today),
        "already_featured": sorted(featured),
        "note": ("距離大不是缺點：實測 8/12 那篇的骨幹是一組距離 ≥4 的配對，"
                 "而唯一一組距離 2 的在文章裡最沒話講。"
                 "距離 1 代表同一件事、該合併成一段。"
                 "規格見 references/digest-framework.md。"),
    }

    out = vault / "_probe" / "digest-worklist.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(out, json.dumps(work, ensure_ascii=False, indent=2) + "\n")

    print(f"pulse-digest-prep  {today}  mode={mode}"
          + (f"（{retro_rule}）" if retro_rule else "")
          + f"  素材={len(items)} 則  配對={len(pairs)} 組")
    if work["all_within_distance_two"]:
        print("  [warn] 素材全部落在距離 2 以內——同題材併起來容易變成清單，"
              "寫之前先確認它們之間有沒有話要說")
    print(f"  待回答的訊號 {len(work['pending_signals'])} 則"
          + ("（`next_signal` 大多是空的，這個數字偏低是現況不是故障）"
             if len(work["pending_signals"]) < 3 else ""))
    print(f"  → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
