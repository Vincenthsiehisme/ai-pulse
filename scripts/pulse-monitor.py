#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-monitor.py — 無人值守健康監看（純規則、零 LLM）。

無人值守最怕的不是出錯，是**靜默沒動**：昨晚 Cowork 跑在 Actions 前面、worklist 是空的，
整條鏈看起來一切正常，其實有事件卡在 review 沒人管。這支就是那個 dead-man's switch。

只讀不寫、不判斷該不該發（那是 gate 的事），只把「現在卡住什麼」算成數字：
  1. 資料新鮮度：最新 _corpus/<date>/ 是不是今天；最後一次 probe 幾天前
  2. 卡關佇列：status=review 的事件數、最久卡幾天、blocker 分佈
  3. 未 enrich：review 且 body 仍含「待编辑」的（＝ enrich 沒跑到）
  4. 敘事鮮度：_probe/narrative-state.json 的簽章數

用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-monitor.py            # 人看的報告
  VAULT_DIR=... python scripts/pulse-monitor.py --json                   # 機器讀
  VAULT_DIR=... python scripts/pulse-monitor.py --alert-days 2           # 卡超過 2 天 → exit 1
依賴：PyYAML。
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import parse_note  # noqa: E402

PLACEHOLDER = "待编辑"

# 這些 blocker 是「設計上就該永遠擋著」的（歷史存檔倒貨被新鮮度閘擋下），
# 不是漏跑、也修不好——算警報會天天狼來了，所以只計數、不觸警。
TERMINAL_BLOCKERS = {"stale_backfill"}


def _as_date(v):
    if not v:
        return None
    s = str(v).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def scan(vault, today):
    events = vault / "Events"
    review, published, unenriched = [], 0, 0
    blocker_hist = {}

    for p in sorted(events.glob("*.md")) if events.exists() else []:
        fm, body = parse_note(p.read_text("utf-8"))
        status = fm.get("status")
        if status == "published":
            published += 1
            continue
        if status != "review":
            continue
        d = _as_date(fm.get("happened_at")) or _as_date(fm.get("date"))
        age = (today - d).days if d else None
        blockers = list(fm.get("blockers") or [])
        for b in blockers:
            blocker_hist[b] = blocker_hist.get(b, 0) + 1
        if PLACEHOLDER in body:
            unenriched += 1
        # 只被 terminal blocker 擋著＝設計上的擋，不算「卡關待處理」
        terminal = bool(blockers) and set(blockers) <= TERMINAL_BLOCKERS
        review.append({
            "id": fm.get("id"),
            "file": p.name,
            "title": (fm.get("title") or "")[:70],
            "age_days": age,
            "blockers": blockers,
            "unenriched": PLACEHOLDER in body,
            "terminal": terminal,
        })

    # 資料新鮮度
    corpus = vault / "_corpus"
    days = sorted([d.name for d in corpus.iterdir() if d.is_dir()]) if corpus.exists() else []
    last_probe = _as_date(days[-1]) if days else None
    probe_lag = (today - last_probe).days if last_probe else None

    narr = vault / "_probe" / "narrative-state.json"
    tracks_tracked = len(json.loads(narr.read_text("utf-8"))) if narr.exists() else 0

    actionable = [e for e in review if not e["terminal"]]
    ages = [e["age_days"] for e in actionable if e["age_days"] is not None]
    # 「還沒 enrich 又放了幾天」＝ enrich 那條鏈根本沒跑到（不是門禁擋，是漏跑）
    stale_unenriched = [e["age_days"] for e in review
                        if e["unenriched"] and e["age_days"] is not None]
    return {
        "date": today.isoformat(),
        "last_probe_date": last_probe.isoformat() if last_probe else None,
        "probe_lag_days": probe_lag,
        "published_total": published,
        "review_total": len(review),
        "review_terminal": len(review) - len(actionable),
        "review_actionable": len(actionable),
        "review_unenriched": unenriched,
        "oldest_unenriched_days": max(stale_unenriched) if stale_unenriched else 0,
        "oldest_stuck_days": max(ages) if ages else 0,
        "blocker_hist": dict(sorted(blocker_hist.items(), key=lambda x: -x[1])),
        "tracks_tracked": tracks_tracked,
        "stuck": sorted(actionable, key=lambda e: -(e["age_days"] or 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="輸出 JSON（給機器 / 給排程摘要引用）")
    ap.add_argument("--alert-days", type=int, default=0,
                    help="待處理卡關最久天數 ≥ 此值 → exit 1（0＝不判警）")
    ap.add_argument("--alert-unenriched-days", type=int, default=0,
                    help="有事件未 enrich 且已放 ≥ 此天數 → exit 1（＝夜間 enrich 鏈漏跑的死人開關）")
    ap.add_argument("--top", type=int, default=5, help="人看報告列出幾則卡最久的")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    today = datetime.now(timezone.utc).date()
    r = scan(vault, today)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        lag = r["probe_lag_days"]
        lag_flag = "" if lag in (0, None) else ("  ⚠ 資料沒更新" if lag >= 2 else "  （昨天）")
        print(f"pulse-monitor  {r['date']}")
        print(f"  最後一次 probe: {r['last_probe_date']}（{lag} 天前）{lag_flag}")
        print(f"  已上線={r['published_total']}  review={r['review_total']}"
              f"（待處理={r['review_actionable']}／設計上擋著={r['review_terminal']}）"
              f"  未 enrich={r['review_unenriched']}  待處理最久={r['oldest_stuck_days']} 天")
        if r["blocker_hist"]:
            print("  ── blocker 分佈 ──")
            for b, n in r["blocker_hist"].items():
                print(f"    {n:3}  {b}")
        if r["stuck"]:
            print(f"  ── 待處理卡最久的 {min(args.top, len(r['stuck']))} 則 ──")
            for e in r["stuck"][:args.top]:
                mark = "未enrich" if e["unenriched"] else "已enrich"
                print(f"    [{e['age_days']}d/{mark}] {e['title']}")
                print(f"           {','.join(e['blockers']) or '(無 blocker 紀錄，gate 還沒跑過)'}")

    rc = 0
    if args.alert_unenriched_days and r["oldest_unenriched_days"] >= args.alert_unenriched_days:
        print(f"[alert] 有事件未 enrich 已放 {r['oldest_unenriched_days']} 天"
              f"（門檻 {args.alert_unenriched_days}）——夜間潤稿那條鏈可能沒跑到", file=sys.stderr)
        rc = 1
    if args.alert_days and r["oldest_stuck_days"] >= args.alert_days:
        print(f"[alert] 有事件卡在 review 已 {r['oldest_stuck_days']} 天（門檻 {args.alert_days}）",
              file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
