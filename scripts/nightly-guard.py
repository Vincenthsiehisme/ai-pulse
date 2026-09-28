#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nightly-guard.py — 雲端夜班的守門（Claude Code hook；確定性，零 LLM）。

規格在 references/nightly-guard.md，不一致時以規格為準（紅線 9）。

雲端排程裡寫作端跟迴圈是同一個 agent，手上有 Bash，於是「不要自己跑 apply、不要
commit、不要 push」退回成 prompt 裡的一句話；平台自己的 Stop hook 又逼它在收尾時處理
git。五晚的即興（09-18、09-19、09-20、09-23、09-27）一個形狀：不准做的事寫在 prompt 裡，
而 prompt 每晚被重新詮釋一次。這支把那幾條變成做不到的事。

接線（.claude/settings.json）：

    PreToolUse（Bash|Write|Edit|MultiEdit|NotebookEdit）  python3 scripts/nightly-guard.py pre
    Stop                                                  python3 scripts/nightly-guard.py stop

只在三個條件都成立時管：`CLAUDE_CODE_REMOTE=true`、session 第一則使用者訊息以
`ROUTINE_MARKER` 開頭、這一次本來就會被擋。其餘一律 exit 0，本機 session 連 stdin 都不讀。

離開碼：0 放行；2 擋下（stderr 是給 agent 看的理由）；1 hook 自己收到壞掉的 payload
（非阻擋，但會出現在 transcript 上，不安靜吞掉）。
"""
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import traceback
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md

# routine prompt 的第一句。改 routine prompt 時這一句不能動，動了守門就安靜失效；
# routine 設定不在 repo 裡，selftest 驗不到（規格〈什麼時候作用〉）。
ROUTINE_MARKER = "你是 AI-Pulse 的半夜潤稿執行者"
STATE_FILE = "_probe/nightly-run.json"
# 平台 Stop hook 的合法出口：只 commit 狀態檔、訊息固定。刻意不用 `nightly: enrich`
# 開頭，也不用資料鏈的 `chore: nightly refresh`：pulse-monitor 的
# night_shift_commit_days() 認夜班看作者或 `nightly: enrich` 前綴，一顆只有狀態檔的
# commit 不能讓潤稿鏈缺日的警報變綠。
STATE_COMMIT_RE = re.compile(r"^chore: nightly run state (\d{4}-\d{2}-\d{2})(?: \(.*\))?$")
NIGHTLY_BRANCH_RE = re.compile(r"^nightly/(\d{4}-\d{2}-\d{2})-[0-9a-f]{4,40}$")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

GIT_READONLY = frozenset({
    "status", "log", "diff", "show", "rev-parse", "rev-list", "merge-base", "ls-files",
    "ls-tree", "cat-file", "blame", "describe", "shortlog", "grep", "name-rev",
    "for-each-ref", "show-ref", "fetch", "help", "version",
})
_BRANCH_WRITE = ("-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy",
                 "-f", "--force", "-u", "--set-upstream-to", "--unset-upstream",
                 "--edit-description", "-t", "--track", "--no-track")
_BRANCH_VALUE_FLAGS = ("--contains", "--no-contains", "--merged", "--no-merged",
                       "--points-at", "--format", "--sort")
_CONFIG_READ = ("--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l")
_PUSH_BANNED = ("-f", "--force", "--force-with-lease", "--force-if-includes", "-d",
                "--delete", "--mirror", "--all", "--tags", "--prune")
_QUIET = ("-q", "--quiet")

PULSE_SCRIPT_RE = re.compile(r"(?:^|/)pulse-[^/]+\.py$")
NIGHTLY_SUBCMDS_OK = ("run", "summary", "status")
NIGHTLY_RUN_BANNED = ("--reset", "--no-push")
_PY_RE = re.compile(r"^python(\d+(\.\d+)*)?$")
_SHELLS = ("bash", "sh", "zsh", "dash")
_WRAPPERS = ("command", "builtin", "nohup", "time", "exec", "sudo")
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_REDIRECT_RE = re.compile(r"^[<>]+&?$|^>&$|^&>>?$")
_SEP_CHARS = set(";&|()")


class Unparseable(Exception):
    """指令拆不開（引號沒關之類）。拆不開就判不了，判不了就擋。"""


class RoutineUnknown(Exception):
    """雲端、呼叫本來會被擋，但判不出是不是夜班。判不出就擋，不猜。"""


# ── 拆指令（純函式）──────────────────────────────────────────────────

def _flatten(cmd):
    """引號外的換行換成 `;`、丟掉 heredoc 內文、拿掉 fd 重導向的雜訊。

    shlex 把換行當空白，不先換掉的話 `git status\\ngit commit` 會被讀成一個 `git status`。
    heredoc 內文不是指令，留著會把內文裡的字當成指令判。`2>&1` 不拿掉會留下一個 `2`
    當成 git 的參數，讓 `git checkout main 2>&1` 對不上允許的寫法。
    """
    out, i, n, q, pending = [], 0, len(cmd), None, []
    while i < n:
        c = cmd[i]
        if q == "'":
            out.append(c)
            q = None if c == "'" else q
            i += 1
            continue
        if q == '"':
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(cmd[i + 1])
                i += 2
                continue
            q = None if c == '"' else q
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            if cmd[i + 1] == "\n":          # 續行
                i += 2
                continue
            out.append(cmd[i:i + 2])
            i += 2
            continue
        if c in "'\"":
            q = c
            out.append(c)
            i += 1
            continue
        if c == "#" and (i == 0 or cmd[i - 1] in " \t\n;&|("):
            j = cmd.find("\n", i)
            i = n if j < 0 else j
            continue
        m = re.match(r"\d*>&(\d+|-)|&>>?|\d+(?=[<>])", cmd[i:])
        if m and (i == 0 or cmd[i - 1] in " \t\n;&|(") or (m and m.group(0).startswith("&")):
            tok = m.group(0)
            out.append(" > " if tok.startswith("&") else " ")
            i += len(tok)
            continue
        if cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            hm = re.match(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2", cmd[i:])
            if hm:
                pending.append((hm.group(3), hm.group(1) == "-"))
                out.append(" ")
                i += hm.end()
                continue
        if c == "\n":
            out.append(";")
            i += 1
            while pending:
                delim, strip = pending.pop(0)
                while i < n:
                    j = cmd.find("\n", i)
                    line = cmd[i:] if j < 0 else cmd[i:j]
                    i = n if j < 0 else j + 1
                    if (line.lstrip("\t") if strip else line) == delim:
                        break
            continue
        out.append(c)
        i += 1
    if q:
        raise Unparseable("引號沒有關起來")
    return "".join(out)


def _substitutions(token):
    """token 裡的 `$(…)` 與反引號內容。會被 shell 執行，所以也要判。"""
    found, i = [], 0
    while i < len(token):
        if token.startswith("$(", i):
            depth, j = 1, i + 2
            while j < len(token) and depth:
                depth += {"(": 1, ")": -1}.get(token[j], 0)
                j += 1
            found.append(token[i + 2:j - 1])
            i = j
        elif token[i] == "`":
            j = token.find("`", i + 1)
            if j < 0:
                raise Unparseable("反引號沒有關起來")
            found.append(token[i + 1:j])
            i = j + 1
        else:
            i += 1
    return found


def split_commands(cmd, _depth=0):
    """一段 Bash → 每一個會被執行的單一指令（token 清單）。拆不開就 raise Unparseable。"""
    if _depth > 6:
        raise Unparseable("巢狀太深")
    lex = shlex.shlex(_flatten(cmd), posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        tokens = list(lex)
    except ValueError as e:
        raise Unparseable(str(e))
    cmds, cur = [], []
    for t in tokens:
        if t and set(t) <= _SEP_CHARS:
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)

    result = []
    for c in cmds:
        clean, skip = [], False
        for t in c:
            if skip:
                skip = False
                continue
            if _REDIRECT_RE.match(t):
                skip = True
                continue
            clean.append(t)
        for t in clean:
            for inner in _substitutions(t):
                result.extend(split_commands(inner, _depth + 1))
        clean = _unwrap(clean)
        if not clean:
            continue
        base = os.path.basename(clean[0])
        if base in _SHELLS:
            code = _shell_c_arg(clean[1:])
            if code is not None:
                result.extend(split_commands(code, _depth + 1))
                continue
        if base == "eval":
            result.extend(split_commands(" ".join(clean[1:]), _depth + 1))
            continue
        if base == "xargs":
            rest = [t for t in clean[1:] if not t.startswith("-")]
            if rest:
                result.append(rest)
            continue
        if base == "find":
            result.extend(_find_exec(clean[1:]))
        result.append(clean)
    return result


def _unwrap(tokens):
    """拿掉前置的 `VAR=值`、`env`、`command`、`timeout 30` 這類外殼。"""
    t = list(tokens)
    while t:
        if _ASSIGN_RE.match(t[0]):
            t.pop(0)
        elif os.path.basename(t[0]) == "env":
            t.pop(0)
            while t and (t[0].startswith("-") or _ASSIGN_RE.match(t[0])):
                t.pop(0)
        elif os.path.basename(t[0]) in _WRAPPERS:
            t.pop(0)
        elif os.path.basename(t[0]) == "timeout" and len(t) > 1:
            t = t[2:]
        else:
            break
    return t


def _shell_c_arg(args):
    for k, a in enumerate(args):
        if a.startswith("-") and not a.startswith("--") and "c" in a[1:] and k + 1 < len(args):
            return args[k + 1]
    return None


def _find_exec(args):
    out, k = [], 0
    while k < len(args):
        if args[k] in ("-exec", "-execdir", "-ok", "-okdir"):
            j = k + 1
            while j < len(args) and args[j] not in (";", "+", "\\;"):
                j += 1
            if j > k + 1:
                out.append(args[k + 1:j])
            k = j
        k += 1
    return out


# ── 判（純函式，git 狀態由 facts 注入）───────────────────────────────

def _commit_message(value):
    """`-m` 的值 → 訊息第一行。`"$(cat <<'EOF' … EOF)"` 這種寫法取 heredoc 內文。"""
    m = re.match(r"^\$\(cat\s+<<-?\s*(['\"]?)(\w+)\1\s*\n(.*?)\n\s*\2\s*\)\s*$", value, re.S)
    body = m.group(3) if m else value
    for line in body.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _git_violation(args, facts, today):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    if sub in GIT_READONLY:
        return None
    if sub == "branch":
        if any(a in _BRANCH_WRITE or a.split("=")[0] in _BRANCH_WRITE for a in rest):
            return "git branch 只准列出，不准建、刪、改名或改追蹤"
        positional, k = [], 0
        while k < len(rest):
            if rest[k] in _BRANCH_VALUE_FLAGS:
                k += 2
                continue
            if not rest[k].startswith("-"):
                positional.append(rest[k])
            k += 1
        if positional and not any(a in ("--list", "-l") for a in rest):
            return "git branch 帶分支名是建分支，夜班不開分支"
        return None
    if sub == "remote":
        return None if (not rest or rest[0] in ("-v", "--verbose", "get-url", "show")) \
            else "git remote 只准列出，不准改"
    if sub == "config":
        flags = [a for a in rest if a.startswith("-")]
        positional = [a for a in rest if not a.startswith("-")]
        if any(f.split("=")[0] in _CONFIG_READ for f in flags):
            return None
        if len(positional) == 1 and set(flags) <= {"--global", "--local", "--show-origin"}:
            return None
        return "git config 只准讀，不准寫"
    if sub == "reflog":
        return "git reflog 只准看" if rest and rest[0] in ("expire", "delete") else None
    if sub == "checkout":
        return None if [a for a in rest if a not in _QUIET] == ["main"] else \
            "git checkout 只准回 main（對齊是 driver 的 align-main 在做），夜班不開分支、不還原檔案"
    if sub == "merge":
        return None if sorted(a for a in rest if a not in _QUIET) == ["--ff-only", "origin/main"] \
            else "git merge 只准 `--ff-only origin/main`"
    if sub == "add":
        paths = [a.lstrip("./") if a.startswith("./") else a for a in rest
                 if a not in ("-v", "--verbose")]
        if paths != [STATE_FILE]:
            return f"git add 只准加 `{STATE_FILE}`（資料 commit 是 driver 在做）"
        extra = facts.dirty_paths() - {STATE_FILE}
        return None if not extra else \
            f"工作樹除了 `{STATE_FILE}` 還有別的改動（{'、'.join(sorted(extra)[:5])}），不准 add"
    if sub == "commit":
        return _commit_violation(rest, facts, today)
    if sub == "push":
        return _push_violation(rest, facts, today)
    if sub == "reset":
        if rest != ["--hard", "origin/main"]:
            return "git reset 只准 `--hard origin/main`，而且要今晚的成果已經在 origin/nightly/* 上"
        if facts.dirty_paths():
            return "工作樹還有沒 commit 的改動，reset --hard 會把它們丟掉"
        if not facts.head_on_remote_nightly():
            return ("HEAD 不在任何一支 origin/nightly/* 裡，reset --hard 會把還沒推出去的 commit 丟掉；"
                    "先把它推到今晚的備援分支")
        return None
    return f"git {sub} 不在夜班的允許清單上"


def _commit_violation(rest, facts, today):
    msgs, k = [], 0
    while k < len(rest):
        a = rest[k]
        if a in ("-m", "--message"):
            if k + 1 >= len(rest):
                return "git commit -m 後面沒有訊息"
            msgs.append(rest[k + 1])
            k += 2
            continue
        if a.startswith("--message="):
            msgs.append(a.split("=", 1)[1])
        elif a.startswith("-m") and len(a) > 2:
            msgs.append(a[2:])
        elif a not in _QUIET:
            return f"git commit 不准帶 `{a}`（只准 -m 與 -q）"
        k += 1
    if not msgs:
        return "git commit 沒有 -m，驗不了訊息"
    first = _commit_message(msgs[0])
    m = STATE_COMMIT_RE.match(first)
    if not m:
        return (f"夜班自己只准 commit 狀態檔，訊息第一行要是 `chore: nightly run state {today}`，"
                f"收到的是「{first[:80]}」。資料 commit 是 driver 在做")
    if m.group(1) != today:
        return f"狀態檔 commit 的日期要是今天（UTC {today}），收到 {m.group(1)}"
    extra = facts.dirty_paths() - {STATE_FILE}
    return None if not extra else \
        f"工作樹除了 `{STATE_FILE}` 還有別的改動（{'、'.join(sorted(extra)[:5])}），不准 commit"


def _push_violation(rest, facts, today):
    for a in rest:
        if a.split("=")[0] in _PUSH_BANNED:
            return f"git push 不准帶 `{a}`"
    positional = [a for a in rest if not a.startswith("-")]
    if any(p.startswith("+") for p in positional):
        return "git push 不准強推（refspec 帶 +）"
    if positional and positional[0] != "origin":
        return "git push 只准推 origin"
    spec = positional[1:] if positional else []
    if len(spec) > 1:
        return "git push 一次只准推一個目的地"
    if not spec or spec[0] in ("main", "HEAD:main", "HEAD:refs/heads/main"):
        return None if facts.current_branch() == "main" else \
            f"現在站在 `{facts.current_branch()}`，不是 main，不准推"
    dst = spec[0][5:] if spec[0].startswith("HEAD:") else None
    if dst and dst.startswith("refs/heads/"):
        dst = dst[len("refs/heads/"):]
    m = NIGHTLY_BRANCH_RE.match(dst or "")
    if not m:
        return f"git push 只准推 main 或今晚的備援分支 nightly/{today}-<sha>，收到 `{spec[0]}`"
    return None if m.group(1) == today else f"備援分支的日期要是今天（UTC {today}）"


def _python_script(args):
    k = 0
    while k < len(args):
        a = args[k]
        if a in ("-c", "-m"):
            return None
        if a in ("-X", "-W"):
            k += 2
            continue
        if a.startswith("-"):
            k += 1
            continue
        return a, args[k + 1:]
    return None


def _pulse_violation(script, rest):
    if not PULSE_SCRIPT_RE.search(script):
        return None
    base = os.path.basename(script)
    if base != "pulse-nightly.py":
        return (f"夜班不准直接跑 `{base}`（含 --dry-run）：順序、判讀與退件是 driver 的事，"
                "退件會記進摘要。寫好交棒檔之後跑 `python3 scripts/pulse-nightly.py run`")
    if any(a in ("-h", "--help") for a in rest):
        return None
    subs = [a for a in rest if not a.startswith("-")]
    if not subs or subs[0] not in NIGHTLY_SUBCMDS_OK:
        return f"pulse-nightly.py 只准 {'、'.join(NIGHTLY_SUBCMDS_OK)}"
    banned = [a for a in rest if a in NIGHTLY_RUN_BANNED]
    if banned:
        return f"pulse-nightly.py run 不准帶 {'、'.join(banned)}：要不要重跑、要不要推是人的決定"
    return None


def bash_violations(cmd, facts, today):
    """一段 Bash → 違規理由清單（空清單＝放行）。拆不開本身就是一條違規。"""
    try:
        commands = split_commands(cmd)
    except Unparseable as e:
        return [f"指令拆不開（{e}），判不了就不放"]
    out = []
    for c in commands:
        base = os.path.basename(c[0])
        why = None
        if base == "git":
            why = _git_violation(c[1:], facts, today)
        elif _PY_RE.match(base):
            hit = _python_script(c[1:])
            why = _pulse_violation(*hit) if hit else None
        elif PULSE_SCRIPT_RE.search(c[0]):
            why = _pulse_violation(c[0], c[1:])
        if why:
            out.append(f"`{' '.join(c)[:120]}`：{why}")
    return out


def write_violation(file_path, repo, result_files):
    """Write／Edit 的目標 → 違規理由或 None。只准 repo 根目錄的交棒檔。"""
    if not file_path:
        return "寫檔工具沒有帶路徑"
    p = Path(file_path)
    p = (p if p.is_absolute() else Path(repo) / p).resolve()
    if p.parent == Path(repo).resolve() and p.name in result_files:
        return None
    return (f"夜班只准寫 repo 根目錄的交棒檔（{'、'.join(result_files)}），不准寫 `{file_path}`。"
            "產生器腳本也不要寫：直接用 Write 寫交棒檔")


# ── 讀 session 與 git（副作用）────────────────────────────────────────

def _transcript_entries(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                yield obj


def _texts(content):
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"]
    return []


def first_user_text(path):
    for obj in _transcript_entries(path):
        if obj.get("type") != "user" or obj.get("isMeta"):
            continue
        texts = _texts((obj.get("message") or {}).get("content"))
        if texts:
            return "".join(texts)
    return None


def is_nightly_routine(payload):
    path = payload.get("transcript_path")
    if not path:
        raise RoutineUnknown("hook payload 沒有 transcript_path")
    try:
        text = first_user_text(path)
    except OSError as e:
        raise RoutineUnknown(f"讀不到 transcript（{e}）")
    if text is None:
        raise RoutineUnknown("transcript 裡還沒有使用者訊息")
    # 看「含」不看「開頭是」：API 觸發時平台可能在 prompt 前面包一層（規格〈什麼時候作用〉）。
    return ROUTINE_MARKER in text


class GitFacts:
    """守門當下的 git 狀態。查不到就 raise，由呼叫端擋（判不了就不放）。"""

    def __init__(self, repo):
        self.repo = str(repo)
        self._cache = {}

    def _git(self, *args):
        r = subprocess.run(["git", "-C", self.repo, *args], capture_output=True,
                           text=True, timeout=20)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} 失敗 rc={r.returncode}：{r.stderr.strip()[:200]}")
        return r.stdout

    def dirty_paths(self):
        if "dirty" not in self._cache:
            paths = set()
            for line in self._git("status", "--porcelain").splitlines():
                if len(line) < 4:
                    continue
                path = line[3:].strip().strip('"')
                if " -> " in path:
                    path = path.split(" -> ", 1)[1].strip().strip('"')
                paths.add(path)
            self._cache["dirty"] = paths
        return self._cache["dirty"]

    def current_branch(self):
        if "branch" not in self._cache:
            self._cache["branch"] = self._git("rev-parse", "--abbrev-ref", "HEAD").strip()
        return self._cache["branch"]

    def head_on_remote_nightly(self):
        if "nightly" not in self._cache:
            out = self._git("branch", "-r", "--contains", "HEAD")
            self._cache["nightly"] = any(l.strip().startswith("origin/nightly/")
                                         for l in out.splitlines())
        return self._cache["nightly"]


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "pulse_nightly", os.path.join(_HERE, "pulse-nightly.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Stop：收尾要原樣帶 driver 的摘要 ──────────────────────────────────

def norm_line(s):
    return " ".join(s.replace("**", "").replace("`", "").split())


def required_summary_lines(summary):
    """summary_lines() 的前段：標題、每一段一行、寫作端成本。尾端的完整輸出不要求。"""
    out = []
    for line in summary:
        if not line.strip():
            break
        out.append(line)
    return out


def missing_summary_lines(summary, texts):
    have = {norm_line(l) for t in texts for l in t.splitlines()}
    return [l.strip() for l in required_summary_lines(summary) if norm_line(l) not in have]


def assistant_texts(path):
    out = []
    for obj in _transcript_entries(path):
        if obj.get("type") == "assistant":
            out.extend(_texts((obj.get("message") or {}).get("content")))
    return out


def stop_check(payload, repo, driver):
    """回 (exit code, stderr 訊息)。"""
    state = driver.load_state(Path(repo))
    today = clock.utc_today().isoformat()
    if state is None or state.get("date") != today:
        # 明寫的放行：driver 今天一次都沒跑到，沒有摘要可以比，那晚要看的是 run log。
        return 0, ""
    texts = assistant_texts(payload["transcript_path"])
    if payload.get("last_assistant_message"):
        texts.append(payload["last_assistant_message"])
    missing = missing_summary_lines(driver.summary_lines(state), texts)
    if not missing:
        return 0, ""
    msg = ("nightly-guard：收尾沒有原樣帶 driver 的摘要，缺這幾行（不要改寫、不要在行尾加註）：\n"
           + "\n".join(f"  {l}" for l in missing)
           + "\n跑 `python3 scripts/pulse-nightly.py summary`，把輸出原樣貼進回覆。")
    return (0 if payload.get("stop_hook_active") else 2), msg


def marker_missing_check(payload, repo, driver_loader, facts):
    """第一則訊息沒有標記，但這個 session 今天跑過 driver：守門整晚沒作用，收尾要講出來。

    雲端每次都是全新 clone，`_probe/nightly-run.json` 是今天的而且工作樹上有改動，就代表是這個
    session 跑的 driver。沒有這一道，prompt 被改、或觸發方式改了訊息形狀的那一晚，守門安靜不見。"""
    state = driver_loader().load_state(Path(repo))
    if state is None or state.get("date") != clock.utc_today().isoformat():
        return 0, ""
    if STATE_FILE not in facts.dirty_paths():
        return 0, ""
    msg = ("nightly-guard：這個 session 今天跑過 driver，但第一則使用者訊息裡沒有夜班標記"
           f"「{ROUTINE_MARKER}」，守門這一晚沒有作用。收尾摘要寫明這一句，"
           "並說明 routine prompt 的第一句或觸發方式是不是改過（references/nightly-guard.md〈什麼時候作用〉）。")
    return (0 if payload.get("stop_hook_active") else 2), msg


# ── 入口 ─────────────────────────────────────────────────────────────

def pre_check(payload, repo, driver_loader=_load_driver, facts=None):
    """回 (exit code, stderr 訊息)。"""
    tool = payload.get("tool_name")
    tin = payload.get("tool_input") or {}
    today = clock.utc_today().isoformat()
    try:
        if tool == "Bash":
            why = bash_violations(tin.get("command") or "", facts or GitFacts(repo), today)
        elif tool in WRITE_TOOLS:
            one = write_violation(tin.get("file_path") or tin.get("notebook_path"), repo,
                                  driver_loader().ROOT_RESULT_FILES)
            why = [one] if one else []
        else:
            return 0, ""
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        why = [f"查不到判斷需要的狀態（{e}），判不了就不放"]
    if not why:
        return 0, ""
    try:
        if not is_nightly_routine(payload):
            return 0, ""
    except RoutineUnknown as e:
        return 2, (f"nightly-guard：判不出這是不是夜班（{e}），而這一次呼叫在夜班裡會被擋，所以擋下：\n"
                   + "\n".join(f"  {w}" for w in why))
    return 2, ("nightly-guard（references/nightly-guard.md）擋下：\n"
               + "\n".join(f"  {w}" for w in why)
               + "\n範圍外的事寫進收尾摘要，不要換一種寫法繞過去。")


def main(argv=None, stdin=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if not argv or argv[0] not in ("pre", "stop"):
        print("用法：nightly-guard.py pre|stop（Claude Code hook，從 stdin 讀 payload）",
              file=sys.stderr)
        return 2
    if env.get("CLAUDE_CODE_REMOTE") != "true":
        return 0
    try:
        payload = json.load(stdin or sys.stdin)
    except ValueError as e:
        print(f"nightly-guard：hook payload 不是 JSON（{e}），這一次沒有檢查", file=sys.stderr)
        return 1
    repo = env.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    if argv[0] == "pre":
        rc, msg = pre_check(payload, repo)
    else:
        rc, msg = stop_main(payload, repo)
    if msg:
        print(msg, file=sys.stderr)
    return rc


def stop_main(payload, repo, driver_loader=_load_driver):
    """Stop 模式。**任何失敗都先看 `stop_hook_active`**：平台那支 hook 不看它，
    所以會擋不完（anthropics/claude-code#69201）；這支自己壞掉時不能變成第二支。"""
    blocking = 0 if payload.get("stop_hook_active") else 2
    try:
        if not is_nightly_routine(payload):
            return marker_missing_check(payload, repo, driver_loader, GitFacts(repo))
        return stop_check(payload, repo, driver_loader())
    except RoutineUnknown as e:
        return blocking, f"nightly-guard：判不出這是不是夜班（{e}），收尾摘要沒有比對"
    except Exception:
        return blocking, "nightly-guard：Stop 檢查自己壞了，收尾摘要沒有比對：\n" + traceback.format_exc()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # 守門自己壞掉要壞得看得見：印 traceback、擋下。本機 session 走不到這裡
        # （CLAUDE_CODE_REMOTE 沒設時 main 第一步就回 0）；Stop 模式的失敗在
        # stop_main() 裡先看過 stop_hook_active，不會落到這裡變成擋不完。
        traceback.print_exc()
        sys.exit(2)
