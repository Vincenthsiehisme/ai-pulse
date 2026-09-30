#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nightly-cost.py — 雲端夜班的成本帳（Claude Code Stop hook；確定性，零 LLM）。

規格：references/nightly-driver.md〈一晚花多少錢，要是一個被記錄的量〉（算法、牌價、帳本）
與 references/nightly-guard.md〈成本帳：守門之外唯一會 commit 的程式〉（條件、為什麼不經過守門）。
不一致時以規格為準（紅線 9）。算式在 lib/nightcost.py。

接線（.claude/settings.json），跟守門的 Stop 並列：

    Stop    python3 scripts/nightly-cost.py

只在雲端半夜潤稿 routine 作用，判斷條件跟守門同一套（import nightly-guard，不另抄）。
帳本一個 session 一行（key 是 `session_id`，`date` 是 transcript 第一筆紀錄的 UTC 日期）。

**先檢查、後寫檔**：工作樹有帳本以外的改動就整個跳過，等下一次 Stop。工作樹乾淨才寫帳本、
commit、push，所以記到的是「量到第一次工作樹乾淨的 Stop 為止」的數字。
**同一個 session 只 commit 一次**：HEAD 的帳本已經有這個 `session_id` 就整個跳過。否則平台
每多擋一輪，帳本就變、又 commit、又 push、又製造競態，可能循環；代價是那幾輪不記。
**hook 結束時帳本絕不能是 dirty**：守門給平台 Stop hook 的出口只准狀態檔，帳本一髒，
那兩個出口就被堵死。

**只在雲端半夜潤稿 routine 作用**，而且這一側比守門嚴：第一則使用者訊息要以 `ROUTINE_MARKER`
開頭（去掉前導空白），守門看的是「含」。成本帳會自己 commit、push，中間引用那句話的雲端
session 不該被當成夜班去推 main。
**成本 commit 必須是唯一被推的那一顆**：寫帳本前先 `git fetch origin main`，要求
`HEAD == origin/main`，不相等或 fetch 失敗就跳過；否則 `git push origin HEAD:main` 會把本機
領先的 commit 一起推上去。
**subagent 也要算**：它們的 request 存在 `<transcript 去掉 .jsonl>/subagents/**/*.jsonl`，
主檔只留 `Agent` 的 tool_use。讀不到或解析失敗時那一行 `usd_equiv` 是 null，不安靜少算。

離開碼：跳過、沒變、推上去都是 0；commit 失敗、push 失敗、HEAD 的帳本讀不進來是 1
（非阻擋，但平台看得見）。沒有任何一種是 2：成本帳記不到不擋 session 結束。
原因一定印在 stderr，不安靜吞掉。
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

from lib import nightcost  # noqa: E402  算式與帳本格式
from lib.atomicwrite import atomic_write_text  # noqa: E402  見 references/atomic-writes.md


LEDGER = nightcost.LEDGER_PATH
# 這三種 exit 1：非阻擋（Stop hook 只有 2 會擋），但平台看得見。其餘 exit 0。
FAILED = ("head-unreadable", "commit-failed", "push-failed")
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


def subagent_entries(transcript_path):
    """這個 session 的 subagent transcript → (所有紀錄, 讀不到的原因清單)。

    路徑是 `<transcript 去掉 .jsonl>/subagents/` 底下所有 `*.jsonl`（含 workflows 之類的巢狀
    目錄），2026-09-30 在本機 `~/.claude/projects/` 實查過這個結構。目錄不存在是「沒有
    subagent」，不是錯。目錄或檔讀不到、任何一行不是合法 JSON，都記進原因清單：呼叫端
    讓那一行的 `usd_equiv` 變成 null，不安靜少算。**不用守門的 `_transcript_entries`**：
    它會跳過壞行，這裡要的正是看見壞行。
    """
    root = Path(transcript_path).with_suffix("") / "subagents"
    if not root.exists():
        return [], []
    entries, problems, files = [], [], []

    def _walk_error(e):
        problems.append(f"subagent 目錄讀不到（{e.filename}：{e.strerror}）")

    for dirpath, _dirs, names in os.walk(root, onerror=_walk_error):
        files += [Path(dirpath) / n for n in names if n.endswith(".jsonl")]
    for f in sorted(files):
        try:
            lines = f.read_text("utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as e:
            problems.append(f"subagent 檔 {f.name} 讀不到（{e}）")
            continue
        for n, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                problems.append(f"subagent 檔 {f.name} 第 {n} 行不是合法 JSON")
                continue
            if isinstance(obj, dict):
                entries.append(obj)
    return entries, problems


def origin_in_sync(repo):
    """fetch origin main 之後 HEAD 是不是剛好等於 origin/main。回 (是不是, 不是的原因)。"""
    r = _git(repo, "fetch", "-q", "origin", "main")
    if r.returncode != 0:
        return False, f"git fetch origin main 失敗 {_why(r)}"
    head = _git(repo, "rev-parse", "HEAD")
    remote = _git(repo, "rev-parse", "refs/remotes/origin/main")
    if head.returncode != 0 or remote.returncode != 0:
        return False, f"查不到 HEAD 或 origin/main（{_why(head)}／{_why(remote)}）"
    if head.stdout.strip() != remote.stdout.strip():
        return False, (f"HEAD（{head.stdout.strip()[:8]}）不等於 origin/main（{remote.stdout.strip()[:8]}），"
                       "推上去會連帶推別的 commit 或被拒，這一次沒有記")
    return True, ""


def commit_ledger(repo, text, day):
    """把帳本寫成 text 並 commit。回 (結果, 訊息)。

    結果 ∈ unchanged（跟 HEAD 一樣，不 commit）、committed、commit-failed（帳本已還原）。
    任何一步出錯都先把帳本還原成 HEAD 那一版再回報：hook 結束時帳本不能是 dirty。
    """
    p = Path(repo).joinpath(*nightcost.LEDGER_REL)
    try:
        if not (p.exists() and p.read_text("utf-8") == text):
            p.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(p, text)
        if text == head_ledger(repo):
            return "unchanged", "帳本跟 HEAD 一樣，不 commit"
        r = _git(repo, "add", "--", LEDGER)
        if r.returncode == 0:
            r = _git(repo, "-c", f"user.name={nightcost.COST_AUTHOR}",
                     "-c", f"user.email={nightcost.COST_EMAIL}",
                     "commit", "-q", "-m", f"chore: nightly cost {day}", "--", LEDGER)
        if r.returncode != 0:
            still = restore_ledger(repo)
            return "commit-failed", (f"git add／commit 失敗 {_why(r)}；帳本已還原成 HEAD 那一版"
                                     + ("，**但還原後仍然是 dirty**" if still else ""))
    except Exception:
        still = restore_ledger(repo)
        return "commit-failed", ("寫帳本或 commit 時出錯，帳本已還原成 HEAD 那一版"
                                 + ("，**但還原後仍然是 dirty**" if still else "")
                                 + "：\n" + traceback.format_exc())
    return "committed", f"chore: nightly cost {day}"


def record(repo, row):
    """帳本那一行 → 檢查、寫檔、commit、push。回 (結果, 訊息)。

    結果 ∈ skipped（沒寫檔）、unchanged、pushed：exit 0；
          head-unreadable（HEAD 的帳本讀不進來）、commit-failed（帳本已還原）、
          push-failed（本機 commit 留著）：exit 1（見 FAILED）。
    """
    facts = guard().GitFacts(repo)
    try:
        branch = facts.current_branch()
        dirty = facts.dirty_paths()
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        return "skipped", f"查不到 git 狀態（{e}），這一次沒有記"
    if branch != "main":
        return "skipped", f"站在 `{branch}`，不是 `main`，這一次沒有記"
    try:
        head_rows = nightcost.parse_ledger(head_ledger(repo) or "")
    except ValueError as e:
        return "head-unreadable", f"HEAD 的 {LEDGER} 讀不進來（{e}），不覆寫它，這一次沒有記"
    if nightcost.has_session(head_rows, row["session_id"]):
        return "skipped", (f"HEAD 的帳本已經有 session {row['session_id']}，同一個 session 只記一次"
                           "（之後被多擋的輪不記）")
    extra = sorted(dirty - {LEDGER})
    if extra:
        return "skipped", ("工作樹還有帳本以外的改動，先不記（等下一次 Stop）："
                           + "、".join(extra[:8]))
    synced, why = origin_in_sync(repo)
    if not synced:
        return "skipped", why

    p = Path(repo).joinpath(*nightcost.LEDGER_REL)
    try:
        rows = nightcost.parse_ledger(p.read_text("utf-8")) if p.exists() else []
    except (ValueError, OSError) as e:
        return "skipped", f"{LEDGER} 讀不進來（{e}），不覆寫它，這一次沒有記"
    status, msg = commit_ledger(repo, nightcost.dump_ledger(nightcost.upsert(rows, row)),
                                row["date"])
    if status != "committed":
        return status, msg

    r = _git(repo, "push", "origin", "HEAD:main")
    if r.returncode != 0:
        return "push-failed", (f"git push origin HEAD:main 失敗 {_why(r)}；"
                               "本機那顆成本 commit 留著，不重試、不強推")
    return "pushed", f"{msg} 已推上 origin/main"


def is_cost_routine(first_text, marker):
    """第一則使用者訊息（去掉前導空白）以身分句開頭才算夜班。純函式。

    比守門嚴（守門看「含」）：成本帳會自己 commit、push，中間引用那句話的 session 不能算。
    """
    return bool(first_text) and first_text.lstrip().startswith(marker)


def main(argv=None, stdin=None, env=None):
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
        first = ng.first_user_text(path)
        entries = list(ng._transcript_entries(path))
    except OSError as e:
        print(f"nightly-cost：讀不到 transcript（{e}），這一次沒有記", file=sys.stderr)
        return 0
    if not is_cost_routine(first, ng.ROUTINE_MARKER):
        if first and ng.ROUTINE_MARKER in first:
            print("nightly-cost：第一則使用者訊息含夜班身分句但不是開頭，不當成夜班，這一次沒有記",
                  file=sys.stderr)
        return 0
    sid = payload.get("session_id")
    if not sid:
        print("nightly-cost：hook payload 沒有 session_id，帳本的 key 對不上，這一次沒有記",
              file=sys.stderr)
        return 0
    sub, problems = subagent_entries(path)
    row = nightcost.ledger_row(entries + sub, sid, problems=problems, date_from=entries)
    if row["date"] is None:
        print("nightly-cost：transcript 裡沒有任何帶 timestamp 的紀錄，定不出 session 開始那天，"
              "這一次沒有記", file=sys.stderr)
        return 0
    repo = env.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    status, msg = record(repo, row)
    usd = "量不到" if row["usd_equiv"] is None else f"USD {row['usd_equiv']:.4f}"
    print(f"nightly-cost：{status}｜{row['date']} session {sid} {row['requests']} 個 request，{usd}"
          + (f"（{row['note']}）" if row["note"] else "") + f"｜{msg}", file=sys.stderr)
    return 1 if status in FAILED else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # 自己壞掉也不擋收尾，但要壞得看得見。
        traceback.print_exc()
        sys.exit(0)
