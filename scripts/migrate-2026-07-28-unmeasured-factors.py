#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把既有 note 裡「從未量測卻存成 0」的傳播因子改成 null。一次性。

**為什麼光改 render 不夠**：那四個因子不是 render 算的，是存在每一份 note 的
`score_factors` frontmatter 裡。而 `pulse-cluster.main()` 只寫 `dirty` 的 event
（`changed = [e for e in events if e.dirty]`），一則沒有新證據進來的已發布事件
**永遠不會被重寫**。實測 56 份 note 烙著 `uniqueAuthors: 0`。

這一課這個 repo 前一天才上過：coverage 那一層第一版也是只改了計算端，
既有 Event 一則都沒長到那個欄位，而當時的計數器還回報「52 有變」。
**改了產生器不等於改了已經產出的東西。**

判準只有一條，而且它已經存在資料裡：`propagationSignals` 記的是「四項傳播輸入
裡有幾項真的量到東西」。

    propagationSignals == 0  →  那四項＋crossRegion 全部是「沒量過」→ null
    propagationSignals  > 0  →  真的量到了，0 就是 0 →  不動

所以這支**不猜**：它只把「資料自己說沒量過」的那些改成 null。

用法：
    VAULT_DIR=. python3 scripts/migrate-2026-07-28-unmeasured-factors.py           # dry-run
    VAULT_DIR=. python3 scripts/migrate-2026-07-28-unmeasured-factors.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import notes  # noqa: E402

# 五格全部由 metrics 衍生。crossRegion 一起改：`regions >= 2` 在沒量測時是 False，
# 而 False 讀起來是「確定不跨區」——同一隻病，換成布林。
UNMEASURED_KEYS = ("uniqueAuthors", "platformBreadth", "regionBreadth",
                   "velocity", "crossRegion")


def plan(vault: Path):
    """→ [(path, {key: 舊值}), …]，只含真的要改的。"""
    out = []
    for path in sorted((vault / "Events").glob("*.md")):
        fm, body = notes.parse_note(path.read_text("utf-8"))
        sf = (fm or {}).get("score_factors")
        if not isinstance(sf, dict):
            continue
        # 這一格不在就跳過：舊到沒有 propagationSignals 的 note，我們無從判斷
        # 它是「沒量過」還是「量到 0」，**而猜就是編造**。
        if sf.get("propagationSignals") is None:
            continue
        if sf["propagationSignals"] != 0:
            continue
        touched = {k: sf[k] for k in UNMEASURED_KEYS
                   if k in sf and sf[k] is not None}
        if touched:
            out.append((path, touched))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    vault = Path(os.environ.get("VAULT_DIR", "."))

    todo = plan(vault)
    print(f"要改的 note：{len(todo)}")
    for path, touched in todo[:5]:
        print(f"  {path.name}  {touched}")
    if len(todo) > 5:
        print(f"  …其餘 {len(todo) - 5} 份同形")
    if not args.apply:
        print("\ndry-run。加 --apply 才會寫檔。")
        return 0

    for path, _ in todo:
        text = path.read_text("utf-8")
        fm, body = notes.parse_note(text)
        for k in UNMEASURED_KEYS:
            if k in fm["score_factors"]:
                fm["score_factors"][k] = None
        # `dump_frontmatter()` **不含 `---` 圍欄**——`parse_note()` 把它們吃掉了，
        # 兩支不是對稱的。第一版寫成 `dump_frontmatter(fm) + body`，56 份 note
        # 的 frontmatter 圍欄當場消失，`pulse-render` 下一秒印 `published=0`。
        # 前一支遷移（migrate-2026-07-27-evidence-titles.py:147）一直是對的，
        # 我沒去看它就自己寫了一個。
        path.write_text(f"---\n{notes.dump_frontmatter(fm)}\n---{body}",
                        encoding="utf-8")
    print(f"\n已寫入 {len(todo)} 份。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
