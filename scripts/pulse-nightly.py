#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-nightly.py — 夜班的階段機器（確定性；零 LLM）。

`enrich-runbook.md` 是一份 356 行的散文，它要求執行的那一方照著跑十七步，而其中
十幾步是純腳本。於是夜班每一晚都在做同一件事：讀那份散文、判斷現在該跑哪一支、
讀它的 exit code、決定那個數字是「沒事」「沒東西」還是「出事了」。**那是把確定性
工作交給模型**，而這個 repo 記錄過的夜班事故幾乎全長在這一層：

    2026-08-12  prep 沒跑，拿上一班留在 repo 裡的 worklist 把昨天已潤好的 10 則
                整批重寫，當天該潤的 7 則一則沒碰，而 commit 訊息看起來很正常
    2026-08-16  digest-prep 跑在 gate 之前，挑不到東西**而且不報錯**
    2026-07-28  github-desc-apply 回 3（收到了但一條都沒過關）被寫成「今晚沒東西要翻」
    2026-07-24  Actions 誤點 96 分，潤稿端 clone 到昨天的 repo，整晚「正常無事」
    2026-09-20  雲端排程（claude.ai/code/routines）把 session 的工作樹 checkout 在
                一支臨時分支上，不是 main。commit 那一關擋得住，但擋下來時敘述
                工作早就寫完了，一整晚的成本全部作廢；前兩晚能推上 main 是寫作端
                自己讀了這支檔案的碼、臨時 checkout 才過的，不是機制保證的

這一支把順序、exit code 判讀、交棒對帳、摘要組裝拿回碼裡。**它不取代 runbook**：
寫的那一方仍然照 runbook 寫六層 prose 與每日精選，這裡只拿走不該由模型每晚重做
一次的東西。規格與階段表在 references/nightly-driver.md。

用法：
    VAULT_DIR=/path/to/ai-pulse python3 scripts/pulse-nightly.py run [--no-push]
    VAULT_DIR=... python3 scripts/pulse-nightly.py status
    VAULT_DIR=... python3 scripts/pulse-nightly.py summary

離開碼：
    0   這一輪跑完了
    1   跑完了，但有事要人看（退件、拒寫、壞檔）
    2   壞了，停住
    10  **還沒完，等你寫東西**（停在 narrative 階段）

10 是刻意跟 0/1/2 分開的：排程那一層要寫得出「跑 → 寫 → 再跑」的迴圈，而
「等你」跟「跑完了」在 shell 裡必須分得開。

依賴：標準函式庫 ＋ lib.clock（時區的單一真相源）、lib.atomicwrite。
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md
from lib.atomicwrite import atomic_write_text  # noqa: E402  見 references/atomic-writes.md
from lib.identity import NIGHT_SHIFT_AUTHOR  # noqa: E402  夜班 commit 身份單一真相源

STATE_REL = ("_probe", "nightly-run.json")

# 資料 commit 的白名單。CONTRIBUTING.md〈兩條路，別走錯〉逐路徑列過，這裡是它的
# 可執行版本：夜班只准推這些。碰到白名單以外的改動就停住，**不是因為那個改動一定
# 是錯的，是因為夜班沒有審它的能力**——碼、CI、_config 的判斷邏輯走 PR，那條規矩
# 不因為現在是半夜就改變。
DATA_PREFIXES = ("_corpus/", "_probe/", "Events/", "Sources/", "_dashboards/",
                 "Tracks/", "Actors/", "Digests/", "_github/", "dist/")
# 這兩個檔是「人跟機器都會寫」的：sources.yaml 只有 lifecycle/robots_ok 兩欄歸鏈，
# narratives.yaml 只有 now/next 兩段歸鏈。欄位級的界線這裡驗不了，由各自的 apply
# 腳本保證（它們只寫那幾欄）。
DATA_FILES = ("_config/sources.yaml", "_config/narratives.yaml")

# 五段敘述工作交棒時寫在 repo 根目錄的產物。這幾個檔只該在同一輪的兩次 `run`
# 之間短暫存在——2026-09-15 一次手動實跑後忘了收，本機排程往後三晚（09-19～09-21）
# 都拿它們當成「這一輪的結果」對帳，一直卡在 enrich-write。見 do_align()。
ROOT_RESULT_FILES = ("enrich-result.json", "digest.json", "narrative-result.json",
                      "title-zh-result.json", "github-desc-result.json")


def stages(date_str):
    """整條夜班鏈。順序就是 runbook 的順序，依賴寫在 requires。

    分開成函式而不是模組常數，因為 commit 訊息要帶當天日期，而日期是跑的時候才知道的。

    子行程一律用 sys.executable，不寫死 "python3"：2026-09-18 發現外殼與這支
    driver 各自解析一次 PATH 上的 python3，兩邊可能解析到不同直譯器（互動 shell
    裝了套件的那支 vs. launchd 環境找到的系統 3.9）。子行程改成沿用啟動 driver
    那支直譯器，PATH 换成哪一支都只有一個地方要對，不必兩邊同步維護。見
    nightly-shell.sh 的 PY= 那行與 references/nightly-driver.md。
    """
    def apply_stage(sid, script, infile, codes, needs):
        # apply 一定是「產出依賴」：它的 narrative 那一段被跳過，就沒有 result 檔可寫回。
        return {"id": sid, "kind": "run", "needs": needs, "dry_first": True,
                "cmd": [sys.executable, f"scripts/{script}", "--in", infile], "codes": codes}

    return [
        # 平台的雲端排程把 session checkout 在一支臨時分支上，不是 main（2026-09-20）；
        # 排在最前面，讓「跑在哪一支」在花任何一分錢寫敘述之前就定案——不然要等到
        # commit 那一關才發現，那時候敘述工作早就寫完了，整晚白做。前面沒有東西可以
        # stop（它是第一步），不需要 after/needs，跟 render 靠「前面 stop 直接終止
        # 整輪」是同一個道理。
        {"id": "align-main", "kind": "align"},
        {"id": "precheck", "kind": "precheck"},
        {"id": "enrich-prep", "kind": "run", "after": ["precheck"],
         "cmd": [sys.executable, "scripts/pulse-enrich-prep.py"],
         "codes": {0: "ok", 2: "stop"}, "summary_grep": "pulse-enrich-prep"},
        {"id": "enrich-write", "kind": "narrative", "needs": ["enrich-prep"],
         "worklist": "_probe/enrich-worklist.json", "items": None, "key": "id",
         "result": "enrich-result.json", "check": "keyed",
         "rules": "scripts/enrich-runbook.md〈流程 步驟 2-3〉與〈speak-human-tw 規則摘要〉",
         "produces": "dict keyed by event_id，六層 prose ＋ category/track/keywords/company"},
        apply_stage("enrich-apply", "pulse-enrich-apply.py", "enrich-result.json",
                    {0: "ok", 1: "noted"}, ["enrich-write"]),
        {"id": "gate", "kind": "run", "after": ["enrich-apply"],
         "cmd": [sys.executable, "scripts/pulse-gate.py"], "codes": {0: "ok", 2: "stop"}},
        {"id": "dashboard", "kind": "run", "needs": ["gate"],
         "cmd": [sys.executable, "scripts/pulse-dashboard.py"], "codes": {0: "ok", 1: "stop"}},
        # 這一條的 requires 是 2026-08-16 那次事故的本體：digest-prep 挑的是「今晚
        # 通過門禁上線」的事件，gate 沒跑就挑不到，而它不會報錯，只會安靜產出空清單。
        {"id": "digest-prep", "kind": "run", "needs": ["gate"],
         "cmd": [sys.executable, "scripts/pulse-digest-prep.py"],
         "codes": {0: "ok"}, "summary_grep": "素材="},
        {"id": "digest-write", "kind": "narrative", "needs": ["digest-prep"],
         "worklist": "_probe/digest-worklist.json", "items": "items", "key": "id",
         "result": "digest.json", "check": "single",
         "rules": "references/digest-apply.md（schema 與退件規則以那份為準）"
                  "、references/digest-framework.md〈四、空日〉",
         "produces": "一份分層 JSON：sections[] 一段一層（A 證據／B 背景／C 推論／D 原文未取用）",
         "write_when_empty": True},
        # digest 這兩條的「不擋 push」是 runbook 寫明的過渡期豁免：Digests/ 還沒有
        # 下游消費者。豁免不等於靜音，結果照樣進摘要與狀態檔。
        apply_stage("digest-apply", "pulse-digest-apply.py", "digest.json",
                    {0: "ok", 1: "noted", 2: "noted"}, ["digest-write"]),
        {"id": "digest-gate", "kind": "run", "after": ["digest-apply"],
         "cmd": [sys.executable, "scripts/pulse-digest-gate.py"],
         "codes": {0: "ok", 1: "noted"}, "summary_grep": "draft="},
        {"id": "narrative-prep", "kind": "run", "needs": ["gate"],
         "cmd": [sys.executable, "scripts/pulse-narrative-prep.py"],
         "codes": {0: "ok", 2: "stop"}, "summary_grep": "pulse-narrative-prep"},
        {"id": "narrative-write", "kind": "narrative", "needs": ["narrative-prep"],
         "worklist": "_probe/narrative-worklist.json", "items": None, "key": "slug",
         "result": "narrative-result.json", "check": "keyed",
         "rules": "scripts/enrich-runbook.md〈C. 主線敘事刷新〉",
         "produces": '{"<track-slug>": {"now": "...", "next": "..."}}，只放 dirty 主線；'
                     "thesis 與 lenses 不要動"},
        apply_stage("narrative-apply", "pulse-narrative-apply.py", "narrative-result.json",
                    {0: "ok", 1: "noted", 2: "stop"}, ["narrative-write"]),
        # C2／C3 的 prep 是 Actions 那班做的，夜班只讀清單。所以這兩段的 worklist
        # **不存在**跟**是空陣列**要分開記：前者代表抓取鏈出事，後者是今晚沒東西要翻。
        {"id": "github-desc-write", "kind": "narrative",
         "worklist": "_probe/github-desc-worklist.json", "items": None, "key": "full_name",
         "result": "github-desc-result.json", "check": "keyed",
         "rules": "scripts/enrich-runbook.md〈C2〉：只翻 desc 那句、≤60 字、專有名詞留原文",
         "produces": '{"<owner/repo>": "中文描述"}',
         "absent_note": "Actions 那班沒有準備清單（抓取鏈那邊出事，不是今晚沒東西要翻）"},
        apply_stage("github-desc-apply", "pulse-github-desc-apply.py",
                    "github-desc-result.json",
                    {0: "ok", 2: "noted", 3: "noted"}, ["github-desc-write"]),
        {"id": "title-write", "kind": "narrative",
         "worklist": "_probe/title-zh-worklist.json", "items": None, "key": "id",
         "result": "title-zh-result.json", "check": "keyed",
         "rules": "scripts/enrich-runbook.md〈C3〉：只翻標題、≤40 字、版本號與產品名一個字都不要動",
         "produces": '{"<event_id>": "中文標題"}',
         "absent_note": "Actions 那班沒有準備清單（抓取鏈那邊出事，不是今晚沒東西要翻）"},
        apply_stage("title-apply", "pulse-title-apply.py", "title-zh-result.json",
                    {0: "ok", 1: "noted", 2: "stop"}, ["title-write"]),
        {"id": "render", "kind": "run",
         "cmd": [sys.executable, "scripts/pulse-render.py"], "codes": {0: "ok"}},
        {"id": "commit", "kind": "commit", "after": ["render"],
         "message": f"nightly: enrich + narrative {date_str}", "date": date_str},
        # --top 5，**不准帶警報旗標**：判準讀本地 git log，在 push 之前它會讀到自己
        # 剛建、還沒推出去的那顆然後回一盞綠燈。理由全文見 references/health-alarms.md。
        {"id": "monitor", "kind": "run",
         "cmd": [sys.executable, "scripts/pulse-monitor.py", "--top", "5"],
         "codes": {0: "ok"}, "summary_full": True},
    ]


# ── 純函式（可離線單測）────────────────────────────────────────────────

def code_action(code, codes):
    """exit code → 動作。表裡沒有的一律 stop。

    **沒有預設的「當成 ok」**：一個沒被寫進表的離開碼，意思是這支腳本長出了一種
    這份規格還不認得的結局。把它當成沒事，就是 2026-07-28 那次「25 條全退被寫成
    今晚沒東西要翻」的形狀。
    """
    return codes.get(code, "stop")


def worklist_keys(doc, items_field, key_field):
    """worklist → (筆數, key 集合)。形狀壞掉時回 (0, set())，不猜。"""
    rows = doc if items_field is None else (doc or {}).get(items_field)
    if not isinstance(rows, list):
        return 0, set()
    return len(rows), {r.get(key_field) for r in rows if isinstance(r, dict)}


def check_result(obj, keys, mode):
    """收回來的 result 對不對得上這一輪的 worklist。回 (ok, 理由)。

    第二條是 2026-08-12 那次事故的補丁：那一晚用的 worklist 是上一班留在 repo 裡的，
    而它躺在那裡是因為它進版控，不是因為它是今天的。
    """
    if mode == "single":
        if not isinstance(obj, dict) or not obj:
            return False, "結果不是一個非空的物件"
        return True, ""
    if not isinstance(obj, dict):
        return False, "結果不是 dict keyed by id"
    if not obj:
        return False, "結果是空的（worklist 非空卻一則都沒寫）"
    extra = sorted(set(obj) - keys)
    if extra:
        return False, ("結果有 worklist 以外的 key：" + "、".join(extra[:5])
                       + "——最可能是拿到上一班留下的清單")
    return True, ""


def total_cost(state):
    """這一輪到目前為止花了多少錢（USD）。回 (總額, 有沒有量到)。

    **量不到跟 0 不一樣。** 一晚沒叫過寫作端（每一段都跳過）是真的 0；外殼沒把數字
    傳回來是量不到。兩者在摘要上要看得出差別，否則「這條鏈很便宜」跟「沒有人在量」
    長得一模一樣——那是這個 repo 記過很多次的形狀。
    """
    vals = [st.get("cost_usd") for st in state.get("stages", [])
            if st.get("cost_usd") is not None]
    asked = [st for st in state.get("stages", []) if st.get("status") == "ok"
             and st.get("id", "").endswith("-write")]
    if not vals:
        return 0.0, not asked
    return round(sum(vals), 4), True


def calls_in(source, func_name, inside):
    """`inside` 這個函式裡有沒有呼叫 `func_name`。走 ast，不走字串比對。

    **純函式測得再好，呼叫端沒接上照樣全綠。** 這個 repo 記過六次同一個形狀：
    規矩寫在一個地方，新接上來的消費者沒有一起接到，而兩邊在規則沒動過的日子裡
    給一模一樣的答案。2026-09-15 寫這支的時候當場又踩到一次：把 `advance()` 裡的
    `keeps_output(...)` 換成寫死的條件，`keeps_output` 自己的測試一條都沒紅。
    """
    import ast as _ast
    for node in _ast.walk(_ast.parse(source)):
        if isinstance(node, _ast.FunctionDef) and node.name == inside:
            for sub in _ast.walk(node):
                if (isinstance(sub, _ast.Call) and isinstance(sub.func, _ast.Name)
                        and sub.func.id == func_name):
                    return True
            return False
    return False


def keeps_output(spec, status):
    """這一段跑完之後，完整輸出要不要留在狀態檔裡。純函式。

    `noted` ＝「跑了，有事要人看」。只記一句 `rc=1` 的話，人看摘要知道有事、**不知道
    是什麼事**——而 runbook 步驟 18 要的是「各退件幾條、為什麼」。2026-09-15 第一次
    實跑就踩到：`title-apply` 回 1，摘要上只有 `rc=1`，退件理由（一則超過 40 字、
    一則清單是舊的）全部不見了。
    """
    return bool(spec.get("summary_full") or status == "noted")


def summary_lines(state):
    """從狀態檔組收尾摘要。

    runbook 步驟 18 列了六七行必須貼進摘要的輸出，漏掉 prep 那一行就**證明不了
    清單是今晚產的**。由碼組就不會漏，也不會有人「順手簡化」。
    """
    out = [f"夜班摘要 {state.get('date')}（{'跑完' if state.get('finished') else '未完'}）"]
    for st in state.get("stages", []):
        note = (st.get("note") or "").strip()
        out.append(f"  {st['id']:<19} {st['status']:<8} {note}".rstrip())
    cost, measured = total_cost(state)
    out.append(f"  {'寫作端成本':<19} {'USD ' + format(cost, '.4f') if measured else '**量不到**（外殼沒有把數字傳回來）'}")
    tail = [st.get("full_output") for st in state.get("stages", []) if st.get("full_output")]
    for t in tail:
        out.append("")
        out.append(t.rstrip())
    return out


def dirty_outside_data(porcelain):
    """`git status --porcelain` → 不在資料白名單裡的路徑。純函式。"""
    bad = []
    for line in (porcelain or "").splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:                      # rename：看目的地
            path = path.split(" -> ", 1)[1].strip().strip('"')
        if path.startswith(DATA_PREFIXES) or path in DATA_FILES:
            continue
        bad.append(path)
    return bad


# ── 副作用 ────────────────────────────────────────────────────────────

def load_state(vault):
    p = vault.joinpath(*STATE_REL)
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text("utf-8"))
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def save_state(vault, state):
    state["updated_at"] = clock.utc_stamp()
    p = vault.joinpath(*STATE_REL)
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(p, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def run(vault, cmd):
    r = subprocess.run(cmd, cwd=str(vault), capture_output=True, text=True,
                       env={**os.environ, "VAULT_DIR": str(vault)})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def grep_line(text, needle):
    for line in text.splitlines():
        if needle in line:
            return line.strip()
    return ""


def stage_record(state, sid):
    for st in state["stages"]:
        if st["id"] == sid:
            return st
    return None


def set_stage(state, sid, status, note="", **extra):
    st = stage_record(state, sid)
    if st is None:
        st = {"id": sid}
        state["stages"].append(st)
    st.update({"status": status, "note": note, "at": clock.utc_stamp()}, **extra)
    return st


def requires_ok(state, spec):
    """前置有沒有成立。回 (ok, 為什麼不成立)。

    **依賴有兩種，混成一種會讓整條鏈在最平常的夜晚停掉。**

        after  順序依賴：前面那一段沒壞就往下走。前面被跳過是正常的。
        needs  產出依賴：前面那一段必須真的產出了東西，否則這一段無事可做。

    多數夜晚 `enrich-worklist` 是空的（沒有新事件要潤），那一晚 `enrich-write` 與
    `enrich-apply` 都會 skipped。若 `gate` 也算成「前置沒產出」而跟著跳過，
    dashboard、digest、narrative、render 會一路連帶跳掉，**整條鏈在最平常的一晚
    等於沒跑**，而狀態檔上每一格都寫著 skipped，看起來像一切正常。

    反過來 `digest-prep` 對 `gate` 就是 needs：它挑的是「今晚通過門禁上線」的事件，
    gate 沒真的跑過就挑不到東西，而且不會報錯（2026-08-16）。
    """
    for rid in spec.get("after", []):
        r = stage_record(state, rid)
        if r is not None and r["status"] == "stop":
            return False, f"前置 {rid} 停住了"
    for rid in spec.get("needs", []):
        r = stage_record(state, rid)
        if r is None:
            return False, f"前置 {rid} 還沒跑"
        if r["status"] not in ("ok", "noted"):
            return False, f"前置 {rid} 沒有產出（{r['status']}）"
    return True, ""


def do_precheck(vault, date_str):
    """runbook 步驟 0：今晚的資料到底進來了沒。**沒進來就停，不補抓。**

    這條鏈跟 Actions 靠觸發順序耦合：夜班要在 `data-refresh.yml` 收工之後才開跑。
    比它早到就是拿昨天的 repo，worklist 空，整晚看起來「正常無事」（2026-07-24）。

    2026-09-24 以前，這裡看到今日 corpus 不在會自己補跑 robots-recheck → probe →
    score → cluster。那條後路是在本機設計的，本機網路全通；搬到雲端排程之後，
    09-23 那次補跑 33 條來源只有 2 條回 200，而且跟 Actions 抓的是同一天：
    撞到 Actions 就 push 被拒（09-22、09-23），沒撞到就把殘缺語料推上 main
    （09-17、09-21）。所以補跑在雲端只要走到就是壞的，改成停下來指名缺哪一天。

    stop 不寫 finished，同一個 UTC 日稍後再觸發一次會重新判斷。重新判斷不等於重新拉
    資料：雲端每次觸發是全新 clone；同一個工作樹手動重跑要先自己 git pull，這裡不拉
    （align-main 一輪只跑一次，站在 main 上也不 fetch）。什麼時候觸發是
    排程那一層的責任，規格見 references/nightly-driver.md〈precheck：語料沒到就停，不補抓〉。
    """
    # 看 probe 報告，不看 _corpus/<date>/：整班 304／0 筆時 probe 不建 corpus 目錄，
    # 但報告照寫、exit 0。拿目錄當證據會把合法的空班誤判成 Actions 還沒到（Codex review）。
    if (vault / "_probe" / date_str / "report.md").is_file():
        return "ok", f"今日 probe 已就緒（_probe/{date_str}/report.md）", ""
    return "stop", (f"今日語料還沒到（`_probe/{date_str}/report.md` 不存在）：Actions 那班還沒"
                    "把語料推上 main，夜班不自己補抓——雲端補抓只連得到少數來源，而且跟"
                    "Actions 抓同一天，push 必然衝突（2026-09-22、09-23）。先查 data-refresh.yml"
                    "那一班有沒有跑完、有沒有推上去，再重新觸發夜班（同一個工作樹手動重跑要先"
                    "`git pull --ff-only`，driver 不替你拉）"), ""


def do_narrative(vault, spec, recorded):
    """交棒點。回 (status, note, extra)。"""
    wl = vault / spec["worklist"]
    if not wl.exists():
        return "absent", spec.get("absent_note", f"{spec['worklist']} 不存在"), {}
    try:
        doc = json.loads(wl.read_text("utf-8"))
    except ValueError as e:
        return "stop", f"{spec['worklist']} 不是合法 JSON：{e}", {}
    count, keys = worklist_keys(doc, spec["items"], spec["key"])
    mtime = int(wl.stat().st_mtime)
    meta = {"path": spec["worklist"], "count": count, "mtime": mtime}

    res = vault / spec["result"]
    if not res.exists():
        if count == 0 and not spec.get("write_when_empty"):
            return "skipped", "清單是空的（今晚沒有東西要做）", {"worklist": meta}
        return "waiting", f"等 {spec['result']}（清單 {count} 筆）", {"worklist": meta}

    # 收回來了。先確認清單沒在交棒之後被換掉。
    old = (recorded or {}).get("worklist")
    if old and (old.get("count") != count or old.get("mtime") != mtime):
        return "stop", (f"{spec['worklist']} 在交棒之後被重寫過"
                        f"（交棒時 {old.get('count')} 筆／{old.get('mtime')}，"
                        f"現在 {count} 筆／{mtime}）——結果對不上這一輪的清單"), {}
    try:
        obj = json.loads(res.read_text("utf-8"))
    except ValueError as e:
        return "stop", f"{spec['result']} 不是合法 JSON：{e}", {}
    ok, why = check_result(obj, keys, spec["check"])
    if not ok:
        return "stop", f"{spec['result']} {why}", {}
    if spec["check"] == "single":
        # 這一段的產物是一篇文章，不是 dict keyed by id。印它的頂層欄位數會讓人
        # 以為寫了 N 則，那是個看起來像資料的假數字。
        return "ok", f"收到 {spec['result']}（素材 {count} 則）", {"worklist": meta}
    return ("ok", f"收到 {spec['result']}（{len(obj)} 筆，清單 {count} 筆）",
            {"worklist": meta})


def narrative_handoff(spec, count):
    """停下來的時候印什麼。**規則本身不複製過來**，只指到 runbook。"""
    return "\n".join([
        f"[narrative] {spec['id']}",
        f"  清單：{spec['worklist']}（{count} 筆）",
        f"  規則：{spec['rules']}",
        f"  產出：{spec['result']}　{spec['produces']}",
        "  紅線：判斷不由你決定發不發、只依證據不編造、去 AI 口吻"
        "（scripts/enrich-runbook.md 開頭三條）",
        f"  寫完再跑一次 `python3 scripts/pulse-nightly.py run`，它會從這裡接回去。",
    ])


def on_target_branch(vault, target="main"):
    """現在站在目標分支上嗎。回 (是不是, 實際在哪一支)。

    **這條擋的是 2026-09-11 那次事故的另一半。** 那一晚夜班把活做完、commit 也建了，
    但它落在一支 session 自己的分支上，沒有到 main，三天沒有人知道。排程跑的是本機
    工作樹，而工作樹會停在人上次切過去的地方——某支 feature 分支、某次 review 的
    detached HEAD 都算。夜班沒有能力判斷那支分支該不該收，所以不猜，停下來。
    """
    r = subprocess.run(["git", "-C", str(vault), "rev-parse", "--abbrev-ref", "HEAD"],
                       capture_output=True, text=True, timeout=20)
    cur = (r.stdout or "").strip()
    return cur == target, (cur or "量不到")


def clean_stale_results(vault):
    """開新的一輪之前，清掉根目錄殘留的敘述產物。回傳真的刪掉的檔名。

    `ROOT_RESULT_FILES` 只該在同一輪的兩次 `run` 之間短暫存在。這支只在
    `align-main` 裡被呼叫一次（見 main() 的一輪一次保證），不會刪到正在交棒中的
    檔——那些檔在同一天稍晚的呼叫根本不會再走到這裡，align-main 已經被記成
    ok／noted，直接跳過。**清掉的東西也要留痕**，回傳清單讓呼叫端寫進 note，
    不要默默刪掉：「今天特別乾淨」跟「有東西被默默清掉」在摘要上不能長得一樣。
    """
    removed = []
    for name in ROOT_RESULT_FILES:
        p = vault / name
        if p.exists():
            p.unlink()
            removed.append(name)
    return removed


def do_align(vault, target="main"):
    """回到 target 分支、跟 origin 對齊，再清掉根目錄殘留的敘述產物。

    回 (status, note, full_output)。

    **這是 2026-09-20 才長出來的一關。** 雲端排程（claude.ai/code/routines）把
    session 的工作樹 checkout 在一支臨時分支上，不是 `main`。`do_commit()` 的
    `on_target_branch()` 檢查擋得住，但擋在 commit 那一步等於整晚白跑——敘述
    工作早就寫完、錢也花了，最後才發現推不上去。09-18、09-19 兩晚能推上 main，
    是那兩晚的寫作端自己讀了這支檔案的碼、臨時做了 `checkout main` 才過的，
    不是這支 driver 保證的；09-20 沒有人做這件事，就整晚作廢。把對齊挪到最前面，
    在花任何一分錢之前就把「跑在哪一支」定案。

    只在工作樹乾淨時切分支：站在別的分支又有未提交改動，代表有人正在用這個
    工作樹做別的事，driver 沒有能力判斷那些改動該留還是該丟，不猜，停下來——
    跟 `do_commit()` 的「地點錯了，內容再乾淨也是推到錯的地方」同一個判斷，
    只是這裡反過來：**內容不乾淨，連地點都不猜著換。**

    跟 `do_commit()` 不同的是失敗時不指名「哪個檔」，因為這裡還沒有夜班自己的
    改動可指——工作樹髒，代表髒的是**別人**留下的東西。
    """
    ok, cur = on_target_branch(vault, target)
    full = ""
    note_parts = []
    if not ok:
        rc, out = run(vault, ["git", "status", "--porcelain"])
        full += out
        if rc != 0:
            return "stop", f"git status 失敗 rc={rc}", full
        if out.strip():
            return "stop", (f"工作樹停在 `{cur}`（不是 `{target}`）且有未提交改動，"
                            "driver 不猜要不要丟棄，人工處理"), full
        rc, fout = run(vault, ["git", "fetch", "origin", target])
        full += fout
        if rc != 0:
            return "stop", f"git fetch origin {target} 失敗 rc={rc}", full
        rc, cout = run(vault, ["git", "checkout", target])
        full += cout
        if rc != 0:
            return "stop", f"git checkout {target} 失敗 rc={rc}", full
        rc, mout = run(vault, ["git", "merge", "--ff-only", f"origin/{target}"])
        full += mout
        if rc != 0:
            return "stop", (f"git merge --ff-only origin/{target} 失敗 rc={rc}"
                            f"（本地 {target} 落後或分歧到 fast-forward 不了，"
                            "人工處理）"), full
        note_parts.append(f"從 `{cur}` 切回 `{target}` 並 ff 到 origin/{target}")

    removed = clean_stale_results(vault)
    if removed:
        note_parts.append("清掉根目錄殘留的敘述產物：" + "、".join(removed))

    if not note_parts:
        return "ok", f"已在 `{target}`，根目錄沒有殘留的敘述產物", full
    return "noted", "；".join(note_parts), full


def do_commit(vault, spec, no_push):
    """git add -A ＋ 有變更才 commit ＋ push；push 失敗改推備援分支。

    兩道關，順序不能換：**先確認站在哪一支**，再擋白名單以外的改動。夜班的授權只到
    資料產物、只到 `main`；碼、CI、_config 的判斷邏輯走 PR，那條規矩不因為現在是
    半夜就改變。`git add -A` 這兩件事都不看，所以看在這裡。

    push 到 main 失敗時改推 `nightly/<UTC日期>-<short-sha>`，status 回 noted
    不是 stop——資料沒丟，只是要人手動併回 main。2026-09-18 加：雲端排程
    （claude.ai/code/routines）跑在拋棄式容器裡，commit 建了但 push 不出去，
    資料就跟著容器一起永久消失，2026-08-05、2026-09-11 兩次事故都是這個形狀。
    不沿用查無依據的舊 `claude/` 前綴——references/health-alarms.md 記過
    9 支同名殘留 ref 讓「未收分支」警報分不清哪些早就進了 main，這裡換一個
    可辨識、不會跟歷史命名混在一起的新前綴。規格見 references/nightly-driver.md。
    """
    ok, cur = on_target_branch(vault)
    if not ok:
        return "stop", (f"工作樹停在 `{cur}`，不是 `main`，夜班不推"
                        "——2026-09-11 那次成果落在 session 分支上三天沒人知道，"
                        "就是這個形狀"), ""
    rc, out = run(vault, ["git", "status", "--porcelain"])
    if rc != 0:
        return "stop", f"git status 失敗 rc={rc}", out
    bad = dirty_outside_data(out)
    if bad:
        return "stop", ("工作樹有資料白名單以外的改動，夜班不推："
                        + "、".join(bad[:8])
                        + "——碼與設定走 PR（CONTRIBUTING.md〈兩條路，別走錯〉）"), out
    rc, out = run(vault, ["git", "add", "-A"])
    if rc != 0:
        return "stop", f"git add 失敗 rc={rc}", out
    rc, _ = run(vault, ["git", "diff", "--cached", "--quiet"])
    if rc == 0:
        return "ok", "無變更，沒有東西要推", ""
    # 用夜班自己的身份，不吃工作樹的 local config。本機那份是 `ai-pulse-bot`，
    # 跟 Actions 那班同名——兩條鏈在作者欄上分不出來，而 night_shift_commit_days()
    # 的其中一個判準正是作者。`-c` 只影響這一次，不改工作樹的設定。
    rc, out = run(vault, ["git",
                          "-c", f"user.name={NIGHT_SHIFT_AUTHOR}",
                          "-c", f"user.email={NIGHT_SHIFT_AUTHOR}@users.noreply.github.com",
                          "commit", "-m", spec["message"]])
    if rc != 0:
        return "stop", f"git commit 失敗 rc={rc}", out
    sha_rc, sha = run(vault, ["git", "rev-parse", "--short", "HEAD"])
    sha = sha.strip() if sha_rc == 0 else "?"
    if no_push:
        return "noted", f"commit {sha}，**沒有 push**（--no-push）", out
    rc, pout = run(vault, ["git", "push"])
    if rc == 0:
        return "ok", f"commit {sha} 已推上 origin", out

    # main 推不上去，改推備援分支——不要讓資料跟著拋棄式容器一起消失。
    branch = f"nightly/{spec['date']}-{sha}"
    rc2, bout = run(vault, ["git", "push", "origin", f"HEAD:refs/heads/{branch}"])
    if rc2 != 0:
        return "stop", (f"git push 失敗 rc={rc}——commit {sha} 還在本機。"
                        f"改推備援分支 {branch} 也失敗 rc={rc2}"), out + pout + bout

    # push 分支「成功」不等於遠端真的收到——這條鏈過去的失效模式就是
    # 「自己以為推上去了」，所以 fetch 回來親眼確認一次。
    rc3, fout = run(vault, ["git", "fetch", "origin"])
    rc4, cout = run(vault, ["git", "branch", "-r", "--contains", sha])
    landed = rc3 == 0 and rc4 == 0 and f"origin/{branch}" in cout
    verify = (f"fetch 後確認 origin/{branch} 已收到 {sha}" if landed
              else f"fetch 驗證不到 origin/{branch}（rc3={rc3} rc4={rc4}），人工再查")
    return "noted", (
        f"main push 失敗 rc={rc}：{pout.strip()[:200]}｜"
        f"已改推 {branch}（{sha}），{verify}，需要人手動併回 main"
    ), out + pout + bout + fout + cout


def do_run_stage(vault, spec):
    rc, out = run(vault, spec["cmd"])
    action = code_action(rc, spec["codes"])
    if spec.get("summary_full"):
        note = f"rc={rc}"
    elif spec.get("summary_grep"):
        note = grep_line(out, spec["summary_grep"]) or f"rc={rc}"
    else:
        note = f"rc={rc}"
    if action == "stop":
        note = f"rc={rc}（表裡沒有這個離開碼或它代表壞了）｜{note}"
    return action, note, out


def already_done(state, date_str):
    """這一輪是不是早就跑完了。純函式。

    **一個 UTC 日只跑一輪**（冪等，enrich 與敘事刷新本來就是）。問題在於台北 04:47
    等於 **UTC 前一天 20:47**，所以同一個 UTC 日會被兩個不同的台北日碰到：白天手動
    跑一次、當晚排程再跑一次，第二次會看到「今天已經跑完」。

    那個判斷是對的，**安靜地結束不對**。2026-09-15 差點這樣過去：手動 kickstart 跑了
    一輪（UTC 03:32），當晚 04:47 那班（UTC 20:47，同一個 UTC 日）會什麼都不做、
    一個字都不印，log 上只有一片空白。而「今晚沒事做」跟「今晚沒跑到」在一片空白
    上長得一模一樣——這份文件從第一行講到現在的同一件事。
    """
    return bool(state.get("finished")) and state.get("date") == date_str


def advance(vault, state, date_str, no_push):
    """推進到下一個交棒點或跑完。回 exit code。"""
    for spec in stages(date_str):
        rec = stage_record(state, spec["id"])
        if rec and rec["status"] in ("ok", "skipped", "absent", "noted"):
            continue
        ok, why = requires_ok(state, spec)
        if not ok:
            set_stage(state, spec["id"], "skipped", why)
            save_state(vault, state)
            continue

        kind = spec["kind"]
        if kind == "precheck":
            status, note, full = do_precheck(vault, date_str)
        elif kind == "align":
            status, note, full = do_align(vault)
        elif kind == "narrative":
            status, note, extra = do_narrative(vault, spec, rec)
            full = ""
            if status == "waiting":
                set_stage(state, spec["id"], "waiting", note, **extra)
                save_state(vault, state)
                print(narrative_handoff(spec, (extra.get("worklist") or {}).get("count", 0)))
                return 10
            set_stage(state, spec["id"], status, note, **extra)
            save_state(vault, state)
            if status == "stop":
                print(f"[stop] {spec['id']}：{note}", file=sys.stderr)
                return 2
            continue
        elif kind == "commit":
            status, note, full = do_commit(vault, spec, no_push)
        else:
            if spec.get("dry_first"):
                dry_rc, dry_out = run(vault, spec["cmd"] + ["--dry-run"])
                if code_action(dry_rc, spec["codes"]) == "stop":
                    set_stage(state, spec["id"], "stop",
                              f"--dry-run 就不過（rc={dry_rc}）", full_output=dry_out)
                    save_state(vault, state)
                    print(f"[stop] {spec['id']}：--dry-run rc={dry_rc}", file=sys.stderr)
                    return 2
            status, note, full = do_run_stage(vault, spec)

        extra = {"full_output": full} if (full and keeps_output(spec, status)) else {}
        set_stage(state, spec["id"], status, note, **extra)
        save_state(vault, state)
        if status == "stop":
            print(f"[stop] {spec['id']}：{note}", file=sys.stderr)
            return 2

    state["finished"] = True
    save_state(vault, state)
    return 1 if any(st["status"] == "noted" for st in state["stages"]) else 0


def main():
    ap = argparse.ArgumentParser(description="夜班的階段機器（規格 references/nightly-driver.md）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="推進到下一個交棒點或跑完")
    r.add_argument("--no-push", action="store_true", help="commit 但不 push")
    r.add_argument("--reset", action="store_true", help="丟掉今天的狀態重跑")
    c = sub.add_parser("cost", help="記一筆寫作端的花費（外殼呼叫）")
    c.add_argument("--stage", required=True)
    c.add_argument("--usd", required=True, type=float)
    sub.add_parser("status", help="現在到哪")
    sub.add_parser("summary", help="印收尾摘要")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    date_str = clock.utc_today().isoformat()

    state = load_state(vault)
    if args.cmd in ("status", "summary"):
        if state is None:
            print("還沒有任何一輪的紀錄", file=sys.stderr)
            return 2
        print("\n".join(summary_lines(state)))
        return 0

    if args.cmd == "cost":
        if state is None:
            print("還沒有任何一輪的紀錄，無處可記", file=sys.stderr)
            return 2
        st = stage_record(state, args.stage)
        if st is None:
            print(f"狀態檔裡沒有 {args.stage} 這一段", file=sys.stderr)
            return 2
        st["cost_usd"] = round((st.get("cost_usd") or 0) + args.usd, 6)
        save_state(vault, state)
        return 0

    if state is None or state.get("date") != date_str or args.reset:
        state = {"date": date_str, "started_at": clock.utc_stamp(), "finished": False,
                 "stages": []}
    elif already_done(state, date_str):
        # 說出來，不要留一片空白。
        print("\n".join(summary_lines(state)))
        print(f"\n這一輪（UTC {date_str}）稍早已經跑完，沒有事情要做。"
              "台北 04:47 等於 UTC 前一天 20:47，所以同一個 UTC 日會被白天與當晚各碰一次。"
              "要重跑用 `run --reset`。")
        return 1 if any(st["status"] == "noted" for st in state["stages"]) else 0
    return advance(vault, state, date_str, args.no_push)


if __name__ == "__main__":
    sys.exit(main())
