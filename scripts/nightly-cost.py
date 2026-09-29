#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nightly-cost.py — 雲端夜班的成本帳（Claude Code Stop hook；確定性，零 LLM）。

規格：references/nightly-driver.md〈一晚花多少錢，要是一個被記錄的量〉（算法、牌價、帳本）
與 references/nightly-guard.md〈成本帳：守門之外唯一會 commit 的程式〉（條件、為什麼不經過守門）。
不一致時以規格為準（紅線 9）。算式在 lib/nightcost.py。

接線（.claude/settings.json），跟守門的 Stop 並列：

    Stop    python3 scripts/nightly-cost.py

只在雲端半夜潤稿 routine 作用，判斷條件跟守門同一套（import nightly-guard，不另抄）。
每一次 Stop 讀整份 transcript 重算，同一天取代帳本那一行，所以最後一次 Stop 記到的
就是量到最後一輪的數字。

**先檢查、後寫檔**：工作樹有帳本以外的改動就整個跳過，等下一次 Stop。工作樹乾淨才寫帳本、
commit、push。**hook 結束時帳本絕不能是 dirty**：守門給平台 Stop hook 的出口只准狀態檔，
帳本一髒，那兩個出口就被堵死。

離開碼一律 0：成本帳記不到不擋 session 結束。原因一定印在 stderr，不安靜吞掉。
"""
import importlib.util
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md
from lib import nightcost  # noqa: E402  算式與帳本格式
from lib.atomicwrite import atomic_write_text  # noqa: E402  見 references/atomic-writes.md


LEDGER = nightcost.LEDGER_PATH
_GUARD = []


def guard():
    """守門模組（ROUTINE_MARKER、讀 transcript、判雲端夜班、GitFacts 都從它來，不另抄）。

    第一次用到才載入，載入失敗也落在 main() 的 exit 0 裡，不變成擋收尾的錯。"""
    if not _GUARD:
        spec = importlib.util.spec_from_file_location(
            "nightly_guard", os.path.join(_HERE, "nightly-guard.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _GUARD.append(mod)
    return _GUARD[0]


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, timeout=60)


def _why(r):
    return f"rc={r.returncode}：{(r.stderr or r.stdout or '').strip()[:300]}"


def head_ledger(repo):
    """HEAD 那一版帳本的內容；HEAD 裡沒有這個檔回 None。"""
    r = _git(repo, "show", f"HEAD:{LEDGER}")
    return r.stdout if r.returncode == 0 else None


def restore_ledger(repo):
    """把帳本還原成 HEAD 那一版（HEAD 沒有就刪掉），index 一起還原。回還原後還髒不髒。"""
    if head_ledger(repo) is None:
        _git(repo, "rm", "-q", "--cached", "--ignore-unmatch", "--", LEDGER)
        p = Path(repo).joinpath(*nightcost.LEDGER_REL)
        if p.exists():
            p.unlink()
    else:
        _git(repo, "checkout", "HEAD", "--", LEDGER)
    return bool(_git(repo, "status", "--porcelain", "--", LEDGER).stdout.strip())


def record(repo, row):
    """帳本那一行 → 檢查、寫檔、commit、push。回 (結果, 訊息)，一律不 raise 到外面。

    結果 ∈ skipped（沒寫檔）、unchanged（跟 HEAD 一樣）、pushed、
          commit-failed（帳本已還原）、push-failed（本機 commit 留著）。
    """
    facts = guard().GitFacts(repo)
    try:
        branch = facts.current_branch()
        dirty = facts.dirty_paths()
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        return "skipped", f"查不到 git 狀態（{e}），這一次沒有記"
    if branch != "main":
        return "skipped", f"站在 `{branch}`，不是 `main`，這一次沒有記"
    extra = sorted(dirty - {LEDGER})
    if extra:
        return "skipped", ("工作樹還有帳本以外的改動，先不記（等下一次 Stop）："
                           + "、".join(extra[:8]))

    p = Path(repo).joinpath(*nightcost.LEDGER_REL)
    try:
        rows = nightcost.parse_ledger(p.read_text("utf-8")) if p.exists() else []
    except (ValueError, OSError) as e:
        return "skipped", f"{LEDGER} 讀不進來（{e}），不覆寫它，這一次沒有記"
    text = nightcost.dump_ledger(nightcost.upsert(rows, row))

    try:
        if not (p.exists() and p.read_text("utf-8") == text):
            p.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(p, text)
        if text == head_ledger(repo):
            return "unchanged", f"{row['date']} 那一行跟 HEAD 一樣，不 commit"
        r = _git(repo, "add", "--", LEDGER)
        if r.returncode == 0:
            r = _git(repo, "-c", f"user.name={nightcost.COST_AUTHOR}",
                     "-c", f"user.email={nightcost.COST_EMAIL}",
                     "commit", "-q", "-m", f"chore: nightly cost {row['date']}", "--", LEDGER)
        if r.returncode != 0:
            still = restore_ledger(repo)
            return "commit-failed", (f"git add／commit 失敗 {_why(r)}；帳本已還原成 HEAD 那一版"
                                     + ("，**但還原後仍然是 dirty**" if still else ""))
    except Exception:
        still = restore_ledger(repo)
        return "commit-failed", ("寫帳本或 commit 時出錯，帳本已還原成 HEAD 那一版"
                                 + ("，**但還原後仍然是 dirty**" if still else "")
                                 + "：\n" + traceback.format_exc())

    r = _git(repo, "push", "origin", "HEAD:main")
    if r.returncode != 0:
        return "push-failed", (f"git push origin HEAD:main 失敗 {_why(r)}；"
                               "本機那顆成本 commit 留著，不重試、不強推")
    return "pushed", f"chore: nightly cost {row['date']} 已推上 origin/main"


def main(argv=None, stdin=None, env=None, today=None):
    env = os.environ if env is None else env
    if env.get("CLAUDE_CODE_REMOTE") != "true":
        return 0
    try:
        payload = json.load(stdin or sys.stdin)
    except ValueError as e:
        print(f"nightly-cost：hook payload 不是 JSON（{e}），這一次沒有記", file=sys.stderr)
        return 0
    path = payload.get("transcript_path")
    if not path:
        print("nightly-cost：hook payload 沒有 transcript_path，這一次沒有記", file=sys.stderr)
        return 0
    ng = guard()
    try:
        if not ng.is_nightly_routine(payload):
            return 0
        entries = list(ng._transcript_entries(path))
    except ng.RoutineUnknown as e:
        print(f"nightly-cost：判不出這是不是夜班（{e}），這一次沒有記", file=sys.stderr)
        return 0
    except OSError as e:
        print(f"nightly-cost：讀不到 transcript（{e}），這一次沒有記", file=sys.stderr)
        return 0
    repo = env.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    day = (today or clock.utc_today()).isoformat()
    row = nightcost.ledger_row(entries, day, payload.get("session_id"))
    status, msg = record(repo, row)
    usd = "量不到" if row["usd_equiv"] is None else f"USD {row['usd_equiv']:.4f}"
    print(f"nightly-cost：{status}｜{day} {row['requests']} 個 request，{usd}"
          + (f"（{row['note']}）" if row["note"] else "") + f"｜{msg}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # 自己壞掉也不擋收尾，但要壞得看得見。
        traceback.print_exc()
        sys.exit(0)
