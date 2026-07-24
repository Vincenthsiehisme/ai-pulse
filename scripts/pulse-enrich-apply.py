#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-enrich-apply.py — Sprint 3c 寫回（確定性）：把 enrich 結果寫進 Event。

吃一份 enrich 結果 JSON（Cowork 依 enrich-runbook 產出），逐個 Event：
  - 每段 prose 過 voice_clean（中國用語 + 半形→全形，belt-and-suspenders）
  - 更新 frontmatter：company / category / track / keywords / summary / enriched: true
  - 重寫 body 六層（保留原「## 證據」連結區塊；「## 判斷」尾端加確定性 rule-tag）
  - 印「跳過確認、事後摘要」（每個 Event 的清理明細），供 git diff 回溯

紅線：不在此編造事實——prose 內容由 Cowork 依證據寫（見 enrich-runbook 的保真規則），
本層只做機械清理與寫回，不新增語意。
用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-enrich-apply.py --in enrich-result.json [--dry-run]
依賴：PyYAML。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import voice_clean  # noqa: E402
from lib.notes import dump_frontmatter, parse_note  # noqa: E402

LAYER_ORDER = [("事實", "fact"), ("證據", None), ("脈絡", "context"),
               ("影響", "impact"), ("判斷", "judgment"), ("下一個訊號", "next_signal")]


def extract_section(body, heading):
    """從 body 抽出「## <heading>」到下一個「## 」之間的內容。"""
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, flags=re.M | re.S)
    return m.group(1).strip() if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    result = json.loads(Path(args.infile).read_text("utf-8"))

    by_id = {}
    for p in events_dir.glob("*.md"):
        fm, _ = parse_note(p.read_text("utf-8"))
        if fm.get("id"):
            by_id[fm["id"]] = p

    total_changes = 0
    written = 0
    print(f"pulse-enrich-apply  收到 {len(result)} 個 Event 的 enrich 結果\n")
    for eid, data in result.items():
        p = by_id.get(eid)
        if p is None:
            print(f"  [skip] 找不到 Event {eid}")
            continue
        fm, body = parse_note(p.read_text("utf-8"))
        evidence_block = extract_section(body, "證據")

        # 每段 prose 過 voice_clean
        cleaned = {}
        ev_changes = []
        for _, key in LAYER_ORDER:
            if key is None:
                continue
            txt, ch = voice_clean.clean(data.get(key, ""))
            cleaned[key] = txt
            ev_changes.extend(ch)
        summary_txt, sc = voice_clean.clean(data.get("summary", ""))
        ev_changes.extend(sc)

        # 判斷層 rule-tag（確定性，依獨立來源數）
        ind = fm.get("independent_sources", 0) or 0
        tag = "（單一獨立來源，暫標待證實）" if ind < 2 else "（多來源佐證）"
        cleaned["judgment"] = (cleaned.get("judgment", "").rstrip() + " " + tag).strip()

        # frontmatter 更新
        for f in ("company", "category", "track"):
            if data.get(f) is not None:
                fm[f] = data[f]
        if data.get("keywords"):
            fm["keywords"] = data["keywords"]
        fm["summary"] = summary_txt
        fm["enriched"] = True

        # 重組 body
        parts = []
        for heading, key in LAYER_ORDER:
            if key is None:
                parts.append(f"## {heading}\n{evidence_block}")
            else:
                parts.append(f"## {heading}\n{cleaned.get(key, '').strip()}")
        new_body = "\n\n".join(parts) + "\n"
        new_text = f"---\n{dump_frontmatter(fm)}\n---\n\n{new_body}"

        # 事後摘要
        print(f"  ● {eid}  ({p.name})")
        print(f"    company={fm.get('company')} category={fm.get('category')} track={fm.get('track')}")
        if ev_changes:
            uniq = {}
            for typ, a, b in ev_changes:
                uniq[(typ, a, b)] = uniq.get((typ, a, b), 0) + 1
            print("    後洗:", "; ".join(f"{a}→{b}" for (typ, a, b) in uniq))
            total_changes += len(ev_changes)
        else:
            print("    後洗: 無殘留")

        if not args.dry_run:
            p.write_text(new_text, encoding="utf-8")
            written += 1

    print(f"\n共 {total_changes} 處機械後洗。", end=" ")
    if args.dry_run:
        print("[dry-run] 未寫檔")
    else:
        print(f"寫入 {written} 個 Event。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
