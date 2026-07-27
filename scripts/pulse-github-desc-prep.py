#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-github-desc-prep.py — 星速榜中文描述的前置（確定性，零 LLM）。

掃 `dist/data/github.json` 現在的榜單，挑出「還沒有有效中文描述」的 repo，打包成
worklist 交潤稿端翻寫。跟 enrich-prep 同一個形狀：判斷誰要翻是規則的事，翻成什麼字
才是潤稿端的事。

有效＝存過、非空、且 src_hash 對得上當下的英文原文。上游改了 description，舊譯文自動
失效並重新排進來——榜上掛著一句在講舊版本的漂亮中文，比整條空著糟得多。

輸出：_probe/github-desc-worklist.json
用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-github-desc-prep.py
  VAULT_DIR=... python scripts/pulse-github-desc-prep.py --limit 15   # 單晚成本封頂
依賴：無（只讀 JSON）。

離開碼：0＝正常（清單可能是空的，那是「今晚沒有東西要翻」）；
        2＝**量不到**（`dist/data/github.json` 不在，榜單這一班沒生出來）。
        兩者必須分得出來：舊版在量不到的時候寫一份空清單，於是下游看到的 `[]`
        同時代表兩件事，而它會照著跳過、沒有人知道為什麼。
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ghdesc  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多列幾條（0＝不限）")
    ap.add_argument("--board", default="dist/data/github.json")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    board = vault / args.board
    outp = vault / "_probe" / "github-desc-worklist.json"
    doc = json.loads(board.read_text("utf-8")) if board.exists() else None
    # `measured: False` 是 pulse-github.py 在抓取全失敗時留下的佔位檔。
    # 不看這一格的話，那份 0 條的榜單會被讀成「今晚沒有東西要翻」——
    # 而那正是這條翻譯鏈停擺幾十班沒人發現的形狀。
    if doc is None or doc.get("measured") is False:
        # **量不到就不要覆寫**（紅線 8）。舊版在這裡寫一份空清單，於是
        # 「榜單這一班沒生出來」跟「今晚沒有東西要翻」在磁碟上長得一模一樣——
        # 而下游（潤稿端）只看得到那個 []，它會照著跳過，然後沒有人知道為什麼。
        # 現在改成不動既有清單、非零離開，讓叫它的那一步自己決定要不要在意。
        # 「這一班到底有沒有量到」另有專門的一格：_github/desc-coverage.json
        #（見 references/vault-pages.md〈榜單的中文描述〉）。
        why = "找不到" if doc is None else "榜單標著 measured: false（那一班沒抓到）"
        print(f"[warn] {args.board} {why}——先跑 pulse-github.py。"
              f"**不覆寫既有 worklist**（量不到 ≠ 沒有東西要翻）。", file=sys.stderr)
        return 2
    repos = (doc or {}).get("repos") or []

    todo = ghdesc.pending(repos, ghdesc.load(vault))
    n_all = len(todo)
    if args.limit:
        todo = todo[: args.limit]

    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(todo, ensure_ascii=False, indent=2), encoding="utf-8")

    n_stale = sum(1 for t in todo if t["stale_zh"])
    capped = f"（榜上共 {n_all} 條待譯，本次取前 {len(todo)}）" if args.limit and n_all > len(todo) else ""
    print(f"pulse-github-desc-prep  榜單 {len(repos)} 條，待譯 {len(todo)} 條"
          f"（其中 {n_stale} 條是上游改了描述要重譯）{capped}"
          f"  → _probe/github-desc-worklist.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
