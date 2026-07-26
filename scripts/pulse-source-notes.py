#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-source-notes.py — 產出 Sources/<id>.md（純規則、零 LLM）。

為什麼會有這支：**每一則 Event 都連向不存在的頁**。

`pulse-render` 寫進 Event 的證據區塊長這樣：

    - [[Sources/src-nvidia-blog|src-nvidia-blog]] — NVIDIA and Japan Bring ...

而 `Sources/` 這個資料夾裡從上線到今天只有一個檔案，還是 0 bytes。也就是說在
Obsidian 裡打開任何一則事件，證據那一行全是紅色的斷鏈；情報模型講的
「Event 是唯一事實節點，Track / Actor / Source 靠 backlink 自動成關聯圖」，
關聯圖的其中一整邊是空的。

這支把那一邊補起來。**不編造任何東西**：每個欄位不是抄自 `_config/sources.yaml`
（人寫的設定），就是數自 `_corpus/` 與 `Events/`（機器量到的事實），
再不然是 `_probe/source-health.json`（健康分算出來的）。沒有一句是生成的散文。

## 四態分離

skill 的核心心智模型是「收錄 ≠ 觀察到 ≠ 有效產出 ≠ 已發布」。這四個數字散在
四個地方，沒有一頁把它們並排放過——所以每條來源的頁上就是這四格：

    收錄     sources.yaml 有這條（lifecycle 說明它會不會被抓）
    已觀測   _corpus/ 裡它產出過幾筆
    有效產出 那些筆之中，有幾筆真的被綁成某則 Event 的證據
    已發布   那些 Event 之中，有幾則通過門禁上線了

四格並排才看得出是哪一層破的：抓得到但沒進 Event ＝ 聚類沒認出來；
進了 Event 但沒上線 ＝ 門禁擋著（那是設計，不是故障）。

## 關於 git 噪音

這支刻意**不寫任何每班都會變的欄位**。`state.json` 的 `last_run` 每兩小時就變一次，
寫進去的話 33 個檔案一天會被改 12 次，diff 裡真正的變化會被埋掉。
所以時間欄位一律只到「日」，而且**內容沒變就不重寫檔案**。

用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-source-notes.py
     VAULT_DIR=... python scripts/pulse-source-notes.py --prune   # 一併移除孤兒頁
依賴：PyYAML。
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.corpus import observed  # noqa: E402  _corpus/ 盤點的單一真相源
from lib.notes import parse_note  # noqa: E402
from lib.sources import iter_sources  # noqa: E402  分節清單單一真相源

RUN_LIFECYCLES = {"active", "degraded", "probing"}

# frontmatter 只放這些欄位（紅線 6）。endpoint 是公開 URL 所以可以進，
# 但 headers / api key / 本機路徑那類東西一個都不准出現在 vault 裡。
FM_FROM_CONFIG = ("owner", "media_group", "person_id", "track", "tier", "role",
                  "source_category", "corpus_type", "region", "language",
                  "lifecycle", "robots_ok", "license_note",
                  "can_satisfy_primary", "endpoint")


def _day(ts):
    """時間戳只留到日。理由見模組 docstring 的「關於 git 噪音」。"""
    return str(ts)[:10] if ts else None


def bound(vault: Path):
    """數 Events/：每條來源被綁成幾則事件的證據、其中幾則已發布。

    注意這裡數的是**事件數**不是證據筆數——同一則事件引同一條來源三次，
    對「這條來源有沒有促成一則事件」這個問題來說是一次。

    `status: dropped` 的事件不算。「有效產出」這一格要回答的是「這條來源有沒有
    促成什麼」，被丟掉的事件不是產出；算進來的話，「抓到了但聚類沒綁上」跟
    「綁上了但被丟掉」在頁面上長得一模一樣。（見 references/vault-pages.md）
    """
    ev, pub = Counter(), Counter()
    edir = vault / "Events"
    if not edir.exists():
        return ev, pub
    for p in sorted(edir.glob("*.md")):
        fm, _ = parse_note(p.read_text("utf-8"))
        if fm.get("status") == "dropped":
            continue
        sids = {e.get("source_id") for e in (fm.get("evidence") or [])
                if e.get("source_id")}
        for sid in sids:
            ev[sid] += 1
            if fm.get("status") == "published":
                pub[sid] += 1
    return ev, pub


# probe 上一班沒有真的送出請求的理由。這些不是 HTTP 狀態碼，是**跳過的原因**。
# 分開列而不是「非 200 就算失敗」：robots 擋住是合規行為不是故障，
# 取不到 robots.txt 是保守跳過也不是故障——健康分不該因此扣，但頁面要說實話。
SKIP_REASONS = {
    "robots_disallow": "**每班都被跳過**：站方 robots.txt 明文 Disallow（合規，不是故障）",
    "robots_unknown": "**每班都被跳過**：robots.txt 取不到，保守跳過（不是站方拒絕）",
    "skipped_lifecycle": "**不會被抓**：lifecycle 不在 active / degraded / probing",
}


def _intake_note(src, last_status):
    """「收錄」那一格的說明。

    lifecycle 是**設定意圖**，`last_status` 是**上一班的事實**。兩者會分岔：
    一條 `lifecycle: probing` 的來源如果每班都被 robots 擋掉，設定說「會被抓」，
    事實是「一次都沒抓」。只印 lifecycle 就是拿一個比事實寬鬆的代理指標代表事實
    ——這頁本來就是為了不讓那種事發生而存在的。
    """
    if last_status in SKIP_REASONS:
        return SKIP_REASONS[last_status]
    if src.get("lifecycle") in RUN_LIFECYCLES:
        return "會被抓"
    return "**不會被抓**"


def render(src, obs, obs_day, ev_n, pub_n, state, health):
    sid = src["id"]
    last_status = (health or {}).get("last_status")
    fm = {"id": sid, "type": "source"}
    for k in FM_FROM_CONFIG:
        if k in src and src[k] is not None:
            fm[k] = src[k]
    # robots_checked_at 每天都會被 robots-recheck 更新一次，只留到日，
    # 否則 32 個檔案每天都會為了一個時分秒的差別產生 diff。
    fm["robots_checked_day"] = _day(src.get("robots_checked_at"))
    first_fetch = (state or {}).get("first_fetch_at")
    fm["first_fetch_at"] = _day(first_fetch)
    fm["last_observed_day"] = obs_day
    # 從沒抓過的來源留空，不寫 0——0 的意思是「量到 0」，我們這裡是「量不到」。
    # 判準是 first_fetch_at 有沒有值，不是 state.json 裡有沒有這個條目：失敗也會
    # 留下 etag / last_run，只有成功抓過一次才會 setdefault 那個欄位。（紅線 8）
    fm["items_observed"] = obs if first_fetch else None
    fm["events_bound"] = ev_n
    fm["events_published"] = pub_n
    if health:
        fm["health_score"] = health.get("score")
        fm["consecutive_failures"] = health.get("consecutive_failures")
        fm["last_status"] = health.get("last_status")

    out = ["---"]
    for k, val in fm.items():
        if val is None:
            out.append(f"{k}:")
        elif isinstance(val, bool):
            out.append(f"{k}: {str(val).lower()}")
        elif isinstance(val, (int, float)):
            out.append(f"{k}: {val}")
        else:
            out.append(f'{k}: "{str(val)}"')
    out += ["---", "",
            f"# {src.get('owner') or sid}（{sid}）", "",
            "> 由 `pulse-source-notes.py` 自動產生（零 LLM）。"
            "設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。"
            "**手動編輯會在下一班被覆蓋。**", "",
            "## 四態", "",
            "| 層 | 數字 | 這一格是 0 代表什麼 |",
            "|---|---|---|",
            f"| 收錄 | `{src.get('lifecycle')}` | {_intake_note(src, last_status)} |",
            f"| 已觀測 | {'**尚未抓取過**' if not first_fetch else f'{obs} 筆'} |"
            f" {'我們對它的產出量一無所知' if not first_fetch else '抓到了，但站方那陣子沒發東西'} |",
            f"| 有效產出 | {ev_n} 則事件 | 抓到了但聚類沒把它綁成證據 |",
            f"| 已發布 | {pub_n} 則 | 綁上了但門禁擋著——那是設計，不是故障 |",
            ""]

    if not first_fetch:
        why = ("上一班的狀態是 `" + str(last_status) + "`。"
               if last_status in SKIP_REASONS else
               "上一班的狀態是 `" + str(last_status) + "`——**送得出請求卻沒留下"
               "首抓時間，這條要查**。" if last_status is not None else "")
        out += ["> 這條來源**從來沒有成功抓取過一次**（`_probe/state.json` 沒有它的 "
                "`first_fetch_at`）。所以上面那格是**量不到**，不是量到 0——"
                "我們對它的產出量一無所知。（紅線 8）" + why, ""]
    if src.get("robots_ok") is None:
        out += ["> robots 狀態未知（`robots_ok:` 空）。空值的意思是**還沒量到**，"
                "不是站方允許、也不是站方禁止。", ""]
    if src.get("can_satisfy_primary") is False:
        out += ["> 這條來源不能單獨作為一手證據（`can_satisfy_primary: false`）。"
                "它的角色是佐證與獨立性，不是「事情發生了」的來源。", ""]
    if src.get("media_group"):
        out += [f"> 媒體集團：**{src['media_group']}**。獨立性是按 source + author +"
                " media group 判的，所以同一個 media_group 的兩條來源"
                "**加起來只算一個獨立聲音**。", ""]
    out += ["## 端點", "",
            f"- `{src.get('endpoint', '(未設定)')}`",
            f"- adapter：`{src.get('adapter', '(未設定)')}`",
            f"- 授權註記：{src.get('license_note') or '(未填)'}", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true",
                    help="移除 sources.yaml 裡已經沒有的孤兒頁")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    import yaml
    vault = Path(os.environ["VAULT_DIR"])
    raw = yaml.safe_load((vault / "_config" / "sources.yaml").read_text("utf-8")) or {}
    srcs = list(iter_sources(raw))

    obs, obs_day = observed(vault)
    ev_n, pub_n = bound(vault)
    state_p = vault / "_probe" / "state.json"
    state = json.loads(state_p.read_text("utf-8")) if state_p.exists() else {}
    health_p = vault / "_probe" / "source-health.json"
    health = (json.loads(health_p.read_text("utf-8")).get("sources")
              if health_p.exists() else {}) or {}

    out_dir = vault / "Sources"
    out_dir.mkdir(parents=True, exist_ok=True)
    written, unchanged, pruned = 0, 0, []
    keep = set()
    for src in srcs:
        sid = src["id"]
        keep.add(f"{sid}.md")
        body = render(src, obs.get(sid, 0), obs_day.get(sid),
                      ev_n.get(sid, 0), pub_n.get(sid, 0),
                      state.get(sid), health.get(sid))
        p = out_dir / f"{sid}.md"
        # 內容沒變就不重寫——不然 33 個檔案會每兩小時被 touch 一次，
        # 真正的變化會淹沒在 diff 裡。
        if p.exists() and p.read_text("utf-8") == body:
            unchanged += 1
            continue
        p.write_text(body, "utf-8")
        written += 1

    if args.prune:
        for p in sorted(out_dir.glob("*.md")):
            if p.name not in keep:
                p.unlink()
                pruned.append(p.name)

    if not args.quiet:
        print(f"pulse-source-notes  寫入 {written}，未變 {unchanged}，共 {len(srcs)} 條")
        if pruned:
            print(f"  移除孤兒頁 {len(pruned)}：{', '.join(pruned)}")
        # 「抓過但零產出」與「從沒抓過」分開印：查法完全不同——前者是解析端
        # （抓得到頁面但解不出項目），後者是抓取端（連一次成功都沒有）。
        # 混在一起印，就是把量不到跟量到 0 當成同一件事。（紅線 8）
        runnable = [s["id"] for s in srcs if s.get("lifecycle") in RUN_LIFECYCLES]
        never = [sid for sid in runnable
                 if not (state.get(sid) or {}).get("first_fetch_at")]
        zero = [sid for sid in runnable if sid not in never and not obs.get(sid)]
        if zero:
            print(f"  ⚠ 抓過但零產出 {len(zero)} 條（解析端）：{', '.join(zero)}")
        if never:
            print(f"  ⚠ 從沒成功抓過 {len(never)} 條（抓取端）：{', '.join(never)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
