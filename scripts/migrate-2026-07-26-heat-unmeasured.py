#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性遷移：磁碟上既有 Event 的 heat 從「假數字」改成 null。

規格：references/readiness-gate.md 的「遷移與回滾」。背景：scoring.py 的 heat 有
四項傳播輸入（作者/推文/平台/地區）合計 63 分權重，在全部 Event 上恆為 0——不是
資料沒進來，是 pulse-cluster.py 呼叫時直接寫死 `metrics=[]`。剩下會動的只有獨立
來源數與新鮮度，於是「熱度」這個欄位量的是別的東西（紅線 8）。

scoring.py 現在在源頭回 None，但**磁碟上已經存在的 51 個 Event 不會自己更新**
（只有拿到新證據才會重新評分）。不遷移的話 vault 會一半新一半舊，而且新加的
`unmeasured_heat` blocker 會把那 51 個全部擋下來。

這支是**磁碟的純函式**：只用 frontmatter 裡已經有的 confidence / impact /
score_factors.freshness 重算，不重抓、不讀時鐘、不重新聚類。同一棵樹跑兩次
結果一樣（第二次是 no-op）。

改三件事：
  heat                              → null
  score_factors.propagationSignals  → 0（把「什麼都沒量到」寫成事實，不是要人推論）
  value                             → conf·0.40 + impact·0.40 + freshness·0.20

只碰 propagationSignals 為 0（或不存在）且四項傳播輸入確實全為 0 的 Event。
任何一項非零就跳過並報告——那代表社群線已經接上了，這支不該再動它。

回滾：`git revert` 那個 commit。Events/*.md 在版本控制裡，改的每個位元組都在 diff。

用法：
    VAULT_DIR=/path/to/AI-Pulse python3 scripts/migrate-2026-07-26-heat-unmeasured.py --dry-run
    VAULT_DIR=/path/to/AI-Pulse python3 scripts/migrate-2026-07-26-heat-unmeasured.py

合併後這支可以刪掉；留著是為了讓 diff 有出處。
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import dump_frontmatter, parse_note  # noqa: E402

PROPAGATION_KEYS = ("uniqueAuthors", "velocity", "platformBreadth", "regionBreadth")


def _clamp(v):
    """跟 lib/scoring._clamp 同一個定義。刻意重寫一次而不 import：
    這支是一次性腳本，未來 scoring.py 改了不該連帶改掉已經遷移完的結果。"""
    return max(0, min(100, int(round(v))))


def new_value(fm):
    conf = float(fm.get("confidence") or 0)
    impact = float(fm.get("impact") or 0)
    fresh = float((fm.get("score_factors") or {}).get("freshness") or 0)
    return _clamp(conf * 0.40 + impact * 0.40 + fresh * 0.20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    changed, skipped, noop = [], [], 0

    for p in sorted((vault / "Events").glob("*.md")):
        text = p.read_text("utf-8")
        fm, body = parse_note(text)
        if not fm:
            continue
        sf = fm.get("score_factors") or {}
        live = [k for k in PROPAGATION_KEYS if (sf.get(k) or 0)]
        if live:
            # 社群線接上了。這支不該覆蓋真的量到的東西。
            skipped.append((p.name, "有傳播訊號：" + ", ".join(live)))
            continue
        if fm.get("heat") is None and sf.get("propagationSignals") == 0:
            noop += 1
            continue
        if "score_factors" not in fm or "freshness" not in sf:
            # 算不出新的 value 就不要猜。少數幾筆用手改比亂寫一個數字好。
            skipped.append((p.name, "score_factors.freshness 缺席，算不出 value"))
            continue

        old_heat, old_value = fm.get("heat"), fm.get("value")
        fm["heat"] = None
        sf["propagationSignals"] = 0
        fm["score_factors"] = sf
        fm["value"] = new_value(fm)
        changed.append((p.name, old_heat, old_value, fm["value"]))
        if not args.dry_run:
            p.write_text(f"---\n{dump_frontmatter(fm)}\n---{body}", encoding="utf-8")

    tag = "[dry-run] " if args.dry_run else ""
    print(f"{tag}改了 {len(changed)}、已是新格式 {noop}、跳過 {len(skipped)}")
    if changed:
        deltas = [nv - (ov or 0) for _, _, ov, nv in changed]
        print(f"  value 變動：min {min(deltas):+d}  max {max(deltas):+d}  "
              f"平均 {sum(deltas) / len(deltas):+.2f}")
        for name, oh, ov, nv in changed[:5]:
            print(f"    {name}  heat {oh}→null  value {ov}→{nv}")
        if len(changed) > 5:
            print(f"    …另外 {len(changed) - 5} 筆")
    for name, why in skipped:
        print(f"  [跳過] {name}：{why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
