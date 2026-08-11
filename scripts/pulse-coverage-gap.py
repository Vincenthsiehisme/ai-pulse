#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-coverage-gap.py — 需求（答不了的問題）× 供給（來源能力）的對照矩陣。

規格見 references/vault-pages.md〈`_dashboards/coverage-gap.md`〉與
references/source-capabilities.md。改這裡之前先改那裡（紅線 9）。

## 它回答的那個問題

「我們看不到什麼」——而且要能指著一個名字說出來，不是一個模糊的感覺。

兩邊的軸是**同一份詞彙表**（`lib/sources.REASONS ⊃ CAPABILITIES`），所以
「這一類我答不了幾次」與「這一類有幾條來源在看」可以直接放在同一列比較。
PRD 原本給了兩份不同的清單（reason 11 個 / capability 14 個），那樣 join 出來
會有些列永遠對不到，而那不是量出來的洞，是詞彙表的洞。理由見規格。

## 分母是人給的，而今天它是 0

`_probe/signal-verdicts.jsonl` 現在 0 筆。需求那一欄**量不到**——不是 0。

這個差別是整支腳本最重要的一件事。一張把「還沒有人回答過」印成 0 的表，
會讓 `procurement`（0 需求、0 來源）看起來跟一個真的沒問題的格子一樣綠，
而它其實是這個系統最大的盲區之一。所以：

  - 樣本數 < `coverage_gap.min_answers` → **每一格都印「量不到」**，不給燈號
  - `other_ratio` 在量不到的時候是 `null`，不是 `0.0`

`0` 跟 `null` 在 JSON 裡差一個字，在判斷上差一個「我們知道」與「我們不知道」。

用法：`VAULT_DIR=... python scripts/pulse-coverage-gap.py --write [--quiet]`
不寫檔時印到 stdout。0 LLM、不碰網路、不呼叫 git。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import clock, history  # noqa: E402
from lib import sources as srcmod  # noqa: E402
from lib.atomicwrite import atomic_write_text  # noqa: E402

import yaml  # noqa: E402

LEDGER = ("_probe", "signal-verdicts.jsonl")
OUT_JSON = ("_probe", "coverage-gap.json")
OUT_PAGE = ("_dashboards", "coverage-gap.md")
F_VERDICT = "verdict"
F_REASON = "unanswerable_reason"

DEFAULTS = {"min_answers": 10, "amber_ratio": 1.0, "red_ratio": 3.0,
            "other_reason_warn": 0.3}


def thresholds(gate):
    """gate.yaml 的 `coverage_gap` 區塊。缺值走 DEFAULTS。

    壞掉的設定檔要讓規則變**嚴**不是變鬆（同 `lib/dictgaps.thresholds()`）：
    這裡的「嚴」是樣本門檻不降低——寧可多說幾天「量不到」，
    也不要因為一個打錯的 YAML 就開始拿 3 筆資料畫紅綠燈。
    """
    cfg = (gate or {}).get("coverage_gap") or {}
    out = {}
    for k, d in DEFAULTS.items():
        v = cfg.get(k, d)
        try:
            out[k] = type(d)(v)
        except (TypeError, ValueError):
            out[k] = d
    return out


def cell(demand, sources, measurable, th):
    """一列的燈號與說明。純函式，可離線單測。

    `measurable` 是整張表共用的：樣本不夠時**每一格**都是量不到，
    不是只有需求那一欄。因為燈號本身就是拿需求算出來的，
    需求量不到而燈號照亮，那個燈亮的是空氣。
    """
    if not measurable:
        return "－", "量不到"
    if sources == 0:
        return ("🔴", "沒有任何來源在看") if demand else ("⚪", "沒人問，也沒人看")
    if demand == 0:
        return "⚪", "這一輪沒有人問到這一類"
    ratio = demand / sources
    if ratio > th["red_ratio"]:
        return "🔴", f"需求是供給的 {ratio:.1f} 倍"
    if ratio > th["amber_ratio"]:
        return "🟡", f"需求是供給的 {ratio:.1f} 倍"
    return "🟢", "供給跟得上"


def other_line(other_n, unanswerable_n, th):
    """`other` 佔比那一行。回 (文字, 要不要提醒)。純函式。

    這份分類表是在 n=0 的情況下猜出來的。`other` 佔比高不代表填的人偷懶，
    代表**分類軸選錯了**——該回頭重看，而不是繼續往一個對不上真實問題的表裡塞。
    """
    if not unanswerable_n:
        return "`other` 佔比：**量不到**（還沒有 `unanswerable` 的裁決）", False
    r = other_n / unanswerable_n
    body = f"`other` 佔比：{other_n}/{unanswerable_n} = {r:.0%}"
    if r > th["other_reason_warn"]:
        return (body + f"，**超過門檻 {th['other_reason_warn']:.0%}**"
                "——分類軸可能選錯了。這份表是在 n=0 時猜出來的，"
                "`other` 就是它的死人開關；該回頭重看那 14 個值，"
                "而不是繼續往一個對不上真實問題的表裡塞"), True
    return body, False


def collect(vault):
    """→ (需求 Counter, 供給 {cap: [sid]}, 已裁決筆數, unanswerable 筆數)。純讀。"""
    rows = history.read(vault / LEDGER[0] / LEDGER[1])
    answered = sum(1 for r in rows if r.get("field") == F_VERDICT)
    unans = sum(1 for r in rows if r.get("field") == F_VERDICT
                and r.get("to") == "unanswerable")
    demand = Counter(str(r.get("to")) for r in rows if r.get("field") == F_REASON)
    raw = yaml.safe_load((vault / "_config" / "sources.yaml").read_text("utf-8")) or {}
    return demand, srcmod.capability_claims(raw), answered, unans


def render(demand, supply, answered, unans, today, th):
    """覆蓋率頁的 markdown。純函式，可離線單測。"""
    measurable = answered >= th["min_answers"]
    oline, obad = other_line(demand.get("other", 0), unans, th)
    out = [
        "---", f'generated_day: "{today}"', "---", "",
        "# 覆蓋缺口：我們看不到什麼", "",
        "> 由 `pulse-coverage-gap.py --write` 產生（零 LLM）。**手動編輯會在下一班被覆蓋。**",
        "",
        "左邊是**需求**（人回答 `unanswerable` 時填的原因碼），"
        "右邊是**供給**（`_config/sources.yaml` 裡會被抓的來源宣稱的能力）。",
        "兩邊用同一份詞彙表，所以可以放在同一列比較——理由見 "
        "`references/source-capabilities.md`。", "",
    ]
    if not measurable:
        out += [
            f"## ⚠ 這張表現在**量不到**（已裁決 {answered} 筆，門檻 "
            f"{th['min_answers']} 筆）", "",
            "需求那一欄是人給的，而現在還沒有人回答過足夠的訊號。",
            "**這不是「需求是 0」**——把「還沒有人回答」印成 0，"
            "會讓 `procurement`（0 需求、0 來源）看起來跟一個真的沒問題的格子一樣。",
            "",
            "供給那一欄現在就量得到，所以下面照印——**它本身已經是一份盲區清單**。",
            "",
            "要讓這張表活過來，走 `_dashboards/signal-review.md` 回答一批"
            f"（建議一次抽樣盤點而不是逐日累積，理由見執行計劃 P0-a）。", "",
        ]
    out += ["## 矩陣", "",
            "| 能力 | 需求（答不了幾次） | 供給（幾條來源） | 判斷 | 說明 |",
            "|---|---:|---:|:---:|---|"]
    keys = sorted(srcmod.CAPABILITIES,
                  key=lambda c: (-demand.get(c, 0), -len(supply.get(c, [])), c))
    for c in keys:
        d, s = demand.get(c, 0), len(supply.get(c, []))
        mark, why = cell(d, s, measurable, th)
        dtxt = str(d) if measurable else "－"
        out.append(f"| `{c}` | {dtxt} | {s} | {mark} | {why} |")
    out += ["", ("- ⚠ " if obad else "- ") + oline, ""]
    # other 不是能力，不進矩陣（沒有來源能宣稱「有能力報導其他」），
    # 但它的計數要看得見——不然一個「大部分都填 other」的狀態會完全隱形。
    zero = sorted(c for c in srcmod.CAPABILITIES if not supply.get(c))
    if zero:
        out += [f"**{len(zero)} 種能力沒有任何在跑的來源宣稱**："
                + "、".join(f"`{c}`" for c in zero),
                "", "這一格不需要等人回答就成立——它是今天就量得到的盲區。", ""]
    out += ["## 這張表要拿來做什麼", "",
            "決定下一波要補哪一類來源，而不是補幾條來源。",
            "PRD §20：Source Expansion 的完成條件是「有沒有補到新的觀測能力」，",
            "不是「新增來源數」。", "",
            "**但先讀 `docs/design/` 底下 2026-08-11 的 attach 實測**：",
            "補來源不會自動讓獨立佐證上升——第三方後續有 12/14 黏不上原事件，",
            "卡在標題相似度 0.46 那道閘。供給補起來之前，先確認接得上。", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    gate = yaml.safe_load((vault / "_config" / "gate.yaml").read_text("utf-8")) or {}
    th = thresholds(gate)
    demand, supply, answered, unans = collect(vault)
    today = clock.utc_today().isoformat()
    measurable = answered >= th["min_answers"]

    doc = {
        "generated_day": today,
        "answered": answered,
        "unanswerable": unans,
        # 量不到的時候是 null 不是 0。0 讀起來是「沒有人填 other」，
        # null 讀起來是「還沒有人填過任何東西」——下游要分得出來。
        "other_ratio": (demand.get("other", 0) / unans) if unans else None,
        "measurable": measurable,
        "min_answers": th["min_answers"],
        "demand": dict(demand),
        "sources": {c: sorted(v) for c, v in supply.items()},
        "unclaimed": sorted(c for c in srcmod.CAPABILITIES if not supply.get(c)),
    }
    page = render(demand, supply, answered, unans, today, th)
    if args.write:
        atomic_write_text(vault / OUT_JSON[0] / OUT_JSON[1],
                          json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        atomic_write_text(vault / OUT_PAGE[0] / OUT_PAGE[1], page)
        if not args.quiet:
            print(f"pulse-coverage-gap  已裁決 {answered}／unanswerable {unans}"
                  f"／{'可量' if measurable else '量不到'}"
                  f"／{len(doc['unclaimed'])} 種能力沒有來源")
        return 0
    print(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
