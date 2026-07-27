#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-dictionary-gaps.py — 跨天累積的字典補漏清單。

規格見 references/vault-pages.md〈`_dashboards/dictionary-gaps.md`〉。
改這裡之前先改那裡（紅線 9）。

為什麼要有這一支：`gate.yaml` 的 `clustering.unknown_entity` 從上線那天就寫著

    report_to: _dashboards/dictionary-gaps.md

**那個檔案不存在，也沒有任何一行碼會去產生它。** 字典缺口目前只出現在
`_probe/<日>/report.md` 的當班區塊裡——一天 12 班，每一班各自算各自的，
沒有任何地方把它們加起來。要發現「這個詞這週被講了 11 次」只能靠人翻語料。

寫進設定檔的那個路徑，於是變成一句「這件事有人在管」的宣稱，而實際上沒有。
跟 `references/evidence-tiers.md` 那次一樣：**用「文件（或設定檔）裡有一個路徑」
代理「那件事有產出」**，指路的人當天是誠實的，只是沒有任何一條測試會因為被指到
的檔案不存在而變紅。

門檻與判準不在這一支裡，在 `gate.yaml` 與 `lib/dictgaps.py`——`_probe` 的當班
區塊讀同一份。抄一份過去，兩邊會在有人調門檻的那天分岔。

不碰網路、不跑子行程。0 LLM。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md
from lib.atomicwrite import atomic_write_text  # noqa: E402
from lib import dictgaps  # noqa: E402

import yaml  # noqa: E402

DEFAULT_REPORT_TO = "_dashboards/dictionary-gaps.md"


def load_gate(vault: Path) -> dict:
    p = vault / "_config" / "gate.yaml"
    return (yaml.safe_load(p.read_text("utf-8")) or {}) if p.is_file() else {}


def report_path(vault: Path, gate: dict) -> Path:
    """`clustering.unknown_entity.report_to` 指到哪。**這一行就是那個 key 的消費者。**

    設定值一律當成 vault 內的相對路徑，而且解析後必須仍在 vault 裡——
    設定檔是走 PR 的，但一個能把檔案寫到 vault 外面的欄位不該存在。
    越界或空值就退回預設路徑，不是靜靜寫到別的地方去。
    """
    raw = str(((gate.get("clustering") or {}).get("unknown_entity") or {})
              .get("report_to") or DEFAULT_REPORT_TO).strip()
    candidate = (vault / raw).resolve()
    try:
        candidate.relative_to(vault.resolve())
    except ValueError:
        return (vault / DEFAULT_REPORT_TO).resolve()
    return candidate


def corpus_rows(vault: Path):
    """`_corpus/` 全部語料，**每個 (source_id, url_canonical) 只算一次**。

    `_corpus/<日>/` 是「當天看到的清單」不是「當天新增的清單」：一則還掛在 feed
    上的新聞，每天都會再被寫進當天的檔案一次。直接跨天累加，數到的是
    **項目 × 天**——`Sources/*.md` 的 `items_observed` 踩過同一個坑（實測 956 行
    對 461 個相異項目，虛胖一倍），寫在 references/vault-pages.md。

    去重之後這一頁的「次數」才跟當班區塊同單位，兩邊的數字才能一起讀。
    """
    seen: set[tuple] = set()
    root = vault / "_corpus"
    if not root.is_dir():
        return []
    out = []
    for day in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(day.glob("*.jsonl")):
            for line in f.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                key = (r.get("source_id"), r.get("url_canonical") or r.get("url"))
                if key in seen:
                    continue
                seen.add(key)
                out.append(r)
    return out


def corpus_days(vault: Path):
    root = vault / "_corpus"
    return sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def render(rows, days, min_hits, min_srcs, day: str, limit: int = 60) -> str:
    cnt, srcs = dictgaps.tally(rows)
    promoted = dictgaps.promoted(cnt, srcs, min_hits, min_srcs)
    single = dictgaps.single_source(cnt, srcs, min_hits)
    span = f"{days[0]} … {days[-1]}" if days else "（沒有語料）"
    lines = [
        "---",
        f"generated_day: '{day}'",
        "generator: scripts/pulse-dictionary-gaps.py",
        "---",
        "",
        "# 字典補漏候選（跨天累積）",
        "",
        f"語料範圍：**{len(days)} 天**（{span}），去重後 **{len(rows)}** 列。",
        f"晉升門檻：跨 ≥{min_srcs} 來源、≥{min_hits} 次"
        "（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`",
        "的當班區塊讀同一份）。",
        "",
        "**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞",
        "累積起來給人看。要不要收，是人的決定——收錄邊界見",
        "`_config/entities.yaml` 的 `meta`。",
        "",
        "## 達標候選",
        "",
        "| 候選 | 次數 | 來源數 |",
        "|---|---|---|",
    ]
    lines += [f"| {c} | {n} | {s} |" for c, n, s in promoted[:limit]] or \
             ["| （目前無達標候選） | | |"]
    lines += [
        "",
        "## 單來源高頻（觀察用，不列入晉升）",
        "",
        "冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，",
        "上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。",
        "這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，",
        "是一份觀察清單，不得直接寫進字典。",
        "",
        "| 候選 | 次數 | 唯一來源 |",
        "|---|---|---|",
    ]
    lines += [f"| {c} | {n} | {s} |" for c, n, s in single[:limit]] or \
             ["| （無） | | |"]
    lines += [
        "",
        "## 這一頁不保證什麼",
        "",
        "- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則",
        "  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。",
        "- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，",
        "  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。",
        "- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，",
        "  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。",
        "- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法",
        "  會分別計數，兩邊都可能因此構不到門檻。",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    gate = load_gate(vault)
    min_hits, min_srcs = dictgaps.thresholds(gate)
    rows = corpus_rows(vault)
    days = corpus_days(vault)
    day = clock.utc_today().isoformat()
    text = render(rows, days, min_hits, min_srcs, day)

    if args.dry_run:
        sys.stdout.write(text)
        return 0

    path = report_path(vault, gate)
    if path.is_file() and path.read_text("utf-8") == text:
        if not args.quiet:
            print("[skip] dictionary-gaps 內容沒變")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    if not args.quiet:
        print(f"[ok] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
