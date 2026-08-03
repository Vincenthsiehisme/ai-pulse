#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-narrative-apply.py — 把重寫後的 now/next 寫回 narratives.yaml（確定性後洗）。

- 只覆寫 result 指定主線的 now / next（thesis、lenses、其他主線一律不動）。
- **覆寫之前先把舊值 append 進 `_probe/narrative-history.jsonl`**（規格
  references/narrative-layer.md〈帳本〉）。now / next 是整段覆寫的，實測相鄰兩版
  有過只剩 10% 相同的——而在這一版之前，被改掉的那一段只活在 git history 裡，
  沒有任何一支腳本或任何一頁在讀它。這個系統因此答不出「我上週對這條線怎麼說」。
  同一個 repo 的來源層早就有帳本（`_probe/source-history.jsonl`），判斷層沒有。
- 每段過 lib.voice_clean（去中國用語、全形標點）——敘述的最後一道確定性防線。
- 每段過 lib.narrative_guard：vault 沒量到 heat 時，含量化熱度宣稱的欄位**拒收**
  （不自動改寫、不靜靜跳過），該班回非零。規格 references/narrative-layer.md。
- 更新 narratives.yaml 的 updated；把 prep 產的 signatures 轉存為 narrative-state.json
  （下次 prep 才知道這批已處理、不再重寫）。

result JSON 格式：{ "<track-slug>": { "now": "...", "next": "..." }, ... }
（也接受 "thesis"，但預設半夜只重寫 now/next。）

用法：VAULT_DIR=... python scripts/pulse-narrative-apply.py --in narrative-result.json [--dry-run]
依賴：PyYAML。
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import clock, history, narrative_guard, voice_clean  # noqa: E402
from lib.atomicwrite import atomic_write_text  # noqa: E402  見 references/atomic-writes.md

import yaml  # noqa: E402

HEADER = ("# narratives.yaml —— 每條主線的編輯性敘事層（thesis / now / next + 決策鏡）。\n"
          "# 這一層是「敘述/口吻」，是全系統唯一准 LLM 動手處：由排程 Cowork 任務（非 0-LLM 自動抓取鏈）\n"
          "# 依 speak-human-tw 重寫，且夾在兩道確定性關卡之間——prep 用事件簽章變化決定「哪條要重寫」（不由 LLM 判斷），\n"
          "# apply 過 voice_clean 機械清理、不新增語意。thesis、lenses 不由此流程動。\n")
FIELDS = ("now", "next", "thesis")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    narr_file = vault / "_config" / "narratives.yaml"
    if not narr_file.exists():
        print("[fatal] 無 _config/narratives.yaml", file=sys.stderr)
        return 2
    doc = yaml.safe_load(narr_file.read_text("utf-8")) or {}
    doc.setdefault("version", 1)
    tracks = doc.setdefault("tracks", {})

    # vault 裡有沒有量到的 heat，決定「熱度 8–14」這種句子是引用還是編造。
    # 現在（四項傳播輸入沒接線）全部是 None，所以擋；接上線之後這條自動放行。
    heat_measured = narrative_guard.vault_has_measured_heat(vault)

    result = json.loads(Path(args.infile).read_text("utf-8"))
    changed = 0
    total_clean = 0
    rejected = 0
    # 覆寫之前留痕。at 走 clock 不用裸 datetime.now()（見 references/timezones.md）。
    ledger = []
    stamp = clock.utc_now().isoformat()
    for slug, fields in result.items():
        if slug not in tracks:
            print(f"  [skip] narratives.yaml 無此主線：{slug}")
            continue
        touched = []
        for k in FIELDS:
            v = fields.get(k)
            if v is None or str(v).strip() == "":
                continue
            cleaned, ch = voice_clean.clean(str(v))
            if not heat_measured:
                hits = narrative_guard.find_heat_claims(cleaned)
                if hits:
                    # 不改寫：改寫等於這支腳本自己編一句話。拒收，交回給人。
                    rejected += 1
                    print(f"  [reject] {slug}.{k}：vault 沒量到 heat，這段卻引用了熱度數字"
                          f"——{'；'.join(hits)}", file=sys.stderr)
                    continue
            # 只有真的變了才記一筆。內容沒動也寫的話，帳本每晚多六筆「什麼都沒改」，
            # 而「這一期有幾條主線改過主張」會被稀釋成常數——又一個沒有鑑別力的指標。
            old_val = tracks[slug].get(k)
            if old_val != cleaned:
                ledger.append(history.change(stamp, slug, k, old_val, cleaned,
                                             "nightly-enrich"))
            tracks[slug][k] = cleaned
            total_clean += len(ch)
            touched.append(k)
        if touched:
            changed += 1
            print(f"  ● {slug}：更新 {', '.join(touched)}")

    # 不用 date.today()：它讀本機時區，同一次執行在台北跟在 Actions 上會蓋出
    # 不同的日期。見 references/timezones.md。
    doc["updated"] = clock.utc_today().isoformat()

    if args.dry_run:
        print(f"\n[dry-run] 會更新 {changed} 條主線、{total_clean} 處後洗、"
              f"拒收 {rejected} 段；帳本會記 {len(ledger)} 筆；未寫檔。")
        return 1 if rejected else 0

    body = yaml.dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
    # tmp + os.replace()。原本是裸 write_text：寫到一半被砍留下的是一份**合法但少了
    # 某幾條主線的 now / next / lenses 的 YAML**——讀得起來、不報錯、被 git add -A
    # commit 上去，而站上與 Tracks/*.md 照樣渲染，只是那幾條線從此沒有敘事。
    # 這個檔本來不在 references/atomic-writes.md 的表裡，這一版補進去了。
    atomic_write_text(narr_file, HEADER + body)

    # 帳本在 yaml 寫成之後才 append：反過來的話，yaml 那一步失敗會留下一筆
    # 「已經改了」的紀錄，而檔案裡還是舊的——帳本從此跟事實對不起來。
    # 兩個檔之間沒有交易，只能挑一個比較不傷的順序（同 lib/atomicwrite.py 的說明）。
    history.append(vault / "_probe" / "narrative-history.jsonl", ledger)

    sig_file = vault / "_probe" / "narrative-signatures.json"
    if sig_file.exists():
        (vault / "_probe" / "narrative-state.json").write_text(
            sig_file.read_text("utf-8"), encoding="utf-8")

    print(f"\n共更新 {changed} 條主線、{total_clean} 處機械後洗，"
          f"{len(ledger)} 筆舊值記入 _probe/narrative-history.jsonl。"
          f"已寫回 narratives.yaml（updated={doc['updated']}）。")
    if rejected:
        # 靜靜跳過等於一顆永遠綠的燈。拒收了就要讓那一班紅。
        print(f"[fail] 另有 {rejected} 段因量化熱度宣稱被拒收，未寫入。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
