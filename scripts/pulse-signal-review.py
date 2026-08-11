#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-signal-review.py — 「我上次說要看什麼，結果呢」的待回答清單與裁決帳本。

規格見 references/vault-pages.md〈`_dashboards/signal-review.md`〉與
docs/design/2026-08-11-theme-tracking-revisited.md。改這裡之前先改那裡（紅線 9）。

## 為什麼是這一支，而不是「把 next_signal 結構化」

原本的 P1 規劃是「把 `next_signal` 從散文變成結構化欄位，讓機器自動核對」。
2026-08-11 實測之後那個規劃有兩個錯誤：

1. **`next_signal` 這個 frontmatter 欄位早就存在，而且 0/86 被填過。**
   有內容的一直是 body 的「## 下一個訊號」那一段散文。所以問題從來不是
   「要不要加欄位」。
2. **填了之後沒有東西能回答它。** 86 則的下一個訊號裡約六成以「看…」開頭
   ——它們是寫給人的觀察指示，不是機器可判定的命題，而且指向的多半是
   benchmark 數字、出貨時程、第三方採購行為這類**這條抓取鏈看不到的世界**。

用系統自己的數字說同一件事：那 86 則裡 **81 則（94%）到今天仍然只有一個
獨立來源**。連最機械、系統本來就在算的那種後續（第二個彼此無關的來源講同一
件事）都只發生在 6% 的事件上。瓶頸不在資料結構，在觀測範圍。

所以這一支**不自動判定任何事**。它做的是把該問的問題整理出來、讓人回答、
把答案記成帳本。累積幾期之後，那份帳本會回答一個現在只能用猜的問題：
**哪些 next_signal 是可回答的、哪些永遠等不到答案。** 那才是決定要不要真的
做自動核對的依據。

## 兩個模式

    --write                產生 `_dashboards/signal-review.md`（待回答清單）
    --answer <sid> --verdict <happened|not-yet|unanswerable> [--note ...]
                           append 一筆進 `_probe/signal-verdicts.jsonl`

已經回答過的不再列進清單——這一頁是**待辦**不是歷史，歷史在帳本裡。

## sid 怎麼來

`<來源鍵>#<內容雜湊前 8 碼>`。綁內容而不是綁流水號的理由跟
`lib/zhtext.py` 的 `src_hash()` 一樣：那段話被改寫過就是**另一個問題**，
舊答案不該繼續掛在上面。改寫後它會以新的 sid 重新排進待答清單。

這一支不碰網路、不呼叫 git、不跑子行程，只讀 vault。0 LLM。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import clock, history  # noqa: E402
from lib.sources import REASONS  # noqa: E402  原因碼＝能力詞彙表＋other，單一真相源
from lib.atomicwrite import atomic_write_text  # noqa: E402

import yaml  # noqa: E402

VERDICTS = ("happened", "not-yet", "unanswerable")
# 一次裁決寫**兩筆**，不是一筆塞兩件事。
#   field="verdict"             to=happened / not-yet / unanswerable
#   field="unanswerable_reason" to=<原因碼>            （只有 unanswerable 才有）
# 兩筆的理由：`lib/history.read()` 本來就吃 `field=` 過濾，覆蓋率矩陣要的是
# 「原因碼的分佈」，用 field 分開之後那是一次過濾就拿得到的東西。
# 把兩件事塞進同一筆（例如 to="unanswerable:enterprise_adoption"）的話，
# 下游每個消費者都要自己 split 一次，而 split 規則會在第二個消費者那裡分岔。
F_VERDICT = "verdict"
F_REASON = "unanswerable_reason"
LEDGER = ("_probe", "signal-verdicts.jsonl")
PAGE = ("_dashboards", "signal-review.md")
SECTION = "下一個訊號"


def sid(key: str, text: str) -> str:
    """穩定 id ＝ 來源鍵 ＋ 內容雜湊。內容改了就是另一個問題，見模組 docstring。"""
    h = hashlib.sha1((text or "").strip().encode("utf-8")).hexdigest()[:8]
    return f"{key}#{h}"


def section(body: str, heading: str = SECTION) -> str:
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body,
                  flags=re.M | re.S)
    return m.group(1).strip() if m else ""


def _split(text: str):
    end = text.find("\n---", 3)
    if not text.startswith("---") or end < 0:
        return {}, text
    return (yaml.safe_load(text[3:end]) or {}), text[end + 4:]


def collect(vault: Path):
    """→ [(sid, 種類, 出處, 那句話)]，依出處排序。純讀，不寫任何檔。

    兩個來源：主線層的 `next`（`_config/narratives.yaml`）與事件層的
    「## 下一個訊號」。**兩層都收**，因為它們回答的是不同尺度的問題——
    主線那句問的是「這條線接下來看什麼」，事件那句問的是「這一則後續如何」。
    只收其中一層的話，報告寫得出趨勢卻對不回具體事件，或者反過來。
    """
    out = []
    nf = vault / "_config" / "narratives.yaml"
    if nf.exists():
        doc = yaml.safe_load(nf.read_text("utf-8")) or {}
        for slug, t in (doc.get("tracks") or {}).items():
            nxt = str((t or {}).get("next") or "").strip()
            if nxt:
                out.append((sid(slug, nxt), "主線", slug, nxt))
    for p in sorted((vault / "Events").glob("*.md")):
        fm, body = _split(p.read_text("utf-8"))
        if fm.get("status") != "published":
            continue
        txt = section(body)
        # 「待編輯」佔位還在＝這則沒潤過，那不是一個待回答的問題，是待潤稿。
        # 混進來的話，這一頁會變成「未 enrich 清單」的副本，而那個清單已經有了。
        if not txt or "待編輯" in txt:
            continue
        out.append((sid(str(fm.get("id")), txt), "事件", str(fm.get("id")), txt))
    return out


def pending(vault: Path):
    """待回答的 ＝ 全部 − 帳本裡已經有裁決的。"""
    answered = {r["id"] for r in history.read(vault / LEDGER[0] / LEDGER[1],
                                              field=F_VERDICT)}
    return [row for row in collect(vault) if row[0] not in answered]


def render(rows, today, answered_n):
    """待回答清單的 markdown。純函式，可離線單測。"""
    head = [
        "---",
        f'generated_day: "{today}"',
        "---",
        "",
        "# 待回答：我上次說要看什麼，結果呢",
        "",
        "> 由 `pulse-signal-review.py --write` 產生（零 LLM）。**手動編輯會在下一班被覆蓋。**",
        "> 這一頁是**待辦**不是歷史——回答過的會從這裡消失，答案在 "
        "`_probe/signal-verdicts.jsonl`。",
        "",
        "**這一頁不判定任何事。** 它只是把該問的問題整理出來讓人回答。"
        "為什麼不自動判定，見 `docs/design/2026-08-11-theme-tracking-revisited.md`。",
        "",
        f"待回答 **{len(rows)}** 則／已裁決 **{answered_n}** 則。",
        "",
        "回答方式：",
        "",
        "```",
        "python scripts/pulse-signal-review.py --answer <sid> \\",
        "    --verdict happened|not-yet|unanswerable \\",
        "    --reason <原因碼，只有 unanswerable 要> --note \"一句話\"",
        "```",
        "",
        "`unanswerable` 不是失敗，是**這一頁最有價值的那個答案**：它累積出來的清單，",
        "就是「這個系統的觀測範圍看不到哪些東西」。",
        "",
    ]
    if not rows:
        head += ["目前沒有待回答的訊號。", ""]
        return "\n".join(head)
    for kind in ("主線", "事件"):
        sub = [r for r in rows if r[1] == kind]
        if not sub:
            continue
        head += [f"## {kind}層（{len(sub)}）", ""]
        for s, _k, src, txt in sub:
            head += [f"- **`{s}`** — {src}", f"  > {txt}", ""]
    return "\n".join(head)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--answer")
    ap.add_argument("--verdict", choices=VERDICTS)
    ap.add_argument("--reason", help="unanswerable 的原因碼（lib/sources.REASONS）")
    ap.add_argument("--note", default="")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    led = vault / LEDGER[0] / LEDGER[1]

    if args.answer:
        if not args.verdict:
            print("[fatal] --answer 要配 --verdict", file=sys.stderr)
            return 2
        # unanswerable 沒有原因碼＝一筆「這個系統看不到它」但沒說看不到哪一類。
        # 那正是整條線最有價值的那個資料點，缺了它這一筆只剩下一個計數。
        if args.verdict == "unanswerable" and not args.reason:
            print("[fatal] --verdict unanswerable 要配 --reason，可選："
                  + "、".join(sorted(REASONS)), file=sys.stderr)
            return 2
        if args.reason and args.reason not in REASONS:
            print(f"[fatal] 不認得的 reason：{args.reason}（可選："
                  + "、".join(sorted(REASONS)) + "）", file=sys.stderr)
            return 2
        # other 是這份分類表的死人開關（表是在 n=0 時猜出來的）。沒有 note 的
        # other 會進分母把比例撐大，卻沒留下任何能拿來重新分類的線索。
        if args.reason == "other" and not args.note.strip():
            print("[fatal] --reason other 要配 --note：分類表是猜出來的，"
                  "`other` 是它的死人開關，而一筆沒有說明的 other 什麼都告訴不了我們",
                  file=sys.stderr)
            return 2
        if args.reason and args.verdict != "unanswerable":
            print(f"[fatal] --reason 只用在 unanswerable（這一筆是 {args.verdict}）"
                  "——happened / not-yet 記了原因碼會進覆蓋率矩陣的分子，"
                  "而那張表問的是「答不了的有哪些」", file=sys.stderr)
            return 2
        known = {row[0] for row in collect(vault)}
        # 打錯一個字就記一筆對不到任何問題的裁決，而那筆會永遠留在帳本裡
        # 當成雜訊——帳本是 append-only，記錯了刪不掉。
        if args.answer not in known:
            print(f"[fatal] 找不到這個 sid：{args.answer}", file=sys.stderr)
            return 2
        at = clock.utc_now().isoformat()
        rows = [history.change(at, args.answer, F_VERDICT,
                               None, args.verdict, args.note or "human-review")]
        if args.reason:
            rows.append(history.change(at, args.answer, F_REASON,
                                       None, args.reason, args.note or "human-review"))
        history.append(led, rows)
        print(f"記錄：{args.answer} → {args.verdict}"
              + (f"（{args.reason}）" if args.reason else ""))
        return 0

    rows = pending(vault)
    # 只數 verdict 那一種，而且只數**現值**。兩筆制之後 `len(read(led))` 會把每一筆
    # unanswerable 算成兩則（一個會隨著「答不了的比例」自己浮動的分母）；
    # 而只過濾 field 還不夠——同一則改過答案會再多算一次（見 lib/history.latest）。
    answered = len(history.latest(history.read(led), F_VERDICT))
    if args.write:
        atomic_write_text(vault / PAGE[0] / PAGE[1],
                          render(rows, clock.utc_today().isoformat(), answered))
        if not args.quiet:
            print(f"pulse-signal-review  待回答 {len(rows)}／已裁決 {answered}")
            print(f"  → {vault / PAGE[0] / PAGE[1]}")
        return 0
    print(f"待回答 {len(rows)}／已裁決 {answered}")
    for s, k, src, txt in rows[:10]:
        print(f"  [{k}] {s}  {txt[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
