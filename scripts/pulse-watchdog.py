#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-watchdog.py — 鏈外的死人開關。

規格見 references/health-alarms.md〈鏈外的那一個〉。改這裡之前先改那裡（紅線 9）。

## 為什麼要有一支「在鏈外面」的

2026-08-09：`main` 從 08-05 到 08-09 沒有進過任何資料，而**四個警報全綠**。

原因不是判準寫錯。`--alert-stale`、`--alert-unenriched-days`、
`--alert-enrich-stale`、`health.md` 的 `generated_day`——四個判準都對，
但它們**全部長在 `data-refresh.yml` 最後兩個 step 上**。那一班卡在部署環境的
閘門、job 一個 step 都沒開始，於是警報也沒開始。

這是這個 repo 一路在修的形狀的極端版：08-05 那次是「推不上去的那一邊沒辦法
通報自己推不上去」，補法是把判準搬到推得上去的那一邊；這次是
**「沒被排上的鏈沒辦法通報自己沒被排上」**，補法只能是**另一條排程**。

事故紀錄：`references/incidents/2026-08-09-the-gate-that-stopped-the-chain.md`。

## 它刻意跟被監看的那條鏈保持距離

- **另一支 workflow、另一個 concurrency group、另一個時間。** 這是重點。
  同一支 workflow 裡加一個 step 完全沒用——job 沒開始，step 也不會開始。
- **不 import 任何 pipeline 模組**，只用 `lib.clock`（取日期的唯一入口，
  紅線；抄第二份日期邏輯是這個 repo 量過很多次的病）。
  `pulse-monitor.py` 若哪天語法壞掉，這一支照樣跑得起來。
- **只讀 git log 與檔案系統**，不讀 `_probe/` 的任何推導產物——那些是被監看的
  那條鏈自己寫的，用它們來判斷它有沒有跑，等於問一個昏迷的人他醒著沒有。

## 它量四件事

| 量什麼 | 從哪裡讀 | 壞掉的樣子 |
|---|---|---|
| 抓取有沒有跑 | `main` 上最後一個 `probe ` commit | 排程沒被排上 / CI 掛了 |
| 有沒有抓到東西 | `_corpus/` 最新的目錄 | 鏈在跑但來源全空 |
| 看板有沒有重生成 | `_dashboards/health.md` 的 `generated_day` | vault 頁那幾步掛了 |
| 潤稿有沒有推回 | `main` 上最後一個 `nightly: enrich` commit | 沙箱授權掉了 |

四格分開判、分開報。擠成一個「健康／不健康」的話，看到紅燈的人得自己去猜是哪一種，
而這四種要做的事完全不同。

淺 checkout 一律回「量不到」且**不觸警**（紅線 8）——`git log --grep` 在
`fetch-depth: 1` 裡什麼都找不到，而「找不到」跟「很久沒有」在數字上長得一樣。

用法：`VAULT_DIR=... python scripts/pulse-watchdog.py [--alert]`
`--alert` 時任一格超過門檻回離開碼 1。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md

import yaml  # noqa: E402

DEFAULT_STALE_DAYS = 2
GREPS = {"probe": "^probe ", "enrich": "^nightly: enrich"}


def _git(vault, *args):
    try:
        return subprocess.run(["git", "-C", str(vault), *args],
                              capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None


def repo_state(vault):
    """→ "ok" | "shallow" | "no-git"。淺 checkout 要自成一種，見模組 docstring。"""
    r = _git(vault, "rev-parse", "--git-dir")
    if r is None or r.returncode != 0:
        return "no-git"
    s = _git(vault, "rev-parse", "--is-shallow-repository")
    if s is not None and s.stdout.strip() == "true":
        return "shallow"
    return "ok"


def last_commit_day(vault, grep):
    out = _git(vault, "log", "-1", "--format=%cd", "--date=short",
               f"--grep={grep}", "--extended-regexp")
    if out is None or out.returncode != 0:
        return None
    return out.stdout.strip() or None


def newest_corpus_day(vault):
    d = vault / "_corpus"
    if not d.is_dir():
        return None
    days = sorted(p.name for p in d.iterdir()
                  if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))
    return days[-1] if days else None


def health_generated_day(vault):
    p = vault / "_dashboards" / "health.md"
    if not p.exists():
        return None
    m = re.search(r'^generated_day:\s*"?(\d{4}-\d{2}-\d{2})"?', p.read_text("utf-8"), re.M)
    return m.group(1) if m else None


def lag_days(today, day):
    """→ 幾天前。`day` 讀不出來回 None。**負數原樣回**，判斷交給呼叫端。"""
    if not day:
        return None
    try:
        return (today - date.fromisoformat(day)).days
    except ValueError:
        return None


def verdict(label, day, lag, stale_days, repo):
    """一格的判定 → (文字, 要不要叫)。純函式，可離線單測。

    四種結果，刻意不擠成兩種：量不到（不叫）／從來沒有（叫）／
    未來日期（叫，而且訊息要跟「太久沒有」分開——一個是鏈斷了，一個是日期壞了）／
    超過門檻（叫）。
    """
    if repo != "ok":
        why = "淺 checkout（`fetch-depth: 1`），看不到 commit 歷史" if repo == "shallow" \
            else "這裡不是一個 git 工作區"
        return f"{label}：**量不到**——{why}", False
    if day is None:
        return f"{label}：**從來沒有過**", True
    if lag is None:
        return f"{label}：最後一次 {day}，但今天的日期讀不出來——量不到", False
    if lag < 0:
        return (f"{label}：讀到一個未來的日期（{day}），**這一格不算數**"
                "——負數的 lag 不是「很新鮮」，是時鐘或寫入端的日期壞了"), True
    body = f"{label}：最後一次 {day}（{lag} 天前）"
    if lag >= stale_days:
        return body + f"，**超過門檻 {stale_days} 天**", True
    return body, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", action="store_true")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])

    cfg = {}
    gp = vault / "_config" / "gate.yaml"
    if gp.exists():
        cfg = (yaml.safe_load(gp.read_text("utf-8")) or {}).get("watchdog") or {}
    stale = int(cfg.get("stale_after_days", DEFAULT_STALE_DAYS))

    repo = repo_state(vault)
    today = clock.utc_today()
    rows = [
        ("抓取有沒有跑（main 上的 probe commit）", last_commit_day(vault, GREPS["probe"])),
        ("有沒有抓到東西（_corpus/ 最新的一天）", newest_corpus_day(vault)),
        ("看板有沒有重生成（health.md 的 generated_day）", health_generated_day(vault)),
        ("潤稿有沒有推回（main 上的 nightly: enrich）", last_commit_day(vault, GREPS["enrich"])),
    ]
    print(f"pulse-watchdog  {today}  門檻 {stale} 天  repo={repo}")
    bad = 0
    for label, day in rows:
        text, is_bad = verdict(label, day, lag_days(today, day), stale, repo)
        print(("  ⚠ " if is_bad else "  · ") + text)
        bad += 1 if is_bad else 0
    print(f"\n  四格裡 {bad} 格要人看。")
    if bad and args.alert:
        print("[alert] 被監看的那條鏈有格子過期了——**這支跑在鏈外面**，"
              "所以它報得出來的正是那條鏈自己報不出來的那種故障。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
