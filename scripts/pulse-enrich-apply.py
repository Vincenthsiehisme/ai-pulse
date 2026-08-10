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


def strip_own_heading(heading, text):
    """剝掉值開頭那一行自己的段落標題。**這一層不信任輸入的形狀。**

    2026-08-10 實測的故障：潤稿端把 `## 事實` 寫進了 `fact` 的**值**裡（runbook 的
    schema 範例當時就是那樣寫的），而下面重組 body 時又加了一次自己的標題，於是
    檔案裡變成：

        ## 事實
        ## 事實
        NVIDIA 官方部落格報導，…

    `pulse-gate.section()` 取的是「這個標題到下一個 `##` 之間」，而下一個 `##`
    正好是那個重複的標題——**抽出來是 0 字**，低於 `thin_fact_min_chars`，
    於是每一則都掛 `thin_fact` 卡在 review。13 則裡 13 則中，零例外。

    更糟的是它**不會自癒**：那幾則的 `enriched` 已經是 true、佔位詞也沒了，
    下一班 prep 不會再挑它們。站上因此六天沒有新文章，而四個警報全綠。

    修在這裡而不是修 runbook，是因為 runbook 只是一份給人／模型讀的文件，
    而這一步是確定性那一層——**寫進檔案的形狀應該由碼決定，不由輸入決定**。
    runbook 的範例同一版也修了，但那是止血不是根治。

    兩種寫法都剝：整行只有標題（`## 事實`、`## 事實：`），或標題後面接了冒號
    再接內容（`## 事實：某某公司發表…`）——後者只剝前綴，內容留著。
    """
    t = (text or "").lstrip()
    for _ in range(3):          # 有界迴圈：重複貼兩次標題也剝得掉，不會無限轉
        m = re.match(rf"^#{{1,6}}\s*{re.escape(heading)}\s*[：:]?[ \t]*(?:\n|$)", t)
        if m:
            t = t[m.end():].lstrip("\n")
            continue
        m = re.match(rf"^#{{1,6}}\s*{re.escape(heading)}\s*[：:][ \t]*", t)
        if m:
            t = t[m.end():]
            continue
        break
    return t


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
        for heading, key in LAYER_ORDER:
            if key is None:
                continue
            # 先剝標題再過 voice_clean：剝掉的東西不算「後洗」，那是形狀不是用字。
            txt, ch = voice_clean.clean(strip_own_heading(heading, data.get(key, "")))
            cleaned[key] = txt
            ev_changes.extend(ch)
        summary_txt, sc = voice_clean.clean(data.get("summary", ""))
        ev_changes.extend(sc)

        # 判斷層 rule-tag **不再寫進 prose**。
        #
        # 這裡原本依當下的 `independent_sources` 把那句話烙進去，之後不再重算——
        # 而同一頁的警示框是 render 即時算的。第二個獨立來源進來之後兩者就分岔，
        # 實測 `evt-2026-07-21-1bdb1a` 在對外站上寫著「單一獨立來源」而
        # frontmatter 是 2。**判斷層不能有兩個時鐘。**
        # 現在由 `pulse-render.layer_html()` 即時產生，與警示框同一個真相源；
        # 舊 note 裡烙著的那一份由 render 的 `strip_frozen_tag()` 剝掉，不必遷移。
        cleaned["judgment"] = cleaned.get("judgment", "").rstrip()

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
