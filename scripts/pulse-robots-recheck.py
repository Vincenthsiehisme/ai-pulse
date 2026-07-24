#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-robots-recheck.py — 把 robots_ok 從「一次寫死的歷史判決」改回「有時效的快取」。

為什麼要有這支：2026-07-24 漏掉 Claude Opus 5 之後回頭查，發現 `src-openai-blog`
掛著 `robots_ok: false`、`lifecycle: dormant`，但 openai.com/robots.txt 其實是
`Allow: /`。也就是說一次假陰性的判定被當成永久事實寫進設定檔，整條 OpenAI 線
就這樣被靜靜關掉，而且**沒有任何機制會去重驗它**。

單獨把那一行改成 true 是治標。根因是：判定沒有時效、降級沒有紀錄。
這支負責兩件事，兩件都是純規則、零 LLM：

  1. 對每條有 URL endpoint 的來源重跑一次 robots 判定，跟設定檔裡存的值比對。
     用的是 pulse-probe 自己那支 robots_verdict（同一個 User-Agent，同一套狀態碼慣例）
     ——重驗必須跟實際抓取用同一把尺，否則量出來的東西沒有意義。
     但只有 `disallow`（200 且明文擋住）才會被寫成 robots_ok: false。401/403/5xx
     一律歸 unknown_keep：**抓不到不等於不准抓**，量測失敗不該偽裝成站方政策。
     這條規則本身就是這次事故的補丁——少了它，這支腳本會在今晚重演同一個錯誤。
  2. 每次變動都往 `_probe/source-history.jsonl` append 一筆。來源怎麼從能跑變成
     不能跑的，要留得下痕跡。

用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-robots-recheck.py           # 只看，不改
  VAULT_DIR=... python scripts/pulse-robots-recheck.py --apply                 # 寫回 robots_ok + 檢查時間
  VAULT_DIR=... python scripts/pulse-robots-recheck.py --apply --revive        # 併：因 robots 被關掉且現已放行的 dormant → probing
  VAULT_DIR=... python scripts/pulse-robots-recheck.py --stale-days 30         # 只重驗超過 30 天沒驗過的
  VAULT_DIR=... python scripts/pulse-robots-recheck.py --json

`--revive` 只動「當初因 robots 被判 false、現在 robots 放行」的 dormant 來源，而且
只升到 `probing`（會被抓，但還沒通過 checklist）。人為停用的來源（robots 本來就 true
卻是 dormant）不碰——那是判斷，不是量測。

寫回用 ruamel.yaml round-trip，sources.yaml 的註解是文件的一部分，不能被 dump 洗掉。
依賴：ruamel.yaml（只有 --apply 需要）。
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location(
    "pulse_probe", os.path.join(_HERE, "pulse-probe.py"))
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)

SECTIONS = ("official_sources", "kol_sources", "aggregator_sources")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _age_days(stamp):
    if not stamp:
        return None
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).days


def check(doc, stale_days=0):
    """→ [每條來源的重驗結果]。只讀，不改 doc。"""
    out = []
    for section in SECTIONS:
        for src in doc.get(section) or []:
            endpoint = src.get("endpoint")
            row = {
                "section": section,
                "id": src.get("id"),
                "lifecycle": src.get("lifecycle"),
                "stored": src.get("robots_ok"),
                "checked_at": src.get("robots_checked_at"),
                "age_days": _age_days(src.get("robots_checked_at")),
                "now": None,
                "reason": None,
                "verdict": None,
            }
            # endpoint 不是 URL 的（github-releases 是 owner/repo）沒有 robots 可驗。
            if not endpoint or not str(endpoint).startswith(("http://", "https://")):
                row["verdict"] = "skip_no_url"
                out.append(row)
                continue
            if stale_days and row["age_days"] is not None and row["age_days"] < stale_days:
                row["verdict"] = "skip_fresh"
                out.append(row)
                continue
            try:
                row["now"], row["reason"] = _probe.robots_verdict(endpoint)
            except Exception as e:  # noqa: BLE001
                row["now"] = None
                row["verdict"] = f"error:{type(e).__name__}"
                out.append(row)
                continue
            if row["reason"] in ("unavailable_403", "unreachable", "error"):
                # 拿不到 robots.txt＝量測失敗，不是站方政策。
                # 這正是當初殺掉 src-openai-blog 的那一刀：一次 403 被存成永久判決。
                # 抓取端照樣保守跳過（robots_allows 仍回 False），但這裡不准寫回設定檔。
                row["verdict"] = "unknown_keep"
            elif row["now"] == row["stored"]:
                row["verdict"] = "unchanged"
            elif row["now"] is True:
                row["verdict"] = "opened"    # 之前擋著、現在放行 → 可能是假陰性
            else:
                row["verdict"] = "closed"    # 200 且明文 Disallow → 這才真的要停
            out.append(row)
    return out


def apply_changes(doc, rows, revive=False):
    """把重驗結果寫回 doc（ruamel 的 round-trip 物件），回傳異動紀錄。"""
    index = {}
    for section in SECTIONS:
        for src in doc.get(section) or []:
            index[src.get("id")] = src

    changes = []
    stamp = _now()
    for r in rows:
        if r["verdict"] in ("skip_no_url", "skip_fresh") or r["verdict"].startswith("error:"):
            continue
        src = index.get(r["id"])
        if src is None:
            continue
        src["robots_checked_at"] = stamp
        if r["verdict"] == "unknown_keep":
            continue
        if r["verdict"] in ("opened", "closed"):
            changes.append({"at": stamp, "id": r["id"], "field": "robots_ok",
                            "from": r["stored"], "to": r["now"],
                            "reason": "robots-recheck"})
            src["robots_ok"] = r["now"]
        # 只復活「當初就是被 robots 判死」的，且只升到 probing。
        if (revive and r["verdict"] == "opened"
                and r["stored"] is False and r["lifecycle"] == "dormant"):
            changes.append({"at": stamp, "id": r["id"], "field": "lifecycle",
                            "from": "dormant", "to": "probing",
                            "reason": "robots-reopened"})
            src["lifecycle"] = "probing"
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="寫回 sources.yaml（預設只看不改）")
    ap.add_argument("--revive", action="store_true",
                    help="併同把「因 robots 被關、現已放行」的 dormant 升為 probing")
    ap.add_argument("--stale-days", type=int, default=0,
                    help="只重驗上次檢查超過 N 天的（0＝全驗）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    path = vault / "_config" / "sources.yaml"

    if args.apply:
        try:
            from ruamel.yaml import YAML
        except ImportError:
            print("[fatal] --apply 需要 ruamel.yaml（保留 sources.yaml 的註解）："
                  "pip install ruamel.yaml", file=sys.stderr)
            return 2
        y = YAML()
        y.preserve_quotes = True
        y.width = 4096
        doc = y.load(path.read_text("utf-8"))
    else:
        import yaml as _pyyaml
        doc = _pyyaml.safe_load(path.read_text("utf-8"))

    rows = check(doc, stale_days=args.stale_days)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(f"pulse-robots-recheck  {_now()}")
        order = {"opened": 0, "closed": 1, "unknown_keep": 2, "unchanged": 3}
        for r in sorted(rows, key=lambda r: (order.get(r["verdict"], 4), r["id"])):
            mark = {"opened": "↑ 現已放行", "closed": "↓ 明文擋住",
                    "unknown_keep": "? 量不到，保留原值",
                    "unchanged": "  一致"}.get(r["verdict"], f"  {r['verdict']}")
            age = "從未檢查" if r["age_days"] is None else f"{r['age_days']}d 前驗過"
            print(f"  {mark:<22} {r['id']:<26} 存={r['stored']!s:<5} 實={r['now']!s:<5} "
                  f"{str(r['reason'] or '-'):<16} {r['lifecycle']:<8} ({age})")
        n_open = sum(1 for r in rows if r["verdict"] == "opened")
        n_close = sum(1 for r in rows if r["verdict"] == "closed")
        print(f"  ── 放行 {n_open}／收緊 {n_close}／共驗 "
              f"{sum(1 for r in rows if r['verdict'] not in ('skip_no_url', 'skip_fresh'))} 條")

    if not args.apply:
        if any(r["verdict"] in ("opened", "closed") for r in rows):
            print("  （加 --apply 才會寫回；--revive 併同把被 robots 誤殺的來源升回 probing）")
        return 0

    changes = apply_changes(doc, rows, revive=args.revive)
    y.dump(doc, path.open("w", encoding="utf-8"))

    hist = vault / "_probe" / "source-history.jsonl"
    hist.parent.mkdir(parents=True, exist_ok=True)
    with hist.open("a", encoding="utf-8") as f:
        for c in changes:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  已寫回 sources.yaml；{len(changes)} 筆異動記入 _probe/source-history.jsonl")
    for c in changes:
        print(f"    {c['id']}: {c['field']} {c['from']} → {c['to']}（{c['reason']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
