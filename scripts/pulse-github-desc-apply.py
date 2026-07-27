#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-github-desc-apply.py — 星速榜中文描述的寫回（確定性，零 LLM）。

吃潤稿端產出的 `{"<owner/repo>": "中文描述", ...}`，逐條過機械檢查與 voice_clean，
寫進 `_github/desc-zh.json`，並就地補進 `dist/data/github.json`（免得為了一句翻譯
再打一次 GitHub API）。

**這一層不產生任何文字，只驗章與搬運。** 檢查全部是機械的、可測的、無語意判斷的：

  1. 對得上原文     譯文必須綁在「當下這句英文」上。潤稿端拿到 worklist 之後上游
                    如果改了描述，就讓它落榜重譯——寧可空著，不可掛一句在講舊版本的中文。
  2. 真的有中文     一個 CJK 字都沒有 ＝ 英文原樣貼回來，這不叫翻譯。擋掉。
  3. 長度封頂       榜是一行字的版面，超過就不是描述是段落。預設 60 字。
  4. 罩詞黑名單     「值得關注」「無限可能」「隨著…的發展」這類 AI 腔套話，一律退回。
                    speak-human-tw 的規則寫在潤稿端，這裡只兜零容忍的那幾個底。
  5. voice_clean    中國用語 + 半形標點，跟 enrich 走同一支後洗。

不通過的不是靜靜丟掉，是**印出來並列進退件清單**。靜默丟棄是這個系統最危險的失敗模式。

用法：
  VAULT_DIR=... python scripts/pulse-github-desc-apply.py --in github-desc-result.json --dry-run
  VAULT_DIR=... python scripts/pulse-github-desc-apply.py --in github-desc-result.json
依賴：無（voice_clean 是本地模組）。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ghdesc, zhtext  # noqa: E402

MAX_LEN = 60

# 判準（黑名單、CJK 檢查、後洗）搬到 lib/zhtext.py：2026-07-27 起 Event 標題也走
# 同一套。抄第二份會在有人往黑名單加一個字的那天分岔，而且不會有任何東西變紅。
# 上限留在這裡，因為它是**版面**決定的不是語言決定的——榜是一行字。


def validate(full_name, raw, src_desc):
    """→ (清理後的中文, 退件原因, 後洗紀錄)。過關時原因為 None。"""
    return zhtext.validate(
        raw, MAX_LEN, src_present=src_desc is not None,
        len_note="（榜是一行字的版面）",
        missing_note="不在目前榜單上（榜換過了，下次 prep 會再排進來）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--board", default="dist/data/github.json")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    board_path = vault / args.board
    board = json.loads(board_path.read_text("utf-8")) if board_path.exists() else {"repos": []}
    repos = board.get("repos") or []
    src_by_name = {r.get("full_name"): (r.get("desc") or "") for r in repos}

    result = json.loads(Path(args.infile).read_text("utf-8"))
    if not isinstance(result, dict):
        print("[fatal] 結果檔必須是 {\"owner/repo\": \"中文描述\"} 的 dict", file=sys.stderr)
        return 2

    store = ghdesc.load(vault)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ok, rejected = [], []

    print(f"pulse-github-desc-apply  收到 {len(result)} 條譯文\n")
    for full_name, raw in result.items():
        src = src_by_name.get(full_name)
        zh, why, changes = validate(full_name, raw, src)
        washed = ("；後洗：" + "、".join(f"{a}→{b}" for _, a, b in changes)) if changes else ""
        if why:
            rejected.append((full_name, why, zh))
            print(f"  [退件] {full_name}\n         {why}\n         「{zh}」{washed}")
            continue
        before = store.get(full_name, {}).get("zh")
        store[full_name] = {"zh": zh, "src_hash": ghdesc.src_hash(src), "at": stamp}
        ok.append(full_name)
        tag = "重譯" if before else "新增"
        print(f"  [{tag}] {full_name}\n         「{zh}」{washed}")

    ghdesc.attach(repos, store)
    n_zh = sum(1 for r in repos if r.get("desc_zh"))

    print(f"\n  過關 {len(ok)}／退件 {len(rejected)}；"
          f"榜上中文覆蓋 {n_zh}/{len(repos)}")
    if rejected:
        print("  退件的不會靜靜消失——下次 prep 會原樣排回待譯清單。")

    if args.dry_run:
        print("  [dry-run] 未寫入 _github/desc-zh.json，也未動 github.json")
        return 0

    ghdesc.save(vault, store)
    board["repos"] = repos
    board_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  已寫入 _github/desc-zh.json 並就地更新 dist/data/github.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
