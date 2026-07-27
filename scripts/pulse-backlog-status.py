#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-backlog-status.py — 每班重新生成 `_dashboards/backlog-status.md`。

規格見 references/vault-pages.md〈`_dashboards/backlog-status.md`〉。
改這裡之前先改那裡（紅線 9）。

為什麼要有這一支：`BACKLOG.md` 的〈現況〉表以前是**人手寫的**。
2026-07-27 那一版在寫下之後 **3 小時**就過期了——四條分支被合併，
表上的 `main` commit、selftest 數、變異數、可刪分支數同時全部作廢。

那已經是同一種病的第 9 個實例（`BACKLOG.md` 的〈已經修掉的〉底下有清單）：
**用一張量過的表代理現況**。上一版的「修法」是把量測時間寫進標題、請下一個人
複量——那本身是一個**靠人記得**的機制，而這份清單存在的理由就是不要有那種機制。

所以照這個 repo 一貫的分法辦：**量測是機械的，判斷是人寫的。**
數字搬到這一頁、每班重生成；`BACKLOG.md` 只留判斷（哪一條重要、壞了會不會紅、
現在有沒有在騙人），一個手寫數字都不留。

刻意**不**放的兩格：selftest 條數與變異結果。
它們不是每班量得到的事實——跑一次要幾十秒到幾分鐘，而且各自已經有自己的
workflow 在紅綠。放上來只會得到一個「上次不知道什麼時候量的」數字，
**而這一頁存在的理由就是不要有那種數字**。它們留在
`BACKLOG.md`〈附：怎麼重新盤點這份清單〉的指令裡，由人在需要時跑。

這一支不碰網路、不呼叫 git、不跑子行程，只讀 vault。0 LLM。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.atomicwrite import atomic_write_text  # noqa: E402
from lib.sources import SECTIONS  # noqa: E402
from lib import gate_keys  # noqa: E402

import yaml  # noqa: E402

PAGE = ("_dashboards", "backlog-status.md")
UNMEASURED = "量不到"


def _read(path: Path):
    return path.read_text("utf-8") if path.is_file() else None


def events_facts(vault: Path) -> dict:
    """Events/ 的狀態分佈。數的是檔案，不是 frontmatter 解析——status 那一行
    是機器寫的、格式固定，整份 YAML parse 51 次沒有換到任何準確度。
    """
    out = Counter()
    stale = 0
    files = sorted((vault / "Events").glob("*.md")) if (vault / "Events").is_dir() else []
    for p in files:
        text = p.read_text("utf-8")
        for line in text.splitlines():
            if line.startswith("status: "):
                out[line[8:].strip()] += 1
                break
        if "stale_backfill" in text:
            stale += 1
    return {"total": len(files), "by_status": dict(out), "stale_backfill": stale}


def corpus_facts(vault: Path) -> dict:
    d = vault / "_corpus"
    days = sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []
    return {"days": len(days), "first": days[0] if days else None,
            "last": days[-1] if days else None}


def source_facts(vault: Path) -> dict:
    raw = yaml.safe_load(_read(vault / "_config" / "sources.yaml") or "") or {}
    life, langs, total = Counter(), Counter(), 0
    for key in SECTIONS:
        for s in raw.get(key) or []:
            if not isinstance(s, dict) or str(s.get("id", "")).endswith("<slug>"):
                continue
            total += 1
            life[str(s.get("lifecycle") or "（未填）")] += 1
            langs[str(s.get("language") or "（未填）")] += 1
    watch = (raw.get("coverage_watch") or {}).get("must_watch") or []
    return {"total": total, "lifecycle": dict(life), "language": dict(langs),
            "watch_total": len(watch),
            "watch_pending": sum(1 for w in watch if isinstance(w, dict) and w.get("pending"))}


def gate_facts(vault: Path) -> dict:
    text = _read(vault / "_config" / "gate.yaml")
    if text is None:
        return {}
    leaves = gate_keys.parse(text)
    return {"leaves": len(leaves),
            "unwired": sum(1 for e in leaves if e["unwired"]),
            "wired": sum(1 for e in leaves if not e["unwired"] and e["consumers"])}


def last_run_facts(vault: Path) -> dict:
    """最後一班的來源狀態。零產出（200 但 0 筆）另外列——那一格是
    references/health-alarms.md〈零產出不是沉默〉在管的東西。
    """
    p = vault / "_probe" / "source-runs.jsonl"
    if not p.is_file():
        return {}
    last = None
    for line in p.read_text("utf-8").splitlines():
        if line.strip():
            last = line
    if not last:
        return {}
    rec = json.loads(last)
    srcs = rec.get("sources") or []
    return {"at": rec.get("at"), "day": rec.get("day"),
            "items": sum(s.get("items") or 0 for s in srcs),
            "sources": len(srcs),
            "status": dict(Counter(str(s.get("status")) for s in srcs)),
            "zero_yield": sorted(s["id"] for s in srcs
                                 if s.get("status") == 200 and not s.get("items"))}


def collect(vault: Path) -> dict:
    return {"events": events_facts(vault), "corpus": corpus_facts(vault),
            "sources": source_facts(vault), "gate": gate_facts(vault),
            "last_run": last_run_facts(vault)}


def _n(v):
    """缺席印「量不到」而不是 0（紅線 8）。0 是量到 0，None 是沒量到。"""
    return UNMEASURED if v is None else str(v)


def render(facts: dict, day: str) -> str:
    ev, co = facts["events"], facts["corpus"]
    sr, ga, lr = facts["sources"], facts["gate"], facts["last_run"]
    by = ev.get("by_status") or {}
    lines = [
        "---",
        f"generated_day: '{day}'",
        "generator: scripts/pulse-backlog-status.py",
        "---",
        "",
        "# 現況（機器量的）",
        "",
        "這一頁**每班重新生成**，`BACKLOG.md` 不再手寫任何數字。",
        "理由與規格見 `references/vault-pages.md`；為什麼非這樣不可，見",
        "`BACKLOG.md` 的實例清單第 9 條——上一版的手寫表在寫下之後 3 小時就過期了。",
        "",
        "**這一頁只有量測，沒有判斷。** 哪一條重要、壞了會不會變紅、現在有沒有在",
        "騙人——那些在 `BACKLOG.md`，那裡一個手寫數字都不留。",
        "",
        "## Events",
        "",
        "| 量到什麼 | 值 |",
        "|---|---|",
        f"| 總數 | {_n(ev.get('total'))} |",
        f"| `published` | {_n(by.get('published', 0))} |",
        f"| `review` | {_n(by.get('review', 0))} |",
        f"| `dropped` | {_n(by.get('dropped', 0))} |",
        f"| 帶 `stale_backfill` | {_n(ev.get('stale_backfill'))} |",
        "",
        "## 語料",
        "",
        "| 量到什麼 | 值 |",
        "|---|---|",
        f"| `_corpus/` 天數 | {_n(co.get('days'))} |",
        f"| 起訖 | {co.get('first') or UNMEASURED} … {co.get('last') or UNMEASURED} |",
        "",
        "## 來源",
        "",
        "| 量到什麼 | 值 |",
        "|---|---|",
        f"| 來源總數 | {_n(sr.get('total'))} |",
        f"| lifecycle 分佈 | {_kv(sr.get('lifecycle'))} |",
        f"| language 分佈 | {_kv(sr.get('language'))} |",
        f"| `coverage_watch.must_watch` | {_n(sr.get('watch_total'))} 條，"
        f"其中 {_n(sr.get('watch_pending'))} 條 `pending` |",
        "",
        "## `gate.yaml` 接線",
        "",
        "| 量到什麼 | 值 |",
        "|---|---|",
        f"| leaf key 總數 | {_n(ga.get('leaves'))} |",
        f"| 標成 ⚠ 未接線 | {_n(ga.get('unwired'))} |",
        f"| 有指名消費者 | {_n(ga.get('wired'))} |",
        "",
        "判準在 `scripts/lib/gate_keys.py`，它**不保證**什麼寫在",
        "`references/gate-config-status.md` 最後一節。",
        "",
        "## 最後一班 probe",
        "",
        "| 量到什麼 | 值 |",
        "|---|---|",
        f"| 時間 | {lr.get('at') or UNMEASURED} |",
        f"| 條目 / 來源 | {_n(lr.get('items'))} items / {_n(lr.get('sources'))} sources |",
        f"| status 分佈 | {_kv(lr.get('status'))} |",
        f"| 零產出（200 但 0 筆） | {', '.join(lr.get('zero_yield') or []) or '（無）'} |",
        "",
        "零產出那一格屬於哪一種 0，看那一天的 `_probe/<日>/report.md`",
        "〈零產出診斷〉——**這一頁不重算它**，重算就會有兩份判準。",
        "",
        "## 這一頁刻意沒有的兩格",
        "",
        "**selftest 條數**與**變異結果**不在這裡。它們不是每班量得到的事實：",
        "跑一次要幾十秒到幾分鐘，而且各自已經有自己的 workflow 在紅綠。",
        "放上來只會得到一個「上次不知道什麼時候量的」數字，",
        "**而這一頁存在的理由就是不要有那種數字**。",
        "",
        "要那兩個數字就自己跑，指令在 `BACKLOG.md`〈附：怎麼重新盤點這份清單〉：",
        "",
        "```bash",
        "python3 scripts/selftest.py | tail -1     # 有幾條測試",
        "python3 scripts/mutate.py                 # 有幾格守不住",
        "```",
        "",
        "`main` 的 commit 也不在這裡：這一頁自己就住在 repo 裡，",
        "它是哪一版產生的，`git log` 比任何自我宣稱都準。",
        "",
    ]
    return "\n".join(lines)


def _kv(d):
    if not d:
        return UNMEASURED
    return "、".join(f"{k} {v}" for k, v in sorted(d.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    day = datetime.now(timezone.utc).date().isoformat()
    text = render(collect(vault), day)
    path = vault / PAGE[0] / PAGE[1]

    if args.dry_run:
        sys.stdout.write(text)
        return 0
    # 內容沒變就不重寫：一天 12 班，每班一個沒有資訊量的 diff 會把真正的變化埋掉
    #（references/vault-pages.md 的共同規則）。
    if _read(path) == text:
        if not args.quiet:
            print("[skip] backlog-status 內容沒變")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    if not args.quiet:
        print(f"[ok] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
