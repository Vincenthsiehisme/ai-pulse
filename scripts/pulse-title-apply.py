#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-title-apply.py — Event 標題中文譯文的寫回（確定性，零 LLM）。

規格見 references/obsidian-schema.md〈Event 的標題有兩個〉。

吃潤稿端產出的 `{"<event_id>": "中文標題", ...}`，逐條過 `lib/zhtext.validate`
（綁原文雜湊、真的有中文、長度封頂、AI 腔黑名單、voice_clean 後洗），寫進
`Events/<id>.md` 的 frontmatter：`title_zh` 與 `title_zh_src`。

**這一層不產生任何文字，只驗章與搬運。** 判準跟榜單描述共用同一支
（`lib/zhtext.py`），差別只有上限與退件訊息——那兩樣是版面決定的。

**不通過的不是靜靜丟掉，是印出來並列進退件清單。** 靜默丟棄是這個系統最危險的
失敗模式。

用法：
  VAULT_DIR=... python scripts/pulse-title-apply.py --in title-zh-result.json --dry-run
  VAULT_DIR=... python scripts/pulse-title-apply.py --in title-zh-result.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.atomicwrite import atomic_write_text  # noqa: E402
from lib import zhtext  # noqa: E402

import yaml  # noqa: E402

# 上限 40：Event 標題出現在卡片一行、時間軸一行、頁面大標。比榜單描述短，
# 因為它旁邊還要放原文——**中文在上、原文在下，兩行都要看得完**。
MAX_LEN = 40


def split_note(text: str):
    """→ (frontmatter dict, frontmatter 原始字串, body)。不是 note 就回 (None, ...)。"""
    if not text.startswith("---"):
        return None, "", text
    end = text.find("\n---", 3)
    if end < 0:
        return None, "", text
    try:
        fm = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return None, "", text
    return fm, text[3:end], text[end + 4:]


def rewrite(text: str, zh: str, src: str):
    """把 title_zh / title_zh_src 寫進 frontmatter，body 一個字不動。

    走 `sort_keys=False` 的 round-trip：`yaml.safe_load` 回的是保留文件順序的
    dict，所以既有欄位的順序不會被洗掉——**順序一變，每則 Event 的 diff 都會
    看起來像被整份改寫過**，真正的變化就埋掉了。
    """
    fm, _, body = split_note(text)
    if fm is None:
        return None
    fm["title_zh"] = zh
    fm["title_zh_src"] = zhtext.src_hash(src)
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                           default_flow_style=False).rstrip()
    return f"---\n{front}\n---{body}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    result = json.loads(Path(args.infile).read_text("utf-8"))
    if not isinstance(result, dict):
        print('[fatal] 結果檔必須是 {"<event_id>": "中文標題"} 的 dict', file=sys.stderr)
        return 2

    by_id = {}
    for p in sorted((vault / "Events").glob("*.md")):
        fm, _, _ = split_note(p.read_text("utf-8"))
        if fm and fm.get("id"):
            by_id[fm["id"]] = p

    ok, rejected = [], []
    print(f"pulse-title-apply  收到 {len(result)} 條譯文\n")
    for eid, raw in result.items():
        path = by_id.get(eid)
        src = ""
        if path is not None:
            fm, _, _ = split_note(path.read_text("utf-8"))
            src = (fm or {}).get("title") or ""
        zh, why, changes = zhtext.validate(
            raw, MAX_LEN, src_present=path is not None,
            len_note="（標題要跟原文並排，兩行都得看得完）",
            missing_note="找不到這個 event id（下次 prep 會重新排）")
        washed = ("；後洗：" + "、".join(f"{a}→{b}" for _, a, b in changes)) if changes else ""
        if why:
            rejected.append((eid, why, zh))
            print(f"  [退件] {eid}\n         {why}\n         「{zh}」{washed}")
            continue
        text = path.read_text("utf-8")
        before = (split_note(text)[0] or {}).get("title_zh")
        new = rewrite(text, zh, src)
        if new is None:
            rejected.append((eid, "frontmatter 解不開", zh))
            print(f"  [退件] {eid}\n         frontmatter 解不開")
            continue
        if not args.dry_run:
            atomic_write_text(path, new)
        ok.append(eid)
        print(f"  [{'重譯' if before else '新增'}] {eid}\n         「{zh}」{washed}\n"
              f"         原文：{src}")

    print(f"\n  寫入 {len(ok)} 則，退件 {len(rejected)} 則"
          + ("　[dry-run] 沒有動任何檔案" if args.dry_run else ""))
    # 退件不讓整班紅：翻譯是加分項。但要回非零讓呼叫端**看得到**，
    # 收尾摘要才寫得出「退了幾條、為什麼」。
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
