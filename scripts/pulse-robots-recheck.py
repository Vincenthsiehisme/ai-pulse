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

`--revive` 只動「當初被 robots 擋在門外、現在 robots 放行」的 dormant 來源，而且
只升到 `probing`（會被抓，但還沒通過 checklist）。人為停用的來源（robots 本來就 true
卻是 dormant）不碰——那是判斷，不是量測。

第二種資格是設定檔裡明示 `revive_when_allowed: true` 的來源：登記當下本機根本量不到
robots（robots_ok 寫 null），於是老實承認「等真網路環境給答案」。v2.4 開張的 KOL 線
有兩條是這樣進來的。判準是明示旗標而不是「robots_ok 是 null 就復活」——null 也可能
只是漏填，靠推論復活等於把漏填當成授權。

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

sys.path.insert(0, _HERE)
from lib.atomicwrite import atomic_write_with  # noqa: E402  見 references/atomic-writes.md
from lib.sources import SECTIONS  # noqa: E402  分節清單單一真相源，見 lib/sources.py


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
                "revive_opt_in": bool(src.get("revive_when_allowed")),
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
            if row["reason"] in ("unavailable_403", "unreachable", "error",
                                 "not_robots"):
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
        if r["verdict"] == "unknown_keep":
            # 不蓋 robots_checked_at。這一欄的意思是「最後一次**驗到**是什麼時候」，
            # 量測失敗蓋上去就是把失敗記成一次成功的驗證——紅線 8。
            # 而且它有後果：`--stale-days 7` 回來之後，check() 會拿這個時戳判 skip_fresh，
            # 於是一次 WAF 擋包可以讓這條來源接下來七天連試都不試，看起來還很正常。
            continue
        src["robots_checked_at"] = stamp
        if r["verdict"] in ("opened", "closed"):
            changes.append({"at": stamp, "id": r["id"], "field": "robots_ok",
                            "from": r["stored"], "to": r["now"],
                            "reason": "robots-recheck"})
            src["robots_ok"] = r["now"]
            # 入場券要跟著結論一起動（references/source-lifecycle.md）。
            # `false` 是唯一會被存成永久判決的值，所以設定檔規定它必須附
            # robots_evidence: "200+disallow"；而這張券只能出現在 false 上，
            # 否則就是拿舊證據替新結論背書。
            #
            # 機器一直沒寫它，不是因為手上沒有證據——`closed` 這個 verdict 的
            # 唯一入口就是 reason == "disallow"（200 且明文擋住）；unavailable_403
            # / unreachable / not_robots / error 全部在上面被攔成 unknown_keep，
            # 根本走不到這裡。所以這裡寫的是已經量到的事實，不是補一個好看的欄位。
            #
            # 2026-07-26 首班 CI 就是這樣把一筆沒有入場券的 false 寫進 sources.yaml
            # （src-media-theregister）。兩條 selftest 當場紅，但 CI 不跑 selftest，
            # 那一班仍是綠的——不變式只釘在人會走的路上，機器走的那條沒釘。
            if r["now"] is False:
                src["robots_evidence"] = "200+disallow"
            elif "robots_evidence" in src:
                del src["robots_evidence"]
        # 只復活「當初就是被 robots 擋在門外」的，且只升到 probing。
        # 兩種資格，共通點是**曾經明示登記過「我是被 robots 卡住的」**：
        #   stored is False          當初被判死（src-openai-blog 那類）
        #   revive_when_allowed      登記時本機就量不到 robots（robots_ok: null），
        #                            白紙黑字說明「等真網路環境給答案」。
        # 為什麼不直接看 robots_ok is None 就復活：null 也可能只是漏填。
        # 靠明示旗標而非推論 null，才守得住原本那條「人為停用的來源不碰」的意思。
        if (revive and r["verdict"] == "opened"
                and (r["stored"] is False or r["revive_opt_in"])
                and r["lifecycle"] == "dormant"):
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
    # tmp + os.replace()，不是直接開 "w"。直接開的話，寫到一半被砍留下的是一份
    # **合法但少了整段 *_sources: 的 YAML**——讀得起來、不報錯、被 commit 上去。
    # 規格與那次實測見 references/atomic-writes.md。
    atomic_write_with(path, lambda fh: y.dump(doc, fh))

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
