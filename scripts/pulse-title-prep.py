#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-title-prep.py — Event 標題中文化的前置（確定性，零 LLM）。

規格見 references/obsidian-schema.md〈Event 的標題有兩個〉。改這裡之前先改那裡
（紅線 9）。

背景：`Events/*.md` 的 `title` 是**來源的原始英文標題**，六層 prose 是中文、站台
框架是中文、只有標題不是。實測 2026-07-27：51 則 Event **全部** 51/51 是英文標題。

跟 `pulse-github-desc-prep.py` 同一個形狀，理由也一樣：**判斷誰要翻是規則的事，
翻成什麼字才是潤稿端的事。**

輸出：`_probe/title-zh-worklist.json`
離開碼：0＝正常（清單可能是空的，那是「今晚沒有東西要翻」）；
        2＝**量不到**（`Events/` 不在）。兩者必須分得出來——量不到的時候
        **不覆寫**既有清單，不寫一份空陣列。同一個坑 `github-desc-prep` 踩過。

用法：
  VAULT_DIR=... python scripts/pulse-title-prep.py
  VAULT_DIR=... python scripts/pulse-title-prep.py --limit 20   # 單晚成本封頂
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import zhtext  # noqa: E402

import yaml  # noqa: E402


def read_front(path: Path):
    text = path.read_text("utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return None      # 壞掉的一則不該讓整份清單產不出來


def pending(events):
    """→ 待譯清單。每一項只給潤稿端**翻譯需要的東西**，不給它判斷用的欄位。

    收進來的兩種：從來沒翻過、以及**原文變了譯文失效**。第二種是靠
    `title_zh_src` 對雜湊判出來的——少了它，標題哪天被改掉，畫面上會掛著一句
    在講舊標題的中文，而那比沒有中文糟得多。
    """
    todo = []
    for fm in events:
        title = (fm.get("title") or "").strip()
        if not title:
            continue
        entry = {"zh": fm.get("title_zh"), "src_hash": fm.get("title_zh_src")}
        if zhtext.valid_for(entry, title):
            continue
        todo.append({
            "id": fm.get("id"),
            "title": title,
            "company": fm.get("company"),
            "track": fm.get("track"),
            "summary": (fm.get("summary") or "")[:200],
            # 有值 ＝ 原文改過、舊譯文失效要重譯，不是新的一則。
            "stale_zh": fm.get("title_zh") if fm.get("title_zh") else None,
        })
    return todo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多列幾條（0＝不限）")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    outp = vault / "_probe" / "title-zh-worklist.json"
    if not events_dir.is_dir():
        print("[warn] 找不到 Events/——**不覆寫既有 worklist**"
              "（量不到 ≠ 沒有東西要翻）。", file=sys.stderr)
        return 2

    fms = [fm for fm in (read_front(p) for p in sorted(events_dir.glob("*.md"))) if fm]
    todo = pending(fms)
    n_all = len(todo)
    if args.limit:
        todo = todo[: args.limit]

    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(todo, ensure_ascii=False, indent=2), encoding="utf-8")

    n_stale = sum(1 for t in todo if t["stale_zh"])
    capped = (f"（共 {n_all} 條待譯，本次取前 {len(todo)}）"
              if args.limit and n_all > len(todo) else "")
    print(f"pulse-title-prep  Event {len(fms)} 則，待譯 {len(todo)} 條"
          f"（其中 {n_stale} 條是原文改了要重譯）{capped}"
          f"  → _probe/title-zh-worklist.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
