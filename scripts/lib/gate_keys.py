# -*- coding: utf-8 -*-
"""gate_keys.py — 機械列舉 gate.yaml 的每一個 leaf key，比對它旁邊的標記。

規格：references/gate-config-status.md 的「這份清單怎麼不腐爛」。改這裡之前先改
那裡（紅線 9）。那一節也寫了這條檢查**不保證**什麼，別把它讀成靜態分析。

存在的理由只有一句：上一版的未接線清單是人手寫的，所以「清單漏了誰」沒有人在管。
列舉改成機械的之後，漏標一個 key 就是 CI 紅，不是一個沒有人會發現的省略。

不讀磁碟、不讀時鐘、不呼叫任何模型——輸入是文字，輸出是資料。
"""
from __future__ import annotations

import re

# key 那一行：縮排 + key 名 + 冒號。list item（- foo）不算 key。
_KEY_LINE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:(?P<rest>.*)$")

# 標記兩種。⚠ 是刻意要求的：不能只在散文裡順口提到「未接線」三個字。
_UNWIRED_MARK = re.compile(r"⚠[^\n]*未接線")
# 「消費者：scripts/x.py」「消費者: scripts/x.py」都收；抓到路徑為止。
_CONSUMER_MARK = re.compile(r"消費者\s*[：:]\s*(?P<path>[A-Za-z0-9_./-]+\.py)")


def _comment_of(line: str) -> str:
    """一行裡屬於註解的部分（沒有就回空字串）。

    只找第一個 #。gate.yaml 沒有值裡帶 # 的情況，真的出現時會誤判成註解——
    誤判的方向是「以為有標記」，所以這裡刻意只吃 `#` 之後、且要求 ⚠ 或「消費者：」
    才算數，一個普通的井字號不會變成標記。
    """
    i = line.find("#")
    return line[i:] if i >= 0 else ""


def parse(text: str):
    """回傳 [{path, key, line, unwired, consumers}]，每個 **leaf** key 一筆。

    leaf = 它底下沒有更深一層的 key（純量、list、或空 mapping）。
    標記由「自己那一行的註解」加上「緊貼在它上面的連續註解區塊」決定，
    並且**向下繼承**：整塊標一次，底下每個 leaf 都算被標到。
    """
    lines = text.splitlines()

    # 第一遍：找出所有 key 行與它們的縮排。
    entries = []
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("#") or not ln.strip():
            continue
        m = _KEY_LINE.match(ln)
        if not m:
            continue
        entries.append({"i": i, "indent": len(m.group("indent")), "key": m.group("key"),
                        "rest": m.group("rest")})

    out = []
    for n, e in enumerate(entries):
        # 這一筆的標記文字：自己那行的註解 + 上方連續註解區塊。
        blob = [_comment_of(lines[e["i"]])]
        j = e["i"] - 1
        while j >= 0 and lines[j].lstrip().startswith("#"):
            blob.append(lines[j])
            j -= 1
        blob = "\n".join(blob)
        e["unwired"] = bool(_UNWIRED_MARK.search(blob))
        e["consumers"] = [m.group("path") for m in _CONSUMER_MARK.finditer(blob)]

        # 有沒有更深一層的 key 直接跟在後面 → 不是 leaf。
        nxt = entries[n + 1] if n + 1 < len(entries) else None
        e["leaf"] = not (nxt and nxt["indent"] > e["indent"])

    # 第二遍：把祖先的標記繼承下來，並組出 dotted path。
    stack = []  # [(indent, key, unwired, consumers)]
    for e in entries:
        while stack and stack[-1][0] >= e["indent"]:
            stack.pop()
        path = ".".join([s[1] for s in stack] + [e["key"]])
        if e["leaf"]:
            unwired = e["unwired"] or any(s[2] for s in stack)
            consumers = list(e["consumers"])
            for s in stack:
                consumers += s[3]
            # 記下標記實際掛在哪一層：驗證要在那一層做，不是在 leaf 做。
            # 取**最外層**帶同一種標記的祖先（沒有就是自己）。取最外層是刻意的：
            # 整塊標一次的時候，內層 leaf 常常叫 enabled / action 這種到處都有的
            # 名字，拿它去搜碼遲早會誤判成「有人在讀」。誤判會被下一個人用改寫
            # 繞過去，然後這條檢查就變成一顆永遠綠的燈。代價寫在規格的
            # 「這條檢查不保證什麼」：block 標記只驗證到 block 那一層。
            levels = [(s[1], s[2], s[3]) for s in stack] + [(e["key"], e["unwired"], e["consumers"])]
            want_unwired = unwired
            marked_at = None
            for name, u, c in levels:
                if (u if want_unwired else c):
                    marked_at = name
                    break
            out.append({"path": path, "key": e["key"], "line": e["i"] + 1,
                        "unwired": unwired, "consumers": sorted(set(consumers)),
                        "marked_at": marked_at})
        stack.append((e["indent"], e["key"], e["unwired"], e["consumers"]))
    return out


def name_in_code(name: str, blob: str) -> bool:
    """這個 key 名有沒有以**字串常值**出現在碼裡。

    刻意不用純子字串：`require_primary_evidence` 出現在 lib/sources.py 的一句
    註解裡，純子字串比對會判它「有消費者」——註解不是消費者。
    """
    return re.search(r"[\"']" + re.escape(name) + r"[\"']", blob) is not None


def unmarked(leaves) -> list[str]:
    """兩種標記都沒有的 leaf。這是上一版缺的那個方向，回非空就該紅。"""
    return [e["path"] for e in leaves if not e["unwired"] and not e["consumers"]]


def wired_but_marked_unwired(leaves, blob) -> list[str]:
    """標了未接線、卻真的有人在讀。有人去接線了就該回來改標記。"""
    seen, bad = set(), []
    for e in leaves:
        if not e["unwired"] or not e["marked_at"] or e["marked_at"] in seen:
            continue
        seen.add(e["marked_at"])
        if name_in_code(e["marked_at"], blob):
            bad.append(e["marked_at"])
    return bad


def consumer_missing(leaves, read_file) -> list[str]:
    """標了消費者、但指名的檔案不存在或裡面搜不到這個 key 名。

    read_file(path) -> str｜None（None = 檔案不存在）。IO 由呼叫端注入，
    這支模組本身不碰磁碟。
    """
    seen, bad = set(), []
    for e in leaves:
        if e["unwired"] or not e["consumers"] or not e["marked_at"]:
            continue
        if e["marked_at"] in seen:
            continue
        seen.add(e["marked_at"])
        for path in e["consumers"]:
            text = read_file(path)
            if text is not None and name_in_code(e["marked_at"], text):
                break
        else:
            bad.append(f"{e['marked_at']} → {','.join(e['consumers'])}")
    return bad
