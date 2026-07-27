# -*- coding: utf-8 -*-
"""deadrefs.py — 掃出「文件裡寫著、實際不存在」的 repo 內部路徑。

為什麼要機械掃：2026-07-27 清根目錄的時候，把兩個檔案搬進 incidents/，順手發現
`pulse-enrich-prep.py` 的 docstring 從很久以前就把 `enrich-runbook.md` 寫成在
references/ 底下，而那個檔案一直都在 scripts/。沒有人會踩到——docstring 不會被執行
——但下一個照著它去找檔案的人會，然後他會以為那份 runbook 被刪了。同一輪還撈到
`lib/voice_clean.py` 指著一份本 repo 從來沒有過的 taiwan-localization 規則表
（那份表在 speak-human-tw 技能裡，不在這裡）。

（這段刻意不寫成完整路徑：寫了，這個模組自己就會被自己掃出來。這也順便說明了
判準的邊界——它認的是「路徑長相」，不是「有沒有在講一個檔案」。）

這跟 `gate_keys` 是同一個形狀：**列舉是機械的，判斷是人寫的。**
路徑長什麼樣子由 regex 機械決定；哪些不算「引用壞掉」由下面幾條**結構性規則**決定，
而不是一份逐條的白名單。白名單會腐爛——它一開始擋掉七個誤報，半年後擋掉的是三個真
的斷鏈加四個已經不存在的誤報，而沒有人會發現。

判準（五條，全部是結構性的）
--------------------------
1. **第一段必須是 repo 頂層真的有的東西**，否則那個字串根本不是在指本 repo：
   `openai.com/robots.txt` 是網址、`assets/app.css` 是 `dist/` 底下的相對連結、
   `data/github.json` 是瀏覽器端 fetch 的路徑。這一條一次收掉這三類。
2. **也試著相對於「寫它的那個檔案」解析一次**。`scripts/pulse-probe.py` 裡寫
   `lib/sources.py` 指的是 `scripts/lib/sources.py`，那是對的，不是斷鏈。
3. **產物目錄不算**：`_probe/`、`Events/`、`dist/` 底下的檔案存不存在取決於「跑過
   沒有」，乾淨的 clone 裡本來就沒有。
4. **單字母檔名是佔位示例**：`scripts/x.py`、`Actors/a.md` 這種是在講格式長怎樣。
5. **還沒動工的提案不算引用**：`docs/design/` 下 `status` 還是 proposal / review /
   draft 的文件，指的是它**要造的東西**。豁免綁在 status 上所以**會過期**——
   提案落地後改掉 status，檢查就回來了。（2026-07-27 加。加之前那些提案得把路徑
   寫成不是路徑的樣子才能讓 CI 綠，而一份提案 11 處這樣寫就讓整個變異安全網
   停擺了一天。）

不保證什麼
----------
- 只認**看起來像路徑**的字串（含 `/`、有已知副檔名）。`AGENTS.md`、`BACKLOG.md`
  這種根目錄裸檔名不掃——掃了會把散文裡每一句「見 xxx.md」都變成候選，誤報淹掉真報。
- 判準 1 的代價：**整個頂層目錄被刪掉的時候，指向它的引用會安靜地不被檢查**。
  換句話說這條檢查抓得到「檔案搬走了」，抓不到「整個目錄沒了」。
- 只查存不存在，不查內容對不對。指向一個存在但講別件事的檔案，這裡是綠的。
- 判準 5 的代價：**提案還開著的期間，它裡面指向既有檔案的路徑打錯也不會被抓到。**
  這是為了「提案不必為了過 CI 而扭曲寫法」換來的，不是忘了。
"""
from __future__ import annotations

import os
import re

# 至少一層目錄 + 已知副檔名。
_PATH_RE = re.compile(
    r"(?<![\w./-])"
    r"((?:[A-Za-z_][\w.-]*/)+[\w.-]+\.(?:md|py|ya?ml|json|jsonl|css|html|txt|sh))"
)

# 判準 3：產物目錄。
ARTIFACT_DIRS = ("_probe/", "_github/", "_corpus/", "_evidence_raw/", "dist/",
                 "Events/", "Sources/", "Tracks/", "Actors/", "_dashboards/")

# 判準 5：還沒動工的提案。放在這個目錄、而且 frontmatter 的 `status` 還在下面那個
# 集合裡的文件，指向不存在的檔案不算斷鏈——那是它**要造的東西**，不是它引用的。
PROPOSAL_DIRS = ("docs/design/",)
#: 豁免只在這幾個狀態下成立。**這是刻意讓豁免會過期的機制**：提案落地之後把
#: status 改掉，檢查立刻回來，那時候還指不到的路徑就是真的斷鏈。一個永不過期的
#: 豁免等於把整個目錄從檢查裡拿掉，而「白名單會腐爛」正是本檔開頭在避免的事。
PROPOSAL_STATUSES = frozenset({"proposal", "review", "draft"})

_STATUS_RE = re.compile(r"^status:\s*([A-Za-z_-]+)\s*$", re.M)

SCAN_EXT = (".md", ".py", ".yaml", ".yml")

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".obsidian",
             "_corpus", "_evidence_raw", "dist", "_probe", "_github",
             "Events", "Sources", "Tracks", "Actors", "_dashboards",
             "_to_delete", "_git_lock_trash"}


def extract(text):
    """→ 這段文字裡出現的候選路徑（去重、保留出現順序）。"""
    seen, out = set(), []
    for m in _PATH_RE.finditer(text):
        p = m.group(1)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def is_artifact(path):
    """判準 3。"""
    return path.startswith(ARTIFACT_DIRS)


def is_placeholder(path):
    """判準 4：單字母檔名（`scripts/x.py`）是在示範格式，不是引用。"""
    return len(os.path.splitext(os.path.basename(path))[0]) <= 1


def is_open_proposal(referrer, text):
    """判準 5：這個檔案是**還沒動工的提案**嗎。

    設計提案照定義就會寫滿它要造的檔案。把那些判成斷鏈，會逼提案作者為了讓
    CI 綠而把路徑寫成不是路徑的樣子——2026-07-27 就發生過：一份提案的 11 處
    寫法讓 selftest 常紅，而 `mutate.py` 要求乾淨基線才肯跑，結果**每個動到
    `scripts/` 的 PR 都合不進去**，整個變異安全網停擺一天，沒有任何東西指出成因。

    豁免綁在 `status` 上而不是只綁目錄，是為了讓它**會過期**：提案落地後把
    status 改掉，檢查立刻回來。代價寫清楚——**提案還開著的期間，它裡面指向
    既有檔案的路徑打錯也不會被抓到**。這是換來的，不是忘了。
    """
    if not referrer.startswith(PROPOSAL_DIRS):
        return False
    m = _STATUS_RE.search(text)
    return bool(m) and m.group(1).strip().lower() in PROPOSAL_STATUSES


def resolves(root, referrer, path):
    """判準 1＋2：這個候選指得到東西嗎？

    先問「這個字串到底有沒有在指本 repo」（判準 1）：第一段要嘛是 repo 頂層真的有
    的名字，要嘛在**寫它的那個檔案旁邊**真的有。兩邊都沒有 → 回 True，不管它。
    有的話，同樣兩個起點各試一次完整路徑（判準 2）。

    判準 1 那個「旁邊」不能漏：`scripts/pulse-probe.py` 裡寫 `lib/sources.py`，
    頂層沒有 `lib/`——只看頂層的話，這種引用會在第一關就被當成「不是 repo 路徑」
    放掉，判準 2 永遠走不到，而 repo 裡三分之二的路徑引用都長這樣。
    """
    here = os.path.dirname(os.path.join(root, referrer))
    head = path.split("/", 1)[0]
    if not (os.path.exists(os.path.join(root, head))
            or os.path.exists(os.path.join(here, head))):
        return True
    return (os.path.exists(os.path.join(root, path))
            or os.path.exists(os.path.join(here, path)))


def scan_files(root):
    """→ 要掃的檔案清單（repo 相對路徑）。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(SCAN_EXT):
                rel = os.path.relpath(os.path.join(dirpath, fn), root)
                out.append(rel.replace(os.sep, "/"))
    return out


def dead(root, files=None):
    """→ [(引用它的檔案, 指到的路徑)]，排序過、去重過。"""
    files = scan_files(root) if files is None else files
    bad = []
    for rel in files:
        try:
            text = open(os.path.join(root, rel), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if is_open_proposal(rel, text):
            continue
        for p in extract(text):
            if is_artifact(p) or is_placeholder(p):
                continue
            if not resolves(root, rel, p):
                bad.append((rel, p))
    return sorted(set(bad))
