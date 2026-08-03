#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-source-health.py — 來源層健康分與 lifecycle 自動降級（純規則、零 LLM）。

規格在 references/source-lifecycle.md，門檻在 _config/gate.yaml 的 source_health。
碼與規格不一致時以規格為準，改門檻前先改規格（紅線 9）。

為什麼會有這支：`gate.yaml` 的 `source_health:` 從上線那天就寫好了六個門檻，
**沒有任何一行程式碼讀它**。同時 `lifecycle` 的五個狀態裡只有一條自動路徑真的
會發生（robots 重驗把被誤殺的來源升回 probing）。結果是：來源壞掉沒有人會知道，
因為壞掉的來源不會讓任何東西變紅，它只是安靜地不再貢獻資料。

這支要非常小心不要變成問題本身。自動降級最容易犯的錯，是把「我們量不到」當成
「來源壞了」，而這兩件事的代價完全不對稱：

    漏抓一條壞掉的來源  → 晚幾天發現，可補
    自動關掉一條好來源  → 不抓就永遠量不到它好了沒有，沒有自癒路徑

2026-07-24 漏抓 Claude Opus 5 就是後者：一次 403 被寫成 robots_ok: false +
dormant，整條 OpenAI 線靜靜關掉。所以這支的判分表刻意往「不罰」那邊倒：

    200（含 0 筆）成功    安靜的 feed 是健康的 feed，不是壞掉的 feed
    304           成功    有回應、內容沒變
    5xx / 例外    失敗    站方伺服器錯誤或抓取炸掉
    404 / 410     重罰    端點真的不在了——唯一一種明確是來源那邊變了的訊號
    401 / 403     不記分  WAF 擋容器 IP／路徑寫錯／真的要登入，這端分不出來
    429           不記分  站方在說我們太快，罰它等於因為自己的頻率去扣來源的分
    robots_*      不記分  robots 是合規政策不是健康度，歸 pulse-robots-recheck
    unsupported_adapter / skipped_lifecycle  不記分  沒有觀測

而且降級只降到 `degraded`（仍然每班抓，才有機會自癒），**永遠不自動寫
`dormant`**。達到隔離門檻的來源只列進報告等人看。升到 `active` 也永遠是人的事
——機器不發信任，機器最多把來源放回 `probing`，而且只撤銷機器自己做過的降級
（靠 `degraded_by: health` 這個記號分辨，人手設的 degraded 不碰）。

用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-source-health.py          # 只看
  VAULT_DIR=... python scripts/pulse-source-health.py --apply               # 寫回 lifecycle
  VAULT_DIR=... python scripts/pulse-source-health.py --json
  VAULT_DIR=... python scripts/pulse-source-health.py --runs 20             # 只看最近 20 班

輸入：_probe/source-runs.jsonl（pulse-probe.write_run_stats 每班 append 一行）
輸出（**三個都只在 --apply 才寫**，沒有 --apply 就一個檔案都不動）：
      _probe/source-health.json（分數、連續計數、降級記號、隔離候選）
      _config/sources.yaml 的 lifecycle
      _probe/source-history.jsonl（每一次異動，與 robots 重驗共用同一個檔）

依賴：ruamel.yaml（只有 --apply 需要，round-trip 才不會把 sources.yaml 的註解洗掉）。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from lib.atomicwrite import atomic_write_text, atomic_write_with  # noqa: E402  見 references/atomic-writes.md
from lib.sources import SECTIONS  # noqa: E402  分節清單單一真相源，見 lib/sources.py
from lib import history  # noqa: E402  帳本讀寫單一真相源，見 lib/history.py

# 這支自動降級只會作用在會被抓的 lifecycle。draft / dormant 根本沒有觀測。
RUNNABLE = {"active", "degraded", "probing"}

# 判分表。改這裡之前先改 references/source-lifecycle.md 的那張表（紅線 9）。
OUTCOME_SUCCESS = "success"        # 加分，連續失敗歸零
OUTCOME_NOT_MODIFIED = "not_modified"
OUTCOME_FAILURE = "failure"        # 扣分，連續成功歸零
OUTCOME_SEVERE = "severe_failure"
OUTCOME_NEUTRAL = "neutral"        # 兩個計數都不動

# 「已知且刻意不記分」的狀態一覽。
#
# 誠實地說：這個集合目前在 classify() 裡是可以拿掉的——底下的 catch-all 本來就
# 回 neutral，刪掉這七個成員行為一個字都不會變。留著不是因為程式需要它，是因為
# **這兩種 neutral 的意思不一樣**，而未來改碼的人需要看得出差別：
#
#   在這個集合裡  = 我們知道這是什麼，而且判斷過「不該記分」（401/403 分不出
#                   WAF 與政策、429 是我們自己太快、robots 歸重驗那支管）
#   落到 catch-all = 沒見過的東西，不知道就不判
#
# 差在哪裡：哪天有人想把 catch-all 改成「未知 4xx 一律算失敗」，這個集合就是
# 401/403 不會被那一刀掃到的護欄。selftest 有一條測試釘住它的成員，
# 少掉任何一個都會紅——所以它是被測試保護的宣告，不是裝飾。
NEUTRAL_STATUSES = {
    401, 403, 429,
    "robots_disallow", "robots_unknown",
    "unsupported_adapter", "skipped_lifecycle",
}


def classify(status) -> str:
    """把一次觀測分類成五種結果之一。這是整支腳本唯一的判斷，規則寫死、零 LLM。

    刻意不做的事：不看 items 筆數。200 抓到 0 筆是成功——src-mistral-news 連兩天
    200／0 筆，那是他們那陣子沒發東西。把「沒新聞」罰成失敗，等於逼整個系統
    偏好吵的來源，而這個 vault 的價值恰好在於它敢收安靜的一手來源。
    """
    if status in NEUTRAL_STATUSES:
        return OUTCOME_NEUTRAL
    if status == 200:
        return OUTCOME_SUCCESS
    if status == 304:
        return OUTCOME_NOT_MODIFIED
    if status in (404, 410):
        return OUTCOME_SEVERE
    if isinstance(status, int) and 500 <= status < 600:
        return OUTCOME_FAILURE
    if status == "error":
        return OUTCOME_FAILURE
    # 沒見過的狀態：不記分。新增一種狀態碼卻忘了在這裡分類時，
    # 誤差方向會是「沒罰到」而不是「錯殺」——這個方向是刻意選的。
    return OUTCOME_NEUTRAL


def load_runs(vault: Path, limit=0):
    """讀 _probe/source-runs.jsonl。limit>0 時只取最近 N 班。"""
    path = vault / "_probe" / "source-runs.jsonl"
    if not path.exists():
        return []
    runs = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 壞行跳過，不讓一行壞資料擋掉整條健康線
    return runs[-limit:] if limit else runs


def tally(runs, thresholds, sources_by_id):
    """把每班觀測捲成每條來源的分數與連續計數。

    分數從 100 起算、夾在 0–100。只算設定檔裡還存在的來源——移除過的來源留在
    歷史裡沒關係，但不該出現在今天的健康表上。
    """
    gain = {OUTCOME_SUCCESS: thresholds["success_gain"],
            OUTCOME_NOT_MODIFIED: thresholds["not_modified_gain"],
            OUTCOME_FAILURE: -thresholds["failure_penalty"],
            OUTCOME_SEVERE: -thresholds["severe_failure_penalty"],
            OUTCOME_NEUTRAL: 0}

    h = {}
    for run in runs:
        for obs in run.get("sources") or []:
            sid = obs.get("id")
            if sid not in sources_by_id:
                continue
            rec = h.setdefault(sid, {"id": sid, "score": 100, "runs": 0,
                                     "consecutive_failures": 0,
                                     "consecutive_successes": 0,
                                     "last_status": None, "last_at": None,
                                     "last_success_at": None, "neutral_runs": 0})
            outcome = classify(obs.get("status"))
            rec["runs"] += 1
            rec["score"] = max(0, min(100, rec["score"] + gain[outcome]))
            rec["last_status"] = obs.get("status")
            rec["last_at"] = run.get("at")
            if outcome in (OUTCOME_SUCCESS, OUTCOME_NOT_MODIFIED):
                rec["consecutive_failures"] = 0
                rec["consecutive_successes"] += 1
                rec["last_success_at"] = run.get("at")
            elif outcome in (OUTCOME_FAILURE, OUTCOME_SEVERE):
                rec["consecutive_successes"] = 0
                rec["consecutive_failures"] += 1
            else:
                # 中性：兩個計數都不動。若中性會歸零，一條每班在 404 與 403
                # 之間輪流的來源永遠湊不滿連續失敗數，會一直掛著假裝健康。
                rec["neutral_runs"] += 1
    return h


# 機器把降級還回去時，允許的目標狀態。
#
# 不變式不是「機器只能寫 degraded」——那句話跟 source-lifecycle.md 的狀態圖打架，
# 而且照它寫會有害。真正的不變式是：
#
#     機器不得把信任層級抬高到超過人設過的那一級，
#     但機器必須把自己做過的降級**原樣**還回去，不多也不少。
#
# 所以 degraded_from 是 active 就還 active——那不是發信任，是還東西。反過來
# 「一律還到 probing」才危險：probing → active 需要人跑 checklist，而那個 checklist
# 至今一次都沒有人跑過，等於機器可以靜靜收掉人給的信任而且沒有自癒路徑。
#
# 但 degraded_from 讀自 source-health.json，那是機器自己寫的檔。所以這裡不信任
# 它的**內容**，只信任它的**形狀**：不在這個集合裡的一律退回 probing。
RESTORABLE = {"probing", "active"}


def rebuild_prior_from_history(vault: Path):
    """`source-health.json` 不見／解不開時，從 append-only 的歷史重建降級記號。

    重建的只有 `degraded_by` / `degraded_from`——那是這個檔案裡唯一重算不回來的
    東西（分數每班都從 source-runs.jsonl 完整重算）。

    為什麼要有這支：少了那兩個記號，機器降下去的來源跟**人手設的** degraded 長得
    一模一樣，而人手設的機器不碰，於是那幾條永遠停在 degraded。那是一個吸收態，
    而且進去之後的樣子跟「一切正常、只是還沒累積」完全一樣——沒有任何一格會變紅。
    （見 references/source-lifecycle.md 的回滾一節）
    """
    hist = vault / "_probe" / "source-history.jsonl"
    if not hist.exists():
        return {}
    out = {}
    for line in hist.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("field") != "lifecycle":
            continue
        sid = row.get("id")
        if not sid:
            continue
        if row.get("reason") == "health-degraded":
            out[sid] = {"degraded_by": "health", "degraded_from": row.get("from")}
        else:
            # 任何其他讓它離開 degraded 的路徑（health-recovered、robots-revive、
            # 人手回填）都代表那次降級已經結束，記號跟著失效。時序照檔案順序，
            # 因為這個檔是 append-only 的。
            out.pop(sid, None)
    return out


def load_prior(vault: Path, hpath: Path):
    """讀上一班的降級記號。回傳 (prior, prior_source)。

    prior_source ∈ {snapshot, history, empty}，會被寫進 snapshot 讓「重建過」
    這件事在檔案裡看得見——重建靠的是 --apply 有寫進歷史，那個假設哪天不成立時，
    這一欄是唯一的線索。
    """
    if hpath.exists():
        try:
            return (json.loads(hpath.read_text("utf-8")).get("sources") or {},
                    "snapshot")
        except json.JSONDecodeError:
            pass
    rebuilt = rebuild_prior_from_history(vault)
    return (rebuilt, "history" if rebuilt else "empty")


def decide(health, sources_by_id, prior, thresholds):
    """依健康分決定 lifecycle 異動。回傳 [(sid, from, to, reason)]。

    三條路徑，其中兩條刻意不對稱：
      降級 probing/active → degraded   機器做，因為 degraded 仍然會被抓，能自癒
      隔離 → dormant                   **機器不做**，只列 quarantine_candidate 等人
      回復 degraded → 降級前那一個      機器只撤銷自己做過的降級（看 degraded_by）
    """
    changes, quarantine = [], []
    for sid, rec in sorted(health.items()):
        src = sources_by_id[sid]
        life = src.get("lifecycle")
        if life not in RUNNABLE:
            continue
        prev = prior.get(sid) or {}
        fails = rec["consecutive_failures"]

        if life == "degraded":
            if fails >= thresholds["quarantine_after_consecutive"]:
                quarantine.append((sid, fails))
                continue
            # 只撤銷機器自己做的降級。人手把來源打成 degraded 是判斷，不是量測，
            # 機器不該因為連續三班 200 就把人的決定推翻掉。
            if (prev.get("degraded_by") == "health"
                    and rec["consecutive_successes"] >= thresholds["recover_after_consecutive"]):
                back = prev.get("degraded_from")
                if back not in RESTORABLE:
                    back = "probing"
                changes.append((sid, "degraded", back, "health-recovered"))
            continue

        if fails >= thresholds["degrade_after_consecutive"]:
            changes.append((sid, life, "degraded", "health-degraded"))
    return changes, quarantine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="寫回 sources.yaml 的 lifecycle（預設只看不改）")
    ap.add_argument("--runs", type=int, default=0,
                    help="只看最近 N 班（0＝全部歷史）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    spath = vault / "_config" / "sources.yaml"
    gpath = vault / "_config" / "gate.yaml"
    hpath = vault / "_probe" / "source-health.json"

    import yaml as _pyyaml
    thresholds = _pyyaml.safe_load(gpath.read_text("utf-8"))["source_health"]

    if args.apply:
        try:
            from ruamel.yaml import YAML
        except ImportError:
            print("[fatal] --apply 需要 ruamel.yaml（保留 sources.yaml 的註解）："
                  "pip install ruamel.yaml", file=sys.stderr)
            return 2
        y = YAML()
        y.preserve_quotes = True
        y.width = 4096
        doc = y.load(spath.read_text("utf-8"))
    else:
        doc = _pyyaml.safe_load(spath.read_text("utf-8"))

    sources_by_id = {}
    for key in SECTIONS:
        for s in doc.get(key) or []:
            if str(s.get("id", "")).endswith("<slug>"):
                continue
            sources_by_id[s["id"]] = s

    runs = load_runs(vault, limit=args.runs)
    prior, prior_source = load_prior(vault, hpath)

    health = tally(runs, thresholds, sources_by_id)
    changes, quarantine = decide(health, sources_by_id, prior, thresholds)

    if args.json:
        print(json.dumps({"runs": len(runs), "sources": health,
                          "prior_source": prior_source,
                          "changes": [{"id": c[0], "from": c[1], "to": c[2],
                                       "reason": c[3]} for c in changes],
                          "quarantine_candidates": sorted(q[0] for q in quarantine)},
                         ensure_ascii=False, indent=2))
    else:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"pulse-source-health  {stamp}  （{len(runs)} 班）")
        if prior_source == "history":
            print("  ⓘ _probe/source-health.json 讀不到，降級記號已從 "
                  "_probe/source-history.jsonl 重建。")
        if not runs:
            print("  _probe/source-runs.jsonl 還沒有任何一班的紀錄。")
            print("  這個檔由 pulse-probe 每班 append；剛接上管線的話要等下一班才有輸入。")
        for sid, rec in sorted(health.items(), key=lambda kv: (kv[1]["score"], kv[0])):
            life = sources_by_id[sid].get("lifecycle")
            mark = "!" if rec["consecutive_failures"] else " "
            print(f"  {mark} {sid:<28} 分={rec['score']:>3} "
                  f"連敗={rec['consecutive_failures']} 連成={rec['consecutive_successes']} "
                  f"中性={rec['neutral_runs']:<3} 末次={rec['last_status']!s:<18} {life}")
        for sid, fails in quarantine:
            print(f"  ⚠ 隔離候選 {sid}：連續失敗 {fails} 班。"
                  f"要不要停用是人的判斷，這支不自動寫 dormant——"
                  f"不抓的來源沒有自癒路徑。")
        if not changes:
            print("  ── 無 lifecycle 異動")
        for sid, a, b, why in changes:
            print(f"  ── {sid}: {a} → {b}（{why}）")

    if not args.apply:
        # `--json` 時不印：那一行以前無條件印在 JSON 後面，把宣稱機器可讀的 stdout
        # 變成 `json.loads` 解不開的東西。
        if changes and not args.json:
            print("  （加 --apply 才會寫回 sources.yaml）")
        # 沒有 --apply 就一個檔案都不寫，_probe/source-health.json 也不寫。
        #
        # 以前這個寫入排在這個守衛之前，理由是「健康分是觀測不是判斷，應該一律寫」。
        # 那個理由不成立：tally() 每次都從 source-runs.jsonl 完整重算，分數不是累積
        # 存下來的，dry run 少寫一次什麼都沒少。這檔案裡唯一重算不回來的是
        # degraded_by / degraded_from——而那兩個恰恰是**判斷**。
        #
        # 後果很具體：任何人為了 debug 跑一次 --json，就把這一班算出來的
        # degraded_by: "health" 寫進去，而 sources.yaml 一個字沒動。兩個檔案從此
        # 互相矛盾，下一班讀到那個 state 會以為降級真的發生過。一個宣稱「只看」的
        # 旗標留下改動，咬到的是未來的自己。
        return 0

    # 以下只在 --apply 才會發生。
    snapshot = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "runs_considered": len(runs),
                # 這一班的降級記號是從哪裡來的：snapshot / history / empty。
                # 留著是為了讓「重建過」在檔案裡看得見。
                "prior_source": prior_source,
                # 達到隔離門檻、等人決定要不要停用的來源。
                #
                # 這個 key 以前只存在於 --json 的 stdout 字典裡，寫到磁碟的 snapshot
                # 沒有它，於是 pulse-monitor.py 的
                # `hjson.get("quarantine_candidates") or []` 永遠拿到空清單，
                # health.md 的「隔離候選」永遠是空的。
                #
                # dormant 只有人能寫，所以這份清單是**機器交棒給人的唯一介面**。
                # 它斷掉的時候不會有任何東西變紅：機器以為自己講了，人這邊沒收到。
                # stdout 印什麼是方便，寫進檔案才算數——讀它的是別支程式，不是眼睛。
                "quarantine_candidates": sorted(q[0] for q in quarantine),
                "sources": {}}
    for sid, rec in health.items():
        keep = dict(rec)
        prev = prior.get(sid) or {}
        keep["degraded_by"] = prev.get("degraded_by")
        keep["degraded_from"] = prev.get("degraded_from")
        snapshot["sources"][sid] = keep
    for sid, a, b, why in changes:
        if why == "health-degraded":
            snapshot["sources"][sid]["degraded_by"] = "health"
            snapshot["sources"][sid]["degraded_from"] = a
        elif why == "health-recovered":
            snapshot["sources"][sid]["degraded_by"] = None
            snapshot["sources"][sid]["degraded_from"] = None
    # 原子寫：半份 source-health.json 會讓連續計數與 degraded_by 記號一起掉，
    # 而 degraded_by 掉了就等於機器再也不會撤銷自己做過的降級——降下去回不來。
    # 見 references/atomic-writes.md。
    atomic_write_text(hpath, json.dumps(snapshot, ensure_ascii=False, indent=2))

    stamp = snapshot["at"]
    recorded = []
    for sid, a, b, why in changes:
        sources_by_id[sid]["lifecycle"] = b
        recorded.append({"at": stamp, "id": sid, "field": "lifecycle",
                         "from": a, "to": b, "reason": why})
    # tmp + os.replace()。直接開 "w" 的話，寫到一半被砍留下的是一份**合法但少了
    # 整段 *_sources: 的 YAML**：讀得起來、不報錯、被 git add -A commit 上去，
    # 下一班的 probe 才發現零條來源。見 references/atomic-writes.md。
    atomic_write_with(spath, lambda fh: y.dump(doc, fh))

    history.append(vault / "_probe" / "source-history.jsonl", recorded)
    print(f"  已寫回 sources.yaml；{len(recorded)} 筆異動記入 _probe/source-history.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
